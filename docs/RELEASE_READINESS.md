# ShelfOps Release Readiness

_Last updated: February 15, 2026_

## Snapshot

ShelfOps is in **pre-production hardening**. Core functionality is implemented and build/test gates are stable, with SMB/mid-market as the practical launch path while enterprise validation continues.

Canonical status source: `docs/PRODUCTION_READINESS_BOARD.md`.

Status taxonomy used across docs:

- `implemented`
- `pilot_validated`
- `partial`
- `blocked`

## Where We Are In Production

- ShelfOps is in **pre-production hardening**.
- **SMB/mid-market workflows are the launch target**.
- Enterprise connectors are implemented and under continuous validation using synthetic enterprise-format data.
- Forecasting can be tuned now on public datasets; some advanced models remain partially blocked pending production telemetry.

## Verified Today

- Backend tests: `254 passed` (`PYTHONPATH=backend python3 -m pytest backend/tests -q`)
- Backend lint: `ruff check` passed
- Backend format gate: `ruff format --check` passed
- Frontend build: `npm run build` passed

## Gate Status

| Gate | Status | Notes |
|---|---|---|
| Unit + integration tests (SQLite harness) | PASS | Full test suite green |
| Lint + formatting | PASS | CI-style checks clean |
| Frontend compile/build | PASS | Bundle-size warning remains |
| ML Ops critical runtime paths | PASS | Backtest/model-contract defects patched |
| Outcomes status integrity | PASS | Anomaly outcomes now map to valid status enum |
| Enterprise connector validation (EDI/SFTP/Kafka) | PASS | Deterministic seed validation + worker-path EDI/SFTP orchestration tests added |
| Production-like DB validation (PostgreSQL CI path) | PASS | Postgres parity job configured and passing in CI workflow |

## Launch Blockers

1. Enforce enterprise CI checks as required branch protection on `main` (`enterprise-seed-validation`, `postgres-parity`, `edi-fixture-e2e`, `contract-validation-suite`).
2. Remove legacy API aliases after sunset window (`docs/API_DEPRECATION_SCHEDULE.md`).

## Branch Protection Requirement

Enable required status checks on `main` in GitHub repository settings:

- `enterprise-seed-validation`
- `postgres-parity`
- `edi-fixture-e2e`
- `contract-validation-suite`

## Readiness Assessment

- **Engineering stability**: Strong
- **Integration reliability**: Strong
- **Operational launch readiness**: Near-ready (pending branch protection enforcement in GitHub settings)
- **Model-tuning readiness**: Ready for controlled iteration on verified datasets

Do not treat this repository as launch-ready until blockers in `docs/KNOWN_ISSUES.md` marked `P0` are resolved.

Industry figures are context; company-specific figures should come from each company’s own SEC filing (`docs/RESEARCH_SOURCES.md`).

## Hardening Claim Policy

- No capability claim is marked `ready` unless code path + test evidence is available.
- Recommendation outputs that depend on assumptions must expose confidence/assumption metadata.
- Any unverified or partial capability must be labeled `partial` in public docs and readiness artifacts.
