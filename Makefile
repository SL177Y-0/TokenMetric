# Simple developer convenience targets
.PHONY: test-contracts test-backend test-mobile dev-up dev-down coverage-aggregate

test-contracts:
	cd contracts && forge test -vvv

test-backend:
	cd backend && pytest -q --cov=backend.app --cov-report=term-missing

test-mobile:
	@echo "Run Maestro flows locally (ensure appId is correct)"
	maestro test mobile/maestro/connect_wallet.yaml || true
	maestro test mobile/maestro/deposit_flow.yaml || true
	maestro test mobile/maestro/error_handling.yaml || true

dev-up:
	cd infra && docker compose up -d

dev-down:
	cd infra && docker compose down -v

coverage-aggregate:
	@echo "Aggregate coverage is project-specific; see .github/workflows/full-ci.yml"
