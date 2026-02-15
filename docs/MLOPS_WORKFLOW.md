# MLOps Workflow (Archived)

_Last updated: February 15, 2026_

This document is archived to avoid policy drift.

## Canonical MLOps Sources

- `docs/TUNING_PROTOCOL.md`
- `backend/ml/arena.py`
- `backend/workers/retrain.py`
- `docs/MODEL_PERFORMANCE_LOG.md`

## Active Promotion Policy (Canonical)

- DS gates are non-regression gates (MAE and MAPE within 2% tolerance).
- Coverage must be measured and non-regressive.
- Business gates are required (stockout miss-rate, overstock rate, overstock dollars).
- Missing required business metrics blocks auto-promotion (`blocked_missing_business_metrics`).
- Legacy 5% auto-promotion language is deprecated and must not be used.
