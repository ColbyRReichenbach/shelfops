# ShelfOps — Known Platform Limitations

- Last verified date: April 29, 2026
- Audience: engineers, technical reviewers, enterprise evaluators
- Scope: current architectural constraints and platform boundaries, separate from active blockers in `docs/product/known_issues.md`
- Source of truth: active backend/frontend code paths and current product docs

These are deliberate boundaries of the current system, not hidden defects.

## ML and Forecasting

- Static lead times in the optimizer.
  `backend/inventory/optimizer.py` treats lead time as an input, not a dynamically inferred signal.
- Tenant-specific interval calibration is not yet measured.
  The active M5 champion carries split-conformal benchmark interval metadata, but live tenant coverage still requires pilot monitoring.
- Feature-tiering is coarse.
  `backend/ml/features.py` serves either `cold_start` or `production`; there is no dynamic per-feature selection.
- No live exogenous signal ingestion.
  Benchmark adapters can preserve calendar, price, stockout, promotion, and weather-like fields where present, but live tenant ingestion does not yet pull external weather, news, or local event feeds.
- New tenants still ramp from limited history.
  Cold-start behavior and conservative gates exist, but early-window forecasts are less personalized until tenant history accumulates.
- No cross-tenant pretraining or transfer learning.
  Models are trained per tenant and evaluated with time-based splits only.

## Infrastructure and Scalability

- Single-region, local-first deployment posture.
  The repo supports local orchestration and deterministic validation, not a multi-region deployment surface.
- Single scheduler path.
  Scheduled tenant fan-out is centralized in `backend/workers/scheduler.py`; no HA scheduler setup is tracked in-repo.
- Batch-oriented ingest cadence.
  Kafka-style plumbing exists as architecture proof, but normalized event-stream writes are not yet an active core-table ingest claim. EDI/SFTP remain batch-oriented.
- Fixed worker capacity.
  ML worker scaling is static; there is no autoscaling policy in the tracked runtime.
- No persistent staging environment.
  Release confidence still relies on CI, local replay, and deterministic runtime prep rather than a permanent staging tier.

## Multi-Tenancy and Security

- Tenant isolation relies on DB RLS plus application session context.
  RLS is enabled and forced in migrations, and API routes use `get_tenant_db()` to set `app.current_customer_id`. There is no separate external audit service continuously validating tenant isolation.
- Enterprise onboarding is non-GA.
  Enterprise provisioning and SLA-backed onboarding remain manual and policy-bounded.

## Integrations

- No measured merchant integration outcomes yet.
  CSV and Square paths exist, including Square mapping and webhook replay, but measured onboarding reliability requires a real pilot.
- EDI coverage is partial.
  The adapter covers a useful X12 subset, not the full retail EDI surface.
- No native ERP connectors.
  Enterprise ERP data still needs to come through file- or adapter-based paths.

## Frontend and Observability

- Forecast uncertainty exists but is still compact in buyer workflows.
  The replenishment drawer surfaces interval/provenance context, but deeper uncertainty visualization remains an evidence-page concern.
- Explainability is artifact-backed, not local per-decision SHAP.
  Global model-driver evidence is available in Model Lab surfaces; local SHAP explanations should not be claimed unless explicitly implemented.
- Operator observability exists, but it is still shallow.
  The `Operations` page exposes sync health, alert load, and model health, but it is not yet a full tenant operations console.
