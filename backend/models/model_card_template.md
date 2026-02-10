# Demand Forecast Model — {{VERSION}}

## Overview
- **Type**: XGBoost + LSTM ensemble (65/35 weight)
- **Feature tier**: {{TIER}} ({{N_FEATURES}} features)
- **Trained on**: {{DATASET}} ({{N_ROWS}} rows, {{DATE_RANGE}})
- **Trained at**: {{TIMESTAMP}}

## Performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| MAE    | {{MAE}} | <15% | {{MAE_STATUS}} |
| MAPE   | {{MAPE}} | <20% | {{MAPE_STATUS}} |
| Coverage (±15%) | {{COVERAGE}} | >70% | {{COVERAGE_STATUS}} |

## Feature Importance (Top 5)

| Rank | Feature | SHAP Value |
|------|---------|------------|
| 1 | {{F1_NAME}} | {{F1_VALUE}} |
| 2 | {{F2_NAME}} | {{F2_VALUE}} |
| 3 | {{F3_NAME}} | {{F3_VALUE}} |
| 4 | {{F4_NAME}} | {{F4_VALUE}} |
| 5 | {{F5_NAME}} | {{F5_VALUE}} |

## Training Configuration

| Parameter | Value |
|-----------|-------|
| XGBoost n_estimators | {{XGB_ESTIMATORS}} |
| XGBoost max_depth | {{XGB_DEPTH}} |
| LSTM sequence_length | {{LSTM_SEQ}} |
| LSTM epochs | {{LSTM_EPOCHS}} |
| CV folds | 5 |

## Data Summary

| Dimension | Value |
|-----------|-------|
| Total rows | {{N_ROWS}} |
| Date range | {{DATE_RANGE}} |
| Stores | {{N_STORES}} |
| Products | {{N_PRODUCTS}} |
| Feature tier | {{TIER}} |

## Limitations

- {{LIMITATION_1}}
- {{LIMITATION_2}}
- {{LIMITATION_3}}

## Ethical Considerations

- No PII in features
- Predictions are recommendations, not automated actions (HITL pattern)
- Model trained on public competition data — may not generalize to all retailers
- Weekly monitoring dashboard tracks prediction drift

## Artifacts

- `xgboost.joblib` — XGBoost model
- `lstm.keras` — LSTM model (if available)
- `metadata.json` — Run parameters and metrics
- `shap_summary.png` — Global feature importance
- `feature_importance.json` — Machine-readable importance
- `shap_local_*.png` — Sample local explanations
