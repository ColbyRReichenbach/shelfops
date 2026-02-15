# ShelfOps (Technical Overview)

## Context

I built ShelfOps to convert my 4+ years of store-level inventory experience at Target into a production-style software system. I’m Colby Reichenbach (UNC Chapel Hill), and I intentionally used AI-assisted development to accelerate delivery while keeping engineering quality gates in place.

## Product Intent

ShelfOps is a multi-tenant inventory intelligence platform designed to:

- forecast demand,
- detect anomalies,
- support decision workflows (reorder/transfer/outcomes),
- and integrate with enterprise-grade ingestion patterns (EDI/SFTP/Kafka focus).

## Architecture at a Glance

- **Backend:** FastAPI + SQLAlchemy (async)
- **Data layer:** PostgreSQL/Timescale-oriented models, Alembic migrations
- **Workers:** Celery tasks for retraining/monitoring/sync workflows
- **Frontend:** React + TypeScript + Vite
- **Quality gates:** pytest, ruff, eslint, TypeScript build checks

## Core Technical Capabilities

- Demand forecasting pipeline and model lifecycle support
- Backtesting and ML Ops endpoints
- Alert and anomaly pipelines with outcomes tracking
- Inventory, purchase order, and integration health APIs
- Enterprise integration foundation with EDI transaction logging and sync observability

## Where We Are In Production

- ShelfOps is in **pre-production hardening**.
- **SMB/mid-market workflows are the launch target**.
- Enterprise connectors are implemented and under continuous validation using synthetic enterprise-format data.
- Forecasting can be tuned now on public datasets; some advanced models remain partially blocked pending production telemetry.

Status taxonomy across readiness artifacts: `implemented`, `pilot_validated`, `partial`, `blocked`.

## Why SMB-First Is Intentional

SMB/mid-market deployment has fewer integration dependencies and allows faster end-to-end validation of business workflows. Enterprise remains a core architectural track, but current positioning is “validated integration logic + pilot-style readiness,” not broad enterprise onboarding today.

## Multi-Dataset Boundary (Locked)

Public datasets are used to improve training/evaluation robustness, not to populate live customer inventory catalogs.

- Training/eval domains: Favorita, Rossmann, Walmart (as available).
- Live dashboard scope: active tenant/customer catalog only.
- Model selection may use dataset/domain-aware routing, but dashboard products remain tenant-owned data.

## Contract-Driven Onboarding (Current)

- Versioned tenant/source profiles live under `contracts/<tenant>/<source>/v1.yaml`.
- Profile-driven mapping + DQ gates are implemented in:
- `backend/ml/contract_profiles.py`
- `backend/ml/contract_mapper.py`
- Validation CLI: `backend/scripts/validate_customer_contract.py`
- SMB onboarding flow script: `backend/scripts/run_onboarding_flow.py`

## Decision Logic Confidence (Current Hardening)

- Reorder/transfer/sourcing recommendations now include policy-source and assumption metadata.
- Supplier-capacity and transfer-cost assumptions are configurable and surfaced in rationale outputs.
- These controls improve operational trust while keeping scope SMB-first and enterprise pilot-credible.

## Engineering Status (Current)

See `docs/PRODUCTION_READINESS_BOARD.md` for canonical live status, with `docs/RELEASE_READINESS.md` as release gate detail:

- backend test suite passing
- lint/format passing
- frontend lint/build passing
- active roadmap centered on enterprise connector validation and CI parity

## Current Technical Priorities

1. EDI end-to-end fixture harness (846/850/856/810)
2. Contract-driven onboarding validation suite and tenant profile coverage
3. Enterprise connector SLA checks in CI
4. PostgreSQL-backed CI test matrix
5. API surface consolidation (`/ml` vs `/models` versioning consistency)

## Evidence Policy

For external business context, I use citation-backed sources and keep claim types explicit:

- `company-disclosed`: direct figures from SEC filings
- `industry-context`: aggregate figures from reliable organizations (e.g., NRF)
- `hypothesis`: planning assumptions that are not reported outcomes

I avoid attributing industry-wide loss values directly to a specific company unless that company explicitly discloses the value in its own filing.

Source of truth for external references and safe wording:

- `docs/RESEARCH_SOURCES.md`

Industry metrics are context; company-specific metrics must come from each company’s own SEC filings.

## Why This Is a Strong Hiring Signal

This project shows I can operate across the full stack and full lifecycle:

- domain modeling from real retail operations
- ML + backend + frontend integration
- pragmatic release hardening
- clear technical prioritization and documentation discipline

## Reference Docs

- Root summary: `README.md`
- Non-technical version: `docs/README_NON_TECHNICAL.md`
- Canonical readiness board: `docs/PRODUCTION_READINESS_BOARD.md`
- Productization execution plan: `docs/PRODUCTIZATION_PLAN.md`
- Productization tracker: `docs/PRODUCTIZATION_TRACKER.md`
- Productization evidence index: `docs/PRODUCTIZATION_EVIDENCE_INDEX.md`
- Operations SLO policy: `docs/OPERATIONS_SLO.md`
- Known issues: `docs/KNOWN_ISSUES.md`
- API contracts: `docs/API_CONTRACTS.md`
- Roadmap: `docs/ROADMAP.md`
- Data strategy: `docs/DATA_STRATEGY.md`
- Cross-domain readiness: `docs/CROSS_DOMAIN_READINESS.md`
- Dataset validation report: `docs/DATASET_VALIDATION_REPORT.md`
- Model performance decision log: `docs/MODEL_PERFORMANCE_LOG.md`
- Model readiness matrix: `docs/MODEL_READINESS_MATRIX.md`
- Forecast tuning protocol: `docs/TUNING_PROTOCOL.md`
- ML effectiveness report: `docs/ML_EFFECTIVENESS_REPORT.md`
- Production decision log: `docs/PRODUCTION_DECISION_LOG.md`
- Enterprise vs SMB architecture brief: `docs/ENTERPRISE_VS_SMB_ARCHITECTURE_BRIEF.md`
- Data contract specification: `docs/DATA_CONTRACT_SPEC.md`
- SMB onboarding runbook: `docs/SMB_ONBOARDING_RUNBOOK.md`
- Enterprise pilot readiness: `docs/ENTERPRISE_PILOT_READINESS.md`
- Source-backed external research: `docs/RESEARCH_SOURCES.md`
- Archived long-form deep dive: `docs/PROJECT_DEEP_DIVE.md`
