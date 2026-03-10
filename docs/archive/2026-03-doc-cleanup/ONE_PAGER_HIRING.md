# ShelfOps One-Pager (Hiring)

## Candidate Positioning
Entry-level to mid-level candidate with production-style ownership across data workflows, forecasting, HITL operations, MLOps controls, and backend platform design.

## What I Built
- Multi-tenant retail backend (FastAPI + SQLAlchemy + workers).
- Forecasting and model lifecycle endpoints (health, history, promotion flows).
- HITL replenishment workflow (approve/edit/reject purchase orders with reason-code logging).
- Feedback loop from operational decisions to model features.
- Reproducible model iteration scripts with JSONL logs and run notes.
- Queue-separated worker runtime with scheduled tasks.
- Enterprise-style integration surface (EDI, SFTP, event-stream) around an SMB-focused product workflow.

## Why It Matters
- Built from 4+ years of direct retail operations context, not from a generic ML benchmark problem.
- Connects model output to operational actions, not just offline metrics.
- Preserves human control on high-impact decisions.
- Makes model iteration auditable and repeatable.
- Demonstrates "project for enterprise, product for SMB" thinking: simple buyer workflow backed by serious systems design.

## Evidence
- Code: `backend/api/v1/routers/*.py`, `backend/workers/*.py`, `backend/ml/*.py`
- Artifacts: `backend/reports/iteration_runs.jsonl`, `backend/models/registry.json`
- Demo sign-off: `docs/demo/DEMO_SIGNOFF_CHECKLIST.md`

## Role Fit
- ML Engineer: lifecycle orchestration, runtime reliability, deployment safety.
- Applied/Product DS: forecasting quality, experimentation, decision impact.
- Data / Analytics Engineer: contracts, ingestion, KPI instrumentation, and operational analysis pipelines.
