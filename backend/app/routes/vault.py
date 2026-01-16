"""
Vault API routes for TokenMetric backend.
"""

from typing import List, Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import (
    Vault, Protocol, User, VaultUser, Transaction,
    TransactionType, TransactionStatus, WithdrawalRequest,
    WithdrawalRequestStatus
)
from ..schemas import (
    VaultCreate, VaultUpdate, VaultResponse, VaultDetail,
    DepositRequest, DepositResponse, WithdrawRequest, WithdrawResponse,
    WithdrawalRequestResponse, VaultStats, UserVaultBalanceResponse
)
from ..blockchain import BlockchainClient, get_client, wei_to_decimal, decimal_to_wei

router = APIRouter(prefix="/vaults", tags=["vaults"])


# =============================================================================
# Vault CRUD Endpoints
# =============================================================================

@router.post("", response_model=VaultResponse, status_code=status.HTTP_201_CREATED)
def create_vault(
    vault_data: VaultCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new vault.

    - **address**: Blockchain address of the vault
    - **asset_address**: Address of the underlying asset (e.g., USDC)
    - **manager_address**: Address of the vault manager
    - **name**: Human-readable name
    - **description**: Optional description
    """
    # Check if vault already exists
    existing = db.query(Vault).filter(Vault.address == vault_data.address).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault with this address already exists"
        )

    vault = Vault(**vault_data.model_dump())
    db.add(vault)
    db.commit()
    db.refresh(vault)

    return vault


@router.get("", response_model=List[VaultResponse])
def list_vaults(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """List all vaults with pagination."""
    query = db.query(Vault)

    if active_only:
        query = query.filter(Vault.is_active == True)

    vaults = query.offset(skip).limit(limit).all()
    return vaults


@router.get("/{vault_id}", response_model=VaultDetail)
def get_vault(
    vault_id: int,
    db: Session = Depends(get_db),
):
    """Get vault details by ID."""
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    # Get protocols
    protocols = db.query(Protocol).filter(Protocol.vault_id == vault_id).all()

    # Get user count
    user_count = db.query(VaultUser).filter(VaultUser.vault_id == vault_id).count()

    response = VaultDetail(
        **vault.__dict__,
        protocols=protocols,
        user_count=user_count,
    )

    return response


@router.get("/address/{address}", response_model=VaultDetail)
def get_vault_by_address(
    address: str,
    db: Session = Depends(get_db),
):
    """Get vault details by blockchain address."""
    vault = db.query(Vault).filter(Vault.address == address).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    protocols = db.query(Protocol).filter(Protocol.vault_id == vault.id).all()
    user_count = db.query(VaultUser).filter(VaultUser.vault_id == vault.id).count()

    return VaultDetail(
        **vault.__dict__,
        protocols=protocols,
        user_count=user_count,
    )


@router.patch("/{vault_id}", response_model=VaultResponse)
def update_vault(
    vault_id: int,
    vault_data: VaultUpdate,
    db: Session = Depends(get_db),
):
    """Update vault information."""
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    update_data = vault_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vault, field, value)

    db.commit()
    db.refresh(vault)

    return vault


@router.delete("/{vault_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vault(
    vault_id: int,
    db: Session = Depends(get_db),
):
    """Delete a vault (soft delete by setting is_active=False)."""
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    vault.is_active = False
    db.commit()


# =============================================================================
# User Balance Endpoints
# =============================================================================

@router.get("/{vault_id}/users/{user_address}", response_model=UserVaultBalanceResponse)
def get_user_balance(
    vault_id: int,
    user_address: str,
    db: Session = Depends(get_db),
    blockchain: BlockchainClient = Depends(get_client),
):
    """Get user's balance in a vault."""
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    # Get or create user
    user = db.query(User).filter(User.wallet_address == user_address).first()
    if not user:
        user = User(wallet_address=user_address)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Get or create vault user relationship
    vault_user = db.query(VaultUser).filter(
        VaultUser.vault_id == vault_id,
        VaultUser.user_id == user.id
    ).first()

    # Try to get balance from blockchain first
    try:
        balance_wei = blockchain.get_balance(vault.address, user_address)
        balance = wei_to_decimal(balance_wei)

        if vault_user:
            vault_user.balance = balance
            db.commit()
    except Exception:
        # Fallback to database
        balance = vault_user.balance if vault_user else Decimal(0)

    return UserVaultBalanceResponse.from_decimal(
        vault_id=vault_id,
        user_address=user_address,
        balance=balance,
        updated_at=vault_user.updated_at if vault_user else None
    )


@router.get("/{vault_id}/users", response_model=List[dict])
def list_vault_users(
    vault_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List all users in a vault with their balances."""
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    vault_users = db.query(VaultUser).filter(
        VaultUser.vault_id == vault_id
    ).offset(skip).limit(limit).all()

    result = []
    for vu in vault_users:
        result.append({
            "user_id": vu.user_id,
            "user_address": vu.user.wallet_address,
            "balance": vu.balance,
            "updated_at": vu.updated_at,
        })

    return result


# =============================================================================
# Deposit Endpoints
# =============================================================================

@router.post("/{vault_id}/deposit", response_model=DepositResponse)
def deposit(
    vault_id: int,
    deposit_data: DepositRequest,
    db: Session = Depends(get_db),
    blockchain: BlockchainClient = Depends(get_client),
):
    """
    Process a deposit to the vault.

    This endpoint prepares a deposit transaction. In production,
    the transaction would be signed by the user's wallet.
    """
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    # Get or create user
    user = db.query(User).filter(User.wallet_address == deposit_data.user_address).first()
    if not user:
        user = User(wallet_address=deposit_data.user_address)
        db.add(user)
        db.commit()
        db.refresh(user)

    amount_wei = decimal_to_wei(deposit_data.amount)

    # Create transaction record
    transaction = Transaction(
        vault_id=vault_id,
        user_id=user.id,
        tx_type=TransactionType.DEPOSIT,
        status=TransactionStatus.PENDING,
        amount=deposit_data.amount,
        from_address=deposit_data.user_address,
        to_address=vault.address,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # In production, you would:
    # 1. Return the transaction data for the user to sign
    # 2. Broadcast the signed transaction
    # 3. Update the transaction record with the receipt

    # For now, simulate a successful deposit
    vault_user = db.query(VaultUser).filter(
        VaultUser.vault_id == vault_id,
        VaultUser.user_id == user.id
    ).first()

    if not vault_user:
        vault_user = VaultUser(vault_id=vault_id, user_id=user.id, balance=deposit_data.amount)
        db.add(vault_user)
    else:
        vault_user.balance += deposit_data.amount

    vault.total_deposits += deposit_data.amount
    vault.tvl += deposit_data.amount

    transaction.status = TransactionStatus.COMPLETED
    transaction.tx_hash = f"0x{'0' * 64}{transaction.id}"  # Mock tx hash

    db.commit()
    db.refresh(transaction)

    return DepositResponse(
        tx_hash=transaction.tx_hash,
        vault_id=vault_id,
        user_id=user.id,
        amount=deposit_data.amount,
        new_balance=vault_user.balance,
        status=transaction.status.value,
    )


# =============================================================================
# Withdrawal Endpoints
# =============================================================================

@router.post("/{vault_id}/withdraw", response_model=WithdrawResponse)
def withdraw(
    vault_id: int,
    withdraw_data: WithdrawRequest,
    db: Session = Depends(get_db),
    blockchain: BlockchainClient = Depends(get_client),
):
    """
    Process a withdrawal from the vault.

    Supports both instant withdrawal (if liquidity available) and
    queued withdrawal (with delay).
    """
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    # Get user
    user = db.query(User).filter(User.wallet_address == withdraw_data.user_address).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get vault user balance
    vault_user = db.query(VaultUser).filter(
        VaultUser.vault_id == vault_id,
        VaultUser.user_id == user.id
    ).first()

    if not vault_user or vault_user.balance < withdraw_data.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance"
        )

    amount_wei = decimal_to_wei(withdraw_data.amount)

    if withdraw_data.instant:
        # Instant withdrawal
        try:
            # Check vault liquidity
            balance_wei = blockchain.get_balance(vault.address, vault.address)
            vault_balance_wei = blockchain.get_token_balance(vault.asset_address, vault.address)

            if vault_balance_wei < amount_wei:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient vault liquidity for instant withdrawal"
                )

            # Create transaction
            transaction = Transaction(
                vault_id=vault_id,
                user_id=user.id,
                tx_type=TransactionType.WITHDRAW,
                status=TransactionStatus.COMPLETED,
                amount=withdraw_data.amount,
                from_address=vault.address,
                to_address=withdraw_data.user_address,
            )
            db.add(transaction)

            # Update balances
            vault_user.balance -= withdraw_data.amount
            vault.total_deposits -= withdraw_data.amount
            vault.tvl -= withdraw_data.amount

            db.commit()

            return WithdrawResponse(
                tx_hash=f"0x{'0' * 63}1",
                vault_id=vault_id,
                user_id=user.id,
                amount=withdraw_data.amount,
                new_balance=vault_user.balance,
                status="completed",
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Instant withdrawal failed: {str(e)}"
            )
    else:
        # Queued withdrawal
        withdrawal = WithdrawalRequest(
            vault_id=vault_id,
            user_id=user.id,
            amount=withdraw_data.amount,
            status=WithdrawalRequestStatus.QUEUED,
            queue_index=0,  # Would be set by contract
        )
        db.add(withdrawal)

        vault_user.balance -= withdraw_data.amount
        vault.total_deposits -= withdraw_data.amount

        db.commit()
        db.refresh(withdrawal)

        return WithdrawResponse(
            queue_index=withdrawal.queue_index,
            vault_id=vault_id,
            user_id=user.id,
            amount=withdraw_data.amount,
            new_balance=vault_user.balance,
            status="queued",
        )


@router.get("/{vault_id}/withdrawals", response_model=List[WithdrawalRequestResponse])
def list_withdrawals(
    vault_id: int,
    user_address: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List withdrawal requests for a vault."""
    query = db.query(WithdrawalRequest).filter(WithdrawalRequest.vault_id == vault_id)

    if user_address:
        user = db.query(User).filter(User.wallet_address == user_address).first()
        if user:
            query = query.filter(WithdrawalRequest.user_id == user.id)

    if status_filter:
        try:
            status_enum = WithdrawalRequestStatus(status_filter)
            query = query.filter(WithdrawalRequest.status == status_enum)
        except ValueError:
            pass

    withdrawals = query.order_by(WithdrawalRequest.requested_at.desc()).all()
    return withdrawals


@router.post("/{vault_id}/withdrawals/{withdrawal_id}/process")
def process_withdrawal(
    vault_id: int,
    withdrawal_id: int,
    db: Session = Depends(get_db),
    blockchain: BlockchainClient = Depends(get_client),
):
    """
    Process a queued withdrawal (manager only).
    """
    withdrawal = db.query(WithdrawalRequest).filter(
        WithdrawalRequest.id == withdrawal_id,
        WithdrawalRequest.vault_id == vault_id
    ).first()

    if not withdrawal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Withdrawal request not found"
        )

    if withdrawal.status != WithdrawalRequestStatus.QUEUED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Withdrawal is not in queued state"
        )

    # In production, call the smart contract
    withdrawal.status = WithdrawalRequestStatus.PROCESSED
    withdrawal.processed_at = datetime.utcnow()
    withdrawal.tx_hash = f"0x{'0' * 63}2"

    db.commit()

    return {"status": "processed", "tx_hash": withdrawal.tx_hash}


# =============================================================================
# Statistics Endpoints
# =============================================================================

@router.get("/{vault_id}/stats", response_model=VaultStats)
def get_vault_stats(
    vault_id: int,
    db: Session = Depends(get_db),
):
    """Get vault statistics."""
    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    # Get user count
    user_count = db.query(VaultUser).filter(VaultUser.vault_id == vault_id).count()

    # Get protocol count
    protocol_count = db.query(Protocol).filter(
        Protocol.vault_id == vault_id,
        Protocol.is_active == True
    ).count()

    # Calculate average APR
    protocols = db.query(Protocol).filter(Protocol.vault_id == vault_id).all()
    total_apr = sum(p.apy for p in protocols if p.apy)
    avg_apr = total_apr / len(protocols) if protocols else Decimal(0)

    # Get total withdrawals from transactions
    total_withdrawals = db.query(Transaction).filter(
        Transaction.vault_id == vault_id,
        Transaction.tx_type == TransactionType.WITHDRAW,
        Transaction.status == TransactionStatus.COMPLETED
    ).with_entities(
        func.sum(Transaction.amount)
    ).scalar() or Decimal(0)

    return VaultStats(
        vault_address=vault.address,
        total_deposits=vault.total_deposits,
        total_withdrawals=total_withdrawals,
        tvl=vault.tvl,
        total_yield=vault.total_yield,
        user_count=user_count,
        protocol_count=protocol_count,
        avg_apr=avg_apr,
    )


@router.get("/{vault_id}/transactions", response_model=List[dict])
def list_transactions(
    vault_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tx_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List transactions for a vault."""
    query = db.query(Transaction).filter(Transaction.vault_id == vault_id)

    if tx_type:
        try:
            tx_enum = TransactionType(tx_type)
            query = query.filter(Transaction.tx_type == tx_enum)
        except ValueError:
            pass

    transactions = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()

    return [
        {
            "id": t.id,
            "tx_type": t.tx_type.value,
            "status": t.status.value,
            "amount": t.amount,
            "tx_hash": t.tx_hash,
            "from_address": t.from_address,
            "to_address": t.to_address,
            "created_at": t.created_at,
        }
        for t in transactions
    ]
