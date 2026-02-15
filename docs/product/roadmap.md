# ShelfOps Product Roadmap

- Last verified date: February 15, 2026
- Audience: builders, reviewers, stakeholders
- Scope: near-term execution priorities and release path
- Source of truth: this roadmap and `docs/product/known_issues.md`

## Priority Roadmap

1. SMB launch-candidate reliability hardening (`implemented` and ongoing)
2. Integration correctness and monitoring depth (`pilot_validated` with ongoing expansion)
3. Production-parity CI and release controls (`implemented` with operational dependencies)
4. API contract stability and deprecation closure (`implemented` with cleanup window)

## Workstreams

| Workstream | Status | Outcome target |
|---|---|---|
| Runtime loop reliability | `implemented` | Stable retrain -> forecast -> accuracy -> gate cycle |
| Onboarding contract coverage | `partial` | More tenant/source profile variants |
| Integration validation | `pilot_validated` | Expanded fixture and incident-drill evidence |
| Frontend performance optimization | `partial` | Lower initial bundle weight |
| Enterprise onboarding commercialization | `blocked` | Non-GA until policy and telemetry gates pass |

## Exit Criteria (SMB Launch Candidate)

- No open `P0` blockers in `docs/product/known_issues.md`.
- CI reliability and migration checks remain green.
- Incident runbook paths are exercised and repeatable.
