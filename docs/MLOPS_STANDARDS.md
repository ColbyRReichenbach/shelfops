# ShelfOps — MLOps, Data Engineering & Analytics Standards

> This document is the single source of truth for how we build, train,
> validate, and deploy ML models, handle data, and produce analysis
> artifacts at ShelfOps.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     docker-compose stack                        │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│   API    │ ML Worker│  MLflow  │  Redis   │  TimescaleDB        │
│ Dockerfile│Dockerfile│ Tracking │         │  (PostgreSQL)       │
│  :8000   │ .ml      │  :5000   │  :6379   │  :5432              │
│          │ Celery   │          │          │                     │
│ FastAPI  │ "ml" Q   │ Experiments│ Pub/Sub │ Transactions/       │
│          │          │ Artifacts │ Tasks   │ Inventory           │
└──────────┴──────────┴──────────┴──────────┴─────────────────────┘
```

### Container Separation

| Container | Dockerfile | Image ~Size | What it runs |
|-----------|-----------|-------------|--------------|
| `api` | `Dockerfile` | ~200MB | FastAPI, routes, alerts, WebSockets |
| `ml-worker` | `Dockerfile.ml` | ~1.5GB | Celery worker, training, prediction, SHAP |
| `mlflow` | Official image | ~300MB | Experiment tracking UI + artifact store |

**Why split?** ML dependencies (TensorFlow, XGBoost, SHAP) add ~1.3GB.
Bundling them in the API container means every API deploy downloads 1.5GB.
Splitting lets the API scale independently at 200MB.

---

## 1. Experiment Tracking (MLflow)

**Module**: `ml/experiment.py`

Every training run is logged to MLflow with:

| Category | What's Logged | Example |
|----------|--------------|---------|
| Parameters | Hyperparameters, feature tier | `n_estimators=500`, `tier=cold_start` |
| Metrics | MAE, MAPE, coverage, training time | `mae=12.3`, `mape=0.18` |
| Tags | Dataset, trigger, version | `dataset=favorita`, `trigger=weekly` |
| Artifacts | Model files, SHAP plots, importance JSON | `xgboost.joblib`, `shap_summary.png` |

**MLflow UI**: Available at `http://localhost:5000` when running `docker-compose up`.

**Fallback**: If MLflow is unavailable, runs log to `reports/run_TIMESTAMP.json`.

---

## 2. Model Explainability (SHAP)

**Module**: `ml/explain.py`

Every model version produces:

1. **Global SHAP summary** (`shap_summary.png`) — Beeswarm plot of top 20 features
2. **Feature importance JSON** (`feature_importance.json`) — Machine-readable
3. **Local explanations** (`shap_local_*.png`) — Waterfall plots for 5 representative predictions

This enables statements like:
> "Our model's top demand drivers are sales_7d, is_holiday, and day_of_week."

---

## 3. Model Registry & Model Cards

**Files**: `models/registry.json`, `models/champion.json`

### Registry Schema
```json
{
  "version": "v1",
  "feature_tier": "cold_start",
  "dataset": "favorita",
  "mae": 12.3,
  "status": "champion | candidate | archived"
}
```

### Champion / Challenger Flow
1. Train new model → status = `candidate`
2. If MAE < champion MAE × 0.95 → promote to `champion`
3. Old champion → `archived` (never deleted)

### Model Cards
Each version gets a `model_card.md` (Google standard) documenting:
performance, limitations, ethical considerations, and training config.
Template at `models/model_card_template.md`.

---

## 4. Data Validation (Pandera)

**Module**: `ml/validate.py`

Three validation gates in the ML pipeline:

| Gate | When | Schema | Behavior |
|------|------|--------|----------|
| Training data | Before `create_features()` | `TrainingDataSchema` | Fail hard |
| Features | After `create_features()` | `ColdStartFeaturesSchema` / `ProductionFeaturesSchema` | Warn + log |
| Prediction input | Before `predict_demand()` | `PredictionInputSchema` | Fail hard |

**Key rule**: Never silently `fillna(0)` without validation first.

---

## 5. Analytics & Visualization

**Module**: `ml/charts.py`

### Tech Stack
| Package | Role |
|---------|------|
| **Plotly** | Primary — interactive HTML charts |
| **Seaborn** | Statistical EDA plots |
| **Matplotlib** | Backend for SHAP only |
| **Kaleido** | Static PNG/PDF export from Plotly |

### Design Tokens
| Token | Value |
|-------|-------|
| Primary color | `#2563EB` (Blue-600) |
| Font | Inter |
| Background | White `#FFFFFF` |
| Grid | Gray-100 `#F3F4F6` |
| Template | `plotly_white` |

### Required Charts per Training Run
| Chart | File |
|-------|------|
| Forecast vs Actual | `reports/forecast_vs_actual.html` |
| Feature Importance | `reports/feature_importance.html` |
| Error Distribution | `reports/error_distribution.html` |
| Tier Comparison | `reports/tier_comparison.html` |
| Training Summary | `reports/training_summary.html` |

---

## 6. Dependencies

### API Container (`requirements.txt`)
FastAPI, SQLAlchemy, Redis, Celery, auth libs, structlog.
**No ML packages.**

### ML Worker Container (`requirements-ml.txt`)
Pandas, NumPy, XGBoost, TensorFlow, Scikit-learn,
MLflow, SHAP, Pandera, Plotly, Seaborn, Matplotlib, Kaleido.

---

## 7. Directory Structure

```
backend/
├── Dockerfile              # API container
├── Dockerfile.ml           # ML worker container
├── requirements.txt        # API deps
├── requirements-ml.txt     # ML deps
├── ml/
│   ├── features.py         # Two-phase feature engineering
│   ├── train.py            # XGBoost + LSTM training
│   ├── predict.py          # Inference
│   ├── experiment.py       # MLflow tracking + registry
│   ├── explain.py          # SHAP explainability
│   ├── validate.py         # Pandera data validation
│   └── charts.py           # Plotly chart design system
├── models/
│   ├── registry.json       # Model version registry
│   ├── champion.json       # Current production model
│   └── model_card_template.md
├── reports/                # Auto-generated analysis outputs
└── workers/
    ├── celery_app.py
    ├── retrain.py
    └── sync.py
notebooks/                  # Analysis notebooks (repo root)
└── templates/
```
