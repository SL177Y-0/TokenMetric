# TokenMetric Test Infrastructure

A comprehensive test infrastructure for DeFi vault protocol covering smart contracts (Foundry), backend APIs (FastAPI/pytest), and mobile UI (Maestro).

---

## Assignment Checklist

| Requirement | Status | Location |
|-------------|--------|----------|
| **1. Smart Contract Fixtures (Foundry)** | Done | `contracts/test/fixtures/VaultFixture.sol` |
| **2. Mobile/UI Tests (Maestro)** | Done | `mobile/maestro/*.yaml` |
| **3. API Test Fixtures (pytest)** | Done | `backend/tests/conftest.py` |
| **4. Test Data Management** | Done | `qa/scripts/`, `qa/data/` |
| **5. Test Coverage Report** | Done | See coverage section below |
| **6. CI Integration** | Done | `.github/workflows/` |
| **Stretch: Fuzz Testing** | Done | `contracts/test/invariants/` |
| **Stretch: Visual Regression** | Done | `mobile/maestro/visual_regression.yaml` |
| **Stretch: Performance Tests** | Done | `contracts/test/performance/`, `mobile/maestro/performance.yaml` |
| **Stretch: Chaos Testing** | Done | `contracts/test/chaos/` |

---

## Project Structure

```
TokenMetric/
├── contracts/                    # Smart Contracts (Foundry)
│   ├── src/
│   │   └── TMVault.sol          # Main vault contract
│   └── test/
│       ├── fixtures/            # Reusable test fixtures
│       │   └── VaultFixture.sol # Base fixture with helpers
│       ├── mocks/               # Mock contracts
│       │   ├── MockUSDC.sol     # Mock USDT token
│       │   └── MockProtocol.sol # Mock DeFi protocol
│       ├── unit/                # Unit tests
│       ├── integration/         # Integration tests
│       ├── invariants/          # Fuzz & invariant tests
│       ├── chaos/               # Chaos engineering tests
│       └── performance/         # Gas benchmarks
│
├── backend/                     # Backend API (FastAPI)
│   ├── app/
│   │   ├── main.py             # FastAPI application
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── schemas.py          # Pydantic schemas
│   │   └── routes/             # API routes
│   └── tests/
│       ├── conftest.py         # pytest fixtures
│       └── test_api.py         # API tests
│
├── mobile/                      # Mobile E2E Tests
│   └── maestro/
│       ├── connect_wallet.yaml  # Wallet connection flow
│       ├── deposit_flow.yaml    # Deposit flow
│       ├── withdraw_flow.yaml   # Withdrawal flow
│       ├── error_handling.yaml  # Error scenarios
│       ├── vault_switching.yaml # Vault navigation
│       ├── performance.yaml     # Performance tests
│       └── visual_regression.yaml # Visual regression
│
├── qa/                          # QA Resources
│   ├── scripts/
│   │   ├── seed_test_data.py   # Database seeding
│   │   └── reset_env.sh        # Environment reset
│   └── data/
│       └── accounts.md         # Test accounts docs
│
├── .github/workflows/           # CI/CD
│   ├── contracts.yml           # Smart contract CI
│   ├── backend.yml             # Backend CI
│   ├── mobile.yml              # Mobile CI
│   └── full-ci.yml             # Full orchestration
│
└── infra/
    └── docker-compose.yml      # Local services
```

---

## Quick Start

### Prerequisites
- **Foundry** for smart contract testing
- **Python 3.9+** for backend
- **Maestro** for mobile E2E tests
- **Docker** for local services

### Smart Contracts
```bash
# Install dependencies
cd contracts
forge install

# Run all tests
forge test -vv

# Run with coverage
forge coverage

# Run specific test suite
forge test --match-contract VaultUnitTests -vv
forge test --match-contract VaultIntegrationTests -vv
forge test --match-contract VaultInvariants -vv
forge test --match-contract ChaosTests -vv
```

### Backend API
```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html
```

### Mobile E2E
```bash
# Run all flows
cd mobile
maestro test maestro/

# Run specific flow
maestro test maestro/deposit_flow.yaml
maestro test maestro/error_handling.yaml
```

### Using Makefile
```bash
make test-contracts   # Run smart contract tests
make test-backend     # Run backend tests
make test-mobile      # Run mobile tests
make dev-up           # Start local services
make dev-down         # Stop local services
```

---

## Test Coverage Matrix

| Component | Unit | Integration | E2E | Fuzz | Chaos | Status |
|-----------|------|-------------|-----|------|-------|--------|
| Vault deposit | Yes | Yes | Yes | Yes | Yes | Ready |
| Vault withdraw | Yes | Yes | Yes | Yes | Yes | Ready |
| Withdrawal queue | Yes | Yes | Yes | Yes | Yes | Ready |
| Protocol routing | Yes | Yes | N/A | Yes | Yes | Ready |
| Yield collection | Yes | Yes | N/A | Yes | N/A | Ready |
| Mobile connect | N/A | N/A | Yes | N/A | N/A | Ready |
| Mobile deposit | N/A | N/A | Yes | N/A | N/A | Ready |
| Mobile withdraw | N/A | N/A | Yes | N/A | N/A | Ready |
| Mobile errors | N/A | N/A | Yes | N/A | N/A | Ready |
| Visual regression | N/A | N/A | Yes | N/A | N/A | Ready |

---

## Test Fixtures

### Smart Contract Fixture (VaultFixture.sol)

```solidity
contract VaultFixture is Test {
    TMVault vault;
    MockUSDC usdt;
    MockProtocol protocolA;
    MockProtocol protocolB;

    // Helper functions reduce boilerplate by ~93%
    function _deposit(address user, uint256 amount) internal;
    function _requestWithdrawal(address user, uint256 amount) internal returns (uint256);
    function _allocate(address protocol, uint256 amount) internal;
    function _simulateYield(uint256 bps) internal;
    
    // Ready-made scenarios
    function scenario_AllocatedFunds() internal;
    function scenario_PendingWithdrawals() internal;
    function scenario_MultipleUsers() internal;
}
```

### API Test Fixtures (conftest.py)

```python
@pytest.fixture
def mock_blockchain():
    """Mock blockchain RPC responses"""
    
@pytest.fixture
def seeded_db(db_session):
    """Database with standard test data"""
    
@pytest.fixture
def api_client(seeded_db):
    """FastAPI test client with seeded data"""
```

---

## CI/CD Workflows

### contracts.yml
- Builds and compiles contracts
- Runs unit, integration, fuzz, and invariant tests
- Generates coverage reports (85% threshold)
- Runs gas benchmarks

### backend.yml
- Sets up Python environment
- Runs pytest with coverage
- Type checking with mypy

### mobile.yml
- Builds mobile app
- Runs Maestro E2E tests

### full-ci.yml
- Orchestrates all test suites
- Aggregates coverage reports
- Posts summary to PR comments
- Runs security scans (Slither)

---

## Test Data Management

### Seeding Test Data
```bash
python qa/scripts/seed_test_data.py
```

### Resetting Environment
```bash
bash qa/scripts/reset_env.sh
bash qa/scripts/reset_env.sh --hard  # Full reset including Docker
```

### Test Accounts
See `qa/data/accounts.md` for:
- Manager accounts
- User test accounts
- Protocol addresses
- Token addresses

---

## Key Features

### Test Isolation
- **Foundry:** Fresh EVM state per test
- **Backend:** Auto database setup/teardown
- **Mobile:** Independent flows with `runFlow` dependencies

### Boilerplate Reduction
VaultFixture reduces test setup from ~50 lines to ~3 lines:
```solidity
// Without fixture: 50+ lines of setup
// With fixture:
function test_Deposit() public {
    _deposit(user1, 100_000e6);
    assertEq(vault.balances(user1), 100_000e6);
}
```

### Coverage Tracking
- Component-level breakdown
- Clear status indicators
- Quality gates in CI (85% minimum)

---

## License

MIT License
