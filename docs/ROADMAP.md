# ShelfOps Roadmap

_Last updated: February 15, 2026_

## Current Baseline

- Backend tests: `236/236` passing
- Backend lint/format: passing
- Frontend production build: passing
- Status: **Pre-production hardening**

## Completed Hardening (This Cycle)

- Stabilized test harness by making JSONB columns SQLite-compatible in model metadata.
- Fixed critical runtime defects in training, alert creation, backtesting, and model/worker SQL execution paths.
- Aligned backend and frontend API contracts for:
  - `GET /ml/backtests`
  - `GET /api/v1/integrations/sync-health`
- Enforced valid anomaly outcome handling and status mapping.
- Added regression tests for contracts/status mapping.
- Cleaned backend quality gates (`ruff check`, `ruff format --check`).

## Priority Roadmap

### P0: Integration Correctness
1. Expand EDI document harness from adapter-path assertions to full worker-path assertions (`846/850/856/810`).
2. Keep connector contract tests for EDI/SFTP/Kafka sync-health outputs current.
3. Maintain tenant contract validation suite and mapping regression coverage.
4. Keep data-readiness gate checklist synced with promotion policy (`docs/DATA_STRATEGY.md`).

### P1: Production-Parity CI
1. Add PostgreSQL-backed backend test job in CI (service container).
2. Keep SQLite fast path for local smoke tests.
3. Enforce enterprise sync SLA/freshness checks in CI.

### P1: API Versioning Consistency
1. Consolidate ML endpoints under one prefix strategy.
2. Add deprecation plan for duplicate/legacy paths.

### P2: Frontend Performance
1. Implement route-level code splitting for MLOps/dashboard pages.
2. Reduce main bundle size below current warning threshold.

### P2: Release Controls
1. Add release checklist enforcement (tests + lint + build + migration checks).
2. Add incident-focused runbook for sync failures and stale-data alerts.

### Deferred: POS Connector (Square)
1. Revisit Square ID mapping and payload normalization when POS connector work is reactivated.

## Exit Criteria for Launch Candidate

- No open `P0` items in `docs/KNOWN_ISSUES.md`.
- CI runs on PostgreSQL and passes.
- EDI/SFTP/Kafka pipelines validated with real provider payloads in staging.
- API contracts frozen and versioned.
