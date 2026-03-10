# ShelfOps ML Effectiveness

- Last verified date: March 9, 2026
- Audience: ML ops, product engineering, reviewers
- Scope: runtime effectiveness contract and interpretation rules
- Source of truth: `backend/api/v1/routers/ml_ops.py`, `backend/ml/metrics_contract.py`

## Effective Metrics Contract

- `mae` (`implemented`)
- `mape_nonzero` (`implemented`)
- `wape` (`implemented`)
- `mase` (`implemented`)
- `bias_pct` (`implemented`)
- `coverage` (`implemented`)
- `stockout_miss_rate` (`implemented`)
- `overstock_rate` (`implemented`)
- `overstock_dollars` (`implemented`)
- `lost_sales_qty` (`implemented`)
- `opportunity_cost_stockout` (`implemented`)
- `opportunity_cost_overstock` (`implemented`)

## Runtime Surface

- Endpoint: `GET /api/v1/ml/effectiveness` (`implemented`)
- Endpoint: `GET /api/v1/ml/models/history` (`implemented`)
- Endpoint: `GET /api/v1/ml/models/health` (`implemented`)
- Segment summaries by family and store-volume slice: `implemented`
- Confidence labels by sample sufficiency: `implemented`

## Interpretation Rules

- DS-metric improvement without business-gate compliance is insufficient for promotion (`implemented`).
- `mase`, `wape`, and `bias_pct` are the primary forecast-quality metrics for current model comparison (`implemented`).
- Public benchmark performance does not equal production tenant outcome proof (`implemented`).
- Low-sample windows should be treated as directional only (`partial` confidence).

## Verified Invocation Surface

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_ml_effectiveness_api.py -q
PYTHONPATH=backend python3 -m pytest backend/tests/test_arena_promotion_gates.py -q
```
