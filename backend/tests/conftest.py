"""
Pytest configuration and fixtures for TokenMetric backend tests.
"""

import os
import pytest
import responses
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.database import get_db
from backend.app.models import Base


# =============================================================================
# Configuration
# =============================================================================

RPC_URL = "https://rpc.example.com"
TESTING = True


# =============================================================================
# Test Database
# =============================================================================

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Setup and teardown test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

    # Clean up test database file
    import os
    import gc
    gc.collect()  # Force garbage collection to release file handles
    try:
        if os.path.exists("./test.db"):
            os.remove("./test.db")
    except (PermissionError, OSError):
        # On Windows, the file might be locked - skip cleanup
        pass


@pytest.fixture
def db_session():
    """Get test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def api_client():
    """Get FastAPI test client."""
    from backend.app.main import app
    from backend.app.database import get_db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def mock_blockchain():
    """Mock blockchain RPC responses."""
    with responses.RequestsMock() as rsps:
        # Mock eth_blockNumber
        rsps.add(
            responses.POST,
            RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "result": "0x123456"},
        )

        # Mock eth_call (for balance checks)
        rsps.add(
            responses.POST,
            RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "result": "0x0de0b6b3a7640000"},  # 1 token
        )

        yield rsps


@pytest.fixture
def seeded_db(db_session):
    """Database with standard test data."""
    from backend.app.models import Vault, Protocol, User, VaultUser
    from decimal import Decimal

    # Create test vault
    vault = Vault(
        address="0x1234567890123456789012345678901234567890",
        asset_address="0xa0b86a33e6d2164388426c72a34a687425225486",  # USDC mainnet
        manager_address="0x9999999999999999999999999999999999999999",
        name="Stable Vault",
        description="A stable yield vault",
        total_deposits=Decimal("1000000"),
        total_allocated=Decimal("600000"),
        total_yield=Decimal("15000"),
        tvl=Decimal("1000000"),
    )
    db_session.add(vault)

    # Create test protocols
    protocol_a = Protocol(
        vault_id=vault.id,
        address="0xprotocol00000000000000000000000000000000000001",
        name="Aave Protocol",
        description="Aave lending protocol",
        apy=Decimal("4.5"),
        risk_level=2,
        allocated_amount=Decimal("300000"),
    )
    protocol_b = Protocol(
        vault_id=vault.id,
        address="0xprotocol00000000000000000000000000000000000002",
        name="Compound Protocol",
        description="Compound lending protocol",
        apy=Decimal("3.8"),
        risk_level=1,
        allocated_amount=Decimal("300000"),
    )
    db_session.add(protocol_a)
    db_session.add(protocol_b)

    # Create test users
    user1 = User(
        wallet_address="0xuser10000000000000000000000000000000000001",
        email="user1@example.com",
    )
    user2 = User(
        wallet_address="0xuser20000000000000000000000000000000000002",
        email="user2@example.com",
    )
    db_session.add(user1)
    db_session.add(user2)

    db_session.commit()

    # Create vault user relationships
    vault_user1 = VaultUser(
        vault_id=vault.id,
        user_id=user1.id,
        balance=Decimal("50000"),
    )
    vault_user2 = VaultUser(
        vault_id=vault.id,
        user_id=user2.id,
        balance=Decimal("25000"),
    )
    db_session.add(vault_user1)
    db_session.add(vault_user2)

    db_session.commit()

    return {
        "vault": vault,
        "protocol_a": protocol_a,
        "protocol_b": protocol_b,
        "user1": user1,
        "user2": user2,
    }


@pytest.fixture
def mock_rpc_responses():
    """Mock various RPC responses."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        # Block number
        def block_number_callback(request):
            return (200, {}, '{"jsonrpc":"2.0","id":1,"result":"0x123456"}')

        # Balance of (erc20 balanceOf)
        def balance_callback(request):
            import json
            payload = json.loads(request.body)
            if "0x" in payload.get("params", [""])[0]:
                # Return large balance for tests (1000000 USDC in 6 decimals = 1000000*10^6)
                return (200, {}, '{"jsonrpc":"2.0","id":1,"result":"0xd3c21bcecceda1000000"}')  # 1e24
            return (200, {}, '{"jsonrpc":"2.0","id":1,"result":"0x0"}')

        # Allowance
        def allowance_callback(request):
            return (200, {}, '{"jsonrpc":"2.0","id":1,"result":"0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"}')

        # Token balance (special contract call for USDC)
        def token_balance_callback(request):
            import json
            payload = json.loads(request.body)
            # Return large balance for token balance checks
            return (200, {}, '{"jsonrpc":"2.0","id":1,"result":"0xd3c21bcecceda1000000"}')  # 1e24

        rsps.add_callback(responses.POST, RPC_URL, callback=block_number_callback)
        rsps.add_callback(responses.POST, RPC_URL, callback=balance_callback)
        rsps.add_callback(responses.POST, RPC_URL, callback=allowance_callback)
        rsps.add_callback(responses.POST, RPC_URL, callback=token_balance_callback)

        yield rsps


# =============================================================================
# Environment Variables
# =============================================================================

@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("RPC_URL", RPC_URL)
    monkeypatch.setenv("CHAIN_ID", "1")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")


# =============================================================================
# Test Utilities
# =============================================================================

@pytest.fixture
def vault_payload():
    """Sample vault creation payload."""
    return {
        "address": "0x1234567890123456789012345678901234567890",
        "asset_address": "0xa0b86a33e6d2164388426c72a34a687425225486",
        "manager_address": "0x9999999999999999999999999999999999999999",
        "name": "Test Vault",
        "description": "A test vault",
    }


@pytest.fixture
def protocol_payload():
    """Sample protocol creation payload."""
    return {
        "vault_id": 1,
        "address": "0xprotocol00000000000000000000000000000000000001",
        "name": "Test Protocol",
        "apy": "5.5",
        "risk_level": 2,
    }


@pytest.fixture
def deposit_payload():
    """Sample deposit payload."""
    return {
        "vault_address": "0x1234567890123456789012345678901234567890",
        "amount": "1000.50",
        "user_address": "0xuser00000000000000000000000000000000000000",
    }


@pytest.fixture
def withdraw_payload():
    """Sample withdrawal payload."""
    return {
        "vault_address": "0x1234567890123456789012345678901234567890",
        "amount": "500",
        "user_address": "0xuser00000000000000000000000000000000000000",
        "instant": True,
    }
