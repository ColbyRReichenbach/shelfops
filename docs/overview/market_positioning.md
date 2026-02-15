# ShelfOps Market Positioning

- Last verified date: February 15, 2026
- Audience: leadership, recruiters, hiring managers
- Scope: SMB launch target and enterprise positioning boundary
- Source of truth: `docs/product/production_readiness.md`, `docs/product/decision_log.md`

## Positioning Summary

- SMB launch-candidate workflows are the near-term shipping path: `implemented` strategy
- Enterprise integration architecture exists and is continuously validated: `pilot_validated`
- Broad enterprise onboarding/availability remains restricted: `blocked`

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).

## SMB Segment

- Contract-driven onboarding from CSV/SFTP inputs: `implemented`
- Forecasting and inventory decision workflows: `implemented`
- Operational runbook and SLO policy coverage: `implemented`

## Enterprise Segment

- EDI/SFTP/event adapter pathways: `implemented`
- Deterministic validation and CI gating: `pilot_validated`
- Partner-scale onboarding and commercial GA: `blocked`

## Message Rules

- Use `pilot_validated` when discussing enterprise integration proof.
- Do not label enterprise onboarding as production-available.
