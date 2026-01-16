"""
Mobile API routes for TokenMetric backend.
Optimized for mobile app consumption with simplified responses.
"""

from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Vault, Protocol, User, VaultUser
from ..schemas import (
    MobileVaultSummary, MobileWalletInfo, MobileDepositFlow,
    MobileErrorResponse
)
from ..blockchain import get_client, wei_to_decimal

router = APIRouter(prefix="/mobile", tags=["mobile"])


# =============================================================================
# Mobile Discovery Endpoints
# =============================================================================

@router.get("/vaults", response_model=List[MobileVaultSummary])
def mobile_list_vaults(
    user_address: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    List vaults optimized for mobile display.

    Returns simplified vault information including TVL, APY,
    and optionally user's balance if user_address is provided.
    """
    query = db.query(Vault).filter(Vault.is_active == True)

    vaults = query.all()
    result = []

    for vault in vaults:
        # Get protocols to calculate average APY
        protocols = db.query(Protocol).filter(
            Protocol.vault_id == vault.id,
            Protocol.is_active == True
        ).all()

        total_apy = sum(p.apy for p in protocols)
        avg_apy = total_apy / len(protocols) if protocols else Decimal(0)

        user_balance = None
        if user_address:
            user = db.query(User).filter(User.wallet_address == user_address).first()
            if user:
                vault_user = db.query(VaultUser).filter(
                    VaultUser.vault_id == vault.id,
                    VaultUser.user_id == user.id
                ).first()
                if vault_user:
                    user_balance = vault_user.balance

        result.append(MobileVaultSummary(
            address=vault.address,
            name=vault.name,
            tvl=vault.tvl,
            apy=avg_apy,
            user_balance=user_balance,
        ))

    return result


@router.get("/vaults/{vault_address}/summary")
def mobile_vault_summary(
    vault_address: str,
    db: Session = Depends(get_db),
):
    """
    Get detailed vault summary for mobile display.
    """
    vault = db.query(Vault).filter(Vault.address == vault_address).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VAULT_NOT_FOUND", "message": "Vault not found"}
        )

    protocols = db.query(Protocol).filter(
        Protocol.vault_id == vault.id,
        Protocol.is_active == True
    ).all()

    total_apy = sum(p.apy for p in protocols)
    avg_apy = total_apy / len(protocols) if protocols else Decimal(0)

    return {
        "address": vault.address,
        "name": vault.name,
        "description": vault.description,
        "asset_address": vault.asset_address,
        "tvl": vault.tvl,
        "total_deposits": vault.total_deposits,
        "total_yield": vault.total_yield,
        "apy": avg_apy,
        "protocols": [
            {
                "address": p.address,
                "name": p.name,
                "apy": p.apy,
                "allocated": p.allocated_amount,
            }
            for p in protocols
        ],
    }


# =============================================================================
# Mobile Wallet Endpoints
# =============================================================================

@router.get("/wallet/{address}")
def mobile_wallet_info(
    address: str,
    db: Session = Depends(get_db),
    blockchain=Depends(get_client),
):
    """
    Get comprehensive wallet information for mobile app.

    Returns:
    - USDC balance
    - Balances across all vaults
    - Total portfolio value
    """
    # Get or create user
    user = db.query(User).filter(User.wallet_address == address).first()
    if not user:
        user = User(wallet_address=address)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Get USDC balance from blockchain (or use mock)
    try:
        vaults = db.query(Vault).filter(Vault.is_active == True).all()
        if vaults:
            usdc_balance = wei_to_decimal(
                blockchain.get_token_balance(vaults[0].asset_address, address)
            )
        else:
            usdc_balance = Decimal(0)
    except Exception:
        usdc_balance = Decimal(0)

    # Get vault balances
    vault_balances = []
    total_vault_value = Decimal(0)

    for vault in db.query(Vault).filter(Vault.is_active == True).all():
        vault_user = db.query(VaultUser).filter(
            VaultUser.vault_id == vault.id,
            VaultUser.user_id == user.id
        ).first()

        balance = vault_user.balance if vault_user else Decimal(0)
        if balance > 0:
            total_vault_value += balance

            # Get protocols for APY
            protocols = db.query(Protocol).filter(
                Protocol.vault_id == vault.id,
                Protocol.is_active == True
            ).all()
            avg_apy = sum(p.apy for p in protocols) / len(protocols) if protocols else Decimal(0)

            vault_balances.append({
                "vault_address": vault.address,
                "vault_name": vault.name,
                "balance": balance,
                "apy": avg_apy,
            })

    return MobileWalletInfo(
        address=address,
        usdc_balance=usdc_balance,
        vault_balances=vault_balances,
    )


# =============================================================================
# Mobile Deposit Flow Endpoints
# =============================================================================

@router.post("/deposit/flow", response_model=MobileDepositFlow)
def mobile_deposit_flow(
    vault_address: str,
    amount: Optional[Decimal] = Query(None),
    user_address: str = Query(...),
    db: Session = Depends(get_db),
    blockchain=Depends(get_client),
):
    """
    Get current state of deposit flow for mobile app.

    Returns the current step and any required actions.
    """
    vault = db.query(Vault).filter(Vault.address == vault_address).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VAULT_NOT_FOUND", "message": "Vault not found"}
        )

    # Check if user exists
    user = db.query(User).filter(User.wallet_address == user_address).first()
    if not user:
        return MobileDepositFlow(
            step="connect",
            vault_address=vault_address,
            approval_required=False,
        )

    # Check allowance
    try:
        allowance = blockchain.get_token_allowance(
            vault.asset_address,
            user_address,
            vault.address
        )

        if amount:
            amount_wei = int(amount * 10**6)  # USDC has 6 decimals
            approval_required = allowance < amount_wei
        else:
            approval_required = allowance < 2**256 - 1  # Check for unlimited

    except Exception:
        approval_required = True

    if approval_required:
        return MobileDepositFlow(
            step="approve",
            vault_address=vault_address,
            amount=amount,
            approval_required=True,
        )

    return MobileDepositFlow(
        step="deposit",
        vault_address=vault_address,
        amount=amount,
        approval_required=False,
    )


@router.post("/deposit/estimate")
def mobile_estimate_deposit(
    vault_address: str,
    amount: Decimal,
    user_address: str,
    db: Session = Depends(get_db),
):
    """
    Estimate deposit results for mobile display.

    Returns:
    - Expected new balance
    - Estimated APY
    - Transaction fee estimate
    """
    vault = db.query(Vault).filter(Vault.address == vault_address).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VAULT_NOT_FOUND", "message": "Vault not found"}
        )

    # Get user's current balance
    user = db.query(User).filter(User.wallet_address == user_address).first()
    current_balance = Decimal(0)

    if user:
        vault_user = db.query(VaultUser).filter(
            VaultUser.vault_id == vault.id,
            VaultUser.user_id == user.id
        ).first()
        if vault_user:
            current_balance = vault_user.balance

    # Get average APY
    protocols = db.query(Protocol).filter(
        Protocol.vault_id == vault.id,
        Protocol.is_active == True
    ).all()
    avg_apy = sum(p.apy for p in protocols) / len(protocols) if protocols else Decimal(0)

    # Calculate expected yearly yield
    new_balance = current_balance + amount
    expected_yearly_yield = new_balance * (avg_apy / 100)

    return {
        "current_balance": current_balance,
        "deposit_amount": amount,
        "new_balance": new_balance,
        "apy": avg_apy,
        "expected_yearly_yield": expected_yearly_yield,
        "estimated_fee_usd": Decimal("0.50"),  # Mock estimate
    }


# =============================================================================
# Mobile Withdrawal Flow Endpoints
# =============================================================================

@router.post("/withdraw/estimate")
def mobile_estimate_withdrawal(
    vault_address: str,
    amount: Decimal,
    user_address: str,
    instant: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Estimate withdrawal for mobile display.

    Returns:
    - Whether instant withdrawal is available
    - Estimated time for queued withdrawal
    - New balance after withdrawal
    """
    vault = db.query(Vault).filter(Vault.address == vault_address).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VAULT_NOT_FOUND", "message": "Vault not found"}
        )

    # Get user's balance
    user = db.query(User).filter(User.wallet_address == user_address).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "USER_NOT_FOUND", "message": "User not found"}
        )

    vault_user = db.query(VaultUser).filter(
        VaultUser.vault_id == vault.id,
        VaultUser.user_id == user.id
    ).first()

    if not vault_user or vault_user.balance < amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INSUFFICIENT_BALANCE", "message": "Insufficient balance"}
        )

    # Check instant withdrawal availability
    instant_available = False
    if instant:
        try:
            vault_balance_wei = blockchain.get_token_balance(vault.asset_address, vault.address)
            instant_available = vault_balance_wei >= int(amount * 10**6)
        except Exception:
            pass

    return {
        "instant_available": instant_available,
        "estimated_time_hours": 24 if not instant_available else 0,
        "current_balance": vault_user.balance,
        "withdrawal_amount": amount,
        "new_balance": vault_user.balance - amount,
    }


# =============================================================================
# Mobile Error Handlers
# =============================================================================

@router.get("/errors/{code}", response_model=MobileErrorResponse)
def mobile_error_info(code: str):
    """
    Get detailed error information for mobile app.

    Returns user-friendly error messages and suggested actions.
    """
    errors = {
        "INSUFFICIENT_FUNDS": MobileErrorResponse(
            code="INSUFFICIENT_FUNDS",
            message="You don't have enough USDC to complete this transaction.",
            details={"action": "Add more USDC to your wallet"}
        ),
        "INSUFFICIENT_ALLOWANCE": MobileErrorResponse(
            code="INSUFFICIENT_ALLOWANCE",
            message="Please approve the vault to spend your USDC.",
            details={"action": "Tap 'Approve' and confirm the transaction"}
        ),
        "NETWORK_ERROR": MobileErrorResponse(
            code="NETWORK_ERROR",
            message="Unable to connect to the network. Please check your connection.",
            details={"action": "Check your internet connection and try again"}
        ),
        "TRANSACTION_FAILED": MobileErrorResponse(
            code="TRANSACTION_FAILED",
            message="Transaction failed. Please try again.",
            details={"action": "Make sure you have enough gas and try again"}
        ),
        "WRONG_NETWORK": MobileErrorResponse(
            code="WRONG_NETWORK",
            message="Please switch to the correct network.",
            details={"action": "Switch your wallet to the intended network"}
        ),
        "VAULT_NOT_FOUND": MobileErrorResponse(
            code="VAULT_NOT_FOUND",
            message="Vault not found.",
            details={"action": "Please refresh and try again"}
        ),
    }

    return errors.get(code, MobileErrorResponse(
        code=code,
        message="An error occurred.",
        details={"action": "Please try again"}
    ))


# =============================================================================
# Mobile Health Check
# =============================================================================

@router.get("/health")
def mobile_health():
    """Mobile-specific health check."""
    return {
        "status": "ok",
        "mobile_api": "v1",
        "features": {
            "wallet_connect": True,
            "biometric": True,
            "push_notifications": True,
        }
    }
