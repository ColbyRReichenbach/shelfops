# ShelfOps — Known Platform Limitations

- Last updated: February 24, 2026
- Audience: engineers, technical reviewers, enterprise evaluators
- Scope: current architectural constraints and platform boundaries — distinct from operational P0/P1 blockers in `docs/product/known_issues.md`

These are known boundaries of the current design, not defects. Each is a deliberate tradeoff made to ship a reliable SMB-focused platform. Most are addressable in later phases and are tracked as forward investments in `docs/product/future_integrations.md`.

---

## ML and Forecasting

**Static lead times in the optimizer**
The reorder point (ROP) and EOQ calculations in `backend/inventory/optimizer.py` treat supplier lead times as fixed inputs per vendor. There is no mechanism to dynamically adjust lead time estimates based on external signals (weather events, carrier delays, port congestion). Buyers must manually update lead time values when disruptions occur.

**Prediction uncertainty fields unpopulated**
The API contract and database schema include `lower_bound`, `upper_bound`, and `confidence` on every forecast record, but the current model does not compute prediction intervals — all three are returned as `null`. Buyers have no way to calibrate trust for high-variance or low-history SKUs until the forecasting pipeline is updated to produce uncertainty estimates.

**Binary feature tier selection**
`detect_feature_tier()` in `backend/ml/features.py` selects either the 27-feature baseline tier or the 45-feature enriched tier based on a single threshold (history depth). There is no per-feature importance scoring or dynamic feature selection — a tenant either qualifies for the enriched tier in full or falls back to baseline.

**No exogenous signal ingestion**
The model is trained entirely on historical POS and inventory data. It has no awareness of external signals — social media trends, news events, competitor stockouts, or macroeconomic indicators — that can drive demand shocks with no historical analog.

**Minimum training history requirement**
The LSTM component requires a minimum window of historical data to produce meaningful sequence predictions. New tenants or newly added product lines start with degraded model confidence until sufficient history accumulates. The promotion gate in `arena.py` provides some protection, but early-window forecasts for new tenants are less reliable.

**Time-series CV only — no cross-tenant model sharing**
Models are trained per-tenant with time-based cross-validation splits. There is no cross-tenant knowledge transfer or pre-training. A new tenant with 30 days of history is starting cold; it cannot benefit from patterns observed across other tenants.

---

## Infrastructure and Scalability

**Single-region deployment**
The current deployment targets a single region. There are no multi-region routing, data residency controls, or cross-region failover mechanisms. This is a blocker for enterprise buyers in regulated markets (EU data residency, HIPAA-adjacent supply chains).

**Celery beat is a single scheduler process**
The 12 scheduled jobs run through a single Celery beat process. There is no high-availability (HA) scheduler configuration. If the beat process crashes, scheduled jobs stop until it is restarted. This is acceptable for the current SMB deployment target but would require an HA scheduler (e.g., RedBeat with Redis locking) for enterprise SLO commitments.

**Batch ingestion cadence — not real-time**
The fastest ingest cadence is 5 minutes (Kafka worker). SFTP and EDI workers run every 15 minutes. Forecast updates and reorder recommendations are therefore delayed by at least one ingestion cycle after a sale event. Real-time shelf-level inventory accuracy is not achievable with the current architecture.

**No horizontal autoscaling for ML workers**
The `ml` Celery queue (retrain, forecasts, monitoring) runs on a fixed worker pool. There is no autoscaling logic to add capacity during scheduled heavy jobs (e.g., midnight retrain across many tenants). Under high tenant load, ML jobs queue and delay.

**Local dev only — no staging environment**
The `docker-compose.yml` covers local development. There is no persistent staging environment. Pre-production validation relies on deterministic fixture-based tests and replay simulations rather than a live staging tier.

---

## Multi-Tenancy and Security

**RLS is application-enforced, not audited externally**
Row-level security is enforced via `SET LOCAL app.current_tenant` at the session level. There is no external audit layer that continuously verifies cross-tenant data isolation. The convention is correctly implemented throughout the codebase, but relies on developer discipline (`get_tenant_db` usage) rather than a hard enforcement boundary outside the application.

**Enterprise onboarding is non-GA**
Enterprise tenant provisioning, billing integration, and SLA-backed onboarding flows are not available as a self-service path. Enterprise customers require manual onboarding. This is tracked as a deferred item in `docs/product/known_issues.md`.

---

## Integrations

**No inbound webhook retry queue**
Inbound webhook events (e.g., Square POS) are processed synchronously. If the processing pipeline fails after acknowledgment, the event is not replayed. There is no persistent webhook event store or dead-letter queue for failed inbound events.

**EDI X12 subset only**
The EDI adapter (`backend/integrations/edi_adapter.py`) handles transaction sets 846 (inventory advice), 856 (advance ship notice), and 810 (invoice). Other common retail EDI sets — 850 (purchase order), 855 (PO acknowledgment), 860 (PO change) — are not currently parsed.

**No native ERP connectors**
Enterprise ERP platforms (SAP S/4HANA, Oracle NetSuite, Microsoft Dynamics 365) are not supported via native API connectors. Data from these systems must be routed through the SFTP batch or EDI pathways, which may not match the real-time expectations of enterprise buyers.

---

## Frontend and Observability

**No prediction interval visualization**
The dashboard surfaces forecast values and SHAP feature importance but does not display confidence intervals or model uncertainty. Buyers have no visual signal for when the model is operating outside its reliable range.

**SHAP explanations not surfaced in buyer-facing views**
SHAP feature importance is rendered in the ML Ops page (`FeatureImportance` component, Models tab) for operator/technical users. It is not available in the buyer-facing forecast or reorder recommendation views — buyers do not see a per-prediction driver summary or week-over-week explanation alongside their suggested POs.

**No tenant-level observability dashboard**
There is no operator-facing view of per-tenant model health, forecast accuracy trends, data freshness, or integration sync status. Monitoring is logged to the database (`IntegrationSyncLog`, accuracy backfill tables) but not surfaced in the UI.
