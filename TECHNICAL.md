# ShelfOps Technical Reference

This document explains the engineering shape of ShelfOps. For the product story and evidence boundaries, start with [README.md](./README.md), [CURRENT_STATE.md](./CURRENT_STATE.md), and [CLAIMS.md](./CLAIMS.md).

## Architecture

ShelfOps is a multi-tenant retail decision platform built around one operational loop:

```text
ingest sales / inventory / catalog data
  -> validate readiness and freshness
  -> train or serve demand model
  -> generate replenishment recommendation
  -> capture buyer decision
  -> compute later outcome
  -> feed evidence back into model and policy improvement
```

Core runtime layers:

- `FastAPI`: authenticated API surface for inventory, forecasting, recommendations, integrations, and reporting
- `PostgreSQL + Timescale-style schema`: operational and ML state storage
- `Celery + Redis`: retraining, sync, monitoring, simulation, and scheduled workflows
- `React + TypeScript`: buyer-facing and evidence-facing product surfaces

## Stack

| Layer | Technology | Notes |
|---|---|---|
| API | FastAPI 0.109 | Async request handling, DI, authenticated tenant routing |
| ORM | SQLAlchemy 2.x async | Tenant-scoped DB sessions |
| Database | PostgreSQL 15 | Core operational and ML state |
| Queue | Celery 5 + Redis | Sync, retrain, monitoring, scheduled jobs |
| Forecasting | LightGBM | Active forecasting architecture |
| Validation | Pandera | Data-contract gates |
| Tracking | MLflow | Experiment and artifact tracking |
| Explainability | SHAP | Forecast explanation artifacts |
| Frontend | React 18 + TypeScript + Vite + Tailwind | Product UI and evidence UI |

## Data And Evidence

Active scope:

- `M5 / Walmart` as the primary public forecasting benchmark
- `FreshRetailNet-50K` as the stockout-aware secondary benchmark
- `CSV onboarding` and `Square` as the pilot/product validation paths

Supporting docs:

- [DATA_SOURCES.md](./DATA_SOURCES.md)
- [MODEL_CARD.md](./MODEL_CARD.md)
- [MODEL_CARD_STOCKOUT_APPENDIX.md](./MODEL_CARD_STOCKOUT_APPENDIX.md)

Important boundary:

- benchmark data can support forecasting and simulation rigor
- only real merchant pilot data can support measured business-impact claims

## Backend Surfaces

Primary backend capabilities:

- tenant-scoped product, store, inventory, alert, and forecast APIs
- replenishment recommendation queue/detail/accept/edit/reject endpoints
- recommendation outcome computation with provenance labels
- simulation endpoints for benchmark replay
- CSV validate/ingest/readiness endpoints
- Square mapping preview, mapping confirmation, webhook log, dead-letter, and replay
- model lifecycle, experiment, runtime health, and effectiveness endpoints

Important files:

- `backend/api/main.py`
- `backend/db/models.py`
- `backend/recommendations/service.py`
- `backend/api/v1/routers/replenishment.py`
- `backend/api/v1/routers/data.py`
- `backend/api/v1/routers/integrations.py`
- `backend/api/v1/routers/simulations.py`
- `backend/api/v1/routers/ml_ops.py`
- `backend/api/v1/routers/models.py`

## ML And Policy Layer

Active ML direction:

- LightGBM-first forecasting
- time-based evaluation
- calibrated split-conformal intervals on the active public champion
- segment reporting and promotion evidence
- file-backed champion artifacts plus runtime model-state APIs

Important files:

- `backend/ml/train.py`
- `backend/ml/predict.py`
- `backend/ml/calibration.py`
- `backend/ml/evaluation.py`
- `backend/ml/segments.py`
- `backend/ml/replenishment_simulation.py`
- `backend/ml/dataset_snapshots.py`
- `backend/models/v3/metadata.json`
- `backend/reports/m5_subset20_benchmark.json`
- `backend/reports/m5_subset20_holdout_eval.json`

## Frontend Product Surfaces

Current product-facing pages:

- `frontend/src/pages/ReplenishmentPage.tsx`
- `frontend/src/pages/DataReadinessPage.tsx`
- `frontend/src/pages/PilotImpactPage.tsx`
- `frontend/src/pages/MLOpsPage.tsx`

These pages are intended to show:

- what to order
- whether the tenant is ready to trust the system
- what outcomes have been observed or simulated
- why the current champion model is credible

## Tenant Isolation

Authenticated backend routes should use `get_tenant_db`.

The repo relies on tenant-scoped session context rather than trusting the UI to filter data correctly. This is a core design assumption and should not be bypassed by convenience helpers in authenticated routes.

## Local Development

```bash
docker compose up db redis
(cd backend && PYTHONPATH=. alembic upgrade head)
PYTHONPATH=backend uvicorn api.main:app --reload
PYTHONPATH=backend celery -A workers.celery_app worker --loglevel=info
cd frontend && npm install && npm run dev
```

## Verification

Backend:

```bash
PYTHONPATH=backend pytest backend/tests/ -v
```

Frontend:

```bash
cd frontend && npm run build
```

For task-by-task progress and completion tracking, use:

- [`.codex/ROADMAP.md`](./.codex/ROADMAP.md)
- [`.codex/TASKS.json`](./.codex/TASKS.json)
