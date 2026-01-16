// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {VaultFixture} from "../fixtures/VaultFixture.sol";

/**
 * @title VaultUnitTests
 * @notice Comprehensive unit tests for TMVault
 * @dev Covers deposit, withdrawal, protocol allocation, and edge cases
 */
contract VaultUnitTests is VaultFixture {

    /*//////////////////////////////////////////////////////////////
                            DEPOSIT TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Deposit_Success() public {
        vm.startPrank(user1);
        usdc.approve(address(vault), DEPOSIT_AMOUNT);

        vm.expectEmit(true, true, false, true);
        emit Deposited(user1, user1, DEPOSIT_AMOUNT);

        uint256 shares = vault.deposit(DEPOSIT_AMOUNT, user1);

        assertEq(shares, DEPOSIT_AMOUNT, "Shares should equal assets");
        assertEq(vault.balances(user1), DEPOSIT_AMOUNT, "Balance should be updated");
        assertEq(vault.totalDeposits(), DEPOSIT_AMOUNT, "Total deposits should match");
        vm.stopPrank();
    }

    function test_Deposit_ToDifferentReceiver() public {
        vm.prank(user1);
        usdc.approve(address(vault), DEPOSIT_AMOUNT);

        vm.prank(user1);
        vault.deposit(DEPOSIT_AMOUNT, user2);

        assertEq(vault.balances(user1), 0, "Sender balance should be 0");
        assertEq(vault.balances(user2), DEPOSIT_AMOUNT, "Receiver balance should be updated");
    }

    function test_Deposit_ZeroAmount_Reverts() public {
        vm.prank(user1);
        usdc.approve(address(vault), DEPOSIT_AMOUNT);

        vm.expectRevert(TMVault.ZeroAssets.selector);
        vault.deposit(0, user1);
    }

    function test_Deposit_InsufficientAllowance_Reverts() public {
        vm.prank(user1);
        usdc.approve(address(vault), DEPOSIT_AMOUNT - 1);

        vm.expectRevert(); // ERC20 allowance error
        vault.deposit(DEPOSIT_AMOUNT, user1);
    }

    function test_Deposit_MultipleDeposits() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _deposit(user1, DEPOSIT_AMOUNT);
        _deposit(user2, DEPOSIT_AMOUNT);

        assertEq(vault.balances(user1), DEPOSIT_AMOUNT * 2, "User1 should have 2x deposits");
        assertEq(vault.balances(user2), DEPOSIT_AMOUNT, "User2 should have 1x deposit");
        assertEq(vault.totalDeposits(), DEPOSIT_AMOUNT * 3, "Total should be sum of all deposits");
    }

    function test_Deposit_MaxUint256() public {
        // Test with very large amount (but not exceeding balance)
        uint256 largeAmount = INITIAL_BALANCE;

        vm.prank(user1);
        usdc.approve(address(vault), largeAmount);

        vm.prank(user1);
        vault.deposit(largeAmount, user1);

        assertEq(vault.balances(user1), largeAmount);
    }

    /*//////////////////////////////////////////////////////////////
                        WITHDRAWAL TESTS
    //////////////////////////////////////////////////////////////*/

    function test_InstantWithdraw_Success() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 balanceBefore = usdc.balanceOf(user1);

        vm.expectEmit(true, false, false, true);
        emit Withdrawn(user1, WITHDRAWAL_AMOUNT, WITHDRAWAL_AMOUNT);

        vm.prank(user1);
        vault.instantWithdraw(WITHDRAWAL_AMOUNT);

        assertEq(vault.balances(user1), DEPOSIT_AMOUNT - WITHDRAWAL_AMOUNT, "Balance should decrease");
        assertEq(usdc.balanceOf(user1), balanceBefore + WITHDRAWAL_AMOUNT, "User should receive funds");
        assertEq(vault.totalDeposits(), DEPOSIT_AMOUNT - WITHDRAWAL_AMOUNT, "Total should decrease");
    }

    function test_InstantWithdraw_InsufficientBalance_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        vm.prank(user1);
        vm.expectRevert(TMVault.InsufficientBalance.selector);
        vault.instantWithdraw(DEPOSIT_AMOUNT + 1);
    }

    function test_InstantWithdraw_ZeroAmount_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        vm.prank(user1);
        vm.expectRevert(TMVault.ZeroAssets.selector);
        vault.instantWithdraw(0);
    }

    function test_InstantWithdraw_ExceedsMaxLimit_Reverts() public {
        _deposit(user1, 200_000e6);

        vm.prank(user1);
        vm.expectRevert(TMVault.WithdrawalTooLarge.selector);
        vault.instantWithdraw(100_001e6); // MAX_SINGLE_WITHDRAWAL + 1
    }

    function test_InstantWithdraw_InsufficientVaultLiquidity_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), DEPOSIT_AMOUNT);

        vm.prank(user1);
        vm.expectRevert(TMVault.InsufficientVaultLiquidity.selector);
        vault.instantWithdraw(WITHDRAWAL_AMOUNT);
    }

    /*//////////////////////////////////////////////////////////////
                        WITHDRAWAL QUEUE TESTS
    //////////////////////////////////////////////////////////////*/

    function test_RequestWithdrawal_Success() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        vm.expectEmit(true, false, false, true);
        emit WithdrawalQueued(user1, WITHDRAWAL_AMOUNT, 0);

        vm.prank(user1);
        uint256 index = vault.requestWithdrawal(WITHDRAWAL_AMOUNT);

        assertEq(index, 0, "First index should be 0");
        assertEq(vault.balances(user1), DEPOSIT_AMOUNT - WITHDRAWAL_AMOUNT, "Balance should decrease");

        (address owner, uint256 amount, uint256 timestamp, bool processed) = vault.getWithdrawalRequest(0);
        assertEq(owner, user1, "Owner should match");
        assertEq(amount, WITHDRAWAL_AMOUNT, "Amount should match");
        assertGt(timestamp, 0, "Timestamp should be set");
        assertFalse(processed, "Should not be processed");
    }

    function test_RequestWithdrawal_MultipleRequests() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 index1 = _requestWithdrawal(user1, 10_000e6);
        uint256 index2 = _requestWithdrawal(user1, 20_000e6);
        uint256 index3 = _requestWithdrawal(user1, 30_000e6);

        assertEq(index1, 0, "First index should be 0");
        assertEq(index2, 1, "Second index should be 1");
        assertEq(index3, 2, "Third index should be 2");

        uint256 queueSize = vault.getQueueSize();
        assertEq(queueSize, 3, "Queue size should be 3");
    }

    function test_RequestWithdrawal_ZeroAmount_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        vm.prank(user1);
        vm.expectRevert(TMVault.ZeroAssets.selector);
        vault.requestWithdrawal(0);
    }

    function test_RequestWithdrawal_ExceedsMaxLimit_Reverts() public {
        _deposit(user1, 200_000e6);

        vm.prank(user1);
        vm.expectRevert(TMVault.WithdrawalTooLarge.selector);
        vault.requestWithdrawal(100_001e6);
    }

    function test_ProcessWithdrawal_Success() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        uint256 index = _requestWithdrawal(user1, WITHDRAWAL_AMOUNT);

        uint256 balanceBefore = usdc.balanceOf(user1);

        skip(ONE_DAY);

        vm.expectEmit(true, false, false, true);
        emit WithdrawalProcessed(user1, WITHDRAWAL_AMOUNT, index);

        vault.processWithdrawal(index);

        assertEq(usdc.balanceOf(user1), balanceBefore + WITHDRAWAL_AMOUNT, "User should receive funds");

        (, , , bool processed) = vault.getWithdrawalRequest(index);
        assertTrue(processed, "Request should be marked processed");
    }

    function test_ProcessWithdrawal_BeforeDelay_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        uint256 index = _requestWithdrawal(user1, WITHDRAWAL_AMOUNT);

        skip(ONE_DAY - 1); // Just before delay

        vm.expectRevert(TMVault.InsufficientVaultLiquidity.selector);
        vault.processWithdrawal(index);
    }

    function test_ProcessWithdrawal_AlreadyProcessed_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        uint256 index = _requestWithdrawal(user1, WITHDRAWAL_AMOUNT);

        skip(ONE_DAY);
        vault.processWithdrawal(index);

        vm.expectRevert(TMVault.NotInQueue.selector);
        vault.processWithdrawal(index);
    }

    function test_ProcessWithdrawal_DeallocatesFromProtocol() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), DEPOSIT_AMOUNT);

        uint256 index = _requestWithdrawal(user1, WITHDRAWAL_AMOUNT);

        skip(ONE_DAY);
        vault.processWithdrawal(index);

        assertEq(usdc.balanceOf(user1), WITHDRAWAL_AMOUNT, "User should receive funds");
    }

    function test_CancelWithdrawal_Success() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        uint256 index = _requestWithdrawal(user1, WITHDRAWAL_AMOUNT);

        vm.expectEmit(true, false, false, true);
        emit WithdrawalCancelled(user1, WITHDRAWAL_AMOUNT, index);

        vm.prank(user1);
        vault.cancelWithdrawal(index);

        assertEq(vault.balances(user1), DEPOSIT_AMOUNT, "Balance should be restored");
        assertEq(vault.totalDeposits(), DEPOSIT_AMOUNT, "Total should be restored");

        (, , , bool processed) = vault.getWithdrawalRequest(index);
        assertTrue(processed, "Request should be marked processed");
    }

    function test_CancelWithdrawal_NotOwner_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        uint256 index = _requestWithdrawal(user1, WITHDRAWAL_AMOUNT);

        vm.prank(user2);
        vm.expectRevert(TMVault.NotManager.selector); // Uses NotManager for non-owner
        vault.cancelWithdrawal(index);
    }

    function test_GetUserWithdrawals() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _deposit(user2, DEPOSIT_AMOUNT);

        uint256 index1 = _requestWithdrawal(user1, 10_000e6);
        uint256 index2 = _requestWithdrawal(user1, 20_000e6);
        _requestWithdrawal(user2, 15_000e6);

        uint256[] memory user1Indices = vault.getUserWithdrawals(user1);
        uint256[] memory user2Indices = vault.getUserWithdrawals(user2);

        assertEq(user1Indices.length, 2, "User1 should have 2 withdrawals");
        assertEq(user1Indices[0], index1, "First index should match");
        assertEq(user1Indices[1], index2, "Second index should match");

        assertEq(user2Indices.length, 1, "User2 should have 1 withdrawal");
    }

    function test_IsWithdrawalReady() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        uint256 index = _requestWithdrawal(user1, WITHDRAWAL_AMOUNT);

        assertFalse(vault.isWithdrawalReady(index), "Should not be ready immediately");

        skip(ONE_DAY);
        assertTrue(vault.isWithdrawalReady(index), "Should be ready after delay");
    }

    function test_QueueFull_Reverts() public {
        _deposit(user1, 10_000_000e6); // Large deposit

        // Fill queue to max
        for (uint256 i = 0; i < 100; i++) {
            _requestWithdrawal(user1, 1000e6);
        }

        // Next request should fail
        vm.prank(user1);
        vm.expectRevert(TMVault.QueueFull.selector);
        vault.requestWithdrawal(1000e6);
    }

    /*//////////////////////////////////////////////////////////////
                    PROTOCOL ALLOCATION TESTS
    //////////////////////////////////////////////////////////////*/

    function test_AllocateToProtocol_Success() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 vaultBalanceBefore = usdc.balanceOf(address(vault));

        vm.prank(manager);
        vm.expectEmit(true, false, false, true);
        emit Allocated(address(protocolA), WITHDRAWAL_AMOUNT);

        vault.allocateToProtocol(address(protocolA), WITHDRAWAL_AMOUNT);

        assertEq(vault.protocolBalance(address(protocolA)), WITHDRAWAL_AMOUNT, "Protocol balance should update");
        assertEq(vault.totalAllocated(), WITHDRAWAL_AMOUNT, "Total allocated should update");
        assertEq(usdc.balanceOf(address(vault)), vaultBalanceBefore - WITHDRAWAL_AMOUNT, "Vault balance should decrease");
    }

    function test_AllocateToProtocol_NotManager_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        vm.prank(user1);
        vm.expectRevert(TMVault.NotManager.selector);
        vault.allocateToProtocol(address(protocolA), WITHDRAWAL_AMOUNT);
    }

    function test_AllocateToProtocol_InvalidProtocol_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        address randomProtocol = makeAddr("random");

        vm.prank(manager);
        vm.expectRevert(TMVault.InvalidProtocol.selector);
        vault.allocateToProtocol(randomProtocol, WITHDRAWAL_AMOUNT);
    }

    function test_AllocateToProtocol_InsufficientLiquidity_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        vm.prank(manager);
        vm.expectRevert(TMVault.InsufficientVaultLiquidity.selector);
        vault.allocateToProtocol(address(protocolA), DEPOSIT_AMOUNT + 1);
    }

    function test_DeallocateFromProtocol_Success() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);

        uint256 vaultBalanceBefore = usdc.balanceOf(address(vault));

        vm.prank(manager);
        vault.deallocateFromProtocol(address(protocolA), WITHDRAWAL_AMOUNT);

        assertEq(vault.protocolBalance(address(protocolA)), 0, "Protocol balance should be 0");
        assertEq(vault.totalAllocated(), 0, "Total allocated should be 0");
        assertEq(usdc.balanceOf(address(vault)), vaultBalanceBefore + WITHDRAWAL_AMOUNT, "Vault should receive funds");
    }

    function test_DeallocateFromProtocol_NotManager_Reverts() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);

        vm.prank(user1);
        vm.expectRevert(TMVault.NotManager.selector);
        vault.deallocateFromProtocol(address(protocolA), WITHDRAWAL_AMOUNT);
    }

    function test_CollectYield_Success() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), DEPOSIT_AMOUNT);

        // Simulate yield in protocol
        _simulateYield(100); // 1% yield

        address[] memory protocols = new address[](1);
        protocols[0] = address(protocolA);

        vm.prank(manager);
        vault.collectYield(protocols);

        assertGt(vault.totalYield(), 0, "Total yield should be > 0");
    }

    function test_TotalAssets() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);

        uint256 totalAssets = vault.totalAssets();

        assertEq(totalAssets, DEPOSIT_AMOUNT, "Total assets should equal deposits");
    }

    /*//////////////////////////////////////////////////////////////
                        ADMIN TESTS
    //////////////////////////////////////////////////////////////*/

    function test_SetProtocols_Success() public {
        vm.prank(manager);
        vm.expectEmit(true, true, false, true);
        emit ProtocolSet(address(protocolA), address(protocolB));

        vault.setProtocols(address(protocolA), address(protocolB));

        assertEq(vault.protocolA(), address(protocolA), "ProtocolA should be set");
        assertEq(vault.protocolB(), address(protocolB), "ProtocolB should be set");
        assertTrue(vault.isProtocol(address(protocolA)), "ProtocolA should be valid");
        assertTrue(vault.isProtocol(address(protocolB)), "ProtocolB should be valid");
    }

    function test_SetProtocols_NotManager_Reverts() public {
        vm.prank(user1);
        vm.expectRevert(TMVault.NotManager.selector);
        vault.setProtocols(address(protocolA), address(protocolB));
    }

    function test_AddProtocol_Success() public {
        vm.prank(manager);
        vault.addProtocol(address(protocolC));

        assertTrue(vault.isProtocol(address(protocolC)), "ProtocolC should be valid");

        address[] memory protocols = vault.getProtocols();
        assertEq(protocols.length, 3, "Should have 3 protocols");
    }

    function test_AddProtocol_AlreadyExists_Reverts() public {
        vm.prank(manager);
        vm.expectRevert(TMVault.InvalidProtocol.selector);
        vault.addProtocol(address(protocolA));
    }

    function test_RemoveProtocol_Success() public {
        vm.prank(manager);
        vault.removeProtocol(address(protocolB));

        assertFalse(vault.isProtocol(address(protocolB)), "ProtocolB should not be valid");
    }

    function test_SetManager_Success() public {
        address newManager = makeAddr("newManager");

        vm.prank(manager);
        vault.setManager(newManager);

        assertEq(vault.manager(), newManager, "Manager should be updated");
    }

    function test_SetManager_ZeroAddress_Reverts() public {
        vm.prank(manager);
        vm.expectRevert(TMVault.ZeroAssets.selector);
        vault.setManager(address(0));
    }

    function test_EmergencyWithdrawAll() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);
        _allocate(address(protocolB), WITHDRAWAL_AMOUNT);

        uint256 vaultBalanceBefore = usdc.balanceOf(address(vault));

        vm.prank(manager);
        vault.emergencyWithdrawAll();

        assertEq(vault.totalAllocated(), 0, "All funds should be deallocated");
        assertEq(usdc.balanceOf(address(vault)), vaultBalanceBefore + WITHDRAWAL_AMOUNT * 2, "Vault should receive all funds");
    }

    /*//////////////////////////////////////////////////////////////
                        VIEW FUNCTION TESTS
    //////////////////////////////////////////////////////////////*/

    function test_GetProtocols() public {
        address[] memory protocols = vault.getProtocols();

        assertEq(protocols.length, 2, "Should have 2 protocols");
        assertEq(protocols[0], address(protocolA), "First protocol should be protocolA");
        assertEq(protocols[1], address(protocolB), "Second protocol should be protocolB");
    }

    function test_GetQueueSize_Empty() public {
        assertEq(vault.getQueueSize(), 0, "Queue should be empty");
    }

    function test_GetQueueSize_WithItems() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _requestWithdrawal(user1, 10_000e6);
        _requestWithdrawal(user1, 20_000e6);

        // Process one
        skip(ONE_DAY);
        vault.processWithdrawal(0);

        assertEq(vault.getQueueSize(), 1, "Queue should have 1 pending item");
    }

    function test_GetWithdrawalRequest_InvalidIndex_Reverts() public {
        vm.expectRevert(TMVault.QueueEmpty.selector);
        vault.getWithdrawalRequest(0);
    }

    /*//////////////////////////////////////////////////////////////
                        INTEGRATION TESTS
    //////////////////////////////////////////////////////////////*/

    function test_FullLifecycle() public {
        // 1. Deposit
        _deposit(user1, DEPOSIT_AMOUNT);
        assertEq(vault.balances(user1), DEPOSIT_AMOUNT);

        // 2. Allocate to protocols
        _allocate(address(protocolA), 50_000e6);
        _allocate(address(protocolB), 30_000e6);
        assertEq(vault.totalAllocated(), 80_000e6);

        // 3. Simulate yield
        _simulateYield(200); // 2% yield
        vm.prank(manager);
        vault.collectYield(vault.getProtocols());

        // 4. Request withdrawal
        uint256 index = _requestWithdrawal(user1, 10_000e6);
        assertEq(vault.balances(user1), 90_000e6);

        // 5. Process withdrawal
        skip(ONE_DAY);
        vault.processWithdrawal(index);

        assertEq(usdc.balanceOf(user1), 10_000e6, "User should receive withdrawal");
    }

    function test_MultiUserScenario() public {
        _deposit(user1, 100_000e6);
        _deposit(user2, 100_000e6);
        _deposit(user3, 100_000e6);

        _allocate(address(protocolA), 150_000e6);

        uint256 index1 = _requestWithdrawal(user1, 30_000e6);
        uint256 index2 = _requestWithdrawal(user2, 20_000e6);
        uint256 index3 = _requestWithdrawal(user3, 10_000e6);

        skip(ONE_DAY);

        vault.processWithdrawal(index1);
        vault.processWithdrawal(index2);
        vault.processWithdrawal(index3);

        assertEq(usdc.balanceOf(user1), 30_000e6);
        assertEq(usdc.balanceOf(user2), 20_000e6);
        assertEq(usdc.balanceOf(user3), 10_000e6);
    }

    /*//////////////////////////////////////////////////////////////
                        FUZZ TESTS
    //////////////////////////////////////////////////////////////*/

    function testFuzz_Deposit(uint256 amount) public {
        // Constrain amount to reasonable values
        vm.assume(amount > 0 && amount <= INITIAL_BALANCE);

        usdc.mint(user1, amount);

        vm.prank(user1);
        usdc.approve(address(vault), amount);

        vm.prank(user1);
        vault.deposit(amount, user1);

        assertEq(vault.balances(user1), amount);
    }

    function testFuzz_DepositWithdraw(uint256 depositAmount, uint256 withdrawAmount) public {
        // Constrain values
        vm.assume(depositAmount > 0 && depositAmount <= INITIAL_BALANCE);
        vm.assume(withdrawAmount > 0 && withdrawAmount <= depositAmount);
        vm.assume(withdrawAmount <= TMVault.MAX_SINGLE_WITHDRAWAL());

        usdc.mint(user1, depositAmount);

        vm.startPrank(user1);
        usdc.approve(address(vault), depositAmount);
        vault.deposit(depositAmount, user1);

        vault.instantWithdraw(withdrawAmount);
        vm.stopPrank();

        assertEq(vault.balances(user1), depositAmount - withdrawAmount);
        assertEq(usdc.balanceOf(user1), INITIAL_BALANCE - depositAmount + withdrawAmount);
    }

    function testFuzz_MultipleDeposits(uint256 amount1, uint256 amount2) public {
        vm.assume(amount1 > 0 && amount1 <= INITIAL_BALANCE / 2);
        vm.assume(amount2 > 0 && amount2 <= INITIAL_BALANCE / 2);

        usdc.mint(user1, INITIAL_BALANCE);

        vm.prank(user1);
        usdc.approve(address(vault), INITIAL_BALANCE);

        vm.startPrank(user1);
        vault.deposit(amount1, user1);
        vault.deposit(amount2, user1);
        vm.stopPrank();

        assertEq(vault.balances(user1), amount1 + amount2);
    }

    function testFuzz_AllocateDeallocate(uint256 allocateAmount) public {
        vm.assume(allocateAmount > 0 && allocateAmount <= DEPOSIT_AMOUNT);

        _deposit(user1, DEPOSIT_AMOUNT);

        vm.prank(manager);
        vault.allocateToProtocol(address(protocolA), allocateAmount);

        assertEq(vault.protocolBalance(address(protocolA)), allocateAmount);

        vm.prank(manager);
        vault.deallocateFromProtocol(address(protocolA), allocateAmount);

        assertEq(vault.protocolBalance(address(protocolA)), 0);
    }

    /*//////////////////////////////////////////////////////////////
                        INVARIANTS
    //////////////////////////////////////////////////////////////*/

    function test_Invariant_BalanceNeverExceedsDeposits() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _deposit(user2, DEPOSIT_AMOUNT);

        uint256 totalUserBalances = vault.balances(user1) + vault.balances(user2);
        assertEq(totalUserBalances, vault.totalDeposits());
    }

    function test_Invariant_AllocatedNeverExceedsTotal() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);

        assertLe(vault.totalAllocated(), vault.totalDeposits());
    }

    function test_Invariant_QueueIndexCorrectness() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        for (uint256 i = 0; i < 10; i++) {
            uint256 index = _requestWithdrawal(user1, 1000e6);
            assertEq(index, i, "Index should match iteration");
        }
    }

    function test_Invariant_ProcessedWithdrawalsNotInQueue() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 index = _requestWithdrawal(user1, 10_000e6);

        skip(ONE_DAY);
        vault.processWithdrawal(index);

        assertEq(vault.getQueueSize(), 0, "Processed withdrawal should not be in queue");
    }
}
