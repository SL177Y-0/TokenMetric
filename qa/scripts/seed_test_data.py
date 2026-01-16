#!/usr/bin/env python3
"""
TokenMetric Test Data Seeding Script

This script populates the test database with seed data for testing.
It creates vaults, protocols, users, and sample transactions.

Usage: python qa/scripts/seed_test_data.py
"""

import os
import sys
from decimal import Decimal
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import (
    Base, Vault, Protocol, User, VaultUser, Transaction,
    TransactionType, TransactionStatus, WithdrawalRequest,
    WithdrawalRequestStatus, ProtocolSnapshot
)


# =============================================================================
# Configuration
# =============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# Test addresses
MANAGER_ADDRESS = "0x7fa3252c0948d6fb5cc06ca5161e2eb6f0b9c2e"
ASSET_ADDRESS = "0xa0b86a33e6d2164388426c72a34a687425225486"  # USDC

USER_ADDRESSES = [
    "0xabc1111111111111111111111111111111111111",
    "0xdef2222222222222222222222222222222222222",
    "0x3333333333333333333333333333333333333",
]

PROTOCOL_ADDRESSES = [
    "0xaave0000000000000000000000000000000001",
    "0xcomp0000000000000000000000000000000001",
    "0xcurve0000000000000000000000000000000001",
]

# =============================================================================
# Seeding Functions
# =============================================================================

def create_vaults(db):
    """Create sample vaults."""
    vaults = [
        Vault(
            address="0xstableVault0000000000000000000000",
            asset_address=ASSET_ADDRESS,
            manager_address=MANAGER_ADDRESS,
            name="Stable Vault",
            description="Low-risk stable yield vault",
            total_deposits=Decimal("1000000"),
            total_allocated=Decimal("600000"),
            total_yield=Decimal("15000"),
            tvl=Decimal("1000000"),
            is_active=True,
        ),
        Vault(
            address="0xhighYieldVault0000000000000000000",
            asset_address=ASSET_ADDRESS,
            manager_address=MANAGER_ADDRESS,
            name="High Yield Vault",
            description="Higher yield with moderate risk",
            total_deposits=Decimal("500000"),
            total_allocated=Decimal("400000"),
            total_yield=Decimal("25000"),
            tvl=Decimal("500000"),
            is_active=True,
        ),
        Vault(
            address="0xbalancedVault00000000000000000000",
            asset_address=ASSET_ADDRESS,
            manager_address=MANAGER_ADDRESS,
            name="Balanced Vault",
            description="Balanced risk-reward vault",
            total_deposits=Decimal("750000"),
            total_allocated=Decimal("500000"),
            total_yield=Decimal("18750"),
            tvl=Decimal("750000"),
            is_active=True,
        ),
    ]

    for vault in vaults:
        db.add(vault)
    db.commit()

    print(f"  ✓ Created {len(vaults)} vaults")
    return vaults


def create_protocols(db, vaults):
    """Create sample protocols."""
    protocols = []

    for i, vault in enumerate(vaults):
        vault_protocols = [
            Protocol(
                vault_id=vault.id,
                address=PROTOCOL_ADDRESSES[i],
                name=f"Protocol {i+1}A",
                description=f"Yield protocol {i+1}A",
                apy=Decimal("4.5"),
                risk_level=2,
                allocated_amount=Decimal("300000"),
                is_active=True,
            ),
            Protocol(
                vault_id=vault.id,
                address=PROTOCOL_ADDRESSES[(i+1) % 3],
                name=f"Protocol {i+1}B",
                description=f"Yield protocol {i+1}B",
                apy=Decimal("3.8"),
                risk_level=1,
                allocated_amount=Decimal("300000"),
                is_active=True,
            ),
        ]

        for protocol in vault_protocols:
            db.add(protocol)
            protocols.append(protocol)
        db.commit()

    print(f"  ✓ Created {len(protocols)} protocols")
    return protocols


def create_users(db):
    """Create sample users."""
    users = []

    for i, address in enumerate(USER_ADDRESSES):
        user = User(
            wallet_address=address,
            email=f"user{i+1}@example.com",
        )
        db.add(user)
        users.append(user)
    db.commit()

    print(f"  ✓ Created {len(users)} users")
    return users


def create_vault_users(db, vaults, users):
    """Create user vault balances."""
    vault_users = []

    for vault in vaults:
        for user in users:
            vault_user = VaultUser(
                vault_id=vault.id,
                user_id=user.id,
                balance=Decimal("50000"),
            )
            db.add(vault_user)
            vault_users.append(vault_user)
        db.commit()

    print(f"  ✓ Created {len(vault_users)} vault user relationships")
    return vault_users


def create_transactions(db, vaults, users):
    """Create sample transactions."""
    transactions = []

    for vault in vaults[:1]:  # Only for first vault
        for i, user in enumerate(users):
            # Deposit transaction
            deposit_tx = Transaction(
                vault_id=vault.id,
                user_id=user.id,
                tx_type=TransactionType.DEPOSIT,
                status=TransactionStatus.COMPLETED,
                amount=Decimal("50000"),
                from_address=user.wallet_address,
                to_address=vault.address,
                tx_hash=f"0x{'0'*63}{i}",
                block_number=1000000 + i,
                gas_used=100000 + i * 1000,
            )
            db.add(deposit_tx)
            transactions.append(deposit_tx)

            # Yield transaction
            if i == 0:
                yield_tx = Transaction(
                    vault_id=vault.id,
                    user_id=None,
                    tx_type=TransactionType.YIELD,
                    status=TransactionStatus.COMPLETED,
                    amount=Decimal("5000"),
                    from_address=vault.address,
                    to_address=vault.protocolA,
                    tx_hash=f"0x{'0'*63}y{i}",
                    block_number=1000100 + i,
                )
                db.add(yield_tx)
                transactions.append(yield_tx)

        db.commit()

    print(f"  ✓ Created {len(transactions)} transactions")
    return transactions


def create_withdrawal_requests(db, vaults, users):
    """Create sample withdrawal requests."""
    requests = []

    for vault in vaults[:1]:  # Only for first vault
        for user in users[:2]:  # Only for first 2 users
            for i in range(2):  # 2 requests per user
                withdrawal = WithdrawalRequest(
                    vault_id=vault.id,
                    user_id=user.id,
                    queue_index=len(requests),
                    amount=Decimal("5000"),
                    status=WithdrawalRequestStatus.QUEUED,
                    requested_at=datetime.utcnow() - timedelta(hours=i),
                )
                db.add(withdrawal)
                requests.append(withdrawal)
        db.commit()

    print(f"  ✓ Created {len(requests)} withdrawal requests")
    return requests


def create_protocol_snapshots(db, protocols):
    """Create protocol snapshots for historical data."""
    snapshots = []

    for protocol in protocols[:3]:  # Only for first 3 protocols
        for i in range(30):  # 30 days of snapshots
            snapshot = ProtocolSnapshot(
                protocol_id=protocol.id,
                tvl=protocol.allocated_amount + (i * 1000),
                apy=protocol.apy,
                timestamp=datetime.utcnow() - timedelta(days=30-i),
            )
            db.add(snapshot)
            snapshots.append(snapshot)
        db.commit()

    print(f"  ✓ Created {len(snapshots)} protocol snapshots")
    return snapshots


# =============================================================================
# Main Seeding Function
# =============================================================================

def seed_all():
    """Seed all test data."""
    print("Seeding test data...")
    print("")

    # Create engine
    engine = create_engine(DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Seed data
        vaults = create_vaults(db)
        protocols = create_protocols(db, vaults)
        users = create_users(db)
        create_vault_users(db, vaults, users)
        create_transactions(db, vaults, users)
        create_withdrawal_requests(db, vaults, users)
        create_protocol_snapshots(db, protocols)

        print("")
        print("=" * 50)
        print("✅ Test data seeded successfully!")
        print("=" * 50)
        print("")
        print(f"  Vaults: {len(vaults)}")
        print(f"  Protocols: {len(protocols)}")
        print(f"  Users: {len(users)}")
        print(f"  Total TVL: $2,250,000")
        print("")

    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
