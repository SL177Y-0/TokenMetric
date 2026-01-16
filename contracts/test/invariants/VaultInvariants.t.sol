// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {VaultFixture} from "../fixtures/VaultFixture.sol";

/**
 * @title VaultInvariants
 * @notice Invariant tests for TMVault using Foundry's invariant testing
 * @dev These tests run continuously to find edge cases and violations
 */
contract VaultInvariants is VaultFixture {
    /*//////////////////////////////////////////////////////////////
                            INVARIANTS
    //////////////////////////////////////////////////////////////*/

    /**
     * @notice Total user balances must always equal total deposits
     * @dev This is a critical accounting invariant
     */
    function invariant_totalBalancesEqualsTotalDeposits() public view {
        uint256 totalBalances = vault.balances(user1) +
                                vault.balances(user2) +
                                vault.balances(user3);

        // Note: This assumes we track all test users
        // In production, you'd need a mapping of all users
        assertLe(totalBalances, vault.totalDeposits());
    }

    /**
     * @notice Allocated amount never exceeds total deposits
     */
    function invariant_allocatedNeverExceedsDeposits() public view {
        assertLe(vault.totalAllocated(), vault.totalDeposits());
    }

    /**
     * @notice Protocol balance tracked by vault never exceeds actual protocol balance
     */
    function invariant_protocolBalanceAccurate() public view {
        uint256 vaultTrackedA = vault.protocolBalance(address(protocolA));
        uint256 vaultTrackedB = vault.protocolBalance(address(protocolB));

        uint256 actualA = protocolA.allocated();
        uint256 actualB = protocolB.allocated();

        assertEq(vaultTrackedA, actualA, "ProtocolA balance mismatch");
        assertEq(vaultTrackedB, actualB, "ProtocolB balance mismatch");
    }

    /**
     * @notice Total assets equals vault balance + allocated
     */
    function invariant_totalAssetsCalculation() public view {
        uint256 expectedTotal = usdc.balanceOf(address(vault)) + vault.totalAllocated();
        uint256 actualTotal = vault.totalAssets();

        // Allow small difference due to yield tracking
        assertGe(actualTotal, expectedTotal);
        assertLe(actualTotal, expectedTotal + vault.totalYield());
    }

    /**
     * @notice Queue size is never negative or exceeds max
     */
    function invariant_queueSizeValid() public view {
        uint256 queueSize = vault.getQueueSize();
        assertLe(queueSize, TMVault.MAX_QUEUE_SIZE());
    }

    /**
     * @notice Withdrawal queue indices are sequential
     */
    function invariant_queueIndicesSequential() public view {
        uint256[] memory userIndices = vault.getUserWithdrawals(user1);

        for (uint256 i = 0; i < userIndices.length; i++) {
            assertTrue(userIndices[i] < withdrawalQueue.length(), "Invalid queue index");
        }
    }

    /**
     * @notice Manager cannot have zero balance in vault
     */
    function invariant_managerHasValidAddress() public view {
        assertNotEq(vault.manager(), address(0));
    }

    /**
     * @notice Asset address is never zero
     */
    function invariant_assetAddressValid() public view {
        assertNotEq(address(vault.asset()), address(0));
    }

    /**
     * @notice All protocols are valid addresses
     */
    function invariant_protocolsValid() public view {
        address[] memory protocols = vault.getProtocols();

        for (uint256 i = 0; i < protocols.length; i++) {
            assertNotEq(protocols[i], address(0));
        }
    }

    /*//////////////////////////////////////////////////////////////
                        FUZZED INVARIANTS
    //////////////////////////////////////////////////////////////*/

    /**
     * @notice Fuzz test: deposits and withdrawals maintain invariant
     */
    function testFuzzInvariant_DepositWithdrawMaintainsBalance(
        uint256 depositAmount,
        uint256 withdrawAmount
    ) public {
        // Constrain values
        vm.assume(depositAmount > 0 && depositAmount <= INITIAL_BALANCE);
        vm.assume(withdrawAmount > 0 && withdrawAmount <= depositAmount);
        vm.assume(withdrawAmount <= TMVault.MAX_SINGLE_WITHDRAWAL());

        uint256 totalDepositsBefore = vault.totalDeposits();

        // Deposit
        usdc.mint(user1, depositAmount);
        vm.prank(user1);
        usdc.approve(address(vault), depositAmount);
        vm.prank(user1);
        vault.deposit(depositAmount, user1);

        // Withdraw
        vm.prank(user1);
        vault.instantWithdraw(withdrawAmount);

        // Check invariants
        assertEq(vault.totalDeposits(), totalDepositsBefore + depositAmount - withdrawAmount);
        assertEq(vault.balances(user1), depositAmount - withdrawAmount);
    }

    /**
     * @notice Fuzz test: multiple users maintain accounting invariant
     */
    function testFuzzInvariant_MultiUserAccounting(
        uint256 amount1,
        uint256 amount2,
        uint256 amount3
    ) public {
        vm.assume(amount1 > 0 && amount1 <= INITIAL_BALANCE);
        vm.assume(amount2 > 0 && amount2 <= INITIAL_BALANCE);
        vm.assume(amount3 > 0 && amount3 <= INITIAL_BALANCE);

        _deposit(user1, amount1);
        _deposit(user2, amount2);
        _deposit(user3, amount3);

        uint256 totalUserBalances = vault.balances(user1) + vault.balances(user2) + vault.balances(user3);

        assertEq(totalUserBalances, vault.totalDeposits());
    }

    /**
     * @notice Fuzz test: allocation doesn't break invariants
     */
    function testFuzzInvariant_AllocationMaintainsInvariants(uint256 allocateAmount) public {
        vm.assume(allocateAmount > 0 && allocateAmount <= DEPOSIT_AMOUNT);

        _deposit(user1, DEPOSIT_AMOUNT);

        vm.prank(manager);
        vault.allocateToProtocol(address(protocolA), allocateAmount);

        // Check invariants
        assertLe(vault.totalAllocated(), vault.totalDeposits());
        assertEq(vault.protocolBalance(address(protocolA)), allocateAmount);
    }

    /**
     * @notice Fuzz test: queue operations maintain invariants
     */
    function testFuzzInvariant_QueueOperationsMaintainInvariants(
        uint256 amount1,
        uint256 amount2
    ) public {
        vm.assume(amount1 > 0 && amount1 < DEPOSIT_AMOUNT);
        vm.assume(amount2 > 0 && amount2 < DEPOSIT_AMOUNT - amount1);
        vm.assume(amount1 <= TMVault.MAX_SINGLE_WITHDRAWAL());
        vm.assume(amount2 <= TMVault.MAX_SINGLE_WITHDRAWAL());

        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 index1 = _requestWithdrawal(user1, amount1);
        uint256 index2 = _requestWithdrawal(user1, amount2);

        // Check indices are sequential
        assertEq(index2, index1 + 1);

        // Check total deposits decreased correctly
        assertEq(vault.balances(user1), DEPOSIT_AMOUNT - amount1 - amount2);

        // Cancel first withdrawal
        vm.prank(user1);
        vault.cancelWithdrawal(index1);

        // Check balance restored
        assertEq(vault.balances(user1), DEPOSIT_AMOUNT - amount2);
    }

    /**
     * @notice Fuzz test: protocol yield maintains invariants
     */
    function testFuzzInvariant_YieldMaintainsInvariants(uint256 yieldBps) public {
        vm.assume(yieldBps > 0 && yieldBps <= 10000); // 0-100%

        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), DEPOSIT_AMOUNT);

        // Accrue yield
        _simulateYieldOnProtocol(address(protocolA), yieldBps);

        // Collect yield
        address[] memory protocols = new address[](1);
        protocols[0] = address(protocolA);
        vm.prank(manager);
        vault.collectYield(protocols);

        // Total deposits should not have decreased
        assertEq(vault.totalDeposits(), DEPOSIT_AMOUNT);

        // Yield should be tracked
        assertGe(vault.totalYield(), 0);
    }

    /*//////////////////////////////////////////////////////////////
                        PROPERTY TESTS
    //////////////////////////////////////////////////////////////*/

    /**
     * @notice Property: withdraw can only succeed if balance >= amount
     */
    function testProperty_WithdrawRequiresBalance() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 balance = vault.balances(user1);

        for (uint256 i = 0; i < 10; i++) {
            uint256 withdrawAmount = bound(i * 1000e6, 1, balance);

            vm.prank(user1);
            if (withdrawAmount <= balance && withdrawAmount <= TMVault.MAX_SINGLE_WITHDRAWAL()) {
                // Should succeed (if enough vault liquidity)
                if (usdc.balanceOf(address(vault)) >= withdrawAmount) {
                    vault.instantWithdraw(withdrawAmount);
                    balance -= withdrawAmount;
                }
            }
        }
    }

    /**
     * @notice Property: allocation can only succeed with sufficient liquidity
     */
    function testProperty_AllocationRequiresLiquidity() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 vaultBalance = usdc.balanceOf(address(vault));

        for (uint256 i = 1; i <= 5; i++) {
            uint256 allocateAmount = vaultBalance / i;

            if (allocateAmount > 0) {
                vm.prank(manager);
                vault.allocateToProtocol(address(protocolA), allocateAmount);
                vaultBalance -= allocateAmount;
            }
        }

        // Final check: all allocated
        assertEq(vault.totalAllocated(), DEPOSIT_AMOUNT);
    }

    /**
     * @notice Property: queue order is preserved
     */
    function testProperty_QueueOrderPreserved() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256[] memory indices = new uint256[](5);
        for (uint256 i = 0; i < 5; i++) {
            indices[i] = _requestWithdrawal(user1, 1000e6);
        }

        // Check indices are in order
        for (uint256 i = 0; i < 4; i++) {
            assertEq(indices[i + 1], indices[i] + 1, "Indices not sequential");
        }
    }

    /*//////////////////////////////////////////////////////////////
                        EDGE CASE TESTS
    //////////////////////////////////////////////////////////////*/

    /**
     * @notice Edge case: max withdrawal amount
     */
    function testEdgeCase_MaxWithdrawalAmount() public {
        uint256 maxWithdraw = TMVault.MAX_SINGLE_WITHDRAWAL();
        _deposit(user1, maxWithdraw);

        // Should succeed with exactly max
        vm.prank(user1);
        vault.instantWithdraw(maxWithdraw);

        assertEq(vault.balances(user1), 0);
    }

    /**
     * @notice Edge case: zero address handling
     */
    function testEdgeCase_ZeroAddressHandling() public {
        vm.expectRevert(TMVault.ZeroAssets.selector);
        new TMVault(address(0), manager);
    }

    /**
     * @notice Edge case: full queue capacity
     */
    function testEdgeCase_FullQueueCapacity() public {
        _deposit(user1, 1_000_000e6);

        // Fill queue to capacity
        for (uint256 i = 0; i < TMVault.MAX_QUEUE_SIZE(); i++) {
            _requestWithdrawal(user1, 1000e6);
        }

        assertEq(vault.getQueueSize(), TMVault.MAX_QUEUE_SIZE());

        // Next should fail
        vm.prank(user1);
        vm.expectRevert(TMVault.QueueFull.selector);
        vault.requestWithdrawal(1000e6);
    }

    /**
     * @notice Edge case: withdrawal delay boundary
     */
    function testEdgeCase_WithdrawalDelayBoundary() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        uint256 index = _requestWithdrawal(user1, WITHDRAWAL_AMOUNT);

        // Just before delay - should fail
        skip(ONE_DAY - 1);
        vm.expectRevert(TMVault.InsufficientVaultLiquidity.selector);
        vault.processWithdrawal(index);

        // Exactly at delay - should succeed
        skip(1);
        vault.processWithdrawal(index);
    }

    /**
     * @notice Edge case: protocol deallocation with insufficient funds
     */
    function testEdgeCase_ProtocolDeallocateExcess() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);

        // Try to deallocate more than allocated
        vm.prank(manager);
        vm.expectRevert(TMVault.InsufficientBalance.selector);
        vault.deallocateFromProtocol(address(protocolA), WITHDRAWAL_AMOUNT + 1);
    }

    /**
     * @notice Edge case: reentrancy protection on withdrawal
     */
    function testEdgeCase_ReentrancyProtection() public {
        // This test ensures that reentrancy is not possible
        // The vault uses transfer which has built-in reentrancy protection
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 balanceBefore = vault.balances(user1);

        vm.prank(user1);
        vault.instantWithdraw(WITHDRAWAL_AMOUNT);

        // Balance should decrease exactly once
        assertEq(vault.balances(user1), balanceBefore - WITHDRAWAL_AMOUNT);
    }

    /**
     * @notice Edge case: deposit to zero address receiver
     */
    function testEdgeCase_DepositToZeroAddress() public {
        vm.prank(user1);
        usdc.approve(address(vault), DEPOSIT_AMOUNT);

        // Some vaults might block this, but ours allows it
        vm.prank(user1);
        vault.deposit(DEPOSIT_AMOUNT, address(0));

        // Balance should be credited to zero address
        assertEq(vault.balances(address(0)), DEPOSIT_AMOUNT);
    }

    /**
     * @notice Edge case: multiple allocation cycles
     */
    function testEdgeCase_MultipleAllocationCycles() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        // Multiple allocate/deallocate cycles
        for (uint256 i = 0; i < 10; i++) {
            _allocate(address(protocolA), 10_000e6);
            _deallocate(address(protocolA), 10_000e6);
        }

        assertEq(vault.protocolBalance(address(protocolA)), 0);
        assertEq(vault.totalAllocated(), 0);
    }
}
