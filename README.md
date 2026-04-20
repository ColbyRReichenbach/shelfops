# ShelfOps

ShelfOps is an inventory decision control plane for SMB and mid-market retailers. It connects sales and inventory data, trains demand models, generates human-reviewed replenishment recommendations, and measures whether those decisions reduce stockout risk, overstock exposure, and buyer workload.

## Product Loop

```text
real data ingest
  -> data validation and readiness
  -> demand forecast and uncertainty
  -> stockout / overstock risk
  -> replenishment recommendation
  -> buyer accept / edit / reject
  -> actual outcome arrives
  -> measured impact and model improvement
```

This is the center of the repo. The backend, frontend, and ML artifacts should all support this loop.

## What Exists Now

ShelfOps already has:

- a multi-tenant FastAPI backend with tenant-scoped database access
- forecasting, alerts, inventory, purchase-order, experiment, and reporting APIs
- a replenishment recommendation backend with accept, edit, reject, and outcome tracking
- benchmark-backed model evidence centered on `M5 / Walmart`
- stockout-aware secondary methodology work on `FreshRetailNet-50K`
- pilot ingestion paths centered on `CSV onboarding` and `Square`
- frontend product surfaces for `Replenishment`, `Data Readiness`, `Pilot Impact`, and `Model Evidence`

Current maturity is still pre-pilot. This repo should be read as a credible pilot-ready buildout path, not as proof of broad production deployment or measured merchant ROI.

## Evidence Boundaries

- Benchmark evidence is not pilot evidence.
- Simulated benchmark replay is not measured merchant impact.
- Real merchant outcome claims require real merchant data.
- Every business metric should be labeled as `measured`, `estimated`, `simulated`, `benchmark`, `provisional`, or `unavailable`.

Use these documents as the public truth surface:

- [CURRENT_STATE.md](./CURRENT_STATE.md)
- [CLAIMS.md](./CLAIMS.md)
- [MODEL_CARD.md](./MODEL_CARD.md)
- [MODEL_CARD_STOCKOUT_APPENDIX.md](./MODEL_CARD_STOCKOUT_APPENDIX.md)
- [DATA_SOURCES.md](./DATA_SOURCES.md)

## Active Scope

Active evidence and product scope:

- `M5 / Walmart` for the primary public forecasting benchmark
- `FreshRetailNet-50K` for stockout/censored-demand methodology
- `CSV onboarding` and `Square` for pilot/product validation

Deferred in the current phase:

- `Shopify`
- broad enterprise ingest breadth as a product claim
- unsupported live-business-impact claims

## Main Product Surfaces

- `Replenishment Queue`: buyer-facing recommendation review and decision workflow
- `Data Readiness`: trainability, freshness, mapping coverage, and unblockers
- `Pilot Impact`: measured or provisional operational outcomes separated from simulated replay evidence
- `Model Evidence`: champion model card, calibration, segment metrics, and promotion evidence

## Local Run

```bash
docker-compose up db redis
PYTHONPATH=backend alembic upgrade head
PYTHONPATH=backend uvicorn api.main:app --reload
PYTHONPATH=backend celery -A workers.celery_app worker --loglevel=info
cd frontend && npm install && npm run dev
```

Backend tests:

```bash
PYTHONPATH=backend pytest backend/tests/ -v
```

Frontend build check:

```bash
cd frontend && npm run build
```

## Roadmap

The active implementation roadmap lives in:

- [`.codex/ROADMAP.md`](./.codex/ROADMAP.md)
- [`.codex/TASKS.json`](./.codex/TASKS.json)

The repo should be evaluated against that roadmap, not against older demo-specific planning artifacts.

## Pilot Packaging

- [PILOT_PLAYBOOK.md](./PILOT_PLAYBOOK.md)
- [docs/templates/CASE_STUDY_TEMPLATE.md](./docs/templates/CASE_STUDY_TEMPLATE.md)

These are included to define how ShelfOps should run a measured pilot and how future outcomes should be documented without overstating what the repo has already proven.
