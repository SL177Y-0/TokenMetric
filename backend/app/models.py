"""
Database models for TokenMetric backend.
Implements SQLAlchemy models for vaults, protocols, users, and transactions.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, DateTime,
    ForeignKey, Index, Enum as SQLEnum, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class TransactionType(str, enum.Enum):
    """Transaction types."""
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    ALLOCATE = "allocate"
    DEALLOCATE = "deallocate"
    YIELD = "yield"


class TransactionStatus(str, enum.Enum):
    """Transaction statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WithdrawalRequestStatus(str, enum.Enum):
    """Withdrawal request statuses."""
    QUEUED = "queued"
    READY = "ready"
    PROCESSED = "processed"
    CANCELLED = "cancelled"


class Vault(Base):
    """
    Vault model representing a yield-bearing vault.

    Attributes:
        id: Primary key
        address: Blockchain address of the vault
        asset_address: Address of the underlying asset
        manager_address: Address of the vault manager
        name: Human-readable name
        description: Vault description
        total_deposits: Total amount deposited
        total_allocated: Total amount allocated to protocols
        total_yield: Total yield collected
        tvl: Total value locked
        is_active: Whether the vault is active
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    __tablename__ = "vaults"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String(42), unique=True, nullable=False, index=True)
    asset_address = Column(String(42), nullable=False)
    manager_address = Column(String(42), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Financial metrics (stored as decimal with 18 precision)
    total_deposits = Column(Numeric(36, 18), default=0)
    total_allocated = Column(Numeric(36, 18), default=0)
    total_yield = Column(Numeric(36, 18), default=0)
    tvl = Column(Numeric(36, 18), default=0)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    protocols = relationship("Protocol", back_populates="vault", cascade="all, delete-orphan")
    users = relationship("VaultUser", back_populates="vault", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="vault", cascade="all, delete-orphan")
    withdrawals = relationship("WithdrawalRequest", back_populates="vault", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_vault_address', 'address'),
        Index('idx_vault_active', 'is_active'),
    )


class Protocol(Base):
    """
    Protocol model representing a yield protocol.

    Attributes:
        id: Primary key
        vault_id: Foreign key to vault
        address: Blockchain address of the protocol
        name: Protocol name
        description: Protocol description
        allocated_amount: Amount allocated to this protocol
        apy: Annual percentage yield
        risk_level: Risk level (1-5)
        is_active: Whether the protocol is active
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    __tablename__ = "protocols"

    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey("vaults.id"), nullable=False)
    address = Column(String(42), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    allocated_amount = Column(Numeric(36, 18), default=0)
    apy = Column(Numeric(10, 2), default=0)
    risk_level = Column(Integer, default=1)  # 1-5 scale

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    vault = relationship("Vault", back_populates="protocols")

    __table_args__ = (
        Index('idx_protocol_vault', 'vault_id'),
        Index('idx_protocol_address', 'address'),
    )


class User(Base):
    """
    User model representing application users.

    Attributes:
        id: Primary key
        wallet_address: Blockchain wallet address
        email: User email (optional)
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String(42), unique=True, nullable=False, index=True)
    email = Column(String(255))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    vault_memberships = relationship("VaultUser", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    withdrawals = relationship("WithdrawalRequest", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_user_wallet', 'wallet_address'),
    )


class VaultUser(Base):
    """
    Junction table for vault-user relationships.
    Tracks user balances in each vault.

    Attributes:
        id: Primary key
        vault_id: Foreign key to vault
        user_id: Foreign key to user
        balance: User's balance in the vault
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    __tablename__ = "vault_users"

    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey("vaults.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    balance = Column(Numeric(36, 18), default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    vault = relationship("Vault", back_populates="users")
    user = relationship("User", back_populates="vault_memberships")

    __table_args__ = (
        Index('idx_vault_user_vault', 'vault_id'),
        Index('idx_vault_user_user', 'user_id'),
        Index('idx_vault_user_unique', 'vault_id', 'user_id', unique=True),
    )


class Transaction(Base):
    """
    Transaction model for tracking all on-chain transactions.

    Attributes:
        id: Primary key
        vault_id: Foreign key to vault
        user_id: Foreign key to user (optional for protocol ops)
        tx_type: Type of transaction
        status: Status of transaction
        amount: Transaction amount
        tx_hash: Blockchain transaction hash
        from_address: Source address
        to_address: Destination address
        block_number: Block number
        gas_used: Gas used for transaction
        error_message: Error message if failed
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey("vaults.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    tx_type = Column(SQLEnum(TransactionType), nullable=False)
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.PENDING)

    amount = Column(Numeric(36, 18))
    tx_hash = Column(String(66), unique=True, index=True)
    from_address = Column(String(42))
    to_address = Column(String(42))
    block_number = Column(Integer)
    gas_used = Column(Integer)
    gas_price = Column(Numeric(36, 0))
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    vault = relationship("Vault", back_populates="transactions")
    user = relationship("User", back_populates="transactions")

    __table_args__ = (
        Index('idx_tx_vault', 'vault_id'),
        Index('idx_tx_user', 'user_id'),
        Index('idx_tx_type', 'tx_type'),
        Index('idx_tx_status', 'status'),
        Index('idx_tx_hash', 'tx_hash'),
        Index('idx_tx_created', 'created_at'),
    )


class WithdrawalRequest(Base):
    """
    Withdrawal request model for queued withdrawals.

    Attributes:
        id: Primary key
        vault_id: Foreign key to vault
        user_id: Foreign key to user
        queue_index: Index in the vault's withdrawal queue
        amount: Amount to withdraw
        status: Status of the withdrawal
        tx_hash: Transaction hash when processed
        requested_at: Timestamp of request
        processed_at: Timestamp of processing
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey("vaults.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    queue_index = Column(Integer, nullable=False)
    amount = Column(Numeric(36, 18), nullable=False)
    status = Column(SQLEnum(WithdrawalRequestStatus), default=WithdrawalRequestStatus.QUEUED)
    tx_hash = Column(String(66))

    requested_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    vault = relationship("Vault", back_populates="withdrawals")
    user = relationship("User", back_populates="withdrawals")

    __table_args__ = (
        Index('idx_withdrawal_vault', 'vault_id'),
        Index('idx_withdrawal_user', 'user_id'),
        Index('idx_withdrawal_status', 'status'),
        Index('idx_withdrawal_queue', 'queue_index'),
    )


class ProtocolSnapshot(Base):
    """
    Protocol snapshot model for tracking historical protocol data.

    Attributes:
        id: Primary key
        protocol_id: Foreign key to protocol
        tvl: Total value locked in protocol
        apy: Annual percentage yield
        timestamp: Snapshot timestamp
        created_at: Timestamp of creation
    """
    __tablename__ = "protocol_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    protocol_id = Column(Integer, ForeignKey("protocols.id"), nullable=False)

    tvl = Column(Numeric(36, 18))
    apy = Column(Numeric(10, 2))

    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_snapshot_protocol', 'protocol_id'),
        Index('idx_snapshot_timestamp', 'timestamp'),
    )
