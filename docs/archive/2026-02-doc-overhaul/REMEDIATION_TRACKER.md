# Remediation Tracker (F-001 to F-016)

_Last updated: February 15, 2026_

| finding_id | status | evidence | notes |
|---|---|---|---|
| F-001 | closed | `backend/ml/features.py`, `backend/tests/test_feature_leakage.py` | Rolling features are now lagged by one step. |
| F-002 | closed | `backend/ml/metrics_contract.py`, `backend/ml/backtest.py`, `backend/scripts/benchmark_datasets.py`, `backend/scripts/benchmark_dataset_combos.py`, `backend/tests/test_metrics_contract.py` | Canonical metric contract is active. |
| F-003 | closed | `backend/workers/retrain.py`, `backend/ml/arena.py`, `backend/tests/test_arena_promotion_gates.py` | Placeholder coverage/smoke logic removed; fail-closed business gates enforced. |
| F-004 | closed | `backend/workers/retrain.py`, `backend/tests/test_retrain_db_mode.py` | DB-mode retrain path implemented with canonical mapping and sufficiency checks. |
| F-005 | closed | `backend/ml/train.py`, `backend/tests/test_registry_rows_trained_integrity.py` | `rows_trained` now logs actual row count. |
| F-006 | closed | `backend/api/main.py`, `backend/api/v1/routers/ml_ops.py`, `backend/api/v1/routers/models.py`, `backend/api/v1/routers/anomalies.py`, `frontend/src/hooks/useShelfOps.ts`, `docs/API_DEPRECATION_SCHEDULE.md` | Canonical `/api/v1/ml/*` surface with legacy compatibility and deprecation headers. |
| F-007 | closed | `backend/workers/sync.py`, `backend/tests/test_edi_worker_e2e.py`, `backend/tests/test_sync_worker_pipeline.py` | Worker-path enterprise orchestration tests added. |
| F-008 | closed | `backend/tests/test_contract_mapper.py`, `backend/tests/fixtures/contracts/tenant_a/transactions.csv`, `backend/tests/fixtures/contracts/tenant_b/transactions.csv` | Two materially different schemas now prove canonical parity. |
| F-009 | closed | `docs/TUNING_PROTOCOL.md` | Baseline commands now use explicit Favorita path and canonical metrics contract snippet. |
| F-010 | closed | `backend/ml/data_contracts.py`, `backend/tests/test_data_contracts.py` | Rossmann is explicitly tagged `store_level_only`. |
| F-011 | closed | `backend/ml/data_contracts.py`, `backend/scripts/walmart_transform_sensitivity.py`, `backend/reports/walmart_transform_sensitivity.json`, `backend/tests/test_data_contracts.py` | Walmart now preserves return signal and emits sensitivity benchmark script output. |
| F-012 | closed | `docs/MLOPS_WORKFLOW.md`, `docs/MLOPS_IMPLEMENTATION_SUMMARY.md`, `docs/MLOPS_QUICK_REFERENCE.md` | Stale conflicting MLOps docs archived with canonical references. |
| F-013 | closed | `backend/core/config.py`, `backend/tests/test_security_guardrails.py` | Non-local insecure startup configurations now fail fast. |
| F-014 | closed | `backend/integrations/sla_policy.py`, `backend/api/v1/routers/integrations.py`, `backend/tests/test_contracts.py` | Sync-health SLA policy externalized and deterministic for unknown names. |
| F-015 | closed | `backend/scripts/validate_enterprise_seed.py` | Enterprise seed validator now explicitly verifies 846/850/856/810. |
| F-016 | closed | `docs/DATA_STRATEGY.md` | Favorita line-count precision corrected. |
