# ShelfOps Data Strategy (Verified + Planned)

_Last updated: February 15, 2026_

## Purpose

This document is the source of truth for ShelfOps data planning and readiness.
It intentionally separates:

- what is **present and verified** in this repository today,
- what is **implemented but not yet validated end-to-end**,
- what is **planned next**.

## Architecture Boundary (Locked)

Public datasets (Favorita/Rossmann/Walmart) are **training and evaluation domains**, not live catalog sources.

- The dashboard and inventory APIs remain tenant/customer-catalog driven.
- Public dataset SKUs/categories are not merged into production tenant product lists.
- Multi-dataset modeling affects model robustness and selection strategy, not which products appear in customer UI.

This boundary is required to keep product behavior honest and production-safe.

## Data Inventory (Verified in Repo)

### 1) Training data currently present

Verified datasets currently available locally:

- `data/kaggle/favorita/train.csv` (3,000,889 lines including header)
- `data/kaggle/favorita/stores.csv` (55 lines including header)
- `data/kaggle/favorita/transactions.csv` (83,489 lines including header)
- `data/kaggle/favorita/oil.csv` (1,219 lines including header)
- `data/kaggle/favorita/holidays_events.csv` (351 lines including header)
- `data/kaggle/walmart/train.csv` (canonical readiness: `ready`)
- `data/kaggle/rossmann/train.csv` (canonical readiness: `ready`)
- `data/seed/transactions/*.csv` synthetic seed transactions (canonical readiness: `ready`)

Verification method:

- `wc -l data/kaggle/favorita/*.csv`

### 2) Additional Kaggle datasets status

- `data/kaggle/walmart/` is present and validates as `ready`.
- `data/kaggle/rossmann/` is present and validates as `ready`.

### 3) Enterprise integration pathways implemented in code

- EDI parser/adapter (846/856/810 parse + 850 generation): `backend/integrations/edi_adapter.py`
- SFTP adapter: `backend/integrations/sftp_adapter.py`
- Event stream adapter (Kafka-style): `backend/integrations/event_adapter.py`
- Enterprise synthetic seeding script: `backend/scripts/seed_enterprise_data.py`
- Sync health API surface: `backend/api/v1/routers/integrations.py`
- EDI transaction audit model: `backend/db/models.py` (`EDITransactionLog`)
- Integration sync logs model: `backend/db/models.py` (`IntegrationSyncLog`)

## Data Layers and Their Roles

### Layer A: Real historical sales data (current foundation)

Current role:

- Train and evaluate baseline forecasting logic using Favorita data.

Why this layer exists:

- It provides real time-series behavior (seasonality, promotion signals, and noise) for model development.

Current limitation:

- It does not represent enterprise exchange formats (EDI/SFTP/Kafka payload behavior).

### Layer A2: Canonical public training contract (implemented)

Current role:

- Normalize heterogeneous public/synthetic transaction data into one schema consumed by retraining.

Implemented path:

- `backend/ml/data_contracts.py` (`load_canonical_transactions`)
- Canonical required fields: `date`, `store_id`, `product_id`, `quantity`
- Canonical metadata fields: `dataset_id`, `country_code`, `frequency`

Supported loaders:

- Favorita (daily, `EC`)
- Walmart (weekly, `US`)
- Rossmann (daily, `DE`)
- Synthetic seed transactions (daily, `US`)
- Generic fallback for transaction-like flat CSV directories

### Layer A3: Tenant onboarding contract layer (implemented)

Current role:

- Normalize unknown customer source schemas through versioned profiles before retraining.

Implemented path:

- Contract profiles: `contracts/<tenant>/<source>/v1.yaml`
- Profile loader: `backend/ml/contract_profiles.py`
- Mapper and DQ gates: `backend/ml/contract_mapper.py`
- Onboarding validator CLI: `backend/scripts/validate_customer_contract.py`
- SMB onboarding flow script: `backend/scripts/run_onboarding_flow.py`

### Layer B: Enterprise-format integration data (implemented, validation pending)

Current role:

- Validate ingestion and observability paths for enterprise-style payloads.

What is implemented:

- Synthetic data generation (`seed_enterprise_data.py`) capable of producing transaction, inventory, EDI, and event files.
- Adapters and API surfaces required to ingest and monitor those sources.

Current limitation:

- End-to-end deterministic fixture validation in CI is not complete yet.

## EDI-Focused Enterprise Data Plan

For enterprise positioning, the minimum data-contract scope should cover:

1. Inventory advice/inquiry flows (`846`)  
2. Purchase order generation (`850`)  
3. Advance ship notices (`856`)  
4. Invoice reconciliation (`810`)

Current state in ShelfOps:

- Parsing/generation support exists in code (`backend/integrations/edi_adapter.py`).
- File-type filtering was hardened to use ST transaction type detection.
- Regression coverage now includes parser behavior and transaction-type filtering (`backend/tests/test_edi_adapter.py`).

Still needed before claiming enterprise readiness:

- Fixture-driven E2E tests that assert parse -> persistence -> audit-log outcomes across all document types.
- SLA/freshness regression checks in CI for EDI/SFTP/Kafka sync health behavior.

## Should We Tune Models Now?

Short answer: **limited tuning is fine; full tuning cycle should wait for enterprise data validation gates.**

### Safe to do now

- Feature-engineering experiments on Favorita.
- Hyperparameter sweeps that do not change serving contracts.
- Backtest/evaluation improvements on existing forecast pipeline.

### Do first before broad tuning push

1. Lock enterprise ingestion correctness (EDI/SFTP/Kafka fixture harness).
2. Add PostgreSQL-backed CI path for production-parity checks.
3. Freeze ML API contracts used by frontend (`/ml/backtests`, `/ml/health`, sync-health envelope).

Rationale:

- Without stable ingestion and CI parity, model improvements are hard to trust operationally.

## Next Priority Data Tasks

1. Complete worker-path enterprise assertions (fixtures -> worker ingestion -> audit outcomes).
2. Enforce required status checks on `main`: `enterprise-seed-validation`, `postgres-parity`, `edi-fixture-e2e`, `contract-validation-suite`.
3. Expand tenant contract templates for additional SMB/enterprise source variants.
4. Keep cross-domain benchmark and tuning tables up to date as new datasets are added.
5. Freeze API prefix strategy and contract versions for external consumers.

## Repeatable Validation Command

Use this after generating synthetic enterprise data:

```bash
python3 backend/scripts/validate_enterprise_seed.py --input data/seed_smoke --strict
```

What it validates:

- Required output directories and minimum file counts
- Transaction/inventory/products/stores CSV header shape
- EDI transaction detection and 846 parsing
- Event JSONL schema sanity and normalization path
- SFTP adapter local parsing flow on sampled files

## Related Decision Artifacts

- `docs/MODEL_READINESS_MATRIX.md` — per-model `ready_now` / `partial` / `blocked` status
- `docs/TUNING_PROTOCOL.md` — current forecasting baseline and targeted sweep policy
- `docs/CROSS_DOMAIN_READINESS.md` — multi-dataset onboarding status and promotion gates
- `docs/DATASET_VALIDATION_REPORT.md` — generated readiness snapshot from canonical validation script
- `docs/DATA_CONTRACT_SPEC.md` — tenant/source data contract specification
- `docs/SMB_ONBOARDING_RUNBOOK.md` — SMB onboarding sequence and SLA
- `docs/ENTERPRISE_PILOT_READINESS.md` — enterprise pilot-style validation gates

## Evidence Policy

When this document includes numeric values, they must come from one of:

- files physically present in this repository,
- deterministic script outputs generated in this repository,
- explicitly cited external sources (with URL and date checked).

If a claim cannot be tied to one of those, it should be moved to a "planned/hypothesis" section and not presented as current fact.
