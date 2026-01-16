# TokenMetric Test Infrastructure Monorepo

This repository contains a reference implementation for the TokenMetric assignment: reusable test infrastructure across smart contracts (Foundry), backend APIs (FastAPI/pytest), and mobile UI (Maestro).

- See `plan.md` for the end-to-end plan and architecture.
- Use `Makefile` targets to run tests locally.
- Use `infra/docker-compose.yml` to bring up local services (Postgres, mock RPC).

## Quickstart

- Contracts: `make test-contracts`
- Backend: `make test-backend`
- Mobile (flows placeholder): `make test-mobile`
- Dev services: `make dev-up` / `make dev-down`
