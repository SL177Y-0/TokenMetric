// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

interface IProtocol {
    function deposit(uint256 amount) external;
    function withdraw(uint256 amount) external;
    function balance() external view returns (uint256);
    function accruedYield() external view returns (uint256);
}

/**
 * @title TMVault
 * @notice Yield-bearing vault with withdrawal queue and protocol routing
 * @dev Manages deposits across multiple protocols with a withdrawal queue system
 */
contract TMVault {
    /*//////////////////////////////////////////////////////////////
                                ERRORS
    //////////////////////////////////////////////////////////////*/
    error ZeroAssets();
    error TransferFailed();
    error NotManager();
    error NotProtocol();
    error InsufficientBalance();
    error InvalidProtocol();
    error QueueEmpty();
    error QueueFull();
    error NotInQueue();
    error WithdrawalTooLarge();
    error InsufficientVaultLiquidity();
    error ProtocolNotFound();

    /*//////////////////////////////////////////////////////////////
                                EVENTS
    //////////////////////////////////////////////////////////////*/
    event Deposited(address indexed caller, address indexed owner, uint256 assets);
    event Withdrawn(address indexed owner, uint256 assets, uint256 shares);
    event ProtocolSet(address indexed protocolA, address indexed protocolB);
    event Allocated(address indexed protocol, uint256 amount);
    event Deallocated(address indexed protocol, uint256 amount);
    event YieldCollected(address indexed protocol, uint256 amount);
    event WithdrawalQueued(address indexed owner, uint256 amount, uint256 index);
    event WithdrawalProcessed(address indexed owner, uint256 amount, uint256 index);
    event WithdrawalCancelled(address indexed owner, uint256 amount, uint256 index);

    /*//////////////////////////////////////////////////////////////
                            IMMUTABLES
    //////////////////////////////////////////////////////////////*/
    IERC20 public immutable asset;
    uint256 public immutable deploymentTime;

    /*//////////////////////////////////////////////////////////////
                            STATE
    //////////////////////////////////////////////////////////////*/
    address public manager;

    // Protocol management
    address public protocolA;
    address public protocolB;
    mapping(address => bool) public isProtocol;
    address[] public protocolList;

    // Protocol allocations
    mapping(address => uint256) public protocolBalance;
    uint256 public totalAllocated;

    // User balances
    mapping(address => uint256) public balances;
    uint256 public totalDeposits;
    uint256 public totalYield;

    // Withdrawal queue
    struct WithdrawalRequest {
        address owner;
        uint256 amount;
        uint256 timestamp;
        bool processed;
    }

    WithdrawalRequest[] public withdrawalQueue;
    mapping(address => uint256[]) public userWithdrawalIndices;

    // Vault parameters
    uint256 public constant MAX_QUEUE_SIZE = 100;
    uint256 public constant WITHDRAWAL_DELAY = 1 days;
    uint256 public constant MAX_SINGLE_WITHDRAWAL = 100_000e6; // 100k USDC

    /*//////////////////////////////////////////////////////////////
                          CONSTRUCTOR
    //////////////////////////////////////////////////////////////*/
    constructor(address _asset, address _manager) {
        if (_asset == address(0)) revert ZeroAssets();
        asset = IERC20(_asset);
        manager = _manager;
        deploymentTime = block.timestamp;
    }

    /*//////////////////////////////////////////////////////////////
                        MODIFIERS
    //////////////////////////////////////////////////////////////*/
    modifier onlyManager() {
        if (msg.sender != manager) revert NotManager();
        _;
    }

    modifier onlyProtocol() {
        if (!isProtocol[msg.sender]) revert NotProtocol();
        _;
    }

    /*//////////////////////////////////////////////////////////////
                    ADMIN FUNCTIONS
    //////////////////////////////////////////////////////////////*/
    /**
     * @notice Set supported protocols
     * @param _a Address of protocol A
     * @param _b Address of protocol B
     */
    function setProtocols(address _a, address _b) external onlyManager {
        protocolA = _a;
        protocolB = _b;

        // Update protocol tracking
        if (_a != address(0) && !isProtocol[_a]) {
            isProtocol[_a] = true;
            protocolList.push(_a);
        }
        if (_b != address(0) && !isProtocol[_b]) {
            isProtocol[_b] = true;
            protocolList.push(_b);
        }

        emit ProtocolSet(_a, _b);
    }

    /**
     * @notice Add a new protocol
     * @param protocol Address of the protocol
     */
    function addProtocol(address protocol) external onlyManager {
        if (protocol == address(0)) revert InvalidProtocol();
        if (isProtocol[protocol]) revert InvalidProtocol();

        isProtocol[protocol] = true;
        protocolList.push(protocol);
    }

    /**
     * @notice Remove a protocol
     * @param protocol Address of the protocol to remove
     */
    function removeProtocol(address protocol) external onlyManager {
        if (!isProtocol[protocol]) revert ProtocolNotFound();

        isProtocol[protocol] = false;

        // Deallocate from protocol first
        uint256 allocated = protocolBalance[protocol];
        if (allocated > 0) {
            _deallocateFromProtocol(protocol, allocated);
        }
    }

    /**
     * @notice Transfer manager role
     * @param newManager Address of the new manager
     */
    function setManager(address newManager) external onlyManager {
        if (newManager == address(0)) revert ZeroAssets();
        manager = newManager;
    }

    /*//////////////////////////////////////////////////////////////
                    DEPOSIT FUNCTIONS
    //////////////////////////////////////////////////////////////*/
    /**
     * @notice Deposit assets into the vault
     * @param assets Amount of assets to deposit
     * @param receiver Address to receive the vault shares
     * @return shares Amount of shares minted (1:1 with assets in this implementation)
     */
    function deposit(uint256 assets, address receiver) external returns (uint256 shares) {
        if (assets == 0) revert ZeroAssets();

        // Transfer assets from sender
        if (!asset.transferFrom(msg.sender, address(this), assets)) {
            revert TransferFailed();
        }

        // Update balances
        balances[receiver] += assets;
        totalDeposits += assets;

        emit Deposited(msg.sender, receiver, assets);
        return assets;
    }

    /*//////////////////////////////////////////////////////////////
                    WITHDRAWAL FUNCTIONS
    //////////////////////////////////////////////////////////////*/
    /**
     * @notice Request a withdrawal (queues the request)
     * @param amount Amount to withdraw
     * @return index Index of the withdrawal request in the queue
     */
    function requestWithdrawal(uint256 amount) external returns (uint256 index) {
        if (amount == 0) revert ZeroAssets();
        if (balances[msg.sender] < amount) revert InsufficientBalance();
        if (amount > MAX_SINGLE_WITHDRAWAL) revert WithdrawalTooLarge();
        if (withdrawalQueue.length >= MAX_QUEUE_SIZE) revert QueueFull();

        // Deduct from balance immediately
        balances[msg.sender] -= amount;
        totalDeposits -= amount;

        // Add to queue
        index = withdrawalQueue.length;
        withdrawalQueue.push(WithdrawalRequest({
            owner: msg.sender,
            amount: amount,
            timestamp: block.timestamp,
            processed: false
        }));

        userWithdrawalIndices[msg.sender].push(index);

        emit WithdrawalQueued(msg.sender, amount, index);
        return index;
    }

    /**
     * @notice Process a withdrawal from the queue
     * @param index Index of the withdrawal request
     */
    function processWithdrawal(uint256 index) external {
        if (index >= withdrawalQueue.length) revert QueueEmpty();

        WithdrawalRequest storage request = withdrawalQueue[index];
        if (request.processed) revert NotInQueue();
        if (block.timestamp < request.timestamp + WITHDRAWAL_DELAY) {
            revert InsufficientVaultLiquidity();
        }

        request.processed = true;

        // Try to get funds from vault liquidity first
        uint256 vaultLiquidity = asset.balanceOf(address(this));
        uint256 toWithdraw = request.amount;

        if (vaultLiquidity < toWithdraw) {
            // Need to deallocate from protocols
            uint256 needed = toWithdraw - vaultLiquidity;
            _deallocateFromProtocols(needed);
        }

        // Transfer to owner
        if (!asset.transfer(request.owner, toWithdraw)) {
            revert TransferFailed();
        }

        emit WithdrawalProcessed(request.owner, toWithdraw, index);
    }

    /**
     * @notice Cancel a pending withdrawal
     * @param index Index of the withdrawal request
     */
    function cancelWithdrawal(uint256 index) external {
        if (index >= withdrawalQueue.length) revert QueueEmpty();

        WithdrawalRequest storage request = withdrawalQueue[index];
        if (request.owner != msg.sender) revert NotManager();
        if (request.processed) revert NotInQueue();

        request.processed = true;

        // Return funds to balance
        balances[msg.sender] += request.amount;
        totalDeposits += request.amount;

        emit WithdrawalCancelled(msg.sender, request.amount, index);
    }

    /**
     * @notice Instant withdraw (if vault has enough liquidity)
     * @param amount Amount to withdraw
     */
    function instantWithdraw(uint256 amount) external {
        if (amount == 0) revert ZeroAssets();
        if (balances[msg.sender] < amount) revert InsufficientBalance();
        if (amount > MAX_SINGLE_WITHDRAWAL) revert WithdrawalTooLarge();

        uint256 vaultLiquidity = asset.balanceOf(address(this));
        if (vaultLiquidity < amount) {
            revert InsufficientVaultLiquidity();
        }

        // Update balances
        balances[msg.sender] -= amount;
        totalDeposits -= amount;

        // Transfer
        if (!asset.transfer(msg.sender, amount)) {
            revert TransferFailed();
        }

        emit Withdrawn(msg.sender, amount, amount);
    }

    /*//////////////////////////////////////////////////////////////
                    PROTOCOL ALLOCATION
    //////////////////////////////////////////////////////////////*/
    /**
     * @notice Allocate funds to a protocol
     * @param protocol Address of the protocol
     * @param amount Amount to allocate
     */
    function allocateToProtocol(address protocol, uint256 amount) external onlyManager {
        if (!isProtocol[protocol]) revert InvalidProtocol();

        uint256 vaultBalance = asset.balanceOf(address(this));
        if (vaultBalance < amount) revert InsufficientVaultLiquidity();

        // Transfer to protocol
        if (!asset.transfer(protocol, amount)) {
            revert TransferFailed();
        }

        // Update state
        protocolBalance[protocol] += amount;
        totalAllocated += amount;

        emit Allocated(protocol, amount);
    }

    /**
     * @notice Deallocate funds from a protocol
     * @param protocol Address of the protocol
     * @param amount Amount to deallocate
     */
    function deallocateFromProtocol(address protocol, uint256 amount) external onlyManager {
        if (!isProtocol[protocol]) revert InvalidProtocol();
        if (protocolBalance[protocol] < amount) revert InsufficientBalance();

        _deallocateFromProtocol(protocol, amount);
    }

    /**
     * @notice Internal function to deallocate from protocol
     * @param protocol Address of the protocol
     * @param amount Amount to deallocate
     */
    function _deallocateFromProtocol(address protocol, uint256 amount) internal {
        IProtocol p = IProtocol(protocol);

        // Withdraw from protocol
        try p.withdraw(amount) {
            // Protocol will transfer back to vault
        } catch {
            // If protocol doesn't implement withdraw, assume it transfers back
        }

        protocolBalance[protocol] -= amount;
        totalAllocated -= amount;

        emit Deallocated(protocol, amount);
    }

    /**
     * @notice Deallocate from protocols to meet withdrawal needs
     * @param needed Amount needed
     */
    function _deallocateFromProtocols(uint256 needed) internal {
        uint256 remaining = needed;

        // Deallocate from protocolA first, then protocolB
        address[] memory protocols = protocolList;
        for (uint256 i = 0; i < protocols.length && remaining > 0; i++) {
            address protocol = protocols[i];
            uint256 allocated = protocolBalance[protocol];

            if (allocated > 0) {
                uint256 toWithdraw = allocated < remaining ? allocated : remaining;
                _deallocateFromProtocol(protocol, toWithdraw);
                remaining -= toWithdraw;
            }
        }
    }

    /**
     * @notice Collect yield from protocols
     * @param protocols Array of protocol addresses
     */
    function collectYield(address[] calldata protocols) external onlyManager {
        for (uint256 i = 0; i < protocols.length; i++) {
            address protocol = protocols[i];
            if (!isProtocol[protocol]) revert InvalidProtocol();

            IProtocol p = IProtocol(protocol);
            uint256 yieldBefore = totalYield;

            try p.balance() returns (uint256 balance) {
                uint256 allocated = protocolBalance[protocol];
                if (balance > allocated) {
                    uint256 yieldAmount = balance - allocated;
                    totalYield += yieldAmount;
                    emit YieldCollected(protocol, yieldAmount);
                }
            } catch {
                // Protocol might not support balance view
            }
        }
    }

    /*//////////////////////////////////////////////////////////////
                    VIEW FUNCTIONS
    //////////////////////////////////////////////////////////////*/
    /**
     * @notice Get total assets managed by vault
     * @return Total assets (vault balance + allocated to protocols + yield)
     */
    function totalAssets() external view returns (uint256) {
        return asset.balanceOf(address(this)) + totalAllocated + totalYield;
    }

    /**
     * @notice Get user's pending withdrawals
     * @param user Address of the user
     * @return indices Array of withdrawal request indices
     */
    function getUserWithdrawals(address user) external view returns (uint256[] memory indices) {
        return userWithdrawalIndices[user];
    }

    /**
     * @notice Get withdrawal request details
     * @param index Index of the withdrawal request
     * @return owner Owner of the request
     * @return amount Amount requested
     * @return timestamp Timestamp of request
     * @return processed Whether the request has been processed
     */
    function getWithdrawalRequest(uint256 index) external view returns (
        address owner,
        uint256 amount,
        uint256 timestamp,
        bool processed
    ) {
        if (index >= withdrawalQueue.length) revert QueueEmpty();
        WithdrawalRequest memory request = withdrawalQueue[index];
        return (request.owner, request.amount, request.timestamp, request.processed);
    }

    /**
     * @notice Get all protocols
     * @return Array of protocol addresses
     */
    function getProtocols() external view returns (address[] memory) {
        return protocolList;
    }

    /**
     * @notice Get current queue size
     * @return Number of pending withdrawal requests
     */
    function getQueueSize() external view returns (uint256) {
        uint256 count = 0;
        for (uint256 i = 0; i < withdrawalQueue.length; i++) {
            if (!withdrawalQueue[i].processed) {
                count++;
            }
        }
        return count;
    }

    /**
     * @notice Check if withdrawal is ready to process
     * @param index Index of the withdrawal request
     * @return ready True if ready to process
     */
    function isWithdrawalReady(uint256 index) external view returns (bool) {
        if (index >= withdrawalQueue.length) return false;
        WithdrawalRequest memory request = withdrawalQueue[index];
        return !request.processed && block.timestamp >= request.timestamp + WITHDRAWAL_DELAY;
    }

    /*//////////////////////////////////////////////////////////////
                    EMERGENCY FUNCTIONS
    //////////////////////////////////////////////////////////////*/
    /**
     * @notice Emergency withdraw all funds from protocols
     */
    function emergencyWithdrawAll() external onlyManager {
        address[] memory protocols = protocolList;
        for (uint256 i = 0; i < protocols.length; i++) {
            address protocol = protocols[i];
            uint256 allocated = protocolBalance[protocol];
            if (allocated > 0) {
                _deallocateFromProtocol(protocol, allocated);
            }
        }
    }
}
