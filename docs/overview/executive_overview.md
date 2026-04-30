# ShelfOps Executive Overview

- Last verified date: April 29, 2026
- Audience: recruiters, hiring managers, business stakeholders
- Scope: concise product and readiness narrative
- Source of truth: root `CURRENT_STATE.md`, `CLAIMS.md`, `MODEL_CARD.md`, and `.codex/ROADMAP.md`

## What ShelfOps Is

ShelfOps is an inventory decision control plane designed for SMB and mid-market launch-candidate workflows, with enterprise-style integration patterns kept as architecture proof rather than a GA claim.

## Capability Summary

- Demand forecasting and decision support: `implemented`
- M5/Walmart benchmark workspace and forecast evidence: `implemented`
- FreshRetailNet anomaly champion/shadow evidence: `implemented`
- Governed manual-vs-AI experiment logging and immutable forecast/anomaly specs: `implemented`
- Measured merchant outcome proof: `blocked until pilot data exists`
- Contract-driven onboarding for heterogeneous source schemas: `implemented`
- Enterprise integration validation harness (EDI/SFTP/event): `implemented`
- Broad enterprise onboarding availability: `blocked`

## Readiness Statement

Current readiness is pre-production hardening for SMB launch-candidate workflows.

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).

Public metrics should be read as benchmark, simulated, provisional, or unavailable unless a real merchant pilot has produced measured outcomes.

## Why SMB-First

- Faster onboarding and tighter operational iteration loops: `implemented` strategy
- Lower dependency surface for first shipping workflows: `implemented` strategy
- Enterprise path retained as validation and architecture depth: `pilot_validated` positioning

## Positioning Boundary

- SMB launch-candidate workflows are the near-term shipping path: `implemented`
- Enterprise integration architecture exists and is continuously validated: `pilot_validated`
- Broad enterprise onboarding and availability remain restricted: `blocked`

Use this rule externally:
- lead with SMB launch and pilot workflows
- present enterprise integration breadth as technical depth and architecture proof
- do not label enterprise onboarding as production-available

## What To Read Next

- Technical overview: `docs/overview/technical_overview.md`
- Production readiness: `docs/product/production_readiness.md`
