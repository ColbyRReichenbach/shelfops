# Known Issues

_Last updated: February 15, 2026_

## P0

### 1) Branch Protection Not Yet Enforcing Enterprise CI Gates
- Files: GitHub branch protection settings (`main`)
- Impact: Enterprise validation regressions can merge if checks are not required.
- Required fix: Enforce required status checks: `enterprise-seed-validation`, `postgres-parity`, `edi-fixture-e2e`, `contract-validation-suite`.

## P1

### 3) Frontend Bundle Size Warning
- Files: `frontend` build output
- Impact: Slower cold loads.
- Required fix: Route-level code splitting and optional `manualChunks` strategy.

### 4) Additional Real-World Dataset Coverage for Forecast Robustness
- Files: `data/kaggle/walmart/`, model training runbooks
- Impact: Cross-domain baselines are active now, but production confidence still depends on tenant telemetry and onboarding quality gates.
- Required fix: Keep cross-domain protocol current and prioritize tenant contract onboarding validation.

## P3 (Deferred)

### 5) Square Connector Normalization
- Files: `backend/workers/sync.py`, `backend/integrations/square.py`
- Impact: Affects POS connector quality, but not current SMB-first plus enterprise-validation positioning.
- Required fix: ID mapping and response-shape normalization when Square becomes active priority.

## Recently Closed

- SQLite test schema failure from JSONB-only columns.
- `model_name` undefined in model save path.
- Alert creation invalid keyword (`metadata_` vs model field).
- Backtest pipeline transaction date-field mismatch.
- SQLAlchemy 2 raw SQL execution incompatibility in model/worker paths.
- ML Ops backtest endpoint contract drift against DB schema.
- Anomaly outcome values writing invalid status enums.
- Receiving path writing non-existent inventory field (`quantity_in_transit`).
- EDI parser compatibility with numbered `LIN`/`IT1` segments.
- Deterministic enterprise seed validation gate in CI.
- Sync-health stale-source SLA breach regression coverage in tests.
- EDI fixture harness coverage for parse -> persist -> audit assertions (adapter path).
- EDI/SFTP worker-path orchestration coverage for parse -> persist -> audit and sync-health logging.
- API namespace normalization to `/api/v1/ml/*` with managed deprecation aliases and sunset schedule.
