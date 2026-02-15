# ShelfOps

AI-powered inventory intelligence platform I built to combine practical store-level retail operations with modern ML and enterprise integration patterns.

## About Me

I’m **Colby Reichenbach**, a **UNC Chapel Hill graduate** with **4+ years in inventory operations at Target (store level)**. I built ShelfOps to show both:

- my real-world retail judgment
- my ability to turn that judgment into production-quality software using AI-assisted development workflows

## Why I Built This

I built ShelfOps for two reasons:

1. **Product opportunity**: give mid-size and smaller retailers access to smart inventory tooling they usually cannot afford or build in-house.
2. **Enterprise credibility**: demonstrate I can design systems aligned to large-company requirements (EDI, auditability, reliability, operational controls).

## What ShelfOps Does

- Predicts demand and stockout risk.
- Supports reorder workflows and transfer optimization logic.
- Surfaces assumption/confidence metadata in recommendation rationale for operational transparency.
- Tracks anomalies and alert outcomes.
- Includes enterprise data exchange foundations (especially EDI-oriented workflows).
- Supports contract-driven onboarding for heterogeneous SMB and enterprise source schemas.
- Provides API + dashboard visibility into inventory health and sync health.

## Who This Is For

- **Small/mid-market retailers** that still run manual or reactive inventory processes.
- **Enterprise hiring teams** evaluating me for data/ML/product engineering roles in retail or supply chain.

## Where We Are In Production

- ShelfOps is in **pre-production hardening**.
- **SMB/mid-market workflows are the launch target**.
- Enterprise connectors are implemented and under continuous validation using synthetic enterprise-format data.
- Forecasting can be tuned now on public datasets; some advanced models remain partially blocked pending production telemetry.

Status labels across project docs use: `implemented`, `pilot_validated`, `partial`, `blocked`.

## Why SMB-First

SMB/mid-market teams can adopt decision workflows faster with fewer integration dependencies, which makes them the practical first deployment path. Enterprise capabilities are still core to the architecture, but are positioned as pilot-ready logic and validation work rather than full enterprise onboarding readiness today.

## Read This Next

- **Non-technical overview (recruiters / business stakeholders):** `docs/README_NON_TECHNICAL.md`
- **Technical overview (engineering / data hiring managers):** `docs/README_TECHNICAL.md`
- **Current readiness and delivery status:** `docs/RELEASE_READINESS.md`
- **Canonical production status board:** `docs/PRODUCTION_READINESS_BOARD.md`
- **Data strategy and model-readiness gates:** `docs/DATA_STRATEGY.md`
- **Data contract specification (SMB + enterprise):** `docs/DATA_CONTRACT_SPEC.md`
- **SMB onboarding runbook:** `docs/SMB_ONBOARDING_RUNBOOK.md`
- **Enterprise pilot readiness gates:** `docs/ENTERPRISE_PILOT_READINESS.md`
- **Known gaps and priorities:** `docs/KNOWN_ISSUES.md`
- **API contract reference:** `docs/API_CONTRACTS.md`
- **Roadmap:** `docs/ROADMAP.md`
- **Productization execution plan:** `docs/PRODUCTIZATION_PLAN.md`
- **Productization tracker:** `docs/PRODUCTIZATION_TRACKER.md`
- **Production decision log:** `docs/PRODUCTION_DECISION_LOG.md`
- **ML effectiveness report:** `docs/ML_EFFECTIVENESS_REPORT.md`
- **Enterprise vs SMB architecture brief:** `docs/ENTERPRISE_VS_SMB_ARCHITECTURE_BRIEF.md`
- **Integration incident runbook:** `docs/INTEGRATION_INCIDENT_RUNBOOK.md`
- **External research sources (filings + industry):** `docs/RESEARCH_SOURCES.md`
- **Model readiness matrix:** `docs/MODEL_READINESS_MATRIX.md`
- **Forecast tuning protocol:** `docs/TUNING_PROTOCOL.md`
- **Full legacy deep-dive (archived from old README):** `docs/PROJECT_DEEP_DIVE.md`

## Current Status

ShelfOps is in **pre-production hardening**.

- Backend tests passing
- Lint/format gates passing
- Frontend build passing
- Enterprise EDI readiness is the active priority

## Quick Start

```bash
# backend
cd backend
python3 -m pytest tests -q

# frontend
cd ../frontend
npm run lint
npm run build
```

## Note on Scope

This repo is both:

- a working product foundation
- a portfolio artifact demonstrating end-to-end ownership across retail domain logic, ML workflows, API/backend engineering, and delivery discipline

Industry-level numbers are context; company-specific figures come from each company’s own 10-K disclosures (see `docs/RESEARCH_SOURCES.md`).
