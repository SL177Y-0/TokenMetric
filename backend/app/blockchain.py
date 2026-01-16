"""
Blockchain integration for TokenMetric backend.
Handles Web3 interactions, contract calls, and transaction management.
"""

import os
from typing import Optional, Dict, Any, List
from decimal import Decimal
import logging
from dataclasses import dataclass

import requests
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError, TimeExhausted

logger = logging.getLogger(__name__)

# =============================================================================
# Contract ABI (minimal for TMVault interaction)
# =============================================================================

TMVAULT_ABI = [
    # Read functions
    {
        "constant": True,
        "inputs": [],
        "name": "asset",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "manager",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "", "type": "address"}],
        "name": "balances",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalDeposits",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalAllocated",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalYield",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalAssets",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "getProtocols",
        "outputs": [{"name": "", "type": "address[]"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "", "type": "address"}],
        "name": "protocolBalance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "getQueueSize",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "index", "type": "uint256"}],
        "name": "getWithdrawalRequest",
        "outputs": [
            {"name": "owner", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "timestamp", "type": "uint256"},
            {"name": "processed", "type": "bool"}
        ],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getUserWithdrawals",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "index", "type": "uint256"}],
        "name": "isWithdrawalReady",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    # Write functions
    {
        "constant": False,
        "inputs": [
            {"name": "assets", "type": "uint256"},
            {"name": "receiver", "type": "address"}
        ],
        "name": "deposit",
        "outputs": [{"name": "shares", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "instantWithdraw",
        "outputs": [],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "requestWithdrawal",
        "outputs": [{"name": "index", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [{"name": "index", "type": "uint256"}],
        "name": "processWithdrawal",
        "outputs": [],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [{"name": "index", "type": "uint256"}],
        "name": "cancelWithdrawal",
        "outputs": [],
        "type": "function"
    },
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "caller", "type": "address"},
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": False, "name": "assets", "type": "uint256"}
        ],
        "name": "Deposited",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": False, "name": "assets", "type": "uint256"},
            {"indexed": False, "name": "shares", "type": "uint256"}
        ],
        "name": "Withdrawn",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "index", "type": "uint256"}
        ],
        "name": "WithdrawalQueued",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "index", "type": "uint256"}
        ],
        "name": "WithdrawalProcessed",
        "type": "event"
    },
]

USDC_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
]

# =============================================================================
# Exceptions
# =============================================================================

class BlockchainError(Exception):
    """Base blockchain error."""
    pass


class TransactionFailedError(BlockchainError):
    """Transaction failed."""
    pass


class ContractCallError(BlockchainError):
    """Contract call failed."""
    pass


class InsufficientFundsError(BlockchainError):
    """Insufficient funds for operation."""
    pass


# =============================================================================
# Blockchain Client
# =============================================================================

@dataclass
class TxReceipt:
    """Transaction receipt data."""
    tx_hash: str
    status: bool
    block_number: int
    gas_used: int
    contract_address: Optional[str] = None
    logs: List[Dict] = None

    def __post_init__(self):
        if self.logs is None:
            self.logs = []


class BlockchainClient:
    """
    Client for interacting with blockchain contracts.

    Handles:
    - RPC connections
    - Contract interactions
    - Transaction submission
    - Event monitoring
    """

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        private_key: Optional[str] = None,
        chain_id: Optional[int] = None,
    ):
        """
        Initialize blockchain client.

        Args:
            rpc_url: RPC endpoint URL
            private_key: Private key for signing transactions
            chain_id: Chain ID for transaction signing
        """
        self.rpc_url = rpc_url or os.getenv("RPC_URL", "http://localhost:8545")
        self.private_key = private_key or os.getenv("PRIVATE_KEY")
        self.chain_id = chain_id or int(os.getenv("CHAIN_ID", "1"))

        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self._contracts: Dict[str, Contract] = {}

        if not self.w3.is_connected():
            logger.warning(f"Could not connect to RPC at {self.rpc_url}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to blockchain."""
        return self.w3.is_connected()

    @property
    def latest_block(self) -> int:
        """Get latest block number."""
        return self.w3.eth.block_number

    def get_contract(self, address: str, abi: List[Dict]) -> Contract:
        """Get or create contract instance."""
        if address not in self._contracts:
            checksum_address = Web3.to_checksum_address(address)
            self._contracts[address] = self.w3.eth.contract(
                address=checksum_address,
                abi=abi
            )
        return self._contracts[address]

    def get_vault_contract(self, vault_address: str) -> Contract:
        """Get TMVault contract instance."""
        return self.get_contract(vault_address, TMVAULT_ABI)

    def get_token_contract(self, token_address: str) -> Contract:
        """Get ERC20 token contract instance."""
        return self.get_contract(token_address, USDC_ABI)

    # =======================================================================
    # Read Functions
    # =======================================================================

    def get_balance(
        self,
        vault_address: str,
        user_address: str,
    ) -> int:
        """Get user's vault balance."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.balances(Web3.to_checksum_address(user_address)).call()

    def get_total_deposits(self, vault_address: str) -> int:
        """Get vault's total deposits."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.totalDeposits().call()

    def get_total_allocated(self, vault_address: str) -> int:
        """Get vault's total allocated to protocols."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.totalAllocated().call()

    def get_total_yield(self, vault_address: str) -> int:
        """Get vault's total yield collected."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.totalYield().call()

    def get_total_assets(self, vault_address: str) -> int:
        """Get vault's total assets."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.totalAssets().call()

    def get_protocols(self, vault_address: str) -> List[str]:
        """Get list of protocol addresses."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.getProtocols().call()

    def get_protocol_balance(self, vault_address: str, protocol_address: str) -> int:
        """Get amount allocated to a protocol."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.protocolBalance(Web3.to_checksum_address(protocol_address)).call()

    def get_queue_size(self, vault_address: str) -> int:
        """Get current withdrawal queue size."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.getQueueSize().call()

    def get_withdrawal_request(
        self,
        vault_address: str,
        index: int,
    ) -> Dict[str, Any]:
        """Get withdrawal request details."""
        vault = self.get_vault_contract(vault_address)
        owner, amount, timestamp, processed = vault.functions.getWithdrawalRequest(index).call()
        return {
            "owner": owner,
            "amount": amount,
            "timestamp": timestamp,
            "processed": processed,
        }

    def get_user_withdrawals(self, vault_address: str, user_address: str) -> List[int]:
        """Get user's withdrawal request indices."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.getUserWithdrawals(Web3.to_checksum_address(user_address)).call()

    def is_withdrawal_ready(self, vault_address: str, index: int) -> bool:
        """Check if withdrawal is ready to process."""
        vault = self.get_vault_contract(vault_address)
        return vault.functions.isWithdrawalReady(index).call()

    def get_token_balance(self, token_address: str, user_address: str) -> int:
        """Get ERC20 token balance."""
        token = self.get_token_contract(token_address)
        return token.functions.balanceOf(Web3.to_checksum_address(user_address)).call()

    def get_token_allowance(
        self,
        token_address: str,
        owner_address: str,
        spender_address: str,
    ) -> int:
        """Get ERC20 token allowance."""
        token = self.get_token_contract(token_address)
        return token.functions.allowance(
            Web3.to_checksum_address(owner_address),
            Web3.to_checksum_address(spender_address),
        ).call()

    # =======================================================================
    # Write Functions (require private key)
    # =======================================================================

    def _build_transaction(
        self,
        from_address: str,
        to_address: Optional[str] = None,
        value: int = 0,
        data: bytes = b"",
        gas_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build transaction dictionary."""
        tx = {
            "from": Web3.to_checksum_address(from_address),
            "value": value,
            "data": data,
            "chainId": self.chain_id,
            "nonce": self.w3.eth.get_transaction_count(Web3.to_checksum_address(from_address)),
        }

        if to_address:
            tx["to"] = Web3.to_checksum_address(to_address)

        if gas_limit:
            tx["gas"] = gas_limit
        else:
            tx["gas"] = self.w3.eth.estimate_gas(tx)

        return tx

    def _sign_and_send_transaction(self, tx: Dict[str, Any]) -> TxReceipt:
        """Sign and send transaction."""
        if not self.private_key:
            raise BlockchainError("Private key not configured")

        # Add gas price if not EIP-1559
        if "maxFeePerGas" not in tx and "gasPrice" not in tx:
            tx["gasPrice"] = self.w3.eth.gas_price

        signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)

        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        except TimeExhausted:
            raise TransactionFailedError("Transaction timed out")

        return TxReceipt(
            tx_hash=receipt["transactionHash"].hex(),
            status=receipt["status"] == 1,
            block_number=receipt["blockNumber"],
            gas_used=receipt["gasUsed"],
            contract_address=receipt.get("contractAddress"),
            logs=[dict(log) for log in receipt.get("logs", [])],
        )

    def approve_token(
        self,
        token_address: str,
        spender_address: str,
        amount: int,
        owner_address: str,
    ) -> TxReceipt:
        """Approve ERC20 token spending."""
        token = self.get_token_contract(token_address)

        tx_data = token.functions.approve(
            Web3.to_checksum_address(spender_address),
            amount,
        ).build_transaction({"from": Web3.to_checksum_address(owner_address)})

        tx_data["chainId"] = self.chain_id
        tx_data["nonce"] = self.w3.eth.get_transaction_count(Web3.to_checksum_address(owner_address))

        return self._sign_and_send_transaction(tx_data)

    def deposit(
        self,
        vault_address: str,
        amount: int,
        user_address: str,
    ) -> TxReceipt:
        """Execute deposit transaction."""
        vault = self.get_vault_contract(vault_address)

        tx_data = vault.functions.deposit(
            amount,
            Web3.to_checksum_address(user_address),
        ).build_transaction({"from": Web3.to_checksum_address(user_address)})

        tx_data["chainId"] = self.chain_id
        tx_data["nonce"] = self.w3.eth.get_transaction_count(Web2.to_checksum_address(user_address))

        return self._sign_and_send_transaction(tx_data)

    def instant_withdraw(
        self,
        vault_address: str,
        amount: int,
        user_address: str,
    ) -> TxReceipt:
        """Execute instant withdrawal."""
        vault = self.get_vault_contract(vault_address)

        tx_data = vault.functions.instantWithdraw(amount).build_transaction(
            {"from": Web3.to_checksum_address(user_address)}
        )

        tx_data["chainId"] = self.chain_id
        tx_data["nonce"] = self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))

        return self._sign_and_send_transaction(tx_data)

    def request_withdrawal(
        self,
        vault_address: str,
        amount: int,
        user_address: str,
    ) -> TxReceipt:
        """Request withdrawal (queue)."""
        vault = self.get_vault_contract(vault_address)

        tx_data = vault.functions.requestWithdrawal(amount).build_transaction(
            {"from": Web3.to_checksum_address(user_address)}
        )

        tx_data["chainId"] = self.chain_id
        tx_data["nonce"] = self.w3.eth.get_transaction_count(Web3.to_checksum_address(user_address))

        return self._sign_and_send_transaction(tx_data)

    def process_withdrawal(
        self,
        vault_address: str,
        index: int,
        sender_address: str,
    ) -> TxReceipt:
        """Process queued withdrawal."""
        vault = self.get_vault_contract(vault_address)

        tx_data = vault.functions.processWithdrawal(index).build_transaction(
            {"from": Web3.to_checksum_address(sender_address)}
        )

        tx_data["chainId"] = self.chain_id
        tx_data["nonce"] = self.w3.eth.get_transaction_count(Web3.to_checksum_address(sender_address))

        return self._sign_and_send_transaction(tx_data)

    # =======================================================================
    # Utility Functions
    # =======================================================================

    @staticmethod
    def to_checksum(address: str) -> str:
        """Convert to checksum address."""
        return Web3.to_checksum_address(address)

    @staticmethod
    def to_wei(amount: Decimal, decimals: int = 6) -> int:
        """Convert Decimal to wei (smallest unit)."""
        return int(amount * (10 ** decimals))

    @staticmethod
    def from_wei(amount: int, decimals: int = 6) -> Decimal:
        """Convert from wei to Decimal."""
        return Decimal(amount) / (10 ** decimals)

    @staticmethod
    def encode_abi(data: Any, typ: str) -> str:
        """Encode data to ABI format."""
        return Web3.codec.encode_abi(typ, data)

    @staticmethod
    def decode_abi(data: str, typ: str) -> Any:
        """Decode data from ABI format."""
        return Web3.codec.decode_abi(typ, data)


# =============================================================================
# RPC Client (for simple JSON-RPC calls without Web3)
# =============================================================================

class RPCClient:
    """
    Simple JSON-RPC client for blockchain queries.
    Used when Web3 is not available or for simple queries.
    """

    def __init__(self, rpc_url: Optional[str] = None):
        self.rpc_url = rpc_url or os.getenv("RPC_URL", "http://localhost:8545")

    def call(self, method: str, params: List = None) -> Dict:
        """Make JSON-RPC call."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": 1,
        }

        response = requests.post(
            self.rpc_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        response.raise_for_status()
        result = response.json()

        if "error" in result:
            raise BlockchainError(result["error"]["message"])

        return result.get("result")

    def get_block_number(self) -> int:
        """Get current block number."""
        result = self.call("eth_blockNumber")
        return int(result, 16)

    def get_balance(self, address: str) -> int:
        """Get ETH balance."""
        result = self.call("eth_getBalance", [address, "latest"])
        return int(result, 16)

    def call_contract(
        self,
        contract_address: str,
        data: str,
        block: str = "latest",
    ) -> str:
        """Make eth_call to contract."""
        return self.call("eth_call", [{
            "to": contract_address,
            "data": data,
        }, block])


# =============================================================================
# Module-level functions for convenience
# =============================================================================

# Global client instance
_client: Optional[BlockchainClient] = None


def get_client() -> BlockchainClient:
    """Get global blockchain client instance."""
    global _client
    if _client is None:
        _client = BlockchainClient()
    return _client


def wei_to_decimal(amount: int, decimals: int = 6) -> Decimal:
    """Convert wei to Decimal."""
    return BlockchainClient.from_wei(amount, decimals)


def decimal_to_wei(amount: Decimal, decimals: int = 6) -> int:
    """Convert Decimal to wei."""
    return BlockchainClient.to_wei(amount, decimals)
