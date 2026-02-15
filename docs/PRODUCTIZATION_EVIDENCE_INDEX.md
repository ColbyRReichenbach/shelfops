# Productization Evidence Index

_Last updated: February 15, 2026_

## Week 1

### PZ-002: Readiness language alignment

- `docs/PRODUCTION_READINESS_BOARD.md`
- `README.md`
- `docs/README_TECHNICAL.md`
- `docs/README_NON_TECHNICAL.md`

### PZ-003: Migration rollout validation (local constraints)

Executed:

```bash
cd backend && alembic heads
cd backend && PYTHONPATH=. alembic current
cd backend && PYTHONPATH=. alembic upgrade head
```

Result:

- Migration graph head resolves to `007`.
- Local upgrade/current blocked due unavailable local PostgreSQL service in this environment.
- Readiness schema behavior validated via tests: `backend/tests/test_readiness_state_machine.py`.

## Week 2

### PZ-004: Runtime chain validation (test depth)

Executed:

```bash
PYTHONPATH=backend python3 -m pytest \
  backend/tests/test_models_api.py::test_models_health_uses_real_drift_and_data_signals \
  backend/tests/test_ml_effectiveness_api.py::test_ml_effectiveness_endpoint_returns_rolling_metrics \
  backend/tests/test_readiness_state_machine.py::test_readiness_reaches_production_tier_active_with_accuracy_samples -q
```

Result: `3 passed`

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
