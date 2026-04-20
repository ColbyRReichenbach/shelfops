# ShelfOps Claims

Last updated: 2026-04-19

This file is the public claim boundary for the repo.

## Safe To Claim

- ShelfOps has a multi-tenant FastAPI backend with tenant-scoped database session handling.
- ShelfOps includes human-in-the-loop purchase-order workflows with approve, edit,
  reject, receive, and decision-history paths.
- ShelfOps includes model-health, experiment, alert, anomaly, outcome, and report APIs.
- ShelfOps includes feedback-loop features derived from buyer purchase-order behavior.
- ShelfOps includes champion/challenger promotion logic and runtime model history surfaces.
- ShelfOps uses LightGBM-first training and time-based validation in the active ML path.

## Safe To Claim With Caveat

- Integration support:
  OAuth/webhook entry points and sync-health surfaces exist, but integration
  hardening and replay/recovery are incomplete.
- Forecast uncertainty:
  the product exposes forecast bounds, but current intervals are heuristic unless
  explicitly labeled otherwise.
- MLOps discipline:
  model lifecycle, lineage, and gates exist, but the active public evidence reset
  around the new benchmark plan is still in progress.

## Do Not Claim

- Measured real-merchant business impact from this repo alone
- Production-grade enterprise readiness
- Fully autonomous ordering
- Fully calibrated uncertainty if the active model output is still heuristic
- Universal forecasting performance across retailer datasets
- Fully hardened end-to-end webhook replay and dead-letter recovery

## Evidence Rules

- Benchmark metrics must be labeled as benchmark evidence.
- Synthetic/demo metrics must be labeled as synthetic, simulated, or estimated.
- Pilot metrics must be labeled as measured only when they come from real merchant data.
- Every user-facing business metric should carry provenance:
  `measured`, `estimated`, `simulated`, `benchmark`, `provisional`, or `unavailable`.

## Active Data Scope

- `M5 / Walmart` is the primary public benchmark path.
- `FreshRetailNet-50K` is the secondary stockout/censored-demand benchmark path.
- `CSV onboarding` and `Square` are the active pilot/product validation paths.
- `Favorita` is legacy/reference only and should not be presented as the active
  champion or forward benchmark story.

## Roadmap Source

The current implementation roadmap is:

- [`.codex/ROADMAP.md`](./.codex/ROADMAP.md)
- [`.codex/TASKS.json`](./.codex/TASKS.json)
