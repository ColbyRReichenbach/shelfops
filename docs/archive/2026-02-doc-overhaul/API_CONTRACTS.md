# API Contracts

_Last updated: February 15, 2026_

This document captures the currently supported response contracts relied on by the frontend.
Example numeric values in JSON snippets are illustrative and represent shape/type expectations, not guaranteed live production metrics.

## ML Ops

### `GET /api/v1/ml/backtests`
Returns an array of entries:

```json
[
  {
    "backtest_id": "uuid",
    "model_name": "demand_forecast",
    "model_version": "v12",
    "forecast_date": "2026-02-13",
    "mae": 11.4,
    "mape": 17.8,
    "stockout_miss_rate": 0.07,
    "overstock_rate": 0.11
  }
]
```

Notes:
- `forecast_date` is authoritative.
- Deprecated fields are not returned: `backtest_date`, `coverage`, `n_predictions`.
- Legacy aliases (`/ml/*`, `/models/*`, `/anomalies/*`) return deprecation headers and are scheduled for removal per `docs/API_DEPRECATION_SCHEDULE.md`.

### `GET /api/v1/ml/health`
Returns:

```json
{
  "status": "healthy",
  "model_counts": {"champion": 1, "candidate": 2},
  "champions": [
    {
      "model_name": "demand_forecast",
      "version": "v12",
      "metrics": {"mae": 11.2, "mape": 18.1},
      "promoted_at": "2026-02-10T02:30:00"
    }
  ],
  "recent_backtests_7d": 7,
  "registry_exists": true,
  "checked_at": "2026-02-14T12:00:00"
}
```

### `GET /api/v1/ml/effectiveness`
Returns rolling effectiveness metrics for operational monitoring:

```json
{
  "window_days": 30,
  "model_name": "demand_forecast",
  "status": "ok",
  "sample_count": 240,
  "trend": "stable",
  "confidence": "measured",
  "metrics": {
    "mae": 2.1431,
    "mape_nonzero": 0.1221,
    "coverage": 0.8917,
    "stockout_miss_rate": 0.0417,
    "overstock_rate": 0.3167
  },
  "by_version": [
    {"model_version": "v12", "samples": 240, "mae": 2.1431, "mape_nonzero": 0.1221}
  ],
  "window_start": "2026-01-16",
  "window_end": "2026-02-15"
}
```

### `GET /api/v1/ml/models/health`
Returns champion/challenger summary plus computed retraining triggers:

```json
{
  "champion": {"version": "v12", "status": "healthy"},
  "challenger": {"version": "v13", "status": "shadow_testing"},
  "retraining_triggers": {
    "drift_detected": false,
    "new_data_available": true,
    "new_data_rows_since_last_retrain": 124,
    "last_trigger": "scheduled",
    "last_retrain_at": "2026-02-15T02:00:00"
  },
  "models_count": 2
}
```

### `POST /api/v1/ml/models/{version}/promote`
Manual promotion endpoint (admin role required).

Request body:

```json
{
  "promotion_reason": "Manual override approved after backtest and merchant review."
}
```

## Integrations

### `GET /api/v1/integrations/sync-health`
Returns an envelope object:

```json
{
  "sources": [
    {
      "integration_type": "EDI",
      "integration_name": "EDI 846 Inventory",
      "last_sync": "2026-02-15T11:30:00",
      "hours_since_sync": 4.0,
      "sla_hours": 48,
      "sla_status": "ok",
      "failures_24h": 0,
      "syncs_24h": 2,
      "records_24h": 3200
    }
  ],
  "overall_health": "healthy",
  "checked_at": "2026-02-15T12:00:00"
}
```

Notes:
- Consumers should read `sources` from the envelope.
- `sla_status` is `ok` or `breach`.

## Outcomes

### `POST /outcomes/anomaly/{anomaly_id}`
Accepted `outcome` values:

- `true_positive`
- `false_positive`
- `resolved`
- `investigating`

Internal status mapping:
- `true_positive` -> `resolved`
- `false_positive` -> `false_positive`
- `resolved` -> `resolved`
- `investigating` -> `investigating`

Values outside this set are rejected.
