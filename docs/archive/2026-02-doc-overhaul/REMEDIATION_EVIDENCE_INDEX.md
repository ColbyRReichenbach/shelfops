# Remediation Evidence Index

_Last updated: February 15, 2026_

## Core Code Evidence

- Leakage fix: `backend/ml/features.py`
- Canonical metric contract: `backend/ml/metrics_contract.py`
- Backtest metric unification: `backend/ml/backtest.py`
- Benchmark metric unification: `backend/scripts/benchmark_datasets.py`, `backend/scripts/benchmark_dataset_combos.py`
- Retrain governance + DB mode: `backend/workers/retrain.py`
- Promotion fail-closed logic: `backend/ml/arena.py`
- API normalization + legacy deprecation: `backend/api/main.py`
- Sync-health SLA policy externalization: `backend/integrations/sla_policy.py`, `backend/api/v1/routers/integrations.py`

## Test Evidence

- Leakage regression tests: `backend/tests/test_feature_leakage.py`
- Metric contract tests: `backend/tests/test_metrics_contract.py`
- Data contract updates (Rossmann/Walmart): `backend/tests/test_data_contracts.py`
- Promotion fail-closed tests: `backend/tests/test_arena_promotion_gates.py`
- DB mode retrain path tests: `backend/tests/test_retrain_db_mode.py`
- Registry rows integrity test: `backend/tests/test_registry_rows_trained_integrity.py`
- EDI worker-path E2E: `backend/tests/test_edi_worker_e2e.py`
- SFTP worker pipeline test: `backend/tests/test_sync_worker_pipeline.py`
- API legacy deprecation headers + sync health contract: `backend/tests/test_contracts.py`
- Security guardrails tests: `backend/tests/test_security_guardrails.py`

## Validation Commands Executed

```bash
PYTHONPATH=backend python3 -m pytest \
  backend/tests/test_feature_leakage.py \
  backend/tests/test_metrics_contract.py \
  backend/tests/test_data_contracts.py \
  backend/tests/test_arena_promotion_gates.py \
  backend/tests/test_contracts.py \
  backend/tests/test_edi_worker_e2e.py \
  backend/tests/test_sync_worker_pipeline.py \
  backend/tests/test_retrain_db_mode.py \
  backend/tests/test_registry_rows_trained_integrity.py \
  backend/tests/test_security_guardrails.py -q
```

Latest result from this run: **30 passed**.

Additional regression validation:

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
```

Latest full backend suite result: **254 passed**.
