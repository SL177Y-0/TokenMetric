// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {TMVault} from "../../src/TMVault.sol";
import {MockUSDC} from "../mocks/MockUSDC.sol";
import {MockProtocol} from "../mocks/MockProtocol.sol";

/**
 * @title VaultFixture
 * @notice Reusable test fixture for TMVault testing
 * @dev Provides setup, helpers, and common test scenarios
 */
contract VaultFixture is Test {
    // Contracts
    TMVault vault;
    MockUSDC usdc;
    MockProtocol protocolA;
    MockProtocol protocolB;
    MockProtocol protocolC;

    // Test accounts
    address manager = makeAddr("manager");
    address user1 = makeAddr("user1");
    address user2 = makeAddr("user2");
    address user3 = makeAddr("user3");
    address attacker = makeAddr("attacker");

    // Constants
    uint256 constant INITIAL_BALANCE = 1_000_000e6; // 1M USDC
    uint256 constant DEPOSIT_AMOUNT = 100_000e6;   // 100k USDC
    uint256 constant WITHDRAWAL_AMOUNT = 50_000e6; // 50k USDC
    uint256 constant ONE_DAY = 1 days;

    // Events for testing
    event Deposited(address indexed caller, address indexed owner, uint256 assets);
    event Withdrawn(address indexed owner, uint256 assets, uint256 shares);
    event WithdrawalQueued(address indexed owner, uint256 amount, uint256 index);
    event WithdrawalProcessed(address indexed owner, uint256 amount, uint256 index);
    event Allocated(address indexed protocol, uint256 amount);
    event Deallocated(address indexed protocol, uint256 amount);

    function setUp() public virtual {
        // Deploy mock contracts
        usdc = new MockUSDC("USD Coin", "USDC", 6);
        vault = new TMVault(address(usdc), manager);
        protocolA = new MockProtocol(address(usdc));
        protocolB = new MockProtocol(address(usdc));
        protocolC = new MockProtocol(address(usdc));

        // Set vault in protocols
        vm.startPrank(manager);
        vault.setProtocols(address(protocolA), address(protocolB));
        protocolA.setVault(address(vault));
        protocolB.setVault(address(vault));
        protocolC.setVault(address(vault));
        vm.stopPrank();

        // Fund users with initial balance
        usdc.mint(user1, INITIAL_BALANCE);
        usdc.mint(user2, INITIAL_BALANCE);
        usdc.mint(user3, INITIAL_BALANCE);
        usdc.mint(attacker, INITIAL_BALANCE);
    }

    /*//////////////////////////////////////////////////////////////
                            HELPERS
    //////////////////////////////////////////////////////////////*/

    /**
     * @notice Helper to deposit assets for a user
     * @param user Address of the user
     * @param amount Amount to deposit
     */
    function _deposit(address user, uint256 amount) internal {
        vm.startPrank(user);
        usdc.approve(address(vault), amount);
        vault.deposit(amount, user);
        vm.stopPrank();
    }

    /**
     * @notice Helper to deposit for multiple users
     * @param users Array of user addresses
     * @param amount Amount for each user
     */
    function _depositMany(address[] memory users, uint256 amount) internal {
        for (uint256 i = 0; i < users.length; i++) {
            _deposit(users[i], amount);
        }
    }

    /**
     * @notice Helper to request a withdrawal
     * @param user Address of the user
     * @param amount Amount to withdraw
     * @return index Index of the withdrawal request
     */
    function _requestWithdrawal(address user, uint256 amount) internal returns (uint256 index) {
        vm.prank(user);
        return vault.requestWithdrawal(amount);
    }

    /**
     * @notice Helper to process a withdrawal (skip time delay)
     * @param index Index of the withdrawal request
     */
    function _processWithdrawal(uint256 index) internal {
        // Skip the withdrawal delay
        skip(ONE_DAY);
        vault.processWithdrawal(index);
    }

    /**
     * @notice Helper to instant withdraw
     * @param user Address of the user
     * @param amount Amount to withdraw
     */
    function _instantWithdraw(address user, uint256 amount) internal {
        vm.prank(user);
        vault.instantWithdraw(amount);
    }

    /**
     * @notice Helper to allocate funds to a protocol
     * @param protocol Address of the protocol
     * @param amount Amount to allocate
     */
    function _allocate(address protocol, uint256 amount) internal {
        vm.prank(manager);
        vault.allocateToProtocol(protocol, amount);
    }

    /**
     * @notice Helper to deallocate funds from a protocol
     * @param protocol Address of the protocol
     * @param amount Amount to deallocate
     */
    function _deallocate(address protocol, uint256 amount) internal {
        vm.prank(manager);
        vault.deallocateFromProtocol(protocol, amount);
    }

    /**
     * @notice Helper to simulate yield accrual
     * @param bps Basis points of yield (100 = 1%)
     */
    function _simulateYield(uint256 bps) internal {
        protocolA.accrue(bps);
        protocolB.accrue(bps);
    }

    /**
     * @notice Helper to simulate yield on specific protocol
     * @param protocol Protocol address
     * @param bps Basis points of yield
     */
    function _simulateYieldOnProtocol(address protocol, uint256 bps) internal {
        MockProtocol(protocol).accrue(bps);
    }

    /**
     * @notice Helper to fund the vault with liquidity
     * @param amount Amount to add to vault
     */
    function _fundVault(uint256 amount) internal {
        usdc.mint(address(vault), amount);
    }

    /**
     * @notice Setup a standard test state with deposits and allocations
     */
    function _setupStandardState() internal {
        // User1 and User2 deposit
        _deposit(user1, DEPOSIT_AMOUNT);
        _deposit(user2, DEPOSIT_AMOUNT);

        // Allocate half to protocolA
        _allocate(address(protocolA), DEPOSIT_AMOUNT);

        // Simulate some yield
        _simulateYield(100); // 1% yield
    }

    /**
     * @notice Setup full queue for testing
     * @param count Number of withdrawal requests to queue
     */
    function _fillQueue(uint256 count) internal {
        for (uint256 i = 0; i < count; i++) {
            _requestWithdrawal(user1, 1000e6);
        }
    }

    /**
     * @notice Assert balance equality within tolerance
     * @param a First value
     * @param b Second value
     * @param tolerance Allowed difference
     */
    function _assertApproxEq(uint256 a, uint256 b, uint256 tolerance) internal {
        uint256 diff = a > b ? a - b : b - a;
        assertTrue(diff <= tolerance, "Values not within tolerance");
    }

    /**
     * @notice Get expected balance with yield
     * @param principal Initial principal
     * @param bps Yield basis points
     * @return Expected balance
     */
    function _expectedWithYield(uint256 principal, uint256 bps) internal pure returns (uint256) {
        return principal + (principal * bps) / 10000;
    }

    /*//////////////////////////////////////////////////////////////
                            SCENARIOS
    //////////////////////////////////////////////////////////////*/

    /**
     * @notice Setup scenario: vault with allocated funds
     */
    function scenario_AllocatedFunds() internal {
        _deposit(user1, 200_000e6);
        _allocate(address(protocolA), 100_000e6);
        _allocate(address(protocolB), 50_000e6);
    }

    /**
     * @notice Setup scenario: pending withdrawals in queue
     */
    function scenario_PendingWithdrawals() internal returns (uint256[] memory indices) {
        _deposit(user1, 100_000e6);
        _deposit(user2, 100_000e6);

        indices = new uint256[](4);
        indices[0] = _requestWithdrawal(user1, 10_000e6);
        indices[1] = _requestWithdrawal(user1, 20_000e6);
        indices[2] = _requestWithdrawal(user2, 15_000e6);
        indices[3] = _requestWithdrawal(user2, 25_000e6);

        skip(ONE_DAY);
    }

    /**
     * @notice Setup scenario: vault with yield
     */
    function scenario_VaultWithYield() internal {
        _deposit(user1, 100_000e6);
        _allocate(address(protocolA), 100_000e6);
        _simulateYield(500); // 5% yield
    }

    /**
     * @notice Setup scenario: multi-user deposits
     */
    function scenario_MultiUserDeposits() internal {
        address[] memory users = new address[](5);
        users[0] = user1;
        users[1] = user2;
        users[2] = user3;
        users[3] = manager;
        users[4] = makeAddr("user4");

        // Fund new users
        usdc.mint(users[3], INITIAL_BALANCE);
        usdc.mint(users[4], INITIAL_BALANCE);

        _depositMany(users, DEPOSIT_AMOUNT);
    }
}
