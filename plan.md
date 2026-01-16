# TokenMetric Assignment – End-to-End Architecture and Delivery Plan

This plan is synthesized from the assignment brief and vetted against best practices from:
- Foundry tests and cheatcodes (snapshots, gas, coverage, CI) — Foundry Book and toolchain docs
- Maestro E2E flows and CI — Maestro docs and CI examples
- Pytest + FastAPI fixtures, DB isolation, HTTP mocking — community and reference guides

## 1) Objectives and Success Criteria
- Objective: Build a cohesive, reusable test infrastructure spanning smart contracts (Foundry), backend APIs (FastAPI/pytest), and mobile UI (Maestro/Detox) with robust fixtures, isolation, coverage, and CI.
- Success Criteria:
  - Reusable fixtures that reduce per-test setup code >50% and enable composition.
  - Deterministic, isolated tests (idempotent, parallel-friendly) using snapshot/rollback strategies.
  - Actionable coverage matrix and thresholds; CI fails on regressions; PR summary posted.
  - E2E mobile and API tests connected to seeded data or mocks; clear error and network handling.

## 2) High-Level Architecture
Monorepo with distinct packages and shared tooling:
- contracts: Foundry-based Solidity project (fixtures, unit, integration, fuzz, invariant tests).
- backend: FastAPI app with pytest, seeded DB, RPC mocks, and deterministic time.
- mobile: React Native app (or sample) with Maestro flows (Detox acceptable alternative).
- qa/testdata: Seeding, reset, and data catalogs for local/testnet.
- infra: Docker Compose for local stack; GitHub Actions workflows; environment templates.
- .github/workflows: CI pipelines for domain suites and full aggregation.

Test isolation strategy:
- Contracts: vm.snapshotState()/vm.revertToState, per-test deployments in setUp, cheatcodes for callers and time.
- Backend: Per-test DB transaction rollback, deterministic seeds/timestamps, RequestsMock for RPC.
- Mobile: Subflows and tagged flows; app launched with test build profile and network+wallet mocks.

## 3) Repository Structure
```
/
├─ contracts/
│  ├─ src/
│  ├─ lib/
│  ├─ test/
│  │  ├─ fixtures/
│  │  │  └─ VaultFixture.sol
│  │  ├─ unit/
│  │  ├─ integration/
│  │  ├─ fuzz/
│  │  └─ invariant/
│  ├─ script/
│  └─ foundry.toml
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  ├─ services/
│  │  ├─ models/
│  │  └─ db/
│  ├─ tests/
│  │  ├─ conftest.py
│  │  ├─ api/
│  │  └─ integration/
│  ├─ pyproject.toml
│  └─ requirements-dev.txt
├─ mobile/
│  ├─ app/
│  ├─ maestro/
│  │  ├─ connect_wallet.yaml
│  │  ├─ deposit_flow.yaml
│  │  └─ error_handling.yaml
│  ├─ detox/
│  └─ package.json
├─ qa/
│  ├─ scripts/
│  │  ├─ seed_testnet_wallets.ts
│  │  ├─ reset_env.sh
│  │  └─ mock_rpc_server.py
│  └─ data/
│     ├─ accounts.md
│     └─ fixtures.json
├─ infra/
│  ├─ docker-compose.yml
│  ├─ .env.example
│  └─ README.md
├─ coverage/
│  └─ matrix.md (generated or tracked)
├─ .github/
│  └─ workflows/
│     ├─ contracts.yml
│     ├─ backend.yml
│     ├─ mobile.yml
│     └─ full-ci.yml
└─ README.md
```

## 4) Scope and Detailed Implementation
### 4.1 Smart Contracts (Foundry) – Fixtures and Tests
- Stack: forge/cast/anvil; forge-std; gas snapshot and coverage reports.
- Core fixture (`test/fixtures/VaultFixture.sol`):
  - Deploy TMVault, MockUSDC, MockProtocolA/B; grant roles; fund users; set adapters.
  - Helpers: `_deposit(user, amount)`, `_simulateYield(bps)`.
  - Isolation: optionally capture a `snapshotId = vm.snapshotState()` at end of `setUp()` and revert in `tearDown()` or in each test.
- Unit tests: deposit/withdraw happy paths; access control; rounding/fees; event emission.
- Integration: protocol routing, rebalances, pausing, withdrawal queue semantics.
- Fuzz: randomized deposit/withdraw sequences; bounds checking; re-entrancy guards (expectRevert patterns).
- Invariant: solvency/accounting invariants (sum of shares <= underlying + accrual); no loss on round-trip.
- Coverage & gas:
  - `forge coverage --report lcov` (export lcov.info)
  - `forge snapshot --gas-report` or `forge test --gas-report` and optional `--junit` for CI artifacts.

Example fixture (sketch):
```solidity
pragma solidity ^0.8.20;
import "forge-std/Test.sol";
import {TMVault} from "../../src/TMVault.sol";
import {MockUSDC} from "../mocks/MockUSDC.sol";
import {MockProtocol} from "../mocks/MockProtocol.sol";

contract VaultFixture is Test {
    TMVault vault;
    MockUSDC usdc;
    MockProtocol protocolA;
    MockProtocol protocolB;

    address manager = makeAddr("manager");
    address user1 = makeAddr("user1");
    address user2 = makeAddr("user2");

    function setUp() public virtual {
        usdc = new MockUSDC();
        vault = new TMVault(address(usdc), manager);
        protocolA = new MockProtocol(address(usdc));
        protocolB = new MockProtocol(address(usdc));
        usdc.mint(user1, 1_000_000e6);
        usdc.mint(user2, 1_000_000e6);
        vm.prank(manager);
        vault.setProtocols(address(protocolA), address(protocolB));
    }

    function _deposit(address user, uint256 amount) internal {
        vm.startPrank(user);
        usdc.approve(address(vault), amount);
        vault.deposit(amount, user);
        vm.stopPrank();
    }

    function _simulateYield(uint256 bps) internal {
        protocolA.accrue(bps);
        protocolB.accrue(bps);
    }
}
```

### 4.2 Backend API (FastAPI) – Fixtures and Tests
- Stack: FastAPI, SQLAlchemy, pytest, responses (RequestsMock) for RPC, TestClient/HTTPX.
- Fixtures (`tests/conftest.py`):
  - DB session per test with transaction rollback; schema create/drop at session-scope.
  - `mock_blockchain` using `responses.RequestsMock()` for `RPC_URL` calls.
  - `seeded_db` to insert standard data (protocols, snapshots, users, balances).
  - `api_client` as `TestClient(app)` or async `httpx.AsyncClient` when needed.
- Tests:
  - Unit: services, parsers, accounting.
  - Integration: API routes invoking services with DB.
  - Bridge tests: ABI decoding, RPC schemas (mocked).
- Coverage: `pytest --cov=app --cov-report=xml --cov-fail-under=85`.

Example fixture (sketch):
```python
import pytest
from fastapi.testclient import TestClient
import responses
from app.main import app

RPC_URL = "https://rpc.example"  # injected via settings in real code

@pytest.fixture
def mock_blockchain():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.POST, RPC_URL, json={"result": "0x1"})
        yield rsps

@pytest.fixture
def seeded_db(db_session):
    # insert protocols, snapshots, users, balances
    return db_session

@pytest.fixture
def api_client(seeded_db):
    return TestClient(app)
```

### 4.3 Mobile/UI E2E (Maestro preferred, Detox acceptable)
- Prefer Maestro for declarative YAML and flake-tolerance; Detox is fine if RN-native is preferred.
- Subflows (per assignment):
  - connect_wallet.yaml: launch, connect, assert address + USDC balance.
  - deposit_flow.yaml: navigate, enter amount, approve, deposit, assert success + updated balance.
  - error_handling.yaml: insufficient funds error; wrong network triggers prompt.
- Wallet/network mocking:
  - Test build profile points API base to mock backend; provide WalletConnect stub or mock provider.
- Optional visual regression: screenshot capture + pixel-diff against baselines.

Example flow (sketch):
```yaml
appId: com.tokenmetric.dev
---
- launchApp
- tapOn: "Connect Wallet"
- runFlow: wallet/connect_stub.yaml
- assertVisible:
    - "0x"
    - "USDC"
```

## 5) Test Data Management
- qa/scripts:
  - seed_testnet_wallets.ts: use ethers.js + anvil or faucet integration to fund dev keys.
  - reset_env.sh: compose down -v, clear DB, restart local services and chain.
  - mock_rpc_server.py: deterministic JSON-RPC responses for mobile/backend tests.
- qa/data:
  - accounts.md: test accounts (never real funds), roles, addresses.
  - fixtures.json: canonical IDs, amounts, expected results.

## 6) Coverage Tracking and Matrix
- Per-suite outputs:
  - Contracts: lcov.info from `forge coverage`.
  - Backend: coverage.xml from pytest.
  - Mobile: scenario coverage mapping (YAML-defined features) -> matrix rows.
- coverage/matrix.md (generated in CI) with columns: Unit | Integration | E2E | Status for components:
  - Vault deposit/withdraw, Withdrawal queue, Protocol routing, Mobile connect/deposit/errors.
- CI aggregates and posts PR comment with deltas; regressions fail the build.

## 7) CI (GitHub Actions)
### 7.1 Contracts (.github/workflows/contracts.yml)
- Steps: checkout, setup Foundry, forge install, forge test + coverage, upload artifacts.
```yaml
name: Contracts
on:
  push:
    paths: [ 'contracts/**' ]
  pull_request:
    paths: [ 'contracts/**' ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: foundry-rs/foundry-toolchain@v1
        with:
          version: nightly
      - name: Install deps
        run: forge install
      - name: Test
        run: forge test -vvv
      - name: Coverage
        run: forge coverage --report lcov && mv lcov.info contracts.lcov.info
      - uses: actions/upload-artifact@v4
        with:
          name: contracts-coverage
          path: contracts.lcov.info
```

### 7.2 Backend (.github/workflows/backend.yml)
- Steps: setup Python, services (Postgres), pytest w/ coverage, upload artifact.
```yaml
name: Backend
on:
  push:
    paths: [ 'backend/**' ]
  pull_request:
    paths: [ 'backend/**' ]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        ports: ['5432:5432']
        options: >-
          --health-cmd="pg_isready -U postgres"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install
        run: |
          python -m pip install -U pip
          pip install -r backend/requirements-dev.txt
      - name: Test
        working-directory: backend
        run: pytest --cov=app --cov-report=xml
      - uses: actions/upload-artifact@v4
        with:
          name: backend-coverage
          path: backend/coverage.xml
```

### 7.3 Mobile (.github/workflows/mobile.yml)
- Maestro local emulator or Maestro Cloud; upload reports.
```yaml
name: Mobile E2E
on:
  push:
    paths: [ 'mobile/**' ]
  pull_request:
    paths: [ 'mobile/**' ]
jobs:
  e2e:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Node
        uses: actions/setup-node@v4
        with: { node-version: '20' }
      - name: Install Maestro
        run: curl -Ls "https://get.maestro.mobile.dev" | bash
      - name: Install deps
        working-directory: mobile
        run: npm ci
      - name: Run Maestro flows
        working-directory: mobile
        run: |
          ~/.maestro/bin/maestro test maestro/connect_wallet.yaml
          ~/.maestro/bin/maestro test maestro/deposit_flow.yaml
          ~/.maestro/bin/maestro test maestro/error_handling.yaml
      - uses: actions/upload-artifact@v4
        with:
          name: mobile-reports
          path: mobile/reports/**
```

### 7.4 Full Aggregation (.github/workflows/full-ci.yml)
- Needs: contracts, backend, mobile jobs; download artifacts; compute matrix; post PR comment and enforce thresholds.
- Use `actions/github-script` or a small script to merge coverage and update `coverage/matrix.md`.

## 8) Environments and Tooling
- Local dev via Docker Compose (postgres, mock-rpc, anvil, backend API, optional mobile dev server).
- Manage .env.example; GH environment secrets for CI.
- Tool versions: Node 20, Python 3.11, Foundry nightly, Android SDK; cache dependencies in CI.
- RPC strategy: Prefer mock RPC server for determinism; testnet optional for manual checks.

## 9) Developer Experience
- Makefile or npm scripts:
  - `make test-contracts`, `make test-backend`, `make test-mobile`, `make coverage-aggregate`.
  - `make dev-up` / `make dev-down` for Compose.
- Pre-commit hooks:
  - solhint/formatter, black/isort/mypy, eslint/prettier.

## 10) Quality Gates and Thresholds
- Coverage thresholds: Contracts >=85%, Backend >=85%, Mobile core flows 100% executed.
- Linting mandatory.
- Mobile flake mitigation: deterministic network stubs, disable animations, retries, and tagged smoke sets on PR vs full on main.

## 11) Milestones
- M1 (Day 1–2): Repo skeleton; Docker Compose; hello-world tests; basic CI.
- M2 (Day 3–4): Core fixtures (VaultFixture, DB seeders, Maestro flows); unit tests green; initial coverage.
- M3 (Day 5): Integration + E2E stable; coverage matrix; PR comments; isolation validated.
- Stretch (Day 6+): Fuzz/invariant tests, visual regression, performance, chaos.

## 12) Risks and Mitigations
- Mobile flakiness → testIDs, disable animations, network stubs, retries.
- Nondeterministic chain data → mock RPC + anvil snapshots; `vm.warp` for time.
- CI timeouts → parallelize, cache, smoke vs full matrix, emulator snapshots.

## 13) Stretch Scope (Optional)
- Foundry invariants & fuzz with coverage reporting; gas snapshot diffs with `forge snapshot --check`.
- Visual regression: Maestro screenshots + pixel-diff stored as artifacts.
- Performance: mobile launch time; backend latency (pytest-benchmark/locust).
- Chaos: RPC failures/timeouts; slow network; verify graceful handling and retries.

## 14) Deliverables
- Reusable fixtures across stack with example tests.
- Coverage matrix with automated updates in CI and regression gating.
- CI that posts PR summaries and fails on regressions.
- Test data scripts, reset tooling, and documented test accounts.

## 15) MCP Integration (Optional/Proactive)
- Atlassian MCP: Propose Jira items for TODOs and Confluence pages for fixture architecture and coverage matrix. Will request approval before creating/updating items.
- TestSprite MCP: Optionally generate test plans or summarize coverage reports for review.
- Personal Knowledge MCP: Store lessons learned and fixture recipes for onboarding.
- Exa/Firecrawl MCP: Ad-hoc doc lookups for Foundry/Maestro/pytest nuances.

## 16) Local Setup (Summary)
- Contracts:
  - `curl -L https://foundry.paradigm.xyz | bash && foundryup`
  - `forge install && forge test`
- Backend:
  - Python 3.11; `pip install -r backend/requirements-dev.txt`
  - `docker compose up -d postgres`; `pytest -q`
- Mobile (Maestro):
  - Install Maestro; `npm ci` in mobile/; run YAML flows.

## 17) Acceptance Criteria Checklist
- Fixtures reduce per-test setup by >50% lines vs naive setup.
- All suites deterministic and isolated locally and in CI.
- Coverage matrix shows Ready for core rows (deposit, routing, mobile connect/deposit).
- CI PR comment includes pass/fail summary and coverage deltas; thresholds enforced.
