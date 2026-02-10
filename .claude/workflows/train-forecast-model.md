# Workflow: Train Forecast Model

**Purpose**: Train demand forecasting models (LSTM + XGBoost ensemble)

**Agent**: ml-engineer

**Duration**: 4-6 hours (includes training time)

**Prerequisites**:
- Transaction data (90+ days minimum)
- Python 3.11 with tensorflow, xgboost, pandas
- Vertex AI configured (for deployment)

---

## Steps

### 1. Prepare Training Data

```python
# scripts/prepare_training_data.py
import pandas as pd
from datetime import datetime, timedelta

async def prepare_data(customer_id: str):
    # Extract 365 days of sales
    query = """
        SELECT 
            product_id,
            store_id,
            DATE(timestamp) as date,
            SUM(quantity) as quantity_sold
        FROM transactions
        WHERE customer_id = %s
            AND timestamp >= NOW() - INTERVAL '365 days'
        GROUP BY product_id, store_id, DATE(timestamp)
    """
    
    data = await db.fetch_all(query, [customer_id])
    df = pd.DataFrame(data)
    
    # Fill missing dates with 0
    df = fill_missing_dates(df)
    
    return df
```

### 2. Feature Engineering (45 Features)

```python
features = create_features(sku, store_id, forecast_date)
# Returns dict with 45 features:
# - temporal (12)
# - sales_history (15)
# - product (6)
# - store (5)
# - promotions (4)
# - weather (3)
```

### 3. Train/Validation Split

```python
# Time-based split (NEVER random)
split_date = datetime.now() - timedelta(days=60)
train_df = df[df['date'] < split_date]
val_df = df[df['date'] >= split_date]
```

### 4. Train LSTM Model

```python
lstm_model = build_lstm_model(sequence_length=30, n_features=45)

history = lstm_model.fit(
    X_train_seq, y_train,
    validation_data=(X_val_seq, y_val),
    epochs=50,
    batch_size=64,
    callbacks=[
        EarlyStopping(patience=5),
        ReduceLROnPlateau(factor=0.5, patience=3)
    ]
)

# Save model
lstm_model.save('models/lstm_v1.h5')
```

### 5. Train XGBoost Model

```python
xgb_model = xgb.XGBRegressor(
    objective='reg:squarederror',
    n_estimators=500,
    learning_rate=0.03,
    max_depth=8
)

xgb_model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    early_stopping_rounds=20
)

# Save model
xgb_model.save_model('models/xgb_v1.json')
```

### 6. Evaluate Performance

```python
def evaluate_ensemble(lstm_model, xgb_model, X_val, y_val):
    # Predictions
    lstm_pred = lstm_model.predict(X_val_seq)
    xgb_pred = xgb_model.predict(X_val)
    
    # Ensemble (weighted average)
    ensemble_pred = 0.35 * lstm_pred + 0.65 * xgb_pred
    
    # Metrics
    mae = np.mean(np.abs(ensemble_pred - y_val))
    mape = np.mean(np.abs((y_val - ensemble_pred) / (y_val + 1e-6))) * 100
    
    # Coverage (% within ±15%)
    within_15 = np.mean(np.abs((ensemble_pred - y_val) / (y_val + 1e-6)) <= 0.15) * 100
    
    return {
        'mae': mae,
        'mape': mape,
        'coverage_15pct': within_15
    }

metrics = evaluate_ensemble(lstm_model, xgb_model, X_val, y_val)
print(f"MAE: {metrics['mae']:.2f}")
print(f"MAPE: {metrics['mape']:.2f}%")
print(f"Coverage: {metrics['coverage_15pct']:.2f}%")

# Check if meets targets
assert metrics['mape'] < 20, "MAPE too high"
assert metrics['coverage_15pct'] > 70, "Coverage too low"
```

### 7. Deploy to Vertex AI

```python
from google.cloud import aiplatform

# Upload models
model = aiplatform.Model.upload(
    display_name="shelfops-forecast-v1",
    artifact_uri="gs://shelfops-models/v1/",
    serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-11:latest"
)

# Create endpoint
endpoint = aiplatform.Endpoint.create(
    display_name="shelfops-forecast-endpoint"
)

# Deploy with autoscaling
model.deploy(
    endpoint=endpoint,
    machine_type="n1-standard-4",
    min_replica_count=1,
    max_replica_count=5
)
```

### 8. Schedule Weekly Retraining

```python
# workers/retrain.py
from celery import Celery
from celery.schedules import crontab

@celery.task
def weekly_retrain(customer_id: str):
    # Prepare data
    X_train, y_train, X_val, y_val = prepare_training_data(customer_id)
    
    # Train new models
    new_lstm = train_lstm(X_train, y_train, X_val, y_val)
    new_xgb = train_xgboost(X_train, y_train, X_val, y_val)
    
    # Evaluate
    new_metrics = evaluate_ensemble(new_lstm, new_xgb, X_val, y_val)
    current_metrics = get_production_metrics(customer_id)
    
    # Deploy if better
    if new_metrics['mae'] < current_metrics['mae']:
        deploy_to_vertex_ai(new_lstm, new_xgb)
        log_deployment(customer_id, new_metrics)
    else:
        log_rejection(customer_id, "No improvement")

# Schedule (every Sunday at 2 AM)
celery_beat_schedule = {
    'weekly-retrain': {
        'task': 'workers.retrain.weekly_retrain',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),
        'args': ('all_customers',)
    }
}
```

---

## Checklist

- [ ] Training data extracted (365 days minimum)
- [ ] Features engineered (45 features verified)
- [ ] Train/val split done (time-based, not random)
- [ ] LSTM trained (50 epochs with early stopping)
- [ ] XGBoost trained (500 estimators with early stopping)
- [ ] Ensemble evaluated (MAE <15%, MAPE <20%, Coverage >70%)
- [ ] Models saved locally
- [ ] Models uploaded to Vertex AI
- [ ] Endpoint created and deployed
- [ ] Weekly retraining scheduled
- [ ] Monitoring dashboard created

---

## Performance Targets

| Metric | Target | Acceptable | Unacceptable |
|--------|--------|------------|--------------|
| MAE | <10% | 10-15% | >15% |
| MAPE | <15% | 15-20% | >20% |
| Coverage (±15%) | >80% | 70-80% | <70% |
| Bias | ±3% | ±3-5% | >±5% |

**If unacceptable**: 
1. Check data quality (missing values, outliers)
2. Add more features (weather, promotions, competitors)
3. Try different model architectures
4. Collect more training data (365 days minimum)

---

## Troubleshooting

**Issue**: MAE >20%  
**Fix**: Check for data quality issues, add more features, increase training data

**Issue**: Model overfitting (train good, val bad)  
**Fix**: Increase dropout (LSTM), reduce max_depth (XGBoost), use more regularization

**Issue**: Training very slow  
**Fix**: Reduce sequence_length, use GPU, batch process

---

**Last Updated**: 2026-02-09
