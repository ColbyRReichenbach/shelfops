# ML Effectiveness Report

_Last updated: February 15, 2026_

## Scope

- Model family: `demand_forecast`
- Target deployment scope: SMB launch-candidate workflows
- Enterprise scope: pilot-validation only

## Metrics Contract

- `mae`
- `mape_nonzero`
- `coverage`
- `stockout_miss_rate`
- `overstock_rate`

Definitions are canonicalized in `backend/ml/metrics_contract.py`.

## Runtime Effectiveness API

- Endpoint: `GET /api/v1/ml/effectiveness`
- Source path: `backend/api/v1/routers/ml_ops.py`
- Uses rolling `ForecastAccuracy` and interval coverage from `DemandForecast`.

## Reproducibility Commands

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_ml_effectiveness_api.py -q
PYTHONPATH=backend python3 -m pytest backend/tests/test_arena_promotion_gates.py -q
```

## Confidence Labels

- `measured`: sample count >= 200
- `estimated`: sample count >= 50
- `low_sample`: sample count < 50
- `unavailable`: no records in window

## Interpretation Guardrails

1. Improvement in MAE without stockout/overstock guardrail compliance is not enough for promotion.
2. Public benchmark datasets establish development signal only; tenant telemetry is required for production claims.
3. Coverage only reflects rows with prediction interval bounds present.
