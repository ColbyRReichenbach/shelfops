# ShelfOps Current State

Last updated: 2026-04-19

ShelfOps is currently a pre-pilot inventory intelligence platform with a substantial
backend foundation, a working multi-tenant API surface, and partially implemented
forecasting, alerting, and purchase-order workflows.

This file is the public current-state summary. It is intentionally stricter than
historical demo materials.

## Product Position

Current product direction:

- inventory decision support for SMB and mid-market retail
- human-reviewed replenishment workflows
- auditable model lifecycle and recommendation history
- benchmark-backed ML evidence now being reset under `.codex/ROADMAP.md`

Current maturity:

- pre-pilot
- not commercially production-ready
- not yet a validated real-merchant outcome system

## Implemented

- FastAPI backend with async SQLAlchemy and tenant-scoped dependencies
- PostgreSQL/Timescale-style schema for stores, products, transactions, inventory,
  forecasts, alerts, purchase orders, experiments, and model lifecycle state
- Celery worker flows for retraining, forecasting, monitoring, syncing, and
  supporting operational jobs
- Purchase-order decision workflow:
  suggested order, approve, edit, reject, receive, decision history
- Forecast APIs, reports APIs, anomaly and alert APIs, model-health APIs
- Feedback-loop features derived from buyer PO behavior
- Champion/challenger runtime state and promotion-gate logic
- Dataset snapshot infrastructure for benchmark and training provenance
- Active file-based M5-backed champion: `v3`
- Public model card for the active champion
- FreshRetailNet stockout-aware benchmark appendix and report artifacts
- Backend recommendation generation service with persisted replenishment records,
  policy versioning, risk labels, and model-version provenance
- Replenishment API for queue/detail/accept/edit/reject plus PO linkage
- Recommendation outcome computation and impact summary with measured/estimated/
  provisional confidence labels
- Benchmark replay simulator for replenishment policy comparison on canonical
  M5 transactions, with explicit simulated-assumption labeling
- Simulation API to run or retrieve replenishment replay summaries with dataset,
  model, and policy provenance
- Webhook event log, dead-letter listing, and replay endpoints for integration
  recovery
- CSV onboarding validation, ingest, and readiness endpoints for stores,
  products, transactions, and inventory batches
- Replenishment Queue UI with buyer decision controls, interval provenance, and
  impact badges
- Data Readiness UI for trainability, freshness, and Square mapping coverage
- Pilot Impact UI that separates operational outcomes from benchmark replay
  simulation evidence
- Model Evidence UI centered on the active champion, calibration, segment
  behavior, and claim boundaries
- React frontend organized around primary operating views
  (`Replenishment`, `Data Readiness`, `Pilot Impact`, `Model Evidence`) plus
  secondary insight/support views (`Inventory`, `Forecasts`, `Operations`,
  `Alerts`, `Integrations`, `Products`, `Stores`)

## Partial

- Forecast evidence quality:
  the active champion is now reset onto M5, and FreshRetailNet now exists as a
  separate stockout-aware methodology track rather than a blended champion claim.
- Prediction intervals:
  the active M5 champion carries calibrated split-conformal interval metadata,
  but interval evidence is not yet surfaced everywhere in the product.
- Integration hardening:
  Square mapping confirmation, replay, and pilot-grade recovery now exist, and
  CSV onboarding now supports validation plus readiness updates; frontend
  readiness/product surfaces are still incomplete.
- Frontend product shape:
  the app shell now lands on the replenishment workflow and separates primary
  operating pages from secondary insight/support pages, but some deeper
  analytical surfaces still reflect the broader platform shape rather than a
  tightly scoped pilot-only UI.
- Replenishment loop:
  backend recommendation generation, decision API, PO linkage, and closed-loop
  outcome measurement now exist, and benchmark replay simulation plus API exist,
  with a working buyer-facing queue now in place.
- Documentation:
  root docs, pilot playbook, and case-study template now align with the new
  product story.

## Not Yet Implemented

- Recommendation outcome measurement with provenance labels across the full
  product UI
- Shopify pilot onboarding; it is deferred in the current phase

## Evidence Boundaries

- Benchmark evidence is not pilot evidence.
- Synthetic/demo artifacts are not merchant outcome evidence.
- Simulated business metrics must be labeled as simulated or estimated.
- Real merchant stockout/overstock reduction cannot be claimed from the current repo state.

## Active Execution Plan

Execution now follows:

- [`.codex/ROADMAP.md`](./.codex/ROADMAP.md)
- [`.codex/TASKS.json`](./.codex/TASKS.json)

Immediate priority:

1. Repo truth reset
2. Focused benchmark evidence and model reset
3. Replenishment decision loop
