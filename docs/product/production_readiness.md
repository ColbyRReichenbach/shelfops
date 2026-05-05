# ShelfOps Production Readiness

- Last verified date: April 29, 2026
- Audience: engineering leadership, operators, reviewers
- Scope: canonical readiness statement, capability status, and release gates
- Source of truth: root `CURRENT_STATE.md`, `CLAIMS.md`, `MODEL_CARD.md`, and `.codex/ROADMAP.md`

## Canonical Statement

Current readiness is pre-production hardening for SMB launch-candidate workflows.

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).

The active public walkthrough is benchmark-backed, not merchant-measured: M5/Walmart
sales seed the workspace, FreshRetailNet supports anomaly/stockout evidence, and
CSV/Square remain the path to measured pilot outcomes.

## Status Taxonomy

- `implemented`: built, test-backed, and active in intended workflow
- `pilot_validated`: deterministic validation exists, but no broad GA claim
- `partial`: present, but missing confidence or rollout dependency
- `blocked`: not acceptable for production claim

## Capability Matrix

| Capability | Status | Notes |
|---|---|---|
| Forecast retrain/register loop | `implemented` | Worker and model lifecycle paths are active. |
| M5/Walmart benchmark workspace | `implemented` | `bootstrap_benchmark_workspace.py` loads benchmark sales plus labeled operational scaffolding. |
| FreshRetailNet anomaly evidence | `implemented` | Champion/challenger artifacts, runtime model rows, anomaly runs, and shadow predictions are persisted. |
| Measured anomaly feedback | `partial` | Persistence exists; real cycle-count outcomes are not yet available. |
| Runtime forecast generation | `implemented` | Scheduled and post-retrain generation paths exist. |
| Runtime accuracy computation | `implemented` | Accuracy loop is active in monitoring worker path. |
| Promotion gate enforcement | `implemented` | Missing required gate inputs fails closed. |
| Retraining event audit persistence | `implemented` | Retrain events are written to `model_retraining_log` for runtime health visibility. |
| File model-log parity with DB runtime state | `implemented` | Runtime retrain sync aligns file registry/champion artifacts with DB/API lifecycle truth. |
| Contract-driven onboarding boundary | `implemented` | Representable vs adapter-required behavior is explicit. |
| EDI/SFTP/event validation depth | `implemented` | EDI ingest worker coverage, Kafka event-stream wiring, and multi-tenant dispatch tests exist as architecture proof. |
| Branch-protection enforcement outside codebase | `partial` | Repository settings are operational dependency. |
| Broad enterprise onboarding availability | `blocked` | Non-GA product policy. |

## Launch-Candidate Gates

| Gate | Status |
|---|---|
| Backend lint and tests | `implemented` |
| Frontend lint and build | `implemented` |
| Postgres parity in CI | `implemented` |
| Integration validation CI paths | `implemented` |
| Branch protection required-check enforcement | `partial` |

## Claim Policy

- Any capability claim without evidence or test coverage must be downgraded to `partial` or `blocked`.
- Enterprise wording must stay within pilot-validation boundaries.
- Benchmark, simulated, provisional, and measured evidence must stay visibly separated.
