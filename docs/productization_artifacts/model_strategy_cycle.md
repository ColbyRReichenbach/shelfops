# Model Strategy Cycle

- generated_at: `2026-02-15T14:59:11.632838+00:00`
- data_dir: `data/seed`
- rows_used: `20000`
- feature_count: `27`

## Base Metrics

- xgboost_mae: `36.358488`
- xgboost_mape: `1.124552`
- lstm_available: `True`
- lstm_mae: `55.932977`
- lstm_mape: `1.915169`

## Weight Sweep

| xgboost_weight | lstm_weight | estimated_mae | estimated_mape |
|---:|---:|---:|---:|
| 1.00 | 0.00 | 36.358488 | 1.124552 |
| 0.90 | 0.10 | 38.315937 | 1.203613 |
| 0.80 | 0.20 | 40.273386 | 1.282675 |
| 0.70 | 0.30 | 42.230835 | 1.361737 |
| 0.65 | 0.35 | 43.209559 | 1.401268 |
| 0.60 | 0.40 | 44.188284 | 1.440799 |
| 0.50 | 0.50 | 46.145732 | 1.519860 |

## Decision

- recommended_mode: `single_xgboost`
- recommended_weights: xgboost=1.0, lstm=0.0
- promotion_status: `hold_as_challenger`
- promotion_reason: `business_metrics_not_available_in_this_cycle`
