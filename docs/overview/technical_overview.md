# ShelfOps Technical Overview

- Last verified date: April 29, 2026
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
| M5 benchmark workspace | `implemented` | `backend/scripts/bootstrap_benchmark_workspace.py` |
| Benchmark evidence sync | `implemented` | `backend/scripts/sync_benchmark_evidence_to_db.py` |
| Runtime forecasts and accuracy loop | `implemented` | `backend/workers/forecast.py`, `backend/workers/monitoring.py` |
| Anomaly champion/shadow persistence | `implemented` | `backend/db/models.py`, `backend/ml/anomaly_feedback.py`, model evidence API |
| Forecast and anomaly experiment specs | `implemented` | `backend/ml/experiment_specs.py`, `backend/api/v1/routers/experiments.py` |
| Promotion gate fail-closed policy | `implemented` | `backend/ml/arena.py` |
| Model lifecycle logging (retrain + promotion + effectiveness) | `implemented` | `backend/workers/retrain.py`, model APIs, MLOps tables |
| File model-log parity with runtime DB state | `implemented` | Runtime retrain sync keeps file artifacts aligned with DB/API lifecycle truth |
| Contract profile loading and mapping | `implemented` | `backend/ml/contract_profiles.py`, `backend/ml/contract_mapper.py` |
| Enterprise fixture and pipeline validation | `implemented` | EDI ingest worker coverage, Kafka event-stream wiring, and deterministic integration tests exist as architecture proof. |
| Cross-tenant telemetry-calibrated enterprise rollout | `blocked` | non-GA policy |

## Production Boundary

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).

Benchmark evidence is not production merchant evidence. M5 supports the forecast
model story, FreshRetailNet supports anomaly/stockout methodology, and CSV/Square
are the only current paths to measured pilot claims.

## Current Priority Areas

- CI and runtime reliability hardening: `implemented` and ongoing
- Contract coverage expansion for onboarding variants: `partial`
- API surface consistency and deprecation management: `implemented` with ongoing cleanup
