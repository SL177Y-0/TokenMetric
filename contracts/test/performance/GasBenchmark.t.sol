// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {VaultFixture} from "../fixtures/VaultFixture.sol";
import {TMVault} from "../../src/TMVault.sol";

/**
 * @title GasBenchmark
 * @notice Gas benchmarking tests for TMVault operations
 * @dev Tracks gas usage for critical operations
 */
contract GasBenchmark is VaultFixture {
    // Gas tracking
    uint256 constant DEPOSIT_GAS_LIMIT = 200_000;
    uint256 constant WITHDRAW_GAS_LIMIT = 250_000;
    uint256 constant ALLOCATE_GAS_LIMIT = 150_000;

    struct GasMetrics {
        string operation;
        uint256 gasUsed;
        uint256 limit;
        bool passed;
    }

    GasMetrics[] public gasReadings;

    function logGas(string memory operation, uint256 gasUsed, uint256 limit) internal {
        bool passed = gasUsed <= limit;
        gasReadings.push(GasMetrics({
            operation: operation,
            gasUsed: gasUsed,
            limit: limit,
            passed: passed
        }));

        emit log(string(abi.encodePacked(operation, ": ", vm.toString(gasUsed))));
    }

    /*//////////////////////////////////////////////////////////////
                            GAS BENCHMARKS
    //////////////////////////////////////////////////////////////*/

    function test_Gas_Deposit() public {
        vm.startPrank(user1);
        usdc.approve(address(vault), DEPOSIT_AMOUNT);
        vm.stopPrank();

        uint256 gasBefore = gasleft();
        vm.prank(user1);
        vault.deposit(DEPOSIT_AMOUNT, user1);
        uint256 gasUsed = gasBefore - gasleft();

        logGas("Deposit", gasUsed, DEPOSIT_GAS_LIMIT);
        assertTrue(gasUsed <= DEPOSIT_GAS_LIMIT, "Deposit gas exceeds limit");
    }

    function test_Gas_InstantWithdraw() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 gasBefore = gasleft();
        vm.prank(user1);
        vault.instantWithdraw(WITHDRAWAL_AMOUNT);
        uint256 gasUsed = gasBefore - gasleft();

        logGas("Instant Withdraw", gasUsed, WITHDRAW_GAS_LIMIT);
        assertTrue(gasUsed <= WITHDRAW_GAS_LIMIT, "Instant withdraw gas exceeds limit");
    }

    function test_Gas_RequestWithdrawal() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 gasBefore = gasleft();
        vm.prank(user1);
        vault.requestWithdrawal(WITHDRAWAL_AMOUNT);
        uint256 gasUsed = gasBefore - gasleft();

        logGas("Request Withdrawal", gasUsed, WITHDRAW_GAS_LIMIT);
        assertTrue(gasUsed <= WITHDRAW_GAS_LIMIT, "Request withdrawal gas exceeds limit");
    }

    function test_Gas_ProcessWithdrawal() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        uint256 index = _requestWithdrawal(user1, WITHDRAWAL_AMOUNT);

        skip(ONE_DAY);

        uint256 gasBefore = gasleft();
        vault.processWithdrawal(index);
        uint256 gasUsed = gasBefore - gasleft();

        logGas("Process Withdrawal", gasUsed, WITHDRAW_GAS_LIMIT);
        assertTrue(gasUsed <= WITHDRAW_GAS_LIMIT, "Process withdrawal gas exceeds limit");
    }

    function test_Gas_AllocateToProtocol() public {
        _deposit(user1, DEPOSIT_AMOUNT);

        uint256 gasBefore = gasleft();
        vm.prank(manager);
        vault.allocateToProtocol(address(protocolA), WITHDRAWAL_AMOUNT);
        uint256 gasUsed = gasBefore - gasleft();

        logGas("Allocate To Protocol", gasUsed, ALLOCATE_GAS_LIMIT);
        assertTrue(gasUsed <= ALLOCATE_GAS_LIMIT, "Allocate gas exceeds limit");
    }

    function test_Gas_DeallocateFromProtocol() public {
        _deposit(user1, DEPOSIT_AMOUNT);
        _allocate(address(protocolA), WITHDRAWAL_AMOUNT);

        uint256 gasBefore = gasleft();
        vm.prank(manager);
        vault.deallocateFromProtocol(address(protocolA), WITHDRAWAL_AMOUNT);
        uint256 gasUsed = gasBefore - gasleft();

        logGas("Deallocate From Protocol", gasUsed, ALLOCATE_GAS_LIMIT);
        assertTrue(gasUsed <= ALLOCATE_GAS_LIMIT, "Deallocate gas exceeds limit");
    }

    /*//////////////////////////////////////////////////////////////
                        STRESS TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Gas_Deposit_Scale(uint256 count) public {
        vm.assume(count >= 1 && count <= 100);

        uint256[] memory gasUsages = new uint256[](int256(count));

        for (uint256 i = 0; i < count; i++) {
            address user = makeAddr(string(abi.encodePacked("user", i)));
            usdc.mint(user, DEPOSIT_AMOUNT);

            vm.startPrank(user);
            usdc.approve(address(vault), DEPOSIT_AMOUNT);

            uint256 gasBefore = gasleft();
            vault.deposit(DEPOSIT_AMOUNT, user);
            gasUsages[int256(i)] = gasBefore - gasleft();
            vm.stopPrank();
        }

        // Gas should not increase linearly with user count (no storage expansion)
        uint256 avgGas = 0;
        for (uint256 i = 0; i < count; i++) {
            avgGas += gasUsages[i];
        }
        avgGas /= count;

        // First deposit might be more expensive, but subsequent ones should be consistent
        assertLe(gasUsages[int256(count - 1)], avgGas * 11 / 10, "Gas increased significantly");
    }

    function test_Gas_QueueFilling() public {
        _deposit(user1, 1_000_000e6);

        uint256[] memory gasUsages = new uint256[](100);

        for (uint256 i = 0; i < 100; i++) {
            uint256 gasBefore = gasleft();
            _requestWithdrawal(user1, 1000e6);
            gasUsages[i] = gasBefore - gasleft();
        }

        // Check for gas increase as queue fills (should be minimal)
        uint256 firstGas = gasUsages[0];
        uint256 lastGas = gasUsages[99];

        assertLe(lastGas, firstGas * 105 / 100, "Queue filling caused significant gas increase");
    }

    /*//////////////////////////////////////////////////////////////
                        BENCHMARK SUMMARY
    //////////////////////////////////////////////////////////////*/

    function test_Gas_Summary() public view {
        // Print summary of all gas readings
        for (uint256 i = 0; i < gasReadings.length; i++) {
            GasMetrics memory reading = gasReadings[i];
            // Results will be in the test output
        }
    }
}
