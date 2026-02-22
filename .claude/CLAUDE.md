# ShelfOps

AI-powered retail inventory intelligence platform. Predicts stockouts 2-3 days early using POS/ERP data, then acts via dynamic reorder optimization and automated PO workflows. Multi-tenant SaaS (customer isolation via RLS).

**Current Phase**: Phase 3 — Testing & Quality

## Stack

- Python 3.11, FastAPI 0.109, PostgreSQL 15 + TimescaleDB, Redis, Celery
- ML: LSTM + XGBoost ensemble (65/35 weights), MLflow, SHAP, Pandera
- Frontend: React 18, TypeScript, Tailwind CSS, Recharts
- Infra: Docker Compose (local dev), GCP Cloud Run (target)

## Run Commands

```bash
PYTHONPATH=backend uvicorn api.main:app --reload   # API on :8000
PYTHONPATH=backend pytest backend/tests/ -v        # Tests
cd frontend && npm run dev                          # UI on :5173
docker-compose up db redis                          # Infrastructure
PYTHONPATH=backend alembic upgrade head             # DB migrations
```

## Critical Conventions

- Use `get_tenant_db` (not `get_db`) for all authenticated routes
- Use `DEV_CUSTOMER_ID` constant — never hardcode UUID strings
- Time-series: always time-based CV split, never `train_test_split(shuffle=True)`
- Pandera validation at 3 gates: raw data → features → predictions
- Exclude TimescaleDB indexes from Alembic autogenerate

## Forbidden

- `get_db` in authenticated routers → breaks tenant isolation
- Hardcoded customer UUIDs → use `DEV_CUSTOMER_ID` from `core.constants`
- Random train/test splits on time-series data
- Schema changes without an Alembic migration
- `SELECT *` in production queries

## Key Files

- `backend/api/main.py` — FastAPI entry point
- `backend/db/models.py` — all 27 SQLAlchemy models
- `backend/ml/features.py` — `detect_feature_tier()`, 27/45-feature architecture
- `backend/inventory/optimizer.py` — dynamic ROP + EOQ decision engine
- `backend/workers/celery_app.py` — 12 scheduled jobs
- `docs/MLOPS_STANDARDS.md` — MLflow, SHAP, Pandera conventions
- `docs/ROADMAP.md` — 8-week plan, phase status
