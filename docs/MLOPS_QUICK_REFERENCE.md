# MLOps Quick Reference — API Endpoints & Workflows

---

## API Endpoints Summary

### **Model Health** (`/api/v1/models`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/models/health` | Champion/challenger status, MAE trends |
| GET | `/models/backtest/{version}` | 90-day backtest time series |
| POST | `/models/{version}/promote` | Manual promotion (admin) |
| GET | `/models/history` | Model version history |

---

### **ML Alerts** (`/api/v1/ml-alerts`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ml-alerts` | List alerts (filter by status/severity) |
| GET | `/ml-alerts/stats` | Unread count by severity |
| GET | `/ml-alerts/{id}` | Get alert details |
| PATCH | `/ml-alerts/{id}/read` | Mark as read |
| PATCH | `/ml-alerts/{id}/action` | Approve/dismiss |

---

### **Experiments** (`/api/v1/experiments`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/experiments` | List experiments |
| GET | `/experiments/{id}` | Get experiment details |
| POST | `/experiments` | Propose new experiment |
| PATCH | `/experiments/{id}/approve` | Approve experiment |
| PATCH | `/experiments/{id}/reject` | Reject experiment |
| POST | `/experiments/{id}/complete` | Complete with results |
| GET | `/experiments/{id}/results` | Get experiment results |

---

## Common Workflows

### **1. Check Model Health**

```bash
curl http://localhost:8000/api/v1/models/health
```

**Response**:
```json
{
  "champion": {
    "version": "v12",
    "status": "healthy",
    "mae_7d": 11.2,
    "trend": "improving"
  },
  "challenger": {
    "version": "v13",
    "mae_7d": 10.9,
    "promotion_eligible": true
  }
}
```

---

### **2. Review Drift Alert**

```bash
# Get unread critical alerts
curl "http://localhost:8000/api/v1/ml-alerts?status=unread&severity=critical"

# Approve drift-triggered retrain
curl -X PATCH http://localhost:8000/api/v1/ml-alerts/{alert_id}/action \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "notes": "Reviewed backtest, approved"}'
```

---

### **3. Propose Experiment**

```bash
curl -X POST http://localhost:8000/api/v1/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_name": "Department-Tiered Forecasting",
    "hypothesis": "Electronics demand differs from Grocery. Dedicated model will improve MAE by 12%",
    "experiment_type": "segmentation",
    "proposed_by": "jane.doe@shelfops.com"
  }'
```

---

### **4. Approve Experiment**

```bash
curl -X PATCH http://localhost:8000/api/v1/experiments/{exp_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved_by": "ml_manager@shelfops.com",
    "rationale": "Approved with constraint: top 500 SKUs only"
  }'
```

---

### **5. Complete Experiment**

```bash
curl -X POST http://localhost:8000/api/v1/experiments/{exp_id}/complete \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "adopt",
    "decision_rationale": "Exceeded target (22% improvement)",
    "results": {
      "baseline_mae": 12.8,
      "experimental_mae": 10.0,
      "improvement_pct": 21.9
    },
    "experimental_version": "v14"
  }'
```

---

## Database Queries

### **Get Recent Retraining Events**

```sql
SELECT
    model_name,
    trigger_type,
    version_produced,
    status,
    started_at,
    completed_at
FROM model_retraining_log
WHERE customer_id = '00000000-0000-0000-0000-000000000001'
ORDER BY started_at DESC
LIMIT 10;
```

---

### **Get Champion Model Metrics**

```sql
SELECT
    version,
    metrics->>'mae' AS mae,
    metrics->>'mape' AS mape,
    metrics->>'tier' AS tier,
    promoted_at
FROM model_versions
WHERE
    customer_id = '00000000-0000-0000-0000-000000000001'
    AND model_name = 'demand_forecast'
    AND status = 'champion';
```

---

### **Get Backtest Trend (Last 30 Days)**

```sql
SELECT
    forecast_date,
    mae,
    mape,
    stockout_miss_rate,
    overstock_rate
FROM backtest_results
WHERE
    customer_id = '00000000-0000-0000-0000-000000000001'
    AND forecast_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY forecast_date ASC;
```

---

### **Get Unread ML Alerts**

```sql
SELECT
    alert_type,
    severity,
    title,
    message,
    action_url,
    created_at
FROM ml_alerts
WHERE
    customer_id = '00000000-0000-0000-0000-000000000001'
    AND status = 'unread'
ORDER BY severity DESC, created_at DESC;
```

---

### **Get Active Experiments**

```sql
SELECT
    experiment_name,
    hypothesis,
    status,
    proposed_by,
    approved_by,
    created_at
FROM model_experiments
WHERE
    customer_id = '00000000-0000-0000-0000-000000000001'
    AND status IN ('proposed', 'approved', 'in_progress', 'shadow_testing')
ORDER BY created_at DESC;
```

---

## Celery Jobs

### **Scheduled Jobs**

| Job | Schedule | Description |
|-----|----------|-------------|
| `retrain_forecast_model` | Sunday 2:00 AM | Weekly retrain (auto-promote) |
| `run_daily_backtest` | Daily 6:00 AM | T-1 validation |
| `run_weekly_backtest` | Sunday 4:00 AM | 90-day backtest |
| `detect_model_drift` | Daily 3:00 AM | Drift detection |

---

### **Manual Triggers**

```python
# Manual retrain
from workers.retrain import retrain_forecast_model
retrain_forecast_model.apply_async(
    args=["00000000-0000-0000-0000-000000000001"],
    kwargs={"trigger": "manual", "data_dir": "data/seed"}
)

# Manual backtest
from workers.monitoring import run_daily_backtest
run_daily_backtest.apply_async(
    args=["00000000-0000-0000-0000-000000000001"]
)
```

---

## Model Status Flow

```
Training Complete
    ↓
status='candidate'
    ↓
    ├─→ Auto-promotion check
    │   ├─→ Improvement ≥5% → status='champion'
    │   └─→ Improvement <5% → status='challenger'
    │
    └─→ Manual review
        ├─→ Approved → status='champion'
        ├─→ Rejected → status='archived'
        └─→ Shadow test → status='shadow'
```

---

## Alert Status Flow

```
Alert Created
    ↓
status='unread'
    ↓
User Views Alert
    ↓
status='read'
    ↓
User Takes Action
    ↓
    ├─→ Approve → status='actioned'
    └─→ Dismiss → status='dismissed'
```

---

## Experiment Status Flow

```
Proposed
    ↓
status='proposed'
    ↓
Manager Reviews
    ↓
    ├─→ Approved → status='approved'
    │              ↓
    │           DS Implements
    │              ↓
    │           status='in_progress'
    │              ↓
    │           Shadow Test
    │              ↓
    │           status='shadow_testing'
    │              ↓
    │           Results Review
    │              ↓
    │           status='completed'
    │
    └─→ Rejected → status='rejected'
```

---

## Troubleshooting

### **Drift Alert Not Creating**

**Check**:
1. Drift detection job running? `docker logs <celery_worker>`
2. MAE degradation >15%? Query `forecast_accuracy` table
3. ML alerts table exists? Run migration 004

---

### **Auto-Promotion Not Working**

**Check**:
1. `customer_id` passed to `retrain_forecast_model()`?
2. Trigger is `"scheduled"` or `"manual"`? (Not `"drift_detected"`)
3. Improvement ≥5%? Check logs: `arena.auto_promoted`

---

### **Experiments Not Showing**

**Check**:
1. Experiments API router registered in `main.py`?
2. RLS context set? `SET app.current_customer_id = '{customer_id}'`
3. Customer ID matches? Query `model_experiments` directly

---

## Testing Checklist

- [ ] Migration 004 runs successfully
- [ ] Model health API returns champion/challenger
- [ ] ML alerts API returns stats
- [ ] Experiments API creates/lists experiments
- [ ] Drift detection creates alert
- [ ] Auto-promotion works for scheduled retrain
- [ ] Manual promotion works via API
- [ ] Backtest jobs run without errors
- [ ] Shadow predictions logged correctly
- [ ] Experiment workflow (propose → approve → complete)
