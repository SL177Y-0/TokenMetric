"""
Protocol API routes for TokenMetric backend.
"""

from typing import List
from decimal import Decimal
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Protocol, Vault, Transaction, TransactionType, TransactionStatus, ProtocolSnapshot
from ..schemas import ProtocolCreate, ProtocolUpdate, ProtocolResponse, ProtocolStats

router = APIRouter(prefix="/protocols", tags=["protocols"])


# =============================================================================
# Protocol CRUD Endpoints
# =============================================================================

@router.post("", response_model=ProtocolResponse, status_code=status.HTTP_201_CREATED)
def create_protocol(
    protocol_data: ProtocolCreate,
    db: Session = Depends(get_db),
):
    """Create a new protocol for a vault."""
    # Verify vault exists
    vault = db.query(Vault).filter(Vault.id == protocol_data.vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    # Check if protocol already exists
    existing = db.query(Protocol).filter(
        Protocol.vault_id == protocol_data.vault_id,
        Protocol.address == protocol_data.address
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Protocol with this address already exists for this vault"
        )

    protocol = Protocol(**protocol_data.model_dump())
    db.add(protocol)
    db.commit()
    db.refresh(protocol)

    return protocol


@router.get("", response_model=List[ProtocolResponse])
def list_protocols(
    vault_id: int = Query(None),
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List all protocols with optional filtering."""
    query = db.query(Protocol)

    if vault_id:
        query = query.filter(Protocol.vault_id == vault_id)

    if active_only:
        query = query.filter(Protocol.is_active == True)

    protocols = query.offset(skip).limit(limit).all()
    return protocols


@router.get("/{protocol_id}", response_model=ProtocolResponse)
def get_protocol(
    protocol_id: int,
    db: Session = Depends(get_db),
):
    """Get protocol details by ID."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol not found"
        )
    return protocol


@router.patch("/{protocol_id}", response_model=ProtocolResponse)
def update_protocol(
    protocol_id: int,
    protocol_data: ProtocolUpdate,
    db: Session = Depends(get_db),
):
    """Update protocol information."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol not found"
        )

    update_data = protocol_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(protocol, field, value)

    db.commit()
    db.refresh(protocol)

    return protocol


@router.delete("/{protocol_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_protocol(
    protocol_id: int,
    db: Session = Depends(get_db),
):
    """Delete a protocol (soft delete by setting is_active=False)."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol not found"
        )

    protocol.is_active = False
    db.commit()


# =============================================================================
# Protocol Allocation Endpoints
# =============================================================================

@router.post("/{protocol_id}/allocate")
def allocate_to_protocol(
    protocol_id: int,
    amount: Decimal = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    """
    Allocate funds to a protocol.

    In production, this would interact with the smart contract.
    """
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol not found"
        )

    if not protocol.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Protocol is not active"
        )

    vault = db.query(Vault).filter(Vault.id == protocol.vault_id).first()
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    # Check vault liquidity
    vault_balance = vault.total_deposits - vault.total_allocated
    if vault_balance < amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient vault liquidity. Available: {vault_balance}"
        )

    # Create allocation transaction
    transaction = Transaction(
        vault_id=protocol.vault_id,
        tx_type=TransactionType.ALLOCATE,
        status=TransactionStatus.COMPLETED,
        amount=amount,
        from_address=vault.address,
        to_address=protocol.address,
    )
    db.add(transaction)

    # Update protocol and vault
    protocol.allocated_amount += amount
    vault.total_allocated += amount

    db.commit()

    return {
        "protocol_id": protocol_id,
        "allocated_amount": protocol.allocated_amount,
        "tx_hash": transaction.tx_hash,
    }


@router.post("/{protocol_id}/deallocate")
def deallocate_from_protocol(
    protocol_id: int,
    amount: Decimal = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    """
    Deallocate funds from a protocol.

    In production, this would interact with the smart contract.
    """
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol not found"
        )

    if protocol.allocated_amount < amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient protocol allocation"
        )

    vault = db.query(Vault).filter(Vault.id == protocol.vault_id).first()

    # Create deallocation transaction
    transaction = Transaction(
        vault_id=protocol.vault_id,
        tx_type=TransactionType.DEALLOCATE,
        status=TransactionStatus.COMPLETED,
        amount=amount,
        from_address=protocol.address,
        to_address=vault.address,
    )
    db.add(transaction)

    # Update protocol and vault
    protocol.allocated_amount -= amount
    vault.total_allocated -= amount

    db.commit()

    return {
        "protocol_id": protocol_id,
        "allocated_amount": protocol.allocated_amount,
        "tx_hash": transaction.tx_hash,
    }


# =============================================================================
# Protocol Statistics Endpoints
# =============================================================================

@router.get("/{protocol_id}/stats", response_model=ProtocolStats)
def get_protocol_stats(
    protocol_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get protocol statistics."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol not found"
        )

    # Get yield generated from transactions
    since = datetime.utcnow() - timedelta(days=days)

    yield_generated = db.query(Transaction).filter(
        Transaction.vault_id == protocol.vault_id,
        Transaction.tx_type == TransactionType.YIELD,
        Transaction.to_address == protocol.address,
        Transaction.status == TransactionStatus.COMPLETED,
        Transaction.created_at >= since
    ).with_entities(
        func.sum(Transaction.amount)
    ).scalar() or Decimal(0)

    # Calculate utilization rate
    vault = db.query(Vault).filter(Vault.id == protocol.vault_id).first()
    utilization_rate = (protocol.allocated_amount / vault.total_deposits * 100) if vault.total_deposits > 0 else Decimal(0)

    return ProtocolStats(
        protocol_address=protocol.address,
        protocol_name=protocol.name,
        allocated=protocol.allocated_amount,
        apy=protocol.apy,
        yield_generated=yield_generated,
        utilization_rate=utilization_rate,
    )


@router.get("/{protocol_id}/snapshots")
def get_protocol_snapshots(
    protocol_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get historical protocol snapshots."""
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol not found"
        )

    since = datetime.utcnow() - timedelta(days=days)

    snapshots = db.query(ProtocolSnapshot).filter(
        ProtocolSnapshot.protocol_id == protocol_id,
        ProtocolSnapshot.timestamp >= since
    ).order_by(ProtocolSnapshot.timestamp.asc()).all()

    return [
        {
            "timestamp": s.timestamp,
            "tvl": s.tvl,
            "apy": s.apy,
        }
        for s in snapshots
    ]


@router.post("/{protocol_id}/snapshots")
def create_protocol_snapshot(
    protocol_id: int,
    db: Session = Depends(get_db),
):
    """
    Create a protocol snapshot.
    Used for tracking historical APY and TVL data.
    """
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol not found"
        )

    snapshot = ProtocolSnapshot(
        protocol_id=protocol_id,
        tvl=protocol.allocated_amount,
        apy=protocol.apy,
        timestamp=datetime.utcnow(),
    )
    db.add(snapshot)
    db.commit()

    return {"snapshot_id": snapshot.id, "timestamp": snapshot.timestamp}


# =============================================================================
# Protocol Comparison Endpoints
# =============================================================================

@router.get("/compare", response_model=List[ProtocolStats])
def compare_protocols(
    protocol_ids: List[int] = Query(...),
    db: Session = Depends(get_db),
):
    """Compare multiple protocols side by side."""
    protocols = db.query(Protocol).filter(Protocol.id.in_(protocol_ids)).all()

    if not protocols:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No protocols found"
        )

    result = []
    for protocol in protocols:
        vault = db.query(Vault).filter(Vault.id == protocol.vault_id).first()
        utilization_rate = (protocol.allocated_amount / vault.total_deposits * 100) if vault and vault.total_deposits > 0 else Decimal(0)

        result.append(ProtocolStats(
            protocol_address=protocol.address,
            protocol_name=protocol.name,
            allocated=protocol.allocated_amount,
            apy=protocol.apy,
            yield_generated=Decimal(0),  # Would be calculated
            utilization_rate=utilization_rate,
        ))

    return result
