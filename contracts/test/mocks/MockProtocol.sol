// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "../../src/TMVault.sol";

/**
 * @title MockProtocol
 * @notice Mock protocol for testing vault allocations
 * @dev Implements deposit, withdraw, and balance tracking
 */
contract MockProtocol {
    error NotVault();
    error InsufficientBalance();

    IERC20 public immutable asset;
    uint256 public allocated;
    uint256 public accruedYield;
    uint256 public yieldBps; // Yield in basis points

    address public vault;
    bool public acceptDeposits;
    bool public allowWithdrawals;

    event DepositReceived(uint256 amount);
    event WithdrawalProcessed(uint256 amount);
    event YieldAccrued(uint256 bps);

    modifier onlyVault() {
        if (msg.sender != vault) revert NotVault();
        _;
    }

    constructor(address _asset) {
        asset = IERC20(_asset);
        acceptDeposits = true;
        allowWithdrawals = true;
    }

    /**
     * @notice Set the vault address
     * @param _vault Address of the vault
     */
    function setVault(address _vault) external {
        vault = _vault;
    }

    /**
     * @notice Set acceptance state
     * @param _acceptDeposits Whether to accept deposits
     * @param _allowWithdrawals Whether to allow withdrawals
     */
    function setState(bool _acceptDeposits, bool _allowWithdrawals) external {
        acceptDeposits = _acceptDeposits;
        allowWithdrawals = _allowWithdrawals;
    }

    /**
     * @notice Deposit assets into protocol
     * @param amount Amount to deposit
     */
    function deposit(uint256 amount) external {
        if (msg.sender != vault && msg.sender != address(0)) revert NotVault();
        if (!acceptDeposits) revert NotVault();

        // Transfer from caller
        if (!asset.transferFrom(msg.sender, address(this), amount)) {
            revert InsufficientBalance();
        }

        allocated += amount;
        emit DepositReceived(amount);
    }

    /**
     * @notice Withdraw assets from protocol
     * @param amount Amount to withdraw
     */
    function withdraw(uint256 amount) external {
        if (!allowWithdrawals) revert InsufficientBalance();
        if (allocated < amount) revert InsufficientBalance();

        allocated -= amount;

        if (!asset.transfer(msg.sender, amount)) {
            revert InsufficientBalance();
        }

        emit WithdrawalProcessed(amount);
    }

    /**
     * @notice Get current balance (including yield)
     * @return Total balance in the protocol
     */
    function balance() external view returns (uint256) {
        // Calculate balance with accrued yield (100 bps = 1%, so divide by 10000)
        uint256 yieldAmount = (allocated * yieldBps) / 10000;
        return allocated + yieldAmount;
    }

    /**
     * @notice Accrue yield at specified basis points
     * @param bps Basis points of yield (100 = 1%)
     */
    function accrue(uint256 bps) external {
        yieldBps += bps;
        emit YieldAccrued(bps);
    }

    /**
     * @notice Reset accrued yield
     */
    function resetYield() external {
        yieldBps = 0;
    }

    /**
     * @notice Get accrued yield amount
     * @return Total accrued yield in basis points
     */
    function getAccruedYieldBps() external view returns (uint256) {
        return yieldBps;
    }

    /**
     * @notice Simulate yield calculation
     * @return The calculated yield amount
     */
    function calculateYield() external view returns (uint256) {
        return (allocated * yieldBps) / 10000;
    }

    /**
     * @notice Get total protocol value
     * @return Total value including principal and yield
     */
    function totalValue() external view returns (uint256) {
        uint256 yieldAmount = (allocated * yieldBps) / 10000;
        return allocated + yieldAmount;
    }

    /**
     * @notice Force update allocated amount (for testing)
     * @param _allocated New allocated amount
     */
    function setAllocated(uint256 _allocated) external {
        allocated = _allocated;
    }

    /**
     * @notice Receive function to accept ETH transfers
     */
    receive() external payable {}
}
