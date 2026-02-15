# ShelfOps Forecast Tuning Protocol (Phase 1)

_Last updated: February 15, 2026_

## Scope

This protocol defines the current tuning standard for forecasting in the SMB-first phase.

- Dataset scope: Favorita only (current verified baseline)
- Tuning scope: manual + targeted sweeps
- Out of scope: Optuna or large auto-search frameworks in this phase

## Baseline Run Standard

Dataset:

- `data/kaggle/favorita/train.csv`
- Supporting files: `stores.csv`, `transactions.csv`, `oil.csv`, `holidays_events.csv`

Split strategy:

- Time-based split only (no random split)
- Train window: earliest period
- Validation window: subsequent period
- Test window: most recent holdout period

Core metrics:

- MAE
- MAPE (non-zero only; canonical metric id: `mape_nonzero`)
- Stockout miss rate
- Overstock rate

Target semantics (canonical for train/retrain/backtest):

- Quantity is treated as **net demand** at the evaluation grain.
- Sales contribute positive units.
- Returns contribute negative units.
- Comparison runs are valid only when all compared runs use the same signed-demand policy.

Tracking:

- Use existing model lifecycle/experiment path in `backend/ml/experiment.py`
- Record model version, feature tier, parameters, and metrics for each run

## Reproducible Commands (Baseline)

```bash
# Run backend tests first
cd backend
python3 -m pytest tests -q

# Execute training entrypoint with explicit Favorita dataset path
python3 scripts/run_training.py \
  --data-dir ../data/kaggle/favorita \
  --dataset favorita \
  --tier cold_start
```

If local command options differ by environment, use the equivalent run path already documented in backend scripts and preserve the same metrics + split policy.

## Reproducible Commands (Recorded Baseline + Sweep)

```bash
cd backend
PYTHONPATH=. python3 - <<'PY'
import pandas as pd
import numpy as np
import xgboost as xgb
from ml.features import create_features, get_feature_cols
from ml.metrics_contract import compute_forecast_metrics

raw = pd.read_csv('../data/kaggle/favorita/train.csv', usecols=['date','store_nbr','family','sales','onpromotion'])
raw = raw.tail(200000).rename(columns={
    'store_nbr': 'store_id',
    'family': 'product_id',
    'sales': 'quantity',
    'onpromotion': 'is_promotional',
})
raw['date'] = pd.to_datetime(raw['date'])
raw = raw.sort_values(['date', 'store_id', 'product_id']).reset_index(drop=True)

feat = create_features(raw, force_tier='cold_start')
cols = [c for c in get_feature_cols('cold_start') if c in feat.columns]
X, y = feat[cols].fillna(0), feat['quantity'].astype(float)
split = int(len(X) * 0.8)
X_train, X_test = X.iloc[:split], X.iloc[split:]
y_train, y_test = y.iloc[:split], y.iloc[split:]

for name, params in {
    'baseline': {'n_estimators': 500, 'max_depth': 6, 'learning_rate': 0.05, 'subsample': 0.85, 'colsample_bytree': 0.85},
    'sweep_2026_02_15_a': {'n_estimators': 700, 'max_depth': 8, 'learning_rate': 0.03, 'subsample': 0.7, 'colsample_bytree': 0.7},
}.items():
    model = xgb.XGBRegressor(**params, reg_alpha=0.1, reg_lambda=1.0, min_child_weight=5, random_state=42)
    model.fit(X_train, y_train, verbose=False)
    preds = np.maximum(model.predict(X_test), 0)
    metrics = compute_forecast_metrics(y_test, preds)
    print(
        name,
        metrics['mae'],
        metrics['mape_nonzero'],
        metrics['stockout_miss_rate'],
        metrics['overstock_rate'],
    )
PY
```

## Phase-1 Targeted Sweep Grid (Locked)

Use the following parameter grid for controlled tuning experiments:

- `n_estimators`: `300`, `500`, `700`
- `max_depth`: `4`, `6`, `8`
- `learning_rate`: `0.03`, `0.05`, `0.1`
- `subsample`: `0.7`, `0.85`, `1.0`
- `colsample_bytree`: `0.7`, `0.85`, `1.0`

Ensemble weight sweep (required before portfolio expansion):

- `xgboost_weight`: `1.0`, `0.9`, `0.8`, `0.7`, `0.65`, `0.6`, `0.5`
- `lstm_weight`: `1.0 - xgboost_weight`

Policy note:

- Current `65/35` (`xgboost/lstm`) is a baseline heuristic, not a retail industry standard.
- Keep or replace this split only through measured improvement against promotion gates.

Execution policy:

- Keep all non-grid parameters fixed for comparability.
- Run one baseline configuration before sweeps.
- Log each trial with a unique run label.

## Promotion Gate

A candidate can be promoted only if all applicable conditions are met:

1. MAE non-regression: candidate MAE must not degrade by more than `2.0%` versus champion.
2. MAPE non-regression: candidate MAPE must not degrade by more than `2.0%` versus champion.
3. Coverage non-regression: candidate coverage must be `>=` champion coverage.
4. Stockout miss-rate non-regression (when available): candidate must be `<= champion + 0.5pp`.
5. Overstock-rate non-regression (when available): candidate must be `<= champion + 0.5pp`.
6. Overstock dollars gate (when available): candidate must either:
- improve overstock dollars by at least `1.0%`, or
- remain within `+0.5%` tolerance while improving stockout miss-rate.

Implementation path:

- Business + DS gate evaluation is implemented in `backend/ml/arena.py`.
- Gate decisions are persisted in model metrics under `promotion_decision` for reproducible auditability.

If any required gate fails, keep as challenger and continue evaluation.

## Optuna Policy (Deferred)

Do not introduce Optuna yet.

Optuna is allowed only when both conditions are true:

1. At least two real-world datasets are active for robust cross-domain validation.
2. Enterprise integration validation gates are fully green in CI and stable.

## Required Deliverables per Tuning Cycle

1. One baseline run summary with metric snapshot.
2. One sweep summary table with best candidate and comparison.
3. Promotion decision note (promote/hold) with rationale.
4. Updated model readiness status in `docs/MODEL_READINESS_MATRIX.md` if status changes.

## Recorded Results (February 15, 2026)

Dataset + split used:
- Favorita `train.csv` (trailing 200,000 rows sample from verified dataset)
- Time-based split: first 80% train, last 20% test

| run_id | params_delta | MAE | MAPE | stockout_miss_rate | overstock_rate |
|---|---|---:|---:|---:|---:|
| baseline | `n_estimators=500, max_depth=6, learning_rate=0.05, subsample=0.85, colsample_bytree=0.85` | 40.764450 | 0.215064 | 0.000275 | 0.540250 |
| sweep_2026_02_15_a | `n_estimators=700, max_depth=8, learning_rate=0.03, subsample=0.70, colsample_bytree=0.70` | 39.648441 | 0.185745 | 0.000125 | 0.544950 |

Promotion decision for this run pair:
- Candidate passes phase-1 gate (MAE improved; MAPE improved within tolerance).
- Candidate should remain challenger until repeated on full-run baseline and additional sweep points.

## Cross-Dataset In-Domain Baselines (February 15, 2026)

Purpose:
- Establish in-domain baseline behavior before duo/all-dataset ensembling.

Reproducible command:

```bash
PYTHONPATH=backend python3 backend/scripts/benchmark_datasets.py \
  --max-rows 200000 \
  --output-json backend/reports/dataset_benchmark_baseline.json
```

Run configuration:
- Per-dataset trailing sample: 200,000 rows
- Time split: 80% train / 20% test
- Fixed baseline params:
  - `n_estimators=500`
  - `max_depth=6`
  - `learning_rate=0.05`
  - `subsample=0.85`
  - `colsample_bytree=0.85`

| dataset_id | rows_used | MAE | MAPE | stockout_miss_rate | overstock_rate |
|---|---:|---:|---:|---:|---:|
| favorita | 200000 | 40.390726 | 0.213475 | 0.000550 | 0.531525 |
| walmart | 200000 | 523.893300 | 0.198941 | 0.000050 | 0.512725 |
| rossmann | 200000 | 271.512635 | 0.050812 | 0.000000 | 0.482800 |

Interpretation:
- Do not compare MAE magnitudes directly across datasets due to different demand scales and frequencies.
- MAPE + stockout/overstock rates are more comparable for cross-domain sanity checks.
- Weekly Walmart baseline is frequency-aware in this run (`use_log_target=true`) and aligned to net-demand signed quantity policy for comparability.
- Next step is pairwise training/validation (`favorita+walmart`, `favorita+rossmann`, `walmart+rossmann`) before all-three routing/ensemble decisions.

## Duo Combination Benchmarks (February 15, 2026)

Reproducible command:

```bash
PYTHONPATH=backend python3 backend/scripts/benchmark_dataset_combos.py \
  --max-rows-each 120000 \
  --output-json backend/reports/dataset_combo_benchmark.json
```

Run policy:
- Pairwise combinations over `favorita`, `walmart`, `rossmann`
- Fixed baseline parameters (same as single-dataset baseline)
- Use `log1p` target transform when weekly data is present in the combo

Overall combo metrics:

| combo_id | rows_used_total | use_log_target | overall_mape | stockout_miss_rate | overstock_rate |
|---|---:|---|---:|---:|---:|
| favorita+walmart | 240000 | true | 0.165204 | 0.000021 | 0.511083 |
| favorita+rossmann | 240000 | false | 0.112555 | 0.002333 | 0.485292 |
| walmart+rossmann | 240000 | true | 0.110907 | 0.000021 | 0.491313 |

Per-dataset test behavior inside each combo:

| combo_id | dataset | test_rows | mape | stockout_miss_rate | overstock_rate |
|---|---|---:|---:|---:|---:|
| favorita+walmart | favorita | 33660 | 0.129609 | 0.000030 | 0.511081 |
| favorita+walmart | walmart | 14340 | 0.239980 | 0.000000 | 0.511088 |
| favorita+rossmann | favorita | 6732 | 0.464623 | 0.016637 | 0.499851 |
| favorita+rossmann | rossmann | 41268 | 0.049949 | 0.000000 | 0.482917 |
| walmart+rossmann | walmart | 8210 | 0.273427 | 0.000122 | 0.492935 |
| walmart+rossmann | rossmann | 39790 | 0.070561 | 0.000000 | 0.490978 |

Interim decision:
- Best current duo for balanced cross-domain behavior: `favorita+walmart`.
- `favorita+rossmann` and `walmart+rossmann` are dominated by Rossmann-heavy test slices and show weak transfer on their minority dataset slices.
- Keep all-three ensemble deferred until transfer stability improves in per-dataset slices, not just overall combo MAPE.

## Discussion Guidance

Current recommended language:

- "Forecasting is trainable and tunable today on verified public data."
- "Advanced production calibration remains dependent on expanded real operational telemetry."

## Model Strategy (Portfolio Gate)

1. Keep the current champion path stable first (ensemble or single model based on measured results).
2. Treat any additional model family as challenger/shadow until productization gates are complete.
3. Move to true portfolio routing only when:
- runtime reliability gates are met,
- at least 2-3 tenants have stable evidence windows,
- challenger wins repeat on business + DS metrics,
- rollback drill is verified.
