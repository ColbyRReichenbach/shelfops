# ShelfOps Product Roadmap

- Last verified date: April 19, 2026
- Audience: builders, reviewers, stakeholders
- Scope: current pilot-productization roadmap aligned to the replenishment-first ShelfOps plan
- Source of truth: `.codex/ROADMAP.md`, `.codex/TASKS.json`, and `docs/product/known_issues.md`

## Completed

1. Root truth docs, claims boundary, and active execution tracker now reflect the current ShelfOps direction. `done`
2. The public benchmark path is reset onto M5 plus a separate FreshRetailNet stockout appendix. `done`
3. The replenishment decision loop now exists end to end: recommendation generation, buyer decisions, PO linkage, and measured or estimated impact. `done`
4. CSV onboarding, Square mapping confirmation, webhook replay, and replenishment replay simulation now exist as pilot-readiness infrastructure. `done`
5. Frontend priority surfaces now center on Replenishment Queue, Data Readiness, Pilot Impact, and Model Evidence. `done`

## Now

1. Keep the repo truth surface strict: archive stale collateral, remove dead demo-only code, and avoid unsupported claims.
2. Harden pilot execution around real merchant onboarding, recommendation review, and operational observability.
3. Continue replacing legacy benchmark or experiment paths that still assume old demo datasets.

## Next

1. Expand measured outcome reporting deeper into the product UI.
2. Broaden release-readiness checks and operator tooling for pilot support.
3. Tighten experiment workflows around the current benchmark and training stack instead of legacy demo flows.

## Later

1. Additional pilot integrations beyond CSV and Square.
2. Richer calibrated-interval UX and model evidence presentation.
3. Commercial packaging and repeatable case-study publication once measured pilot evidence exists.

## Exit Criteria (First SMB Pilot)

- No open repo-truth or claim-boundary blockers.
- A merchant can onboard through CSV or Square and reach trainable readiness without manual DB intervention.
- Buyers can review, edit, accept, or reject recommendations with auditable provenance.
- Pilot outcome reporting distinguishes measured, estimated, simulated, provisional, and unavailable metrics.
