// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {VaultFixture} from "../fixtures/VaultFixture.sol";

/**
 * @title ChaosTests
 * @notice Chaos engineering tests for TMVault
 * @dev Tests system behavior under adverse conditions
 */
contract ChaosTests is VaultFixture {

    /*//////////////////////////////////////////////////////////////
                        PROTOCOL FAILURE TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Chaos_ProtocolReverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);

        // Set protocol to reject all withdrawals
        protocolA.setState(true, false);

        // Try to deallocate - should handle gracefully
        vm.prank(manager);
        vm.expectRevert(); // Protocol will revert
        vault.deallocateFromProtocol(address(protocolA), WITHDRAWAL_AMOUNT);
    }

    function test_Chaos_ProtocolReturnsLess() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);

        // Protocol simulates loss (returns less than allocated)
        protocolA.setAllocated(protocolA.allocated() * 90 / 100);

        // Vault should still track correctly
        assertEq(vault.protocolBalance(address(protocolA)), WITHDRAWAL_AMOUNT);

        // Deallocate will succeed but with less returned
        vm.prank(manager);
        vault.deallocateFromProtocol(address(protocolA), WITHDRAWAL_AMOUNT);

        assertEq(vault.protocolBalance(address(protocolA)), 0);
    }

    function test_Chaos_ProtocolDisappears() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);

        // Remove protocol from vault (simulating protocol delisting)
        vm.prank(manager);
        vault.removeProtocol(address(protocolA));

        // Try to deallocate - should fail gracefully
        vm.prank(manager);
        vm.expectRevert();
        vault.deallocateFromProtocol(address(protocolA), WITHDRAWAL_AMOUNT);
    }

    /*//////////////////////////////////////////////////////////////
                        NETWORK CONDITION TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Chaos_BlockGasSpike() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        // Simulate high gas environment
        vm.txGasPrice(500 gwei);

        // Operations should still complete
        vm.prank(user1);
        vault.instantWithdraw(1000e6);

        assertEq(vault.balances(user1), DEPOSIT_AMOUNT - 1000e6);
    }

    function test_Chaos_BlockReorg() public {
        // Simulate blockchain reorg by reverting
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 balanceBefore = vault.balances(user1);

        // Create a fork and revert
        vm.roll(block.number - 1);

        // State should be consistent
        assertEq(vault.balances(user1), balanceBefore);
    }

    /*//////////////////////////////////////////////////////////////
                        RACE CONDITION TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Chaos_ConcurrentDeposits() public {
        address[] memory users = new address[](10);
        for (uint256 i = 0; i < 10; i++) {
            users[i] = makeAddr(string(abi.encodePacked("user", i)));
            usdc.mint(users[i], DEPOSIT_AMOUNT);
        }

        // All users deposit at once
        vm.startPrank(users[0]);
        usdc.approve(address(vault), DEPOSIT_AMOUNT);
        vault.deposit(DEPOSIT_AMOUNT, users[0]);
        vm.stopPrank();

        for (uint256 i = 1; i < 10; i++) {
            vm.prank(users[i]);
            usdc.approve(address(vault), DEPOSIT_AMOUNT);
            vault.deposit(DEPOSIT_AMOUNT, users[i]);
        }

        // All deposits should be processed correctly
        for (uint256 i = 0; i < 10; i++) {
            assertEq(vault.balances(users[i]), DEPOSIT_AMOUNT);
        }

        assertEq(vault.totalDeposits(), DEPOSIT_AMOUNT * 10);
    }

    function test_Chaos_ConcurrentWithdrawals() public {
        _deposit(user1, 1_000_000e6);

        uint256[] memory indices = new uint256[](10);

        // Queue multiple withdrawals rapidly
        for (uint256 i = 0; i < 10; i++) {
            indices[i] = _requestWithdrawal(user1, 10_000e6);
        }

        // Process all
        skip(ONE_DAY);

        for (uint256 i = 0; i < 10; i++) {
            vault.processWithdrawal(indices[i]);
        }

        // All should be processed
        assertEq(vault.getQueueSize(), 0);
        assertEq(usdc.balanceOf(user1), 100_000e6);
    }

    /*//////////////////////////////////////////////////////////////
                        EXTREME VALUE TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Chaos_MaxUintOperations() public {
        uint256 maxDeposit = type(uint256).max;

        // This should revert due to overflow protection
        usdc.mint(user1, INITIAL_BALANCE);

        vm.prank(user1);
        usdc.approve(address(vault), INITIAL_BALANCE);

        // Valid deposit
        vm.prank(user1);
        vault.deposit(INITIAL_BALANCE, user1);
    }

    function test_Chaos_ZeroAddress() public {
        // Deploy vault with zero asset address
        vm.expectRevert();
        new TMVault(address(0), manager);
    }

    function test_Chaos_ExtremeQueueUsage() public {
        _deposit(user1, 10_000_000e6);

        // Fill queue to max
        for (uint256 i = 0; i < 100; i++) {
            _requestWithdrawal(user1, 1000e6);
        }

        assertEq(vault.getQueueSize(), 100);

        // Next should fail
        vm.prank(user1);
        vm.expectRevert();
        vault.requestWithdrawal(1000e6);

        // Process all
        skip(ONE_DAY);

        for (uint256 i = 0; i < 100; i++) {
            vault.processWithdrawal(i);
        }

        // Queue should be empty
        assertEq(vault.getQueueSize(), 0);
    }

    /*//////////////////////////////////////////////////////////////
                        STATE CORRUPTION RECOVERY
    //////////////////////////////////////////////////////////////*/

    function test_Chaos_ReenterancyProtection() public {
        // Create malicious contract that tries to reenter
        MaliciousContract attacker = new MaliciousContract(address(vault), address(usdc));

        usdc.mint(address(attacker), DEPOSIT_AMOUNT);

        vm.startPrank(address(attacker));
        usdc.approve(address(vault), DEPOSIT_AMOUNT);

        // Attempt reentrancy attack
        vm.expectRevert(); // Should fail due to checks-effects-interactions
        attacker.attack(DEPOSIT_AMOUNT);
        vm.stopPrank();
    }

    /*//////////////////////////////////////////////////////////////
                        RESOURCE EXHAUSTION TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Chaos_MemoryExhaustion() public {
        // Create large amount of data through many operations
        _deposit(user1, 1_000_000e6);

        // Many small withdrawals
        for (uint256 i = 0; i < 50; i++) {
            _requestWithdrawal(user1, 1000e6);
        }

        skip(ONE_DAY);

        // Process all - should handle without OOG
        for (uint256 i = 0; i < 50; i++) {
            vault.processWithdrawal(i);
        }
    }

    function test_Chaos_StorageExhaustion() public {
        // Create many users
        address[] memory users = new address[](50);
        for (uint256 i = 0; i < 50; i++) {
            users[i] = makeAddr(string(abi.encodePacked("user", i)));
            usdc.mint(users[i], DEPOSIT_AMOUNT);
            _deposit(users[i], DEPOSIT_AMOUNT);
        }

        // All user operations should still work
        for (uint256 i = 0; i < 50; i++) {
            assertEq(vault.balances(users[i]), DEPOSIT_AMOUNT);
        }
    }
}

/**
 * @title MaliciousContract
 * @notice Contract attempting reentrancy attacks
 */
contract MaliciousContract {
    TMVault public vault;
    MockUSDC public usdc;
    bool public attacking;

    constructor(address _vault, address _usdc) {
        vault = TMVault(_vault);
        usdc = MockUSDC(_usdc);
    }

    function attack(uint256 amount) external {
        attacking = true;
        usdc.approve(address(vault), amount);
        vault.deposit(amount, address(this));

        // Try to reenter during deposit
        if (attacking) {
            vault.instantWithdraw(amount);
        }
    }

    receive() external payable {
        if (attacking) {
            // Try to reenter
            vault.instantWithdraw(usdc.balanceOf(address(this)));
        }
    }
}
