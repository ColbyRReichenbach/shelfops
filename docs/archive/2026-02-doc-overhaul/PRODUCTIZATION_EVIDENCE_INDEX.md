# Productization Evidence Index

_Last updated: February 15, 2026_

## Week 1

### PZ-002: Readiness language alignment

- `docs/PRODUCTION_READINESS_BOARD.md`
- `README.md`
- `docs/README_TECHNICAL.md`
- `docs/README_NON_TECHNICAL.md`

### PZ-003: Migration rollout validation

Executed:

```bash
PGPASSWORD=dev_password psql -h localhost -p 5432 -U shelfops -d postgres -c "DROP DATABASE IF EXISTS shelfops_audit;"
PGPASSWORD=dev_password psql -h localhost -p 5432 -U shelfops -d postgres -c "CREATE DATABASE shelfops_audit;"
cd backend && PYTHONPATH=. DATABASE_URL='postgresql+asyncpg://shelfops:dev_password@localhost:5432/shelfops_audit' alembic upgrade head
cd backend && PYTHONPATH=. DATABASE_URL='postgresql+asyncpg://shelfops:dev_password@localhost:5432/shelfops_audit' alembic current
```

Result:

- Fresh Postgres database upgraded successfully through `007 (head)`.
- Migration artifact: `docs/productization_artifacts/migration_rollout_validation.md`.
- Readiness schema behavior validated via tests: `backend/tests/test_readiness_state_machine.py`.

## Week 2

### PZ-004: Runtime chain validation (staging harness + tests)

Executed:

```bash
cd backend && DATABASE_URL='postgresql+asyncpg://shelfops:dev_password@localhost:5432/shelfops_audit' PYTHONPATH=. python3 scripts/seed_test_data.py
cd backend && DATABASE_URL='postgresql+asyncpg://shelfops:dev_password@localhost:5432/shelfops_audit' PYTHONPATH=. python3 - <<'PY'
# Runs retrain -> generate_forecasts -> backfill historical forecasts (staging harness)
# -> compute_forecast_accuracy -> writes docs/productization_artifacts/staging_runtime_chain_validation.json/md
PY
```

Result:

- Runtime chain completed with worker outputs: retrain `success`, forecast generation `success`, accuracy compute `success`.
- Artifact evidence: `docs/productization_artifacts/staging_runtime_chain_validation.md`.
- Machine-readable output: `docs/productization_artifacts/staging_runtime_chain_validation.json`.
- Supporting tests:
  - `backend/tests/test_ml_pipeline.py::TestPredictDemand::test_predict_demand_lstm_missing_norm_stats_falls_back`
  - `backend/tests/test_scheduler_dispatch.py::test_dispatch_active_tenants_fans_out_only_active_and_trial`
  - `backend/tests/test_ml_effectiveness_api.py::test_ml_effectiveness_endpoint_returns_rolling_metrics`

### PZ-005: Multi-tenant dispatch validation

Executed:

```bash
PYTHONPATH=backend python3 -m pytest \
  backend/tests/test_scheduler_dispatch.py::test_dispatch_active_tenants_fans_out_only_active_and_trial -q
```

Result: `1 passed`

### PZ-006: Incident simulation validation

Executed:

```bash
PYTHONPATH=backend python3 -m pytest \
  backend/tests/test_contracts.py::test_sync_health_contract_is_enveloped \
  backend/tests/test_contracts.py::test_sync_health_marks_stale_source_as_breach -q
```

Result: `2 passed`

## Week 3

### PZ-007 / PZ-008 / PZ-009: Onboarding dry runs

Executed validator runs:

```bash
PYTHONPATH=backend python3 backend/scripts/validate_customer_contract.py \
  --contract contracts/productization/smb_tenant_a_v1.yaml \
  --sample-path backend/tests/fixtures/contracts/tenant_a/transactions.csv \
  --output-json docs/productization_artifacts/smb_tenant_a/contract_validation_report.json \
  --output-md docs/productization_artifacts/smb_tenant_a/contract_validation_report.md \
  --write-canonical docs/productization_artifacts/smb_tenant_a/canonical_transactions.csv
```

```bash
PYTHONPATH=backend python3 backend/scripts/validate_customer_contract.py \
  --contract contracts/productization/smb_tenant_b_v1.yaml \
  --sample-path backend/tests/fixtures/contracts/tenant_b/transactions.csv \
  --output-json docs/productization_artifacts/smb_tenant_b/contract_validation_report.json \
  --output-md docs/productization_artifacts/smb_tenant_b/contract_validation_report.md \
  --write-canonical docs/productization_artifacts/smb_tenant_b/canonical_transactions.csv
```

```bash
PYTHONPATH=backend python3 backend/scripts/validate_customer_contract.py \
  --contract contracts/productization/enterprise_like_v1.yaml \
  --sample-path backend/tests/fixtures/contracts/enterprise_like \
  --output-json docs/productization_artifacts/enterprise_like/contract_validation_report.json \
  --output-md docs/productization_artifacts/enterprise_like/contract_validation_report.md \
  --write-canonical docs/productization_artifacts/enterprise_like/canonical_transactions.csv
```

Result: all three runs passed.

### PZ-010: Non-representable schema boundary

- Test evidence: `backend/tests/test_contract_mapper.py` (`requires_custom_adapter` path).

## Week 4

### PZ-011: Runtime SLO policy

- `docs/OPERATIONS_SLO.md`

### PZ-012: Rollback drill

- `docs/ROLLBACK_DRILL_REPORT_2026_02_15.md`
- Test: `backend/tests/test_model_rollback_drill.py`

## Week 5

### PZ-013 / PZ-014: Model strategy cycle + promotion decision artifact

Executed:

```bash
PYTHONPATH=backend python3 backend/scripts/run_model_strategy_cycle.py \
  --data-dir data/seed \
  --max-rows 20000 \
  --output-json docs/productization_artifacts/model_strategy_cycle.json \
  --output-md docs/productization_artifacts/model_strategy_cycle.md
```

Decision artifact:

- `docs/MODEL_STRATEGY_DECISION_2026_02_15.md`

## Week 6

### PZ-015: Recruiter evidence package refreshed

- `docs/ML_EFFECTIVENESS_REPORT.md`
- `docs/PRODUCTION_DECISION_LOG.md`
- `docs/ENTERPRISE_VS_SMB_ARCHITECTURE_BRIEF.md`
- `docs/DEMO_SCRIPT_TECHNICAL.md`
- `docs/DEMO_SCRIPT_RECRUITER.md`

### PZ-016: Final production-ready statement alignment

- `README.md`
- `docs/PRODUCTION_READINESS_BOARD.md`
- `docs/RELEASE_READINESS.md`

## Replay Demo Hardening

### Time-Travel replay implementation (Favorita-first contract)

Implemented:

- `backend/ml/replay_partition.py`
- `backend/ml/replay_hitl_policy.py`
- `backend/scripts/run_replay_simulation.py`

Validation:

```bash
cd backend
PYTHONPATH=. pytest -q \
  tests/test_replay_partition.py \
  tests/test_replay_hitl_policy.py \
  tests/test_replay_simulation_script.py
```

Sample artifact run (seed synthetic smoke replay):

```bash
cd backend
PYTHONPATH=. python3 scripts/run_replay_simulation.py \
  --dataset-dir ../data/seed \
  --holdout-days 30 \
  --max-replay-days 14 \
  --max-training-rows 20000 \
  --portfolio-mode auto \
  --dry-run \
  --output-dir ../docs/productization_artifacts
```

Generated artifacts:

- `docs/productization_artifacts/replay_partition_manifest.json`
- `docs/productization_artifacts/replay_daily_log.jsonl`
- `docs/productization_artifacts/replay_summary.json`
- `docs/productization_artifacts/replay_summary.md`
- `docs/productization_artifacts/replay_hitl_decisions.json`
- `docs/productization_artifacts/replay_model_strategy_decision.md`
