# ShelfOps

ShelfOps is an inventory decision control plane for SMB and mid-market retailers. It connects sales and inventory data, trains demand and anomaly models, generates human-reviewed replenishment recommendations, and records the decision and outcome evidence needed to measure stockout risk, overstock exposure, and buyer workload.

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
- a replenishment recommendation backend with accept, edit, reject, outcome tracking,
  and decision economics for order cost, holding cost, and perishable spoilage risk
- a default benchmark workspace seeded from `M5 / Walmart` sales history
- benchmark-backed model evidence centered on `M5 / Walmart`
- decision-aware experiment reports that connect forecast quality to simulated
  replenishment replay and shadow promotion gates
- stockout-aware anomaly evidence and shadow tracking on `FreshRetailNet-50K`
- pilot ingestion paths centered on `CSV onboarding` and `Square`
- frontend product surfaces for `Replenishment`, `Data Readiness`, `Evidence`, and `Model Lab`

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
- `Model Lab`: champion model card, anomaly evidence, calibration, segment metrics, governed specs, and promotion evidence

## Pre-Pilot Quick Start

For a clean local walkthrough that matches the current product story:

```bash
docker compose up -d db redis redpanda api
./scripts/setup_production.sh
APP_ENV=local DEBUG=true PYTHONPATH=backend python3 backend/scripts/bootstrap_benchmark_workspace.py --wipe-existing
APP_ENV=local DEBUG=true PYTHONPATH=backend python3 backend/scripts/sync_benchmark_evidence_to_db.py
cd frontend && npm run dev
```

That flow creates a deterministic `Production Pilot` tenant with:

- M5/Walmart benchmark sales as the operational example workspace
- simulated inventory/supplier scaffolding explicitly labeled as benchmark support, not merchant evidence
- forecast, accuracy, reorder point, alert, and replenishment queue rows
- FreshRetailNet-backed anomaly champion/challenger evidence and shadow-prediction persistence
- Model Lab experiment spec templates for M5 forecast trials and FreshRetailNet
  anomaly shadow trials; persisted specs are created when a run materializes one
- impact and scenario surfaces with benchmark/provisional/simulated boundaries visible

See [PRE_PILOT_CHECKLIST.md](./PRE_PILOT_CHECKLIST.md) for the readiness standard
to hit before outreach. For Neon or any explicit database target, use the
credential-free reset path in
[docs/operations/benchmark_workspace_reset.md](./docs/operations/benchmark_workspace_reset.md).

## Local Run

```bash
docker compose up db redis
(cd backend && PYTHONPATH=. alembic upgrade head)
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
