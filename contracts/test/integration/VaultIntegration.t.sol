// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {VaultFixture} from "../fixtures/VaultFixture.sol";
import {TMVault} from "../../src/TMVault.sol";

/**
 * @title VaultIntegrationTests
 * @notice Integration tests for TMVault covering multi-contract interactions
 * @dev Tests interactions between vault, protocols, and multiple users
 */
contract VaultIntegrationTests is VaultFixture {

    /*//////////////////////////////////////////////////////////////
                    PROTOCOL ROUTING TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Integration_ProtocolRouting_AllocationStrategy() public {
        // Setup: multiple deposits
        _deposit(user1, 100_000e6);
        _deposit(user2, 100_000e6);
        _deposit(user3, 100_000e6);

        // Manager allocates 60% to protocolA, 40% to protocolB
        vm.prank(manager);
        vault.allocateToProtocol(address(protocolA), 120_000e6);

        vm.prank(manager);
        vault.allocateToProtocol(address(protocolB), 80_000e6);

        assertEq(vault.protocolBalance(address(protocolA)), 120_000e6);
        assertEq(vault.protocolBalance(address(protocolB)), 80_000e6);
        assertEq(vault.totalAllocated(), 200_000e6);

        // Simulate yield
        protocolA.accrue(500); // 5%
        protocolB.accrue(300); // 3%

        // Collect yield
        address[] memory protocols = new address[](2);
        protocols[0] = address(protocolA);
        protocols[1] = address(protocolB);

        vm.prank(manager);
        vault.collectYield(protocols);

        // Verify yield collected
        assertGt(vault.totalYield(), 0);
    }

    function test_Integration_ProtocolRouting_Rebalancing() public {
        // Initial allocation
        _deposit(user1, 200_000e6);
        _allocate(address(protocolA), 150_000e6);

        // Rebalance: move funds from A to B
        vm.prank(manager);
        vault.deallocateFromProtocol(address(protocolA), 50_000e6);

        vm.prank(manager);
        vault.allocateToProtocol(address(protocolB), 50_000e6);

        assertEq(vault.protocolBalance(address(protocolA)), 100_000e6);
        assertEq(vault.protocolBalance(address(protocolB)), 50_000e6);
    }

    function test_Integration_ProtocolRouting_MultiProtocolWithdrawal() public {
        // Setup: funds allocated to both protocols
        _deposit(user1, 200_000e6);
        _allocate(address(protocolA), 100_000e6);
        _allocate(address(protocolB), 80_000e6);

        // Vault has 20k left
        assertEq(usdt.balanceOf(address(vault)), 20_000e6);

        // Request withdrawal larger than vault liquidity
        uint256 index = _requestWithdrawal(user1, 50_000e6);

        skip(ONE_DAY);

        // Should deallocate from protocols to fulfill
        vault.processWithdrawal(index);

        // Verify withdrawal succeeded (user had INITIAL_BALANCE, deposited 200k, now gets 50k back)
        assertEq(usdt.balanceOf(user1), INITIAL_BALANCE - 200_000e6 + 50_000e6);

        // Verify deallocation happened
        assertLt(vault.totalAllocated(), 180_000e6);
    }

    /*//////////////////////////////////////////////////////////////
                    WITHDRAWAL QUEUE TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Integration_Queue_MultiUserSequentialProcessing() public {
        // Multiple users deposit
        _deposit(user1, 100_000e6);
        _deposit(user2, 100_000e6);
        _deposit(user3, 100_000e6);

        // Allocate most funds
        _allocate(address(protocolA), 200_000e6);

        // Queue withdrawals
        uint256 index1 = _requestWithdrawal(user1, 30_000e6);
        uint256 index2 = _requestWithdrawal(user2, 20_000e6);
        uint256 index3 = _requestWithdrawal(user3, 10_000e6);

        skip(ONE_DAY);

        // Process in order
        vault.processWithdrawal(index1);
        vault.processWithdrawal(index2);
        vault.processWithdrawal(index3);

        // Users started with INITIAL_BALANCE, deposited 100k each, withdrew partial amounts
        assertEq(usdt.balanceOf(user1), INITIAL_BALANCE - 100_000e6 + 30_000e6);
        assertEq(usdt.balanceOf(user2), INITIAL_BALANCE - 100_000e6 + 20_000e6);
        assertEq(usdt.balanceOf(user3), INITIAL_BALANCE - 100_000e6 + 10_000e6);
    }

    function test_Integration_Queue_WithYieldAccrual() public {
        _deposit(user1, 100_000e6);
        _allocate(address(protocolA), 100_000e6);

        // Accrue yield
        protocolA.accrue(1000); // 10%

        // Request withdrawal
        uint256 index = _requestWithdrawal(user1, 50_000e6);

        skip(ONE_DAY);

        // Process withdrawal - yield should be tracked
        vault.processWithdrawal(index);

        // User started with INITIAL_BALANCE, deposited 100k, withdrew 50k
        assertEq(usdt.balanceOf(user1), INITIAL_BALANCE - 100_000e6 + 50_000e6);
    }

    function test_Integration_Queue_CancelAndRequeue() public {
        _deposit(user1, 100_000e6);

        uint256 index1 = _requestWithdrawal(user1, 30_000e6);

        // User changes mind
        vm.prank(user1);
        vault.cancelWithdrawal(index1);

        // Request again
        uint256 index2 = _requestWithdrawal(user1, 20_000e6);

        skip(ONE_DAY);
        vault.processWithdrawal(index2);

        // User started with INITIAL_BALANCE, deposited 100k, withdrew 20k
        assertEq(usdt.balanceOf(user1), INITIAL_BALANCE - 100_000e6 + 20_000e6);
        assertEq(vault.balances(user1), 80_000e6);
    }

    /*//////////////////////////////////////////////////////////////
                    END-TO-END SCENARIOS
    //////////////////////////////////////////////////////////////*/

    function test_Integration_E2E_UserJourney() public {
        // 1. User discovers vault and checks protocols
        address[] memory protocols = vault.getProtocols();
        assertEq(protocols.length, 2);

        // 2. User deposits
        _deposit(user1, 50_000e6);

        // 3. Manager allocates funds
        vm.prank(manager);
        vault.allocateToProtocol(address(protocolA), 50_000e6);

        // 4. Time passes, yield accrues
        protocolA.accrue(500); // 5%

        // 5. Manager collects yield
        address[] memory prots = new address[](1);
        prots[0] = address(protocolA);
        vm.prank(manager);
        vault.collectYield(prots);

        // 6. User requests withdrawal
        uint256 index = _requestWithdrawal(user1, 10_000e6);

        // 7. Wait period
        skip(ONE_DAY);

        // 8. Withdrawal processed
        vault.processWithdrawal(index);

        // 9. User receives funds (started with INITIAL_BALANCE, deposited 50k, withdrew 10k)
        assertEq(usdt.balanceOf(user1), INITIAL_BALANCE - 50_000e6 + 10_000e6);
        assertEq(vault.balances(user1), 40_000e6);
    }

    function test_Integration_E2E_VaultLifecycle() public {
        // Phase 1: Initial deposits
        _deposit(user1, 100_000e6);
        _deposit(user2, 100_000e6);
        _deposit(user3, 100_000e6);

        assertEq(vault.totalDeposits(), 300_000e6);

        // Phase 2: Strategic allocation
        _allocate(address(protocolA), 150_000e6);
        _allocate(address(protocolB), 100_000e6);

        assertEq(vault.totalAllocated(), 250_000e6);

        // Phase 3: Yield generation
        _simulateYield(200); // 2% across both

        // Phase 4: Partial withdrawals
        uint256 index1 = _requestWithdrawal(user1, 20_000e6);
        uint256 index2 = _requestWithdrawal(user2, 30_000e6);

        skip(ONE_DAY);

        vault.processWithdrawal(index1);
        vault.processWithdrawal(index2);

        // Phase 5: New deposits
        address newUser = makeAddr("newUser");
        usdt.mint(newUser, 50_000e6);
        _deposit(newUser, 50_000e6);

        // Final state checks (users deposited 100k each, withdrew 20k and 30k respectively)
        assertEq(vault.totalDeposits(), 300_000e6 - 50_000e6);
        assertEq(usdt.balanceOf(user1), INITIAL_BALANCE - 100_000e6 + 20_000e6);
        assertEq(usdt.balanceOf(user2), INITIAL_BALANCE - 100_000e6 + 30_000e6);
    }

    function test_Integration_E2E_EmergencyScenario() public {
        // Setup: funds allocated
        _deposit(user1, 100_000e6);
        _deposit(user2, 100_000e6);
        _allocate(address(protocolA), 150_000e6);

        // Pending withdrawals
        uint256 index1 = _requestWithdrawal(user1, 10_000e6);
        uint256 index2 = _requestWithdrawal(user2, 10_000e6);

        // Emergency: manager recalls all funds
        vm.prank(manager);
        vault.emergencyWithdrawAll();

        // All funds back in vault
        assertEq(vault.totalAllocated(), 0);
        assertGt(usdt.balanceOf(address(vault)), 0);

        // Withdrawals can still process
        skip(ONE_DAY);
        vault.processWithdrawal(index1);
        vault.processWithdrawal(index2);
    }

    /*//////////////////////////////////////////////////////////////
                    STRESS TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Integration_Stress_RapidDepositsWithdrawals() public {
        // Many rapid deposits
        for (uint256 i = 0; i < 50; i++) {
            usdt.mint(user1, INITIAL_BALANCE);
            _deposit(user1, 10_000e6);
        }

        // Rapid withdrawals
        for (uint256 i = 0; i < 25; i++) {
            vm.prank(user1);
            vault.instantWithdraw(5_000e6);
        }

        assertEq(vault.balances(user1), 250_000e6);
    }

    function test_Integration_Stress_MaxQueueOperations() public {
        _deposit(user1, 1_000_000e6);

        uint256[] memory indices = new uint256[](100);

        // Fill queue
        for (uint256 i = 0; i < 100; i++) {
            indices[i] = _requestWithdrawal(user1, 1_000e6);
        }

        // Process all
        skip(ONE_DAY);
        for (uint256 i = 0; i < 100; i++) {
            vault.processWithdrawal(indices[i]);
        }

        assertEq(vault.getQueueSize(), 0);
    }

    function test_Integration_Stress_MultiUserConcurrent() public {
        address[] memory users = new address[](20);
        for (uint256 i = 0; i < 20; i++) {
            users[i] = makeAddr(string(abi.encodePacked("user", i)));
            usdt.mint(users[i], INITIAL_BALANCE);
        }

        // All users deposit
        for (uint256 i = 0; i < 20; i++) {
            _deposit(users[i], 50_000e6);
        }

        // Allocate
        vm.prank(manager);
        vault.allocateToProtocol(address(protocolA), 500_000e6);

        // Half request withdrawals
        uint256[] memory indices = new uint256[](10);
        for (uint256 i = 0; i < 10; i++) {
            indices[i] = _requestWithdrawal(users[i], 10_000e6);
        }

        skip(ONE_DAY);

        // Process all
        for (uint256 i = 0; i < 10; i++) {
            vault.processWithdrawal(indices[i]);
        }

        // Verify all users have correct balances
        for (uint256 i = 0; i < 10; i++) {
            assertEq(vault.balances(users[i]), 40_000e6);
            assertEq(usdt.balanceOf(users[i]), INITIAL_BALANCE - 50_000e6 + 10_000e6);
        }

        for (uint256 i = 10; i < 20; i++) {
            assertEq(vault.balances(users[i]), 50_000e6);
        }
    }

    /*//////////////////////////////////////////////////////////////
                    PROTOCOL FAILover TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Integration_Failover_SingleProtocolFailure() public {
        _deposit(user1, 100_000e6);
        _allocate(address(protocolA), 50_000e6);
        _allocate(address(protocolB), 30_000e6);

        // Protocol A stops allowing withdrawals
        protocolA.setState(true, false);

        // Withdrawal should still work using protocol B and vault liquidity
        uint256 index = _requestWithdrawal(user1, 25_000e6);

        skip(ONE_DAY);

        // Should deallocate from B first
        vault.processWithdrawal(index);

        // User started with INITIAL_BALANCE, deposited 100k, withdrew 25k\n        assertEq(usdt.balanceOf(user1), INITIAL_BALANCE - 100_000e6 + 25_000e6);
    }

    function test_Integration_Failover_ProtocolRemoval() public {
        _deposit(user1, 100_000e6);
        _allocate(address(protocolA), 50_000e6);
        _allocate(address(protocolB), 30_000e6);

        // Remove protocol A (should deallocate first)
        vm.prank(manager);
        vault.removeProtocol(address(protocolA));

        assertFalse(vault.isProtocol(address(protocolA)));
        assertEq(vault.protocolBalance(address(protocolA)), 0);

        // Can still use protocol B
        vm.prank(manager);
        vault.allocateToProtocol(address(protocolB), 50_000e6);
    }

    /*//////////////////////////////////////////////////////////////
                    YIELD DISTRIBUTION TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Integration_Yield_MultiProtocolYieldCollection() public {
        _deposit(user1, 100_000e6);
        _allocate(address(protocolA), 50_000e6);
        _allocate(address(protocolB), 30_000e6);

        // Different yields
        protocolA.accrue(1000); // 10%
        protocolB.accrue(500);  // 5%

        address[] memory prots = new address[](2);
        prots[0] = address(protocolA);
        prots[1] = address(protocolB);

        vm.prank(manager);
        vault.collectYield(prots);

        // Expected: (50k * 0.10) + (30k * 0.05) = 5000 + 1500 = 6500
        assertGe(vault.totalYield(), 6500 - 100); // Small tolerance
        assertLe(vault.totalYield(), 6500 + 100);
    }

    /*//////////////////////////////////////////////////////////////
                    ACCESS CONTROL TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Integration_AccessControl_ManagerTransfer() public {
        _deposit(user1, 100_000e6);

        address newManager = makeAddr("newManager");

        vm.prank(manager);
        vault.setManager(newManager);

        // Old manager can no longer allocate
        vm.prank(manager);
        vm.expectRevert(TMVault.NotManager.selector);
        vault.allocateToProtocol(address(protocolA), 10_000e6);

        // New manager can
        vm.prank(newManager);
        vault.allocateToProtocol(address(protocolA), 10_000e6);
    }

    /*//////////////////////////////////////////////////////////////
                    CROSS-CONTRACT TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Integration_CrossContract_ProtocolVaultInteraction() public {
        _deposit(user1, 100_000e6);

        // Allocate to protocol
        vm.prank(manager);
        vault.allocateToProtocol(address(protocolA), 50_000e6);

        // Verify protocol received funds
        assertEq(protocolA.allocated(), 50_000e6);

        // Protocol generates yield
        protocolA.accrue(1000);

        // Vault can deallocate
        vm.prank(manager);
        vault.deallocateFromProtocol(address(protocolA), 20_000e6);

        // Verify protocol state updated
        assertEq(protocolA.allocated(), 30_000e6);
        assertEq(vault.protocolBalance(address(protocolA)), 30_000e6);
    }
}
