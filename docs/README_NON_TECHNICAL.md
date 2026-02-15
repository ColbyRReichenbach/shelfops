# ShelfOps (Non-Technical Overview)

## What I Built

I built ShelfOps as an AI-powered inventory platform to help retailers avoid stockouts, reduce overstock, and make faster replenishment decisions.

I designed it from my own experience: I spent 4+ years in inventory operations at Target store level, so I built this around real retail pain points, not theoretical ones.

## Who I Am

I’m Colby Reichenbach, a UNC Chapel Hill graduate. I use both retail domain expertise and AI-assisted software development to build practical products that can operate in real environments.

## Why This Matters

Most smaller and mid-size retailers still rely on manual processes, static reorder points, and delayed reporting. ShelfOps gives them a path to smarter inventory planning without needing a massive internal data team.

For enterprise hiring teams, ShelfOps demonstrates that I can:

- understand operations on the ground
- design systems with enterprise expectations in mind
- execute from idea to working product

## External Evidence (Source-Backed)

I also grounded this work in public filings and industry research, not just product intuition:

- Target FY2024/2025 filing reports comp sales at +0.1%, with elevated shrink discussed and a disclosed shrink-reserve sensitivity.
- Walmart FY2024/2025 filing reports +4.8% U.S. comp sales (incl. fuel) and continued theft/shrink risk language.
- Lowe's FY2024/2025 filing reports -2.7% comp sales and explicitly discloses shrink reserve/sensitivity.
- NRF reports industry shrink context (1.6% average and $112.1B total in NRSS 2023).

For exact citations and safe wording rules, see: `docs/RESEARCH_SOURCES.md`.

## What ShelfOps Helps With

- Predicting future demand
- Flagging risk before shelves go empty
- Supporting reorder decisions and inventory action workflows
- Monitoring data and sync health
- Giving teams one place to review inventory decisions

## Where We Are In Production

- ShelfOps is in **pre-production hardening**.
- **SMB/mid-market workflows are the launch target**.
- Enterprise connectors are implemented and under continuous validation using synthetic enterprise-format data.
- Forecasting can be tuned now on public datasets; some advanced models remain partially blocked pending production telemetry.

Status labels used in project updates: `implemented`, `pilot_validated`, `partial`, `blocked`.

## Why SMB-First Is Intentional

Smaller operators can adopt faster with fewer integration constraints, so this is the most practical initial market. Enterprise logic is still built and validated in parallel so the system can support pilot-style enterprise scenarios without over-claiming full enterprise rollout readiness.

## Business Positioning

I see two clear paths:

1. **Product path (SMB/mid-market):** market this as a practical inventory intelligence layer for companies that do not yet have AI-driven supply/inventory systems.
2. **Career path (enterprise):** use ShelfOps to show I can contribute immediately in data science, ML, or product engineering roles at large retailers and supply-chain organizations.

## What To Read Next

- Technical hiring-manager version: `docs/README_TECHNICAL.md`
- Canonical readiness board: `docs/PRODUCTION_READINESS_BOARD.md`
- Productization execution plan: `docs/PRODUCTIZATION_PLAN.md`
- Productization evidence index: `docs/PRODUCTIZATION_EVIDENCE_INDEX.md`
- Readiness and launch status: `docs/RELEASE_READINESS.md`
- Data contract and onboarding spec: `docs/DATA_CONTRACT_SPEC.md`
- SMB onboarding runbook: `docs/SMB_ONBOARDING_RUNBOOK.md`
- Enterprise pilot readiness gates: `docs/ENTERPRISE_PILOT_READINESS.md`
- Product priorities and gaps: `docs/KNOWN_ISSUES.md`
- ML effectiveness report: `docs/ML_EFFECTIVENESS_REPORT.md`
- Enterprise vs SMB architecture brief: `docs/ENTERPRISE_VS_SMB_ARCHITECTURE_BRIEF.md`
- Source-backed research references: `docs/RESEARCH_SOURCES.md`
- Model readiness matrix: `docs/MODEL_READINESS_MATRIX.md`

Industry metrics are context; company-specific metrics should come from each company’s own 10-K disclosures.
