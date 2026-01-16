"""
Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, validator, field_serializer


# =============================================================================
# Vault Schemas
# =============================================================================

class VaultBase(BaseModel):
    """Base vault schema."""
    address: str = Field(..., description="Blockchain address of the vault")
    asset_address: str = Field(..., description="Address of the underlying asset")
    manager_address: str = Field(..., description="Address of the vault manager")
    name: str = Field(..., description="Human-readable name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Vault description")


class VaultCreate(VaultBase):
    """Schema for creating a vault."""
    pass


class VaultUpdate(BaseModel):
    """Schema for updating a vault."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class VaultResponse(VaultBase):
    """Schema for vault response."""
    id: int
    total_deposits: Decimal
    total_allocated: Decimal
    total_yield: Decimal
    tvl: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VaultDetail(VaultResponse):
    """Detailed vault response with related data."""
    protocols: List['ProtocolResponse'] = []
    user_count: int = 0


# =============================================================================
# Protocol Schemas
# =============================================================================

class ProtocolBase(BaseModel):
    """Base protocol schema."""
    address: str = Field(..., description="Blockchain address of the protocol")
    name: str = Field(..., description="Protocol name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Protocol description")
    apy: Decimal = Field(default=0, ge=0, le=10000, description="APY in percentage")
    risk_level: int = Field(default=1, ge=1, le=5, description="Risk level (1-5)")

    @field_serializer('apy')
    def serialize_apy(self, apy: Decimal) -> str:
        """Serialize APY without trailing zeros."""
        return format(apy, 'f').rstrip('0').rstrip('.') if '.' in format(apy, 'f') else str(apy)


class ProtocolCreate(ProtocolBase):
    """Schema for creating a protocol."""
    vault_id: int


class ProtocolUpdate(BaseModel):
    """Schema for updating a protocol."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    apy: Optional[Decimal] = Field(None, ge=0, le=10000)
    risk_level: Optional[int] = Field(None, ge=1, le=5)
    is_active: Optional[bool] = None


class ProtocolResponse(ProtocolBase):
    """Schema for protocol response."""
    id: int
    vault_id: int
    allocated_amount: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# User Schemas
# =============================================================================

class UserBase(BaseModel):
    """Base user schema."""
    wallet_address: str = Field(..., description="Blockchain wallet address")


class UserCreate(UserBase):
    """Schema for creating a user."""
    email: Optional[str] = Field(None, description="User email")


class UserResponse(UserBase):
    """Schema for user response."""
    id: int
    email: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Vault User (Balance) Schemas
# =============================================================================

class VaultUserResponse(BaseModel):
    """Schema for user's vault balance."""
    vault_id: int
    vault_name: str
    vault_address: str
    balance: Decimal
    updated_at: datetime

    class Config:
        from_attributes = True


class UserVaultBalanceResponse(BaseModel):
    """Schema for user balance response."""
    vault_id: int
    user_address: str
    balance: str  # Balance as string for JSON serialization
    updated_at: Optional[datetime] = None

    @classmethod
    def from_decimal(cls, vault_id: int, user_address: str, balance: Decimal, updated_at: Optional[datetime] = None):
        """Create response from Decimal balance."""
        # Normalize decimal to remove trailing zeros
        normalized_balance = format(balance, 'f').rstrip('0').rstrip('.')
        return cls(
            vault_id=vault_id,
            user_address=user_address,
            balance=normalized_balance,
            updated_at=updated_at
        )


# =============================================================================
# Transaction Schemas
# =============================================================================

class TransactionBase(BaseModel):
    """Base transaction schema."""
    vault_id: int
    tx_type: str = Field(..., description="Transaction type")
    amount: Optional[Decimal] = Field(None, ge=0)


class TransactionCreate(TransactionBase):
    """Schema for creating a transaction."""
    user_id: Optional[int] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None


class TransactionResponse(TransactionBase):
    """Schema for transaction response."""
    id: int
    user_id: Optional[int]
    status: str
    tx_hash: Optional[str]
    from_address: Optional[str]
    to_address: Optional[str]
    block_number: Optional[int]
    gas_used: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Withdrawal Request Schemas
# =============================================================================

class WithdrawalRequestCreate(BaseModel):
    """Schema for creating a withdrawal request."""
    vault_id: int
    amount: Decimal = Field(..., gt=0, description="Amount to withdraw")


class WithdrawalRequestResponse(BaseModel):
    """Schema for withdrawal request response."""
    id: int
    vault_id: int
    user_id: int
    queue_index: int
    amount: Decimal
    status: str
    tx_hash: Optional[str]
    requested_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class WithdrawalRequestList(BaseModel):
    """Schema for list of user's withdrawal requests."""
    vault_id: int
    requests: List[WithdrawalRequestResponse]


# =============================================================================
# Deposit/Withdrawal Schemas
# =============================================================================

class DepositRequest(BaseModel):
    """Schema for deposit request."""
    vault_address: str = Field(..., description="Vault address")
    amount: Decimal = Field(..., gt=0, description="Amount to deposit")
    user_address: str = Field(..., description="User wallet address")


class DepositResponse(BaseModel):
    """Schema for deposit response."""
    tx_hash: str
    vault_id: int
    user_id: int
    amount: Decimal
    new_balance: Decimal
    status: str


class WithdrawRequest(BaseModel):
    """Schema for withdrawal request."""
    vault_address: str = Field(..., description="Vault address")
    amount: Decimal = Field(..., gt=0, description="Amount to withdraw")
    user_address: str = Field(..., description="User wallet address")
    instant: bool = Field(False, description="Whether to do instant withdraw")


class WithdrawResponse(BaseModel):
    """Schema for withdrawal response."""
    tx_hash: Optional[str] = None
    queue_index: Optional[int] = None
    vault_id: int
    user_id: int
    amount: Decimal
    new_balance: Decimal
    status: str


# =============================================================================
# Mobile API Schemas
# =============================================================================

class MobileVaultSummary(BaseModel):
    """Vault summary for mobile app."""
    address: str
    name: str
    tvl: Decimal
    apy: Decimal
    user_balance: Optional[Decimal] = None


class MobileWalletInfo(BaseModel):
    """Wallet info for mobile app."""
    address: str
    usdc_balance: Decimal
    vault_balances: List[dict]


class MobileDepositFlow(BaseModel):
    """Mobile deposit flow state."""
    step: str  # "connect", "approve", "deposit", "complete"
    vault_address: str
    amount: Optional[Decimal] = None
    approval_required: bool = False
    tx_hash: Optional[str] = None


class MobileErrorResponse(BaseModel):
    """Error response for mobile app."""
    code: str
    message: str
    details: Optional[dict] = None


# =============================================================================
# Stats & Analytics Schemas
# =============================================================================

class VaultStats(BaseModel):
    """Vault statistics."""
    vault_address: str
    total_deposits: Decimal
    total_withdrawals: Decimal
    tvl: Decimal
    total_yield: Decimal
    user_count: int
    protocol_count: int
    avg_apr: Decimal


class ProtocolStats(BaseModel):
    """Protocol statistics."""
    protocol_address: str
    protocol_name: str
    allocated: Decimal
    apy: Decimal
    yield_generated: Decimal
    utilization_rate: Decimal


class GlobalStats(BaseModel):
    """Global platform statistics."""
    total_vaults: int
    total_tvl: Decimal
    total_users: int
    total_protocols: int
    total_yield_24h: Decimal


# =============================================================================
# Health & Status Schemas
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    database: str
    blockchain: str


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str
    message: str
    details: Optional[dict] = None


# =============================================================================
# Pagination Schemas
# =============================================================================

class PaginatedResponse(BaseModel):
    """Generic paginated response."""
    items: List[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)


# =============================================================================
# Blockchain Event Schemas
# =============================================================================

class BlockchainEvent(BaseModel):
    """Blockchain event schema."""
    vault_address: str
    event_type: str
    tx_hash: str
    block_number: int
    data: dict


class SyncStatus(BaseModel):
    """Blockchain sync status."""
    last_block_synced: int
    latest_block: int
    blocks_behind: int
    sync_percentage: float
    is_synced: bool


# =============================================================================
# Update forward references
# =============================================================================
VaultDetail.model_rebuild()
