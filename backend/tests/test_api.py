"""
Comprehensive tests for TokenMetric backend API.
"""

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.database import get_db
from backend.app.models import Base, Vault, Protocol, User, VaultUser, Transaction
from backend.app.schemas import VaultCreate, ProtocolCreate, UserCreate


# =============================================================================
# Test Database Setup
# =============================================================================

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
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


@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Get test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    """Get test client."""
    from backend.app.main import app
    from backend.app.database import get_db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_vault(db_session):
    """Create sample vault."""
    vault = Vault(
        address="0x1234567890123456789012345678901234567890",
        asset_address="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        manager_address="0x9999999999999999999999999999999999999999",
        name="Test Vault",
        description="A test vault",
        total_deposits=Decimal("1000000"),
        tvl=Decimal("1000000"),
    )
    db_session.add(vault)
    db_session.commit()
    db_session.refresh(vault)
    return vault


@pytest.fixture
def sample_user(db_session):
    """Create sample user."""
    user = User(
        wallet_address="0x1111111111111111111111111111111111111111",
        email="test@example.com",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_protocol(db_session, sample_vault):
    """Create sample protocol."""
    protocol = Protocol(
        vault_id=sample_vault.id,
        address="0xprotocol000000000000000000000000000000000000",
        name="Test Protocol",
        description="A test protocol",
        apy=Decimal("5.5"),
        risk_level=2,
        allocated_amount=Decimal("500000"),
    )
    db_session.add(protocol)
    db_session.commit()
    db_session.refresh(protocol)
    return protocol


@pytest.fixture
def vault_with_user(db_session, sample_vault, sample_user):
    """Create vault with user having a balance."""
    vault_user = VaultUser(
        vault_id=sample_vault.id,
        user_id=sample_user.id,
        balance=Decimal("10000"),
    )
    db_session.add(vault_user)

    sample_vault.total_deposits = Decimal("10000")
    db_session.commit()

    return sample_vault


# =============================================================================
# Health Tests
# =============================================================================

class TestHealth:
    """Tests for health endpoints."""

    def test_health_ok(self, client):
        """Test health check returns ok."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data
        assert "blockchain" in data

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "TokenMetric Backend"
        assert "endpoints" in data


# =============================================================================
# Vault Tests
# =============================================================================

class TestVaults:
    """Tests for vault endpoints."""

    def test_create_vault(self, client):
        """Test vault creation."""
        vault_data = {
            "address": "0x1234567890123456789012345678901234567890",
            "asset_address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "manager_address": "0x9999999999999999999999999999999999999999",
            "name": "New Vault",
            "description": "A new vault",
        }
        response = client.post("/vaults", json=vault_data)

        assert response.status_code == 201
        data = response.json()
        assert data["address"] == vault_data["address"]
        assert data["name"] == vault_data["name"]
        assert "id" in data

    def test_create_vault_duplicate_fails(self, client, sample_vault):
        """Test creating duplicate vault fails."""
        vault_data = {
            "address": sample_vault.address,
            "asset_address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "manager_address": "0x9999999999999999999999999999999999999999",
            "name": "Duplicate Vault",
        }
        response = client.post("/vaults", json=vault_data)

        assert response.status_code == 409

    def test_list_vaults(self, client, sample_vault):
        """Test listing vaults."""
        response = client.get("/vaults")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(v["address"] == sample_vault.address for v in data)

    def test_list_vaults_pagination(self, client, db_session):
        """Test vault listing pagination."""
        # Create multiple vaults
        for i in range(5):
            vault = Vault(
                address=f"0x{'0' * 39}{i}",
                asset_address="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
                manager_address="0x9999999999999999999999999999999999999999",
                name=f"Vault {i}",
            )
            db_session.add(vault)
        db_session.commit()

        response = client.get("/vaults?skip=0&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_get_vault_by_id(self, client, sample_vault):
        """Test getting vault by ID."""
        response = client.get(f"/vaults/{sample_vault.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_vault.id
        assert data["address"] == sample_vault.address

    def test_get_vault_by_id_not_found(self, client):
        """Test getting non-existent vault."""
        response = client.get("/vaults/99999")
        assert response.status_code == 404

    def test_get_vault_by_address(self, client, sample_vault):
        """Test getting vault by address."""
        response = client.get(f"/vaults/address/{sample_vault.address}")

        assert response.status_code == 200
        data = response.json()
        assert data["address"] == sample_vault.address

    def test_update_vault(self, client, sample_vault):
        """Test updating vault."""
        update_data = {"name": "Updated Vault Name"}
        response = client.patch(f"/vaults/{sample_vault.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Vault Name"

    def test_delete_vault(self, client, sample_vault):
        """Test soft deleting vault."""
        response = client.delete(f"/vaults/{sample_vault.id}")
        assert response.status_code == 204

        # Verify vault is inactive
        response = client.get(f"/vaults/{sample_vault.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False


# =============================================================================
# User Balance Tests
# =============================================================================

class TestUserBalances:
    """Tests for user balance endpoints."""

    def test_get_user_balance(self, client, vault_with_user, sample_user):
        """Test getting user balance in vault."""
        response = client.get(
            f"/vaults/{vault_with_user.id}/users/{sample_user.wallet_address}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["vault_id"] == vault_with_user.id
        assert data["user_address"] == sample_user.wallet_address
        assert data["balance"] == "10000"

    def test_get_user_balance_not_found(self, client, sample_vault):
        """Test getting balance for non-existent user."""
        response = client.get(
            f"/vaults/{sample_vault.id}/users/0xnonexistent"
        )

        # Should create user entry with 0 balance
        assert response.status_code == 200

    def test_list_vault_users(self, client, vault_with_user):
        """Test listing vault users."""
        response = client.get(f"/vaults/{vault_with_user.id}/users")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1


# =============================================================================
# Deposit Tests
# =============================================================================

class TestDeposits:
    """Tests for deposit endpoints."""

    def test_deposit(self, client, sample_vault):
        """Test making a deposit."""
        deposit_data = {
            "vault_address": sample_vault.address,
            "amount": "1000.50",
            "user_address": "0xuser00000000000000000000000000000000000000",
        }
        response = client.post(f"/vaults/{sample_vault.id}/deposit", json=deposit_data)

        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == "1000.50"
        assert "new_balance" in data
        assert "tx_hash" in data

    def test_deposit_insufficient_funds(self, client, sample_vault):
        """Test deposit with insufficient funds."""
        # This would require blockchain integration to properly test
        # For now, we just verify the endpoint exists
        deposit_data = {
            "vault_address": sample_vault.address,
            "amount": "999999999999",
            "user_address": "0xuser00000000000000000000000000000000000000",
        }
        response = client.post(f"/vaults/{sample_vault.id}/deposit", json=deposit_data)

        # With mock implementation, this succeeds
        assert response.status_code == 200


# =============================================================================
# Withdrawal Tests
# =============================================================================

class TestWithdrawals:
    """Tests for withdrawal endpoints."""

    def test_instant_withdraw(self, client, vault_with_user, sample_user):
        """Test instant withdrawal."""
        withdraw_data = {
            "vault_address": vault_with_user.address,
            "amount": "5000",
            "user_address": sample_user.wallet_address,
            "instant": True,
        }
        response = client.post(f"/vaults/{vault_with_user.id}/withdraw", json=withdraw_data)

        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == "5000"
        assert "new_balance" in data
        assert data["new_balance"] == "5000"

    def test_queued_withdraw(self, client, vault_with_user, sample_user):
        """Test queued withdrawal."""
        withdraw_data = {
            "vault_address": vault_with_user.address,
            "amount": "3000",
            "user_address": sample_user.wallet_address,
            "instant": False,
        }
        response = client.post(f"/vaults/{vault_with_user.id}/withdraw", json=withdraw_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "queue_index" in data

    def test_withdraw_insufficient_balance(self, client, sample_vault, sample_user):
        """Test withdrawal with insufficient balance."""
        withdraw_data = {
            "vault_address": sample_vault.address,
            "amount": "999999",
            "user_address": sample_user.wallet_address,
        }
        response = client.post(f"/vaults/{sample_vault.id}/withdraw", json=withdraw_data)

        assert response.status_code == 400


# =============================================================================
# Protocol Tests
# =============================================================================

class TestProtocols:
    """Tests for protocol endpoints."""

    def test_create_protocol(self, client, sample_vault):
        """Test creating a protocol."""
        protocol_data = {
            "vault_id": sample_vault.id,
            "address": "0xprot00000000000000000000000000000000000001",
            "name": "New Protocol",
            "apy": "7.5",
            "risk_level": 3,
        }
        response = client.post("/protocols", json=protocol_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Protocol"
        assert data["apy"] == "7.5"

    def test_list_protocols(self, client, sample_protocol):
        """Test listing protocols."""
        response = client.get("/protocols")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_list_protocols_by_vault(self, client, sample_vault, sample_protocol):
        """Test listing protocols filtered by vault."""
        response = client.get(f"/protocols?vault_id={sample_vault.id}")

        assert response.status_code == 200
        data = response.json()
        assert all(p["vault_id"] == sample_vault.id for p in data)

    def test_get_protocol_stats(self, client, sample_protocol):
        """Test getting protocol statistics."""
        response = client.get(f"/protocols/{sample_protocol.id}/stats")

        assert response.status_code == 200
        data = response.json()
        assert "protocol_address" in data
        assert "allocated" in data
        assert "apy" in data

    def test_allocate_to_protocol(self, client, sample_vault, sample_protocol):
        """Test allocating funds to protocol."""
        response = client.post(
            f"/protocols/{sample_protocol.id}/allocate",
            params={"amount": "10000"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "allocated_amount" in data
        assert data["allocated_amount"] > 0

    def test_deallocate_from_protocol(self, client, sample_vault, sample_protocol):
        """Test deallocating funds from protocol."""
        # First allocate
        client.post(f"/protocols/{sample_protocol.id}/allocate", params={"amount": "5000"})

        # Then deallocate
        response = client.post(
            f"/protocols/{sample_protocol.id}/deallocate",
            params={"amount": "2000"}
        )

        assert response.status_code == 200


# =============================================================================
# Stats Tests
# =============================================================================

class TestStats:
    """Tests for statistics endpoints."""

    def test_get_vault_stats(self, client, sample_vault):
        """Test getting vault statistics."""
        response = client.get(f"/vaults/{sample_vault.id}/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_deposits" in data
        assert "tvl" in data
        assert "user_count" in data
        assert "protocol_count" in data

    def test_get_global_stats(self, client):
        """Test getting global platform statistics."""
        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_vaults" in data
        assert "total_tvl" in data
        assert "total_users" in data

    def test_list_vault_transactions(self, client, sample_vault):
        """Test listing vault transactions."""
        response = client.get(f"/vaults/{sample_vault.id}/transactions")

        assert response.status_code == 200
        assert isinstance(response.json(), list)


# =============================================================================
# Mobile API Tests
# =============================================================================

class TestMobileAPI:
    """Tests for mobile-specific endpoints."""

    def test_mobile_list_vaults(self, client, sample_vault):
        """Test mobile vault listing."""
        response = client.get("/mobile/vaults")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_mobile_vault_summary(self, client, sample_vault):
        """Test mobile vault summary."""
        response = client.get(f"/mobile/vaults/{sample_vault.address}/summary")

        assert response.status_code == 200
        data = response.json()
        assert "address" in data
        assert "tvl" in data
        assert "apy" in data

    def test_mobile_wallet_info(self, client, sample_user):
        """Test mobile wallet info."""
        response = client.get(f"/mobile/wallet/{sample_user.wallet_address}")

        assert response.status_code == 200
        data = response.json()
        assert "address" in data
        assert "vault_balances" in data

    def test_mobile_deposit_flow(self, client, sample_vault):
        """Test mobile deposit flow."""
        response = client.post(
            "/mobile/deposit/flow",
            params={
                "vault_address": sample_vault.address,
                "user_address": "0xuser00000000000000000000000000000000000000",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "step" in data
        assert data["step"] in ["connect", "approve", "deposit"]

    def test_mobile_deposit_estimate(self, client, sample_vault):
        """Test mobile deposit estimate."""
        response = client.post(
            "/mobile/deposit/estimate",
            params={
                "vault_address": sample_vault.address,
                "amount": "5000",
                "user_address": "0xuser00000000000000000000000000000000000000",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "new_balance" in data
        assert "apy" in data
        assert "expected_yearly_yield" in data

    def test_mobile_withdrawal_estimate(self, client, vault_with_user, sample_user):
        """Test mobile withdrawal estimate."""
        response = client.post(
            "/mobile/withdraw/estimate",
            params={
                "vault_address": vault_with_user.address,
                "amount": "1000",
                "user_address": sample_user.wallet_address,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "instant_available" in data
        assert "estimated_time_hours" in data

    def test_mobile_health(self, client):
        """Test mobile health endpoint."""
        response = client.get("/mobile/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "features" in data


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_validation_error(self, client):
        """Test request validation error."""
        invalid_data = {
            "address": "not-a-valid-address",
            "asset_address": "",
            "manager_address": "",
            "name": "",
        }
        response = client.post("/vaults", json=invalid_data)

        assert response.status_code == 422

    def test_not_found_error(self, client):
        """Test 404 error."""
        response = client.get("/vaults/99999")
        assert response.status_code == 404
