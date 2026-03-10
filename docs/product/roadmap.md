# ShelfOps Product Roadmap

- Last verified date: March 9, 2026
- Audience: builders, reviewers, stakeholders
- Scope: demo closure, first SMB pilot readiness, and later-stage productization
- Source of truth: this roadmap and `docs/product/known_issues.md`

## Completed: Demo Hardening

1. Truthful demo runtime with anomaly-backed alerts, governed MLOps evidence, and deterministic walkthrough state. `done`
2. Forecast runtime now serves the trained feature tier when runtime context supports it, with explicit fallback only when required signals are missing. `done`
3. Two live walkthroughs now close with `Today / Pilot next / Later` instead of overclaiming enterprise readiness. `done`
4. Alerts-centered anomaly flow is demo-visible in the production app. `done`
5. Operator observability view exists for the first pilot narrative. `done`

## Now: Before Demo Sign-Off

1. Real Favorita baseline/challenger evidence run and artifact capture.
2. Full frontend visual review and demo-only polish.
3. End-to-end rehearsal of both walkthroughs and terminal/API proof.
4. Final claims-safe sign-off using `docs/demo/DEMO_SIGNOFF_CHECKLIST.md`.

## Next: Before SMB Pilot

1. Integration resilience for Square or CSV-first onboarding: retry, replay, and failed-ingest inspection.
2. Stronger release confidence than local replay alone: repeatable pre-release checks and go/no-go criteria.
3. Pilot telemetry that can report forecast accuracy trend, alert/action volume, sync incidents, and model lineage without manual DB digging.
4. Broader operator tooling and reporting depth beyond the current control view.

## Later

1. Calibrated quantile intervals and richer uncertainty UX.
2. Cross-tenant transfer learning / pretraining.
3. Exogenous demand signals.
4. Native ERP connectors.
5. Multi-region, HA scheduler, and broader enterprise infrastructure.
6. Self-serve onboarding and enterprise commercialization.

## Exit Criteria (First SMB Pilot)

- No open `P0` blockers in `docs/product/known_issues.md`.
- Operator can manage pilot health from the product surface without DB inspection.
- Integration ingest failures are observable and recoverable.
- Pre-release validation is documented and repeatable before each pilot update.
