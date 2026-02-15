# ShelfOps Model Tuning and Dataset Readiness

- Last verified date: February 15, 2026
- Audience: ML engineers and data reviewers
- Scope: dataset readiness, tuning protocol, and promotion gate inputs
- Source of truth: `backend/workers/retrain.py`, `backend/ml/arena.py`, `backend/ml/experiment.py`, `backend/scripts/validate_training_datasets.py`

## Data Boundary

- Public datasets are for development and evaluation workflows (`implemented`).
- Tenant telemetry is required for production calibration claims (`partial`).

## Dataset Readiness

| Dataset family | Status | Notes |
|---|---|---|
| Favorita | `implemented` | Canonical contract-ready development dataset. |
| Walmart | `implemented` | Weekly-format contract-ready dataset path. |
| Rossmann | `implemented` | Daily-format contract-ready dataset path. |
| Synthetic seed transactions | `implemented` | Deterministic local validation dataset. |

## Tuning Policy

- Time-based splits only for evaluation comparability (`implemented`).
- Canonical metrics: `mae`, `mape_nonzero`, `stockout_miss_rate`, `overstock_rate` (`implemented`).
- Promotion requires non-regression DS and business gates (`implemented`).
- Large auto-search expansion without stronger production telemetry is deferred (`partial`).

## Model Iteration Logging Contract

| Surface | Status | Notes |
|---|---|---|
| Training run artifacts (`backend/reports/*/run_*.json`) | `implemented` | Local/MLflow fallback experiment traces from `ExperimentTracker`. |
| File registry lineage (`backend/models/registry.json`) | `implemented` | Append-only model registration history on disk. |
| File champion pointer (`backend/models/champion.json`) | `implemented` | Local artifact pointer for disk-based champion loading. |
| Retraining event log (`model_retraining_log`) | `implemented` | Retrain worker now persists trigger/status/version audit rows. |
| Runtime champion/challenger state (`model_versions`) | `implemented` | Runtime truth for promotion decisions and serving state. |
| Runtime validation streams (`backtest_results`, `shadow_predictions`) | `implemented` | Continuous validation and challenger comparison evidence. |
| Promotion decision trail (`model_experiments`) | `implemented` | Persisted gate decision records and rationale. |
| File-log parity with DB promotion lifecycle | `implemented` | Runtime retrain sync reconciles file registry/champion artifacts to DB lifecycle state. |

## Source-of-Truth Order for Iteration

1. Runtime state: Postgres MLOps tables + `/api/v1/ml/models/history` and `/api/v1/ml/models/health` (`implemented`).
2. Local artifact lineage: `backend/models/registry.json`, `backend/models/champion.json`, `backend/reports/MODEL_PERFORMANCE_LOG.md` (`implemented` parity with runtime retrain flow).
3. Training diagnostics: `backend/reports/*/run_*.json` and MLflow runs (`implemented`).

## Reproducible Command Surfaces

```bash
PYTHONPATH=backend python3 backend/scripts/validate_training_datasets.py --help
PYTHONPATH=backend python3 backend/scripts/run_training.py --help
PYTHONPATH=backend python3 backend/scripts/benchmark_datasets.py --help
PYTHONPATH=backend python3 backend/scripts/benchmark_dataset_combos.py --help
PYTHONPATH=backend python3 backend/scripts/generate_model_performance_log.py --help
PYTHONPATH=backend python3 -m pytest backend/tests/test_models_api.py -q
PYTHONPATH=backend python3 -m pytest backend/tests/test_arena_promotion_gates.py -q
```

## Enterprise Constraint

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).
