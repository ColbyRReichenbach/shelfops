# ShelfOps Current State

Last updated: 2026-04-29

ShelfOps is currently a pre-pilot inventory intelligence platform with a substantial
backend foundation, a working multi-tenant API surface, and implemented
forecasting, anomaly, alerting, replenishment, and purchase-order workflows.

This file is the public current-state summary. It is intentionally stricter than
historical demo materials.

## Product Position

Current product direction:

- inventory decision support for SMB and mid-market retail
- human-reviewed replenishment workflows
- auditable model lifecycle and recommendation history
- benchmark-backed ML evidence now being reset under `.codex/ROADMAP.md`
- M5/Walmart benchmark workspace as the default local walkthrough state

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
- FreshRetailNet anomaly detector artifacts for champion `a1` and challenger `a2`
- Anomaly detection run and shadow-prediction persistence for benchmark/shadow evidence
- Benchmark workspace bootstrap for M5/Walmart sales with positive operational
  transactions, forecast rows, accuracy rows, reorder points, alerts, and
  replenishment recommendations
- Backend recommendation generation service with persisted replenishment records,
  policy versioning, risk labels, and model-version provenance
- Replenishment API for queue/detail/accept/edit/reject plus PO linkage
- Recommendation outcome computation and impact summary with measured/estimated/
  provisional confidence labels
- Replenishment recommendations now account for supplier order cost, holding cost,
  and perishable spoilage economics in the decision policy rather than treating
  those costs as forecast accuracy
- Benchmark replay simulator for replenishment policy comparison on canonical
  M5 transactions, with explicit simulated-assumption labeling
- Decision-aware experiment report for M5 benchmark work that ties forecast
  metrics, uncertainty, segment behavior, replenishment replay, promotion gates,
  lineage, and claim boundaries into one auditable artifact
- Manual-vs-AI experiment governance with context packages, source-labeled
  hypotheses, agent trace records, and comparison reports for manual,
  AI-assisted, and AI-agent experiment lanes
- Immutable experiment specs for the bounded M5 decision-aware runner and the
  FreshRetailNet anomaly benchmark runner; specs persist executable feature
  controls, model parameters, thresholds/gates where applicable, spec hashes,
  and benchmark provenance
- Simulation API to run or retrieve replenishment replay summaries with dataset,
  model, and policy provenance
- Webhook event log, dead-letter listing, and replay endpoints for integration
  recovery
- Square sync now follows current order/inventory cursor pages, verifies webhooks
  against the Square notification-url signature format, and stores Square order
  timestamps instead of sync time for transactions
- CSV onboarding validation, ingest, and readiness endpoints for stores,
  products, transactions, and inventory batches
- Replenishment Queue UI with buyer decision controls, interval provenance, and
  impact badges
- Recommendation drawer surfaces the decision-economics context behind each order
  quantity, including delivery/order cost, holding/spoilage cost, shelf life, and
  perishable caps when available
- Data Readiness UI for trainability, freshness, and Square mapping coverage
- Pilot Impact UI that separates operational outcomes from benchmark replay
  simulation evidence
- Model Lab UI centered on the active champion, calibration, segment
  behavior, and claim boundaries
- Model Lab UI includes anomaly precision/recall/FPR, shadow-disagreement
  state, whether measured anomaly feedback is available, and model-family-specific
  experiment metrics in Model Lab
- React frontend organized around primary operating views
  (`Replenishment`, `Data Readiness`, `Evidence`, `Model Lab`) plus
  secondary insight/support views (`Inventory`, `Forecasts`, `Operations`,
  `Alerts`, `Integrations`, `Products`, `Stores`)

## Partial

- Forecast evidence quality:
  the active champion is now reset onto M5, and FreshRetailNet now exists as a
  separate stockout-aware methodology track rather than a blended champion claim.
- Anomaly evidence quality:
  FreshRetailNet benchmark metrics now populate the anomaly detector champion and
  challenger records, but measured cycle-count precision is still unavailable
  until real outcomes are recorded.
- Prediction intervals:
  the active M5 champion carries calibrated split-conformal interval metadata,
  but interval evidence is not yet surfaced everywhere in the product.
- Integration hardening:
  Square mapping confirmation, replay, cursor-aware sync, and pilot-grade recovery
  now exist, and CSV onboarding now supports validation plus readiness updates;
  real merchant authorization and pilot monitoring are still required.
- Frontend product shape:
  the app shell lands on the replenishment workflow, primary pages are API-backed,
  and category/department filters are derived from product data. Some deeper
  analytical surfaces still reflect the broader platform shape rather than a
  tightly scoped pilot-only UI.
- Replenishment loop:
  backend recommendation generation, decision API, PO linkage, and closed-loop
  outcome measurement now exist, and benchmark replay simulation plus API exist,
  with a working buyer-facing queue now in place.
- Experiment workflow:
  the experiment run endpoint now executes the M5 decision-aware benchmark cycle
  for `demand_forecast` and the FreshRetailNet stockout-anomaly benchmark cycle
  for `anomaly_detector`, then persists challenger evidence for shadow review.
  It does not promote models from benchmark replay without measured pilot or
  cycle-count outcomes.
- AI-assisted DS workflow:
  agents can be represented through context packages, hypotheses, traces, and
  comparison reports, and approved experiments can run from immutable forecast or
  anomaly spec templates. There is no autonomous agent runner that can promote
  models or make production ordering decisions without human review.
- Documentation:
  root docs, data-source docs, model cards, and pre-pilot checklist now align
  with the M5/FreshRetailNet benchmark boundary and CSV/Square pilot path.

## Not Yet Implemented

- Shopify pilot onboarding; it is deferred in the current phase
- Kafka/PubSub normalized events are audited, but they are not yet persisted into
  the core transaction and inventory tables as active streaming ingest
- True shelf-availability sensing, substitution intelligence, and edge/physical-AI
  signals are outside the current SMB pilot scope

## Evidence Boundaries

- Benchmark evidence is not pilot evidence.
- Synthetic/demo artifacts are not merchant outcome evidence.
- Simulated business metrics must be labeled as simulated or estimated.
- M5 inventory/supplier/replenishment scaffolding is simulated even though the
  underlying sales history is benchmark data.
- FreshRetailNet anomaly evidence is benchmark evidence until a real retailer
  records cycle-count or buyer-review outcomes.
- Real merchant stockout/overstock reduction cannot be claimed from the current repo state.

## Active Execution Plan

Execution now follows:

- [`.codex/ROADMAP.md`](./.codex/ROADMAP.md)
- [`.codex/TASKS.json`](./.codex/TASKS.json)

Immediate priority:

1. Repo truth reset
2. Focused benchmark evidence and model reset
3. Replenishment decision loop
