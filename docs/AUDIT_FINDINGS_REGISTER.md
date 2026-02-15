# ShelfOps Audit Findings Register

_Date: February 15, 2026 (Post-remediation update)_

## Findings Status (F-001 to F-016)

| id | severity | domain | status | evidence | risk after remediation |
|---|---|---|---|---|---|
| F-001 | critical | ml | closed | `backend/ml/features.py`, `backend/tests/test_feature_leakage.py` | mitigated |
| F-002 | critical | ml/business | closed | `backend/ml/metrics_contract.py`, `backend/ml/backtest.py`, `backend/scripts/benchmark_datasets.py`, `backend/scripts/benchmark_dataset_combos.py`, `backend/tests/test_metrics_contract.py` | mitigated |
| F-003 | critical | mlops | closed | `backend/workers/retrain.py`, `backend/ml/arena.py`, `backend/tests/test_arena_promotion_gates.py` | mitigated |
| F-004 | critical | data/mlops | closed | `backend/workers/retrain.py`, `backend/tests/test_retrain_db_mode.py` | mitigated |
| F-005 | high | mlops | closed | `backend/ml/train.py`, `backend/tests/test_registry_rows_trained_integrity.py` | mitigated |
| F-006 | high | code | closed | `backend/api/main.py`, `backend/api/v1/routers/ml_ops.py`, `backend/api/v1/routers/models.py`, `backend/api/v1/routers/anomalies.py`, `frontend/src/hooks/useShelfOps.ts` | mitigated |
| F-007 | high | mlops/integrations | closed | `backend/workers/sync.py`, `backend/tests/test_edi_worker_e2e.py`, `backend/tests/test_sync_worker_pipeline.py` | mitigated |
| F-008 | high | data | closed | `backend/tests/test_contract_mapper.py`, `backend/tests/fixtures/contracts/tenant_a/transactions.csv`, `backend/tests/fixtures/contracts/tenant_b/transactions.csv` | mitigated |
| F-009 | high | docs/mlops | closed | `docs/TUNING_PROTOCOL.md` | mitigated |
| F-010 | high | data/business | closed | `backend/ml/data_contracts.py`, `backend/tests/test_data_contracts.py` | mitigated |
| F-011 | medium | data/ml | closed | `backend/ml/data_contracts.py`, `backend/scripts/walmart_transform_sensitivity.py`, `backend/tests/test_data_contracts.py` | mitigated |
| F-012 | medium | docs | closed | `docs/MLOPS_WORKFLOW.md`, `docs/MLOPS_IMPLEMENTATION_SUMMARY.md`, `docs/MLOPS_QUICK_REFERENCE.md` | mitigated |
| F-013 | medium | security/code | closed | `backend/core/config.py`, `backend/tests/test_security_guardrails.py` | mitigated |
| F-014 | medium | integrations/business | closed | `backend/integrations/sla_policy.py`, `backend/api/v1/routers/integrations.py`, `backend/tests/test_contracts.py` | mitigated |
| F-015 | medium | integrations | closed | `backend/scripts/validate_enterprise_seed.py` | mitigated |
| F-016 | low | docs/data | closed | `docs/DATA_STRATEGY.md` | mitigated |

## Remediation Tracker

See `docs/REMEDIATION_TRACKER.md` and `docs/REMEDIATION_EVIDENCE_INDEX.md` for command/test evidence and closure references.
