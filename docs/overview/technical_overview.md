# ShelfOps Technical Overview

- Last verified date: February 15, 2026
- Audience: engineers, technical hiring managers
- Scope: architecture, capabilities, and current status
- Source of truth: backend code paths and product/engineering docs in active surface

## Architecture

- Backend API and domain services: FastAPI + SQLAlchemy async (`implemented`)
- Worker orchestration: Celery-based retrain/forecast/monitor/sync paths (`implemented`)
- Data layer: PostgreSQL/Timescale pattern + Alembic migrations (`implemented`)
- Frontend: React + TypeScript + Vite (`implemented`)
- Integration adapters: EDI, SFTP, event-stream consumption paths (`implemented`)

## Capability Board

| Capability | Status | Primary code path |
|---|---|---|
| Train/register model lifecycle | `implemented` | `backend/workers/retrain.py`, `backend/ml/arena.py` |
| Runtime forecasts and accuracy loop | `implemented` | `backend/workers/forecast.py`, `backend/workers/monitoring.py` |
| Promotion gate fail-closed policy | `implemented` | `backend/ml/arena.py` |
| Model lifecycle logging (retrain + promotion + effectiveness) | `implemented` | `backend/workers/retrain.py`, model APIs, MLOps tables |
| File model-log parity with runtime DB state | `implemented` | Runtime retrain sync keeps file artifacts aligned with DB/API lifecycle truth |
| Contract profile loading and mapping | `implemented` | `backend/ml/contract_profiles.py`, `backend/ml/contract_mapper.py` |
| Enterprise fixture and pipeline validation | `pilot_validated` | CI and integration test paths |
| Cross-tenant telemetry-calibrated enterprise rollout | `blocked` | non-GA policy |

## Production Boundary

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).

## Current Priority Areas

- CI and runtime reliability hardening: `implemented` and ongoing
- Contract coverage expansion for onboarding variants: `partial`
- API surface consistency and deprecation management: `implemented` with ongoing cleanup
