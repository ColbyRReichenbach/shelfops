Evaluate the current ML model performance and produce a diagnostic report.

Steps:
1. Read `models/registry.json` — identify champion model version and training date
2. Read `backend/workers/monitoring.py` — check drift detection logic and thresholds
3. Look for recent entries in `forecast_accuracy` table or MLflow run data
4. Check `backend/ml/features.py` — confirm active feature tier

## Model Health Report

**Champion Model**: [version, trained date, feature tier]

**Current Metrics**
| Metric | Actual | Target | Status |
|--------|--------|--------|--------|
| MAE | | <15% | |
| MAPE | | <20% | |
| Coverage ±15% | | >70% | |

**Drift Status**: [OK / WARNING / CRITICAL — MAE delta vs 30-day baseline]

**Feature Tier**: [cold_start / production] — reasoning

**Recommendations**
- MAE degradation > 15%: trigger retraining via `workers/retrain.py`
- Stuck on cold_start after 90 days: investigate data pipeline ingestion
- MAPE > 20%: list top 3 likely causes

**Next Scheduled Retraining**: [from celery_app.py beat schedule]
