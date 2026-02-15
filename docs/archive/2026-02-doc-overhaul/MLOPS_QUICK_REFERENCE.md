# MLOps Quick Reference (Archived)

_Last updated: February 15, 2026_

This file is archived to prevent stale quick-reference guidance from conflicting with runtime behavior.

## Use These Instead

- `docs/TUNING_PROTOCOL.md`
- `backend/ml/arena.py`
- `backend/workers/retrain.py`
- `docs/API_DEPRECATION_SCHEDULE.md`

## Current Truth

- API surface: `/api/v1/ml/*` (legacy `/ml`, `/models`, `/anomalies` are compatibility aliases with deprecation headers).
- Promotion flow is fail-closed on missing required gate metrics.
- Model decision history is tracked in `docs/MODEL_PERFORMANCE_LOG.md` and model registry artifacts.
