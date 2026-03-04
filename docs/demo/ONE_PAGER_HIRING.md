# ShelfOps One-Pager (Hiring)

## Candidate Positioning
Entry-level candidate with production-style ownership across data workflows, forecasting, HITL operations, and MLOps controls.

## What I Built
- Multi-tenant retail backend (FastAPI + SQLAlchemy + workers).
- Forecasting and model lifecycle endpoints (health, history, promotion flows).
- HITL replenishment workflow (approve/edit/reject purchase orders with reason-code logging).
- Feedback loop from operational decisions to model features.
- Reproducible model iteration scripts with JSONL logs and run notes.
- Queue-separated worker runtime with scheduled tasks.

## Why It Matters
- Connects model output to operational actions, not just offline metrics.
- Preserves human control on high-impact decisions.
- Makes model iteration auditable and repeatable.

## Evidence
- Code: `backend/api/v1/routers/*.py`, `backend/workers/*.py`, `backend/ml/*.py`
- Artifacts: `backend/reports/iteration_runs.jsonl`, `backend/models/registry.json`
- Validation: `docs/demo/VALIDATION_GATES.md`

## Role Fit
- ML Engineer: lifecycle orchestration, runtime reliability, deployment safety.
- Applied/Product DS: forecasting quality, experimentation, decision impact.
- Data Analytics: KPI instrumentation and operational analysis pipelines.
