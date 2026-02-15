# ShelfOps ML Effectiveness

- Last verified date: February 15, 2026
- Audience: ML ops, product engineering, reviewers
- Scope: runtime effectiveness contract and interpretation rules
- Source of truth: `backend/api/v1/routers/ml_ops.py`, `backend/ml/metrics_contract.py`

## Effective Metrics Contract

- `mae` (`implemented`)
- `mape_nonzero` (`implemented`)
- `coverage` (`implemented`)
- `stockout_miss_rate` (`implemented`)
- `overstock_rate` (`implemented`)

## Runtime Surface

- Endpoint: `GET /api/v1/ml/effectiveness` (`implemented`)
- Endpoint: `GET /api/v1/ml/models/history` (`implemented`)
- Endpoint: `GET /api/v1/ml/models/health` (`implemented`)
- Confidence labels by sample sufficiency: `implemented`

## Interpretation Rules

- MAE improvement without business-gate compliance is insufficient for promotion (`implemented`).
- Public benchmark performance does not equal production tenant outcome proof (`implemented`).
- Low-sample windows should be treated as directional only (`partial` confidence).

## Verified Invocation Surface

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_ml_effectiveness_api.py -q
PYTHONPATH=backend python3 -m pytest backend/tests/test_arena_promotion_gates.py -q
```
