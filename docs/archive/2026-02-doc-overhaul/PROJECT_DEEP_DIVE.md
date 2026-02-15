# ShelfOps Project Deep Dive (Verified)

_Last updated: February 15, 2026_

## Scope of this document

This deep dive is limited to claims that are directly verifiable from this repository (code, tests, build output, and tracked docs). It intentionally excludes external market-size/ROI claims unless a source is provided.

## Builder Context

I am Colby Reichenbach (UNC Chapel Hill), with 4+ years of inventory operations experience at Target at the store level. I built ShelfOps as both:

- a practical inventory intelligence product direction for smaller and mid-size retailers
- a demonstration of enterprise-ready systems thinking for large retail organizations

## Where We Are In Production

- ShelfOps is in **pre-production hardening**.
- **SMB/mid-market workflows are the launch target**.
- Enterprise connectors are implemented and under continuous validation using synthetic enterprise-format data.
- Forecasting can be tuned now on public datasets; some advanced models remain partially blocked pending production telemetry.

## Why SMB-First Is Intentional

SMB deployment is the fastest path to validating full operational workflows with lower integration overhead. Enterprise architecture remains a first-class concern, but current external positioning is “validated enterprise logic and pilot readiness,” not broad enterprise onboarding availability.

## Verified Product Capabilities

### 1) Demand Forecasting Pipeline

Verified in code:

- Feature engineering: `backend/ml/features.py`
- Training entrypoint: `backend/ml/train.py`
- Prediction logic: `backend/ml/predict.py`
- Validation utilities: `backend/ml/validate.py`

Verified by tests:

- `backend/tests/test_ml_pipeline.py`

### 2) Alerting and Anomaly Flows

Verified in code:

- Alert engine and dedup/publish flow: `backend/alerts/engine.py`
- ML anomaly detection: `backend/ml/anomaly.py`
- Outcome tracking and status mapping: `backend/ml/alert_outcomes.py`
- Outcomes API routes: `backend/api/v1/routers/outcomes.py`

Verified by tests:

- `backend/tests/test_alert_engine.py`
- `backend/tests/test_contracts.py`

### 3) Inventory and PO Decision Workflows

Verified in code:

- Dynamic reorder logic: `backend/inventory/optimizer.py`
- PO approve/reject/receive APIs: `backend/api/v1/routers/purchase_orders.py`
- Receiving discrepancy handling: `backend/supply_chain/receiving.py`
- Transfer optimization logic: `backend/supply_chain/transfers.py`

Current hardening note:

- Recommendation payloads expose assumption confidence (for example, vendor-capacity assumptions and policy-source metadata) so operators can distinguish measured vs assumed inputs.

Verified by tests:

- `backend/tests/test_bugfixes.py`
- `backend/tests/test_inventory_optimizer.py`
- `backend/tests/test_supply_chain.py`

### 4) Enterprise Integration Foundation (EDI/SFTP/Kafka)

Verified in code:

- EDI adapter/parsers (846/856/810) and 850 generation: `backend/integrations/edi_adapter.py`
- SFTP adapter: `backend/integrations/sftp_adapter.py`
- Integration sync health endpoint: `backend/api/v1/routers/integrations.py`
- EDI audit model: `backend/db/models.py` (`EDITransactionLog`)

Current state:

- Foundation exists.
- Deterministic EDI fixture harness coverage exists (`backend/tests/test_edi_adapter.py`).
- CI gates now include enterprise seed validation + EDI fixture suite + contract validation suite.
- Full production partner certification remains out of scope in this phase.

### 5) Contract-Driven Onboarding Foundation

Verified in code:

- Contract profile loader: `backend/ml/contract_profiles.py`
- Canonical mapper + validator: `backend/ml/contract_mapper.py`
- Onboarding validator CLI: `backend/scripts/validate_customer_contract.py`
- SMB onboarding flow script: `backend/scripts/run_onboarding_flow.py`

### 6) Frontend Visibility

Verified in code:

- API hooks: `frontend/src/hooks/useShelfOps.ts`
- MLOps/data-health UI modules: `frontend/src/components/mlops/`
- Main app routes: `frontend/src/App.tsx`

## Current Engineering Evidence

As verified in this repo on February 15, 2026:

- Backend tests passing: `236/236`
- Backend lint/format passing: `ruff check`, `ruff format --check`
- Frontend lint/build passing: `npm run lint`, `npm run build`

Authoritative status source:

- `docs/RELEASE_READINESS.md`

## Data Reality (for Model Work)

What is present in this repo:

- Kaggle Favorita dataset files under `data/kaggle/favorita/`
- Existing model/report artifacts under `backend/models/` and `backend/reports/`

What is not yet proven here:

- Production enterprise retailer data ingestion at scale with contractual SLA validation.

Source of truth for current vs planned data layers:

- `docs/DATA_STRATEGY.md`
- `docs/MODEL_READINESS_MATRIX.md`
- `docs/TUNING_PROTOCOL.md`
- `docs/DATA_CONTRACT_SPEC.md`
- `docs/SMB_ONBOARDING_RUNBOOK.md`
- `docs/ENTERPRISE_PILOT_READINESS.md`

## External Research Context (Citation-Governed)

This project also includes a source-governed external context file:

- `docs/RESEARCH_SOURCES.md`

Use case for that file:

- grounding problem framing in SEC disclosures and NRF industry research,
- avoiding unsourced or over-attributed loss claims,
- keeping company-specific versus industry-wide numbers clearly separated.

Examples of safe context from that source set:

- Target and Lowe's filings explicitly disclose shrink reserve sensitivity language.
- Walmart filing explicitly supports growth and risk context, but not a single shrink-loss dollar figure in the same format.
- NRF provides industry-level shrink statistics that should be cited as industry context, not company-specific losses.

Policy: industry figures are context; company-specific numbers should come from the company’s own SEC filings.

## Model Iteration Readiness

Model iteration is possible now, but should be staged:

1. Establish enterprise ingestion validation harness first (EDI/SFTP/Kafka path correctness).
2. Lock production-parity CI (PostgreSQL-backed test job).
3. Then tune forecasting models on stable, validated datasets and evaluation protocol.

## What this document does not claim

- No external TAM, ROI, or market-loss figures are asserted here.
- No projected business metrics are presented as observed outcomes.

If external business or market statistics are added later, they should include explicit citations in a dedicated sources section.
