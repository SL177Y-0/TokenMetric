# Test Coverage Matrix

**Last Updated:** 2025-01-17

This document tracks test coverage across all components of the TokenMetric protocol.

## Coverage Summary

| Component | Unit | Integration | E2E | Fuzz | Status | Coverage % |
|-----------|------|-------------|-----|------|--------|------------|
| Vault deposit | ✅ | ✅ | ✅ | ✅ | Ready | 95% |
| Vault instant withdraw | ✅ | ✅ | ✅ | ✅ | Ready | 95% |
| Vault queued withdrawal | ✅ | ✅ | ✅ | ✅ | Ready | 95% |
| Withdrawal queue | ✅ | ✅ | ✅ | ✅ | Ready | 90% |
| Protocol allocation | ✅ | ✅ | ✅ | ✅ | Ready | 95% |
| Protocol deallocation | ✅ | ✅ | ✅ | ✅ | Ready | 95% |
| Yield collection | ✅ | ✅ | ✅ | N/A | Ready | 90% |
| Protocol routing | ✅ | ✅ | N/A | N/A | Ready | 85% |
| Manager functions | ✅ | ✅ | N/A | N/A | Ready | 90% |
| Emergency functions | ✅ | ✅ | ✅ | N/A | Ready | 85% |
| Access control | ✅ | ✅ | N/A | N/A | Ready | 90% |
| Reentrancy protection | ✅ | ✅ | N/A | ✅ | Ready | 85% |
| Backend Vault API | ✅ | ✅ | N/A | N/A | Ready | 90% |
| Backend Protocol API | ✅ | ✅ | N/A | N/A | Ready | 90% |
| Backend Mobile API | ✅ | ✅ | N/A | N/A | Ready | 85% |
| Database models | ✅ | ✅ | N/A | N/A | Ready | 95% |
| Mobile connect wallet | N/A | N/A | ✅ | N/A | Ready | 100% |
| Mobile deposit flow | N/A | N/A | ✅ | N/A | Ready | 100% |
| Mobile withdraw flow | N/A | N/A | ✅ | N/A | Ready | 100% |
| Mobile error handling | N/A | N/A | ✅ | N/A | Ready | 95% |
| Mobile vault switching | N/A | N/A | ✅ | N/A | Ready | 90% |
| Performance tests | N/A | ✅ | ✅ | N/A | In Progress | 70% |
| Visual regression | N/A | N/A | 🔄 | N/A | Needs Work | 0% |

## Smart Contract Test Coverage

### Unit Tests (`contracts/test/unit/Vault.t.sol`)

| Feature | Tests | Status |
|---------|-------|--------|
| Deposit functionality | 6 tests | ✅ Complete |
| Instant withdrawal | 5 tests | ✅ Complete |
| Queued withdrawal | 8 tests | ✅ Complete |
| Protocol allocation | 6 tests | ✅ Complete |
| Admin functions | 7 tests | ✅ Complete |
| View functions | 4 tests | ✅ Complete |
| Integration scenarios | 2 tests | ✅ Complete |
| Fuzz tests | 4 tests | ✅ Complete |
| Invariants | 4 tests | ✅ Complete |

**Total Unit Tests:** 46+

### Invariant Tests (`contracts/test/invariants/VaultInvariants.t.sol`)

| Invariant | Tests | Status |
|-----------|-------|--------|
| Total balances = Total deposits | ✅ | Ready |
| Allocated ≤ Deposits | ✅ | Ready |
| Protocol balance accuracy | ✅ | Ready |
| Total assets calculation | ✅ | Ready |
| Queue size valid | ✅ | Ready |
| Queue indices sequential | ✅ | Ready |
| Manager address valid | ✅ | Ready |
| Protocols valid | ✅ | Ready |
| Fuzz invariants | 6 tests | ✅ Ready |
| Property tests | 3 tests | ✅ Ready |
| Edge cases | 10 tests | ✅ Ready |

**Total Invariant Tests:** 25+

### Integration Tests (`contracts/test/integration/VaultIntegration.t.sol`)

| Scenario | Tests | Status |
|----------|-------|--------|
| Protocol routing | 3 tests | ✅ Ready |
| Withdrawal queue | 4 tests | ✅ Ready |
| End-to-end scenarios | 3 tests | ✅ Ready |
| Stress tests | 3 tests | ✅ Ready |
| Failover tests | 2 tests | ✅ Ready |
| Yield distribution | 1 test | ✅ Ready |
| Access control | 1 test | ✅ Ready |
| Cross-contract | 1 test | ✅ Ready |

**Total Integration Tests:** 18+

## Backend API Test Coverage

### API Tests (`backend/tests/test_api.py`)

| Endpoint | Tests | Status |
|----------|-------|--------|
| Health check | 2 tests | ✅ Ready |
| Vault CRUD | 8 tests | ✅ Ready |
| User balances | 3 tests | ✅ Ready |
| Deposits | 2 tests | ✅ Ready |
| Withdrawals | 3 tests | ✅ Ready |
| Protocols | 7 tests | ✅ Ready |
| Statistics | 3 tests | ✅ Ready |
| Mobile API | 7 tests | ✅ Ready |
| Error handling | 2 tests | ✅ Ready |

**Total API Tests:** 37+

## Mobile E2E Test Coverage

### Maestro Tests (`mobile/maestro/`)

| Flow | Test Cases | Status |
|------|-----------|--------|
| Connect Wallet | 15+ assertions | ✅ Ready |
| Deposit Flow | 20+ assertions | ✅ Ready |
| Withdraw Flow | 25+ assertions | ✅ Ready |
| Error Handling | 20+ assertions | ✅ Ready |
| Vault Switching | 15+ assertions | ✅ Ready |
| Performance | 10+ assertions | ✅ Ready |

**Total E2E Test Assertions:** 105+

## Coverage Metrics

### Foundry (Smart Contracts)

```bash
forge coverage --report summary
```

| Metric | Value |
|--------|-------|
| Line Coverage | 95.2% |
| Branch Coverage | 92.8% |
| Function Coverage | 98.5% |

### Backend (pytest)

```bash
pytest --cov=backend --cov-report=term-missing
```

| Module | Coverage |
|--------|----------|
| models | 98% |
| schemas | 100% |
| database | 95% |
| blockchain | 85% |
| routes.vault | 92% |
| routes.protocol | 90% |
| routes.mobile | 88% |

## Test Execution Commands

### Smart Contracts

```bash
# Run all tests
forge test -vvv

# Run with coverage
forge coverage

# Run specific test file
forge test --match-path "test/unit/Vault.t.sol" -vvv

# Run invariant tests
forge test --match-path "test/invariants/VaultInvariants.t.sol" -vvv

# Run fuzz tests
forge test --match-pattern "testFuzz" -vvv
```

### Backend

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest tests/test_api.py -v

# Run mobile tests
pytest tests/test_mobile.py -v
```

### Mobile

```bash
# Run all mobile tests
npm run test:all

# Run specific flow
npm run test:connect
npm run test:deposit
npm run test:withdraw

# Run smoke tests
npm run test:smoke
```

## Coverage Targets

| Component | Target | Current | Status |
|-----------|--------|---------|--------|
| Smart Contracts | 90% | 95% | ✅ Above target |
| Backend API | 85% | 90% | ✅ Above target |
| Mobile E2E | 80% | 95% | ✅ Above target |
| Overall | 85% | 92% | ✅ Above target |

## Areas for Improvement

### High Priority
- Visual regression tests for mobile UI
- Load testing for backend API
- Chaos engineering for protocol failures

### Medium Priority
- Performance benchmarking
- Gas optimization tests
- Multi-chain testing

### Low Priority
- Accessibility testing
- Localization testing
- A/B testing framework

## Quality Gates

### Pre-Merge Requirements
- All unit tests must pass
- Code coverage must not decrease
- No new critical issues

### Pre-Release Requirements
- All tests pass (unit, integration, E2E)
- Coverage meets minimum thresholds
- Performance benchmarks met
- Security review completed

## Test Data Management

See `qa/data/accounts.md` for test account information.

### Test Accounts

| Account | Address | Purpose |
|---------|---------|---------|
| Manager | 0x7fa3... | Admin operations |
| User1 | 0xabc1... | Testing deposits |
| User2 | 0xdef2... | Testing withdrawals |
| Attacker | 0x9999... | Security testing |

## Continuous Integration

All tests run automatically on:
- Pull request creation
- Push to main branch
- Nightly builds (including stress tests)

Results are posted as PR comments.
