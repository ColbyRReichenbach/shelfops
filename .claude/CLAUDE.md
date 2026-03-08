# ShelfOps

AI-powered retail inventory intelligence platform. Predicts stockouts 2-3 days early using POS/ERP data, then acts via dynamic reorder optimization and automated PO workflows. Multi-tenant SaaS (customer isolation via RLS).

**Current Phase**: Phase 3 — Demo Readiness (Sprint 3 in progress)

**Active Goal**: Shepherd.js guided tours (WS-5) — buyer tour first, then technical tour, then /welcome route.
See `.claude/DEMO_PLAN.md` for the full plan, P0 checklist, and session handoff state.
See `.claude/PROJECT_PLAN.md` for workstream status and sprint progress.
Start every session by reading DEMO_PLAN.md and running the test suite to confirm baseline.

## Stack

- Python 3.11, FastAPI 0.109, PostgreSQL 15 + TimescaleDB, Redis, Celery
- ML: Pure LightGBM (switched from LSTM+XGBoost ensemble); WAPE + MASE metrics; MLflow, SHAP, Pandera
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
- `docs/BRAINSTORM.md` — 25-section strategy doc; §19 has P0/P1/P2 priority framework
- `docs/demo/recruiter_demo_runbook.md` — hiring manager demo (exists)
- `backend/scripts/run_recruiter_demo.py` — recruiter demo orchestrator (exists)

## Test Baseline

Current passing: **497 tests**. Every session must end at ≥ 497 passing.
Command: `PYTHONPATH=backend pytest backend/tests/ -v --tb=short 2>&1 | tail -20`

## Demo Work Protocol

For every P0/P1 item in `.claude/DEMO_PLAN.md`:
1. Run `/spec` to draft the spec before touching code
2. Implement with tests alongside
3. Run `/test-loop` until green
4. Commit to `claude/analyze-codebase-FEu8K`, push
5. Check off the item in `DEMO_PLAN.md §9`
