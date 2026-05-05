# ShelfOps Claims

Last updated: 2026-05-05

This file is the public claim boundary for the repo.

## Safe To Claim

- ShelfOps has a multi-tenant FastAPI backend with tenant-scoped database session handling.
- ShelfOps includes human-in-the-loop purchase-order workflows with approve, edit,
  reject, receive, and decision-history paths.
- ShelfOps converts forecasts into buyer-reviewed replenishment recommendations
  using reorder points, safety stock, supplier lead time, order cost, holding cost,
  and perishable spoilage economics.
- ShelfOps includes model-health, experiment, alert, anomaly, outcome, and report APIs.
- ShelfOps logs structured replenishment recommendation decisions for accept,
  edit, and reject actions, then links those decisions to closed outcomes when
  the recommendation horizon can be measured.
- ShelfOps includes lagged feedback-loop features derived from buyer decision
  history; recommendation rejects are captured even when no purchase order is
  created.
- ShelfOps includes champion/challenger promotion logic and runtime model history surfaces.
- ShelfOps uses LightGBM-first training and time-based validation in the active ML path.
- ShelfOps includes pilot-oriented Square mapping, webhook persistence, replay, and
  cursor-aware Square order/inventory sync paths.
- ShelfOps can seed a public benchmark workspace from M5/Walmart sales history,
  then derive labeled forecast, replenishment, alert, and impact surfaces around it.
- ShelfOps can run a decision-aware M5 benchmark experiment that compares the
  active champion proxy with a challenger across forecast metrics, uncertainty,
  segment behavior, and simulated replenishment replay.
- ShelfOps includes governed manual-vs-AI experiment workflow objects: context
  packages, source-labeled hypotheses, auditable agent traces, and comparison
  reporting for manual, AI-assisted, and AI-agent experiment lanes.
- ShelfOps supports immutable experiment specs for both current model families:
  M5 demand-forecast templates define executable feature windows, LightGBM
  parameters, calibration strategy, and decision replay assumptions; FreshRetailNet
  anomaly templates define detector feature flags, lookback windows, score
  weights, thresholds, and promotion gates.
- ShelfOps persists FreshRetailNet-backed anomaly detector champion/challenger
  evidence, anomaly detection runs, and shadow-prediction records.

## Safe To Claim With Caveat

- Integration support:
  Square is the active POS path and now includes mapping confirmation, webhook
  replay/recovery, cursor-aware order/inventory fetching, and order-time
  transaction timestamps; it still requires a real merchant pilot before any
  live outcome claim.
- Forecast uncertainty:
  the active M5 champion carries calibrated split-conformal interval metadata;
  tenant-specific live coverage still needs measured pilot monitoring.
- MLOps discipline:
  model lifecycle, lineage, gates, benchmark evidence, and model-card surfaces
  exist; segment-specific production models remain future work unless explicitly
  backed by a promoted artifact.
- Experiment evidence:
  decision-aware experiment reports are benchmark/shadow evidence. Replenishment
  replay outputs are simulated and cannot be described as measured merchant ROI.
- AI-assisted DS workflow:
  the platform can log AI-agent hypotheses and traces for human review, but this
  is governance/audit infrastructure. It is not evidence of autonomous production
  promotion or live business impact.
- Closed-loop learning:
  decision and outcome events can form auditable policy-training datasets, and
  lagged decision aggregates can enter forecast retraining. This is not
  immediate online learning, and buyer decisions are not treated as demand
  labels by themselves.
- Experiment specs:
  UI-selected specs change the bounded M5 forecast runner and the FreshRetailNet
  anomaly benchmark runner. They remain curated contracts, not arbitrary code
  generation or unrestricted dataset/model selection.
- Anomaly detection:
  FreshRetailNet supports benchmark precision/recall/false-positive-rate claims
  for the stockout/inventory-integrity detector. Measured buyer feedback remains
  unavailable until real cycle-count outcomes are recorded.

## Do Not Claim

- Measured real-merchant business impact from this repo alone
- Production-grade enterprise readiness
- Fully autonomous ordering
- Fully autonomous data-science agents that promote models without review
- Fully calibrated uncertainty for a tenant until live coverage is measured
- Universal forecasting performance across retailer datasets
- FreshRetailNet or M5 as proof of U.S. SMB merchant ROI
- Kafka/PubSub as active transaction or inventory ingest until normalized events
  are persisted into the core operational tables

## Evidence Rules

- Benchmark metrics must be labeled as benchmark evidence.
- Synthetic/demo metrics must be labeled as synthetic, simulated, or estimated.
- Pilot metrics must be labeled as measured only when they come from real merchant data.
- Every user-facing business metric should carry provenance:
  `measured`, `estimated`, `simulated`, `benchmark`, `provisional`, or `unavailable`.

## Active Data Scope

- `M5 / Walmart` is the primary public benchmark path.
- `FreshRetailNet-50K` is the secondary stockout/censored-demand benchmark path.
- `CSV onboarding` and `Square` are the active pilot/product validation paths.
- `Favorita` is legacy/reference only and should not be presented as the active
  champion or forward benchmark story.

## Runtime Workspace Boundary

- The default public workspace should be loaded with
  `backend/scripts/bootstrap_benchmark_workspace.py`, not fabricated sales.
- M5 sales rows are benchmark evidence; operational transactions contain positive
  sales events only because zero-demand days are not transactions.
- Inventory, supplier, reorder, and recommendation rows around M5 are simulated
  app scaffolding and must not be used for measured impact claims.
- FreshRetailNet anomaly shadow rows are benchmark/shadow evidence until linked
  to real cycle-count outcomes.

## Roadmap Source

The current implementation roadmap is:

- [`.codex/ROADMAP.md`](./.codex/ROADMAP.md)
- [`.codex/TASKS.json`](./.codex/TASKS.json)
