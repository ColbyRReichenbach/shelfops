# ShelfOps

ShelfOps is an inventory intelligence platform focused on SMB launch-candidate workflows with enterprise-oriented integration design.

## Current Readiness

- Last verified date: February 15, 2026
- Current readiness: pre-production hardening for SMB launch-candidate workflows.
- Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).
- Status taxonomy used across docs: `implemented`, `pilot_validated`, `partial`, `blocked`.

## Capability Snapshot

| Capability | Status | Notes |
|---|---|---|
| Forecast train/register loop | `implemented` | Retrain worker and model registration paths are active in backend code. |
| Runtime forecast and accuracy loop | `implemented` | Forecast generation and accuracy backfill are implemented in worker paths. |
| Promotion gates (business + DS) | `implemented` | Fail-closed policy is enforced in model arena logic. |
| Contract-driven onboarding | `implemented` | Versioned YAML profiles and validation mapping paths are active. |
| Enterprise EDI/SFTP/event integration validation | `pilot_validated` | Deterministic fixture and CI validation are present. |
| Broad enterprise onboarding availability | `blocked` | Non-GA by product policy. |

## Stack (Code-Verified)

- Backend: FastAPI, SQLAlchemy async, Celery
- Data: PostgreSQL/Timescale pattern, Alembic, Redis
- Streaming/integration: Redpanda/Kafka-compatible flow, EDI, SFTP adapters
- ML: XGBoost/LSTM training paths, metrics contract, model lifecycle APIs
- Frontend: React + TypeScript + Vite

## Docs Start Here

- Documentation index: `docs/README.md`
- Executive overview: `docs/overview/executive_overview.md`
- Technical overview: `docs/overview/technical_overview.md`
- Production readiness: `docs/product/production_readiness.md`
- API contracts: `docs/engineering/api_contracts.md`

## Quick Verification Commands

```bash
# Backend checks
PYTHONPATH=backend python3 -m pytest backend/tests -q
ruff check backend/ --config pyproject.toml
ruff format --check backend/ --config pyproject.toml

# Frontend checks
npm --prefix frontend run lint
npm --prefix frontend run build

# Docs checks
bash scripts/validate_docs.sh
```

## Positioning

- SMB shipping target: practical onboarding and decision workflows first.
- Enterprise posture: integration architecture and validation depth are present, but onboarding remains non-GA.

## Boundaries

- Public datasets are used for development and evaluation workflows.
- Live tenant behavior must be calibrated from tenant telemetry and validated onboarding flows.
- This repository does not claim broad enterprise production availability.
