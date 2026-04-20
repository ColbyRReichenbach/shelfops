# ShelfOps

ShelfOps is an inventory decision control plane for SMB and mid-market retailers.
It connects POS, inventory, supplier, and purchase-order data; trains auditable
demand models; generates human-reviewed replenishment recommendations; and measures
whether those recommendations reduce stockout risk, overstock exposure, forecast
error, and buyer workload.

## Source Of Truth

All planning and execution should follow:

- `.codex/ROADMAP.md` — product + engineering specification
- `.codex/TASKS.json` — phased implementation plan and acceptance criteria

The old `.claude` planning layer is superseded and should not be used for roadmap
decisions.

## Current Direction

Primary target state:

- pilot-ready inventory decision platform
- benchmark-backed forecast evidence
- replenishment-first product surface
- measured recommendation outcomes
- coherent MLOps evidence with explicit provenance
- clean public repo with truthful claims

Primary workflow to build and prove:

```text
real data ingest
  -> data validation / readiness
  -> demand forecast + uncertainty
  -> stockout / overstock risk
  -> replenishment recommendation
  -> buyer accept/edit/reject
  -> actual outcome arrives
  -> measured business impact
  -> model / policy improvement
```

## Stack

- Python 3.11, FastAPI, PostgreSQL, Redis, Celery
- ML: LightGBM-first forecasting, evaluation, registry, explainability
- Frontend: React 18, TypeScript, Tailwind CSS, Recharts
- Infra: Docker Compose local runtime

## Critical Conventions

- Use `get_tenant_db` for authenticated routes
- Keep tenant/session naming consistent with actual code and docs
- No random train/test splits for time-series work
- Every ML/user-facing metric must include provenance:
  `measured`, `estimated`, `simulated`, `benchmark`, `provisional`, or `unavailable`
- Do not use synthetic/demo data for performance claims unless explicitly labeled
- Do not leave active champion metadata pointing at legacy artifacts
- Schema changes require Alembic migrations

## Forbidden

- Unsupported business-impact claims
- Silent blending of benchmark evidence and real pilot evidence
- Heuristic uncertainty presented as calibrated without a label
- Hardcoded tenant UUIDs where shared constants/utilities exist
- `SELECT *` in production queries

## Run Commands

```bash
PYTHONPATH=backend uvicorn api.main:app --reload
PYTHONPATH=backend pytest backend/tests/ -v
cd frontend && npm run dev
docker compose up db redis
PYTHONPATH=backend alembic upgrade head
```

## Execution Protocol

For roadmap work:

1. Read `.codex/ROADMAP.md` and the relevant phase/task in `.codex/TASKS.json`
2. Confirm current code/runtime state before changing anything
3. Implement against the active acceptance criteria
4. Add or update tests with the change
5. Run the relevant verification commands
6. Keep docs and claims aligned with the actual implementation state

## Repo Goals

Near-term execution priority should follow the new phased plan:

1. Repo truth reset
2. Focused benchmark evidence and model reset
3. Replenishment decision loop
4. Simulation and impact evidence
5. Integration hardening
6. Frontend productization
