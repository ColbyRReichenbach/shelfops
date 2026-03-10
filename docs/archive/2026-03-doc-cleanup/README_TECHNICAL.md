# ShelfOps (Technical Overview)

## Context

ShelfOps is a multi-tenant inventory intelligence platform built around SMB launch-candidate workflows with enterprise-oriented integration architecture.

## Product Intent

- Forecast demand with reproducible model lifecycle controls.
- Detect inventory/anomaly risks and support human-in-the-loop operations.
- Support contract-driven onboarding across heterogeneous source schemas.
- Operate scheduled sync, forecast, retrain, and monitoring loops by tenant.

## Architecture at a Glance

- Backend: FastAPI + SQLAlchemy (async)
- Data layer: PostgreSQL/Timescale-oriented models, Alembic migrations
- Workers: Celery tasks for retraining/monitoring/sync workflows
- Frontend: React + TypeScript + Vite
- Quality gates: pytest, ruff, eslint, TypeScript build checks

## Current Readiness

Current readiness is pre-production hardening for SMB launch-candidate workflows.

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).

## Technical Strengths

- Demand forecasting and champion/challenger promotion gates
- Backtesting, effectiveness APIs, and runtime health endpoints
- Inventory, purchase-order, alert, anomaly, and outcome workflows
- Contract profiles, mapping, and data-quality validation gates
- CI coverage for backend, frontend, Postgres parity, and integration suites

## Active Gaps

- Broad enterprise onboarding availability is blocked by policy.
- Square normalization/mapping depth expansion remains partial.
- Frontend bundle optimization remains pending.
- Additional tenant telemetry depth is needed for stronger model confidence.

## Reference Docs

- Root summary: `README.md`
- Documentation index: `docs/README.md`
- Production readiness: `docs/product/production_readiness.md`
- Known issues: `docs/product/known_issues.md`
- API contracts: `docs/engineering/api_contracts.md`
- Roadmap: `docs/product/roadmap.md`
