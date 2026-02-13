# MLOps Workflow — Autonomous + Human-in-the-Loop

**ShelfOps ML lifecycle management** combines automated retraining (scheduled + event-driven) with human-led experimentation. This document explains how both coexist.

---

## Table of Contents
1. [Automated Retraining (No Human Approval)](#1-automated-retraining-no-human-approval)
2. [Event-Driven Retraining (Human Review Required)](#2-event-driven-retraining-human-review-required)
3. [Human-Led Experiments (Hypothesis-Driven)](#3-human-led-experiments-hypothesis-driven)
4. [In-App ML Alerts](#4-in-app-ml-alerts)
5. [Model Segmentation (Department-Tiered Models)](#5-model-segmentation-department-tiered-models)
6. [Full Experiment Workflow Example](#6-full-experiment-workflow-example)

---

## 1. Automated Retraining (No Human Approval)

### **Trigger**: Weekly Schedule (Sunday 2:00 AM)

**Workflow**:
```
Sunday 2:00 AM
 ↓
Celery job: retrain_forecast_model(trigger="scheduled")
 ↓
Train on last 90 days of transactions
 ↓
Register model in DB: status='candidate'
 ↓
Auto-backtest on last 30 days
 ↓
Compare to champion: MAE, MAPE, coverage
 ↓
IF improvement ≥ 5% → PROMOTE to champion (auto)
 ↓
IF improvement < 5% → Keep as challenger (shadow test)
 ↓
Log to model_retraining_log table
```

**Key Point**: **No human approval needed** — system auto-promotes if low-risk (<5% improvement).

**Database Log**:
```sql
INSERT INTO model_retraining_log (
    customer_id, model_name, trigger_type, status, version_produced, started_at, completed_at
) VALUES (
    '00000000...', 'demand_forecast', 'scheduled', 'completed', 'v12', '2026-02-16 02:00:00', '2026-02-16 02:23:14'
);
```

**No ML Alert** — This is routine maintenance. Only logged for audit trail.

---

## 2. Event-Driven Retraining (Human Review Required)

### **Trigger**: Drift Detected (MAE degraded >15%)

**Workflow**:
```
Daily 3:00 AM: drift detection job runs
 ↓
Recent 7-day MAE: 18.5 | Baseline 30-day MAE: 12.8 → Drift = 45% degradation!
 ↓
Celery job: retrain_forecast_model(trigger="drift_detected")
 ↓
Emergency retrain on last 30 days (not 90 — faster)
 ↓
Register model: status='challenger' (NOT auto-promoted)
 ↓
Create ML Alert: "CRITICAL: Model drift detected, retrain complete, review required"
 ↓
Data scientist reviews within 2 hours:
  - Is drift real or data quality issue?
  - Check SHAP feature importance
  - Review backtest results
 ↓
IF approved → POST /api/v1/models/v13/review (action='approve')
 ↓
System promotes v13 to champion
```

**Database Logs**:
```sql
-- Retraining event
INSERT INTO model_retraining_log (...) VALUES (
    'drift_detected', '{"drift_pct": 45.2, "baseline_mae": 12.8, "recent_mae": 18.5}', ...
);

-- ML Alert
INSERT INTO ml_alerts (alert_type, severity, title, message, metadata, status, action_url) VALUES (
    'drift_detected',
    'critical',
    '🚨 Model Drift Detected — 45% MAE Degradation',
    'Champion model performance degraded significantly. Emergency retrain completed. Review v13 before promoting.',
    '{"baseline_mae": 12.8, "recent_mae": 18.5, "drift_pct": 45.2, "new_version": "v13"}',
    'unread',
    '/models/review/v13'
);
```

**UI Flow**:
1. Dashboard shows **red notification badge**: "1 Critical ML Alert"
2. User clicks → sees alert details + action button: "Review Model v13"
3. Clicks → `/models/review/v13` page showing:
   - Backtest comparison chart (v12 vs v13)
   - SHAP feature importance deltas
   - "Approve" or "Reject" buttons
4. User approves → v13 promoted to champion
5. Alert status → 'actioned'

---

## 3. Human-Led Experiments (Hypothesis-Driven)

### **Scenario**: DS observes Electronics category has worse MAE than other departments

**Hypothesis**: "Department-tiered models will improve Electronics MAE by 12-15%"

**Workflow**:
```
1. Propose Experiment
 ↓
POST /api/v1/experiments
{
  "experiment_name": "Department-Tiered Forecasting — Electronics Focus",
  "hypothesis": "Electronics demand patterns differ from Grocery/Apparel. Dedicated model will reduce Electronics MAE from 18.2 to 15.5 (15% improvement).",
  "experiment_type": "segmentation",
  "model_name": "demand_forecast",
  "proposed_by": "data_scientist@shelfops.com"
}
 ↓
Status: 'proposed' → Stored in model_experiments table
 ↓
2. Approval (Manager Reviews Hypothesis)
 ↓
PATCH /api/v1/experiments/{id}/approve
{
  "approved_by": "ml_manager@shelfops.com",
  "rationale": "Electronics has high variability (promotions + tech cycles). Tier justification approved."
}
 ↓
Status: 'approved' → approved_at timestamp set
 ↓
3. Implementation
 ↓
DS creates new feature tier: 'department_tiered'
Modifies ml/features.py:
  - Add `department` feature
  - Train 3 separate models: Electronics, Grocery, Apparel
Triggers retrain:
  retrain_forecast_model(
      trigger="experiment",
      trigger_metadata={"experiment_id": "abc-123", "tier": "department_tiered"}
  )
 ↓
Status: 'in_progress'
 ↓
3 models produced: v13_electronics, v13_grocery, v13_apparel
Register all as status='experimental' (separate from champion/challenger)
 ↓
4. Shadow Testing (7-14 days)
 ↓
All 3 experimental models run in shadow mode
Compare to global champion v12
Log to shadow_predictions table
 ↓
Status: 'shadow_testing'
 ↓
5. Results Analysis
 ↓
After 14 days shadow test:
  - Global v12 MAE: 12.8
  - Electronics v13: 14.2 (22% improvement in Electronics only!)
  - Grocery v13: 12.1 (5% improvement)
  - Apparel v13: 13.5 (no improvement)

Decision: Promote Electronics model only
 ↓
6. Promotion
 ↓
POST /api/v1/experiments/{id}/complete
{
  "decision": "partial_adopt",
  "decision_rationale": "Electronics model shows strong improvement (22%). Grocery marginal (5%). Apparel no benefit. Adopt Electronics tier, keep global for others.",
  "results": {
    "baseline_mae": 12.8,
    "electronics_mae": 14.2,
    "grocery_mae": 12.1,
    "apparel_mae": 13.5,
    "improvement_electronics_pct": 22.0
  }
}
 ↓
Status: 'completed' → completed_at timestamp
 ↓
System creates new routing logic:
  - IF product.department == 'Electronics' → use v13_electronics
  - ELSE → use global champion v12
 ↓
7. ML Alert (Experiment Complete)
 ↓
INSERT INTO ml_alerts (...) VALUES (
    'experiment_complete',
    'info',
    '✅ Experiment Complete: Department-Tiered Forecasting',
    'Electronics model improved MAE by 22%. Partially adopted. See full results.',
    '{"experiment_id": "abc-123", "improvement_pct": 22.0}',
    'unread',
    '/experiments/abc-123/results'
);
```

**Database State After Experiment**:
```sql
-- Experiment record
SELECT * FROM model_experiments WHERE experiment_id = 'abc-123';
 experiment_name        | Department-Tiered Forecasting — Electronics Focus
 hypothesis             | Electronics demand patterns differ...
 experiment_type        | segmentation
 status                 | completed
 baseline_version       | v12
 experimental_version   | v13_electronics, v13_grocery, v13_apparel
 results                | {"baseline_mae": 12.8, "electronics_mae": 14.2, ...}
 decision_rationale     | Electronics model shows strong improvement...
 approved_by            | ml_manager@shelfops.com
 completed_at           | 2026-02-20 14:23:00

-- Retraining log
SELECT * FROM model_retraining_log WHERE trigger_type = 'experiment';
 trigger_metadata       | {"experiment_id": "abc-123", "tier": "department_tiered"}
 status                 | completed
 version_produced       | v13_electronics

-- Model registry
SELECT * FROM model_versions WHERE version LIKE 'v13%';
 version               | status      | metrics
 v13_electronics       | champion    | {"mae": 14.2, "tier": "department_tiered", "segment": "Electronics"}
 v13_grocery           | archived    | {"mae": 12.1, ...}  -- Not adopted
 v13_apparel           | archived    | {"mae": 13.5, ...}  -- Not adopted
```

---

## 4. In-App ML Alerts

### **Alert Types**

| Type | Severity | Requires Action | Auto-Created By |
|------|----------|-----------------|----------------|
| `drift_detected` | critical | YES — Review retrain | Drift detection job |
| `promotion_pending` | warning | YES — Approve/reject | Auto-promotion logic |
| `backtest_degradation` | warning | MAYBE — Investigate | Daily backtest job |
| `experiment_complete` | info | NO — FYI | Experiment completion |
| `new_data_source_ready` | info | YES — Validate schema | Data integration job |
| `shadow_test_complete` | info | YES — Review results | Shadow mode job |

### **API Endpoints**

```python
# Get unread ML alerts
GET /api/v1/ml-alerts?status=unread

# Mark as read
PATCH /api/v1/ml-alerts/{id}/read

# Take action (approve/dismiss)
PATCH /api/v1/ml-alerts/{id}/action
{
  "action": "approve",  # or "dismiss"
  "notes": "Reviewed backtest, promotion approved"
}
```

### **UI Component** (Frontend Integration)

```tsx
// components/MLAlertsDropdown.tsx
<Dropdown>
  <Badge count={unreadAlerts.length} />
  <Menu>
    {alerts.map(alert => (
      <AlertItem
        severity={alert.severity}  // 'critical' → red, 'warning' → yellow
        title={alert.title}
        message={alert.message}
        actionUrl={alert.action_url}  // "Review Model v13" button
        onDismiss={() => dismissAlert(alert.id)}
      />
    ))}
  </Menu>
</Dropdown>
```

---

## 5. Model Segmentation (Department-Tiered Models)

### **Global vs Segmented Models**

| Approach | When | Pros | Cons |
|----------|------|------|------|
| **Global Model** | Default (all products) | Simple, single model to maintain | May underfit for categories with unique demand patterns |
| **Department-Tiered** | Electronics, Grocery, Apparel, Hardware | Better accuracy per department | 4x models to maintain, complex routing |
| **Store-Cluster-Tiered** | Urban vs Suburban vs Rural | Captures geographic differences | Need clustering logic |
| **Product-Lifecycle-Tiered** | New (<30 days) vs Mature | Handles cold-start better | Switching logic when products mature |

### **When to Segment** (Human Decision)

**Signals that segmentation might help**:
1. **Backtest shows category-specific degradation**: "Electronics MAE = 18.2, but Grocery MAE = 9.5"
2. **SHAP shows `category` as top feature**: Model is already trying to segment internally
3. **Business domain knowledge**: "Tech products have promotion cycles that Grocery doesn't"
4. **Data availability**: Electronics has 3+ years of history vs new category with 6 months

**Experiment Workflow**:
1. DS proposes experiment: "Hypothesis: Electronics-specific model will improve MAE by 12%"
2. Manager approves (allocates DS time/compute budget)
3. DS implements feature tier logic in `ml/features.py`
4. Shadow test for 14 days
5. Review results → decide to adopt or reject

### **Code Implementation** (Department Segmentation)

```python
# ml/features.py
def create_features(transactions_df, force_tier=None):
    tier = detect_feature_tier(transactions_df) if not force_tier else force_tier

    # NEW: Check if department segmentation is enabled
    if tier == "department_tiered":
        # Group by department, train separate models
        departments = transactions_df['category'].map(CATEGORY_TO_DEPT)
        segmented_features = {}

        for dept in departments.unique():
            dept_df = transactions_df[departments == dept]
            dept_features = _create_features_for_segment(dept_df, dept)
            segmented_features[dept] = dept_features

        return segmented_features  # Returns dict, not single DataFrame

    # Default: global model
    return _create_features_for_segment(transactions_df, segment="global")

# ml/predict.py
def predict_demand(store_id, product_id, forecast_date):
    # Load product to get department
    product = db.query(Product).get(product_id)

    # Route to correct model
    if product.department == "Electronics":
        model = load_model("v13_electronics")
    else:
        model = load_model("v12_global")  # Champion for other departments

    # Predict
    features = create_features_for_prediction(store_id, product_id, forecast_date)
    return model.predict(features)
```

---

## 6. Full Experiment Workflow Example

### **Scenario**: Adding "Google Trends" as a Feature

**Hypothesis**: "Search volume for product names correlates with demand. Adding Google Trends feature will improve MAE by 8-10%."

**Step-by-Step**:

#### **Week 1: Propose Experiment**
```bash
POST /api/v1/experiments
{
  "experiment_name": "Google Trends Feature Integration",
  "hypothesis": "Search volume for product names correlates with demand. Adding Google Trends 7-day search volume will improve MAE by 8-10%.",
  "experiment_type": "feature_engineering",
  "model_name": "demand_forecast",
  "proposed_by": "jane.doe@shelfops.com"
}
```

**Manager reviews**:
- Pros: Logical hypothesis, Google Trends API is free tier
- Cons: API rate limits (5000 requests/day), latency overhead
- Decision: **APPROVED** — but limit to top 500 SKUs only

```bash
PATCH /api/v1/experiments/{id}/approve
{
  "approved_by": "ml_manager@shelfops.com",
  "rationale": "Approved with constraint: top 500 SKUs only due to API limits. Monitor latency impact."
}
```

#### **Week 2-3: Implementation**

```python
# 1. Create Google Trends integration
# integrations/google_trends.py
def fetch_search_volume(product_name, lookback_days=7):
    from pytrends.request import TrendReq
    pytrends = TrendReq()
    pytrends.build_payload([product_name], timeframe=f'now {lookback_days}-d')
    return pytrends.interest_over_time()

# 2. Add Celery job to sync data daily
# workers/sync_google_trends.py
@celery_app.task
def sync_google_trends(customer_id):
    top_products = get_top_products(customer_id, limit=500)
    for product in top_products:
        volume = fetch_search_volume(product.name)
        db.add(GoogleTrendsData(product_id=product.id, search_volume=volume))
    db.commit()

# 3. Modify feature engineering
# ml/features.py
def create_features(transactions_df, force_tier=None):
    # ...existing logic...

    if tier == "production_with_trends":  # NEW TIER
        # Add search volume feature
        trends_data = db.query(GoogleTrendsData).filter(
            GoogleTrendsData.product_id.in_(product_ids),
            GoogleTrendsData.date >= lookback_date
        ).all()

        features_df = features_df.merge(trends_data, on='product_id', how='left')
        features_df['search_volume_7d'] = features_df['search_volume'].fillna(0)

    return features_df

# 4. Trigger retrain
retrain_forecast_model(
    customer_id="00000000...",
    trigger="experiment",
    trigger_metadata={
        "experiment_id": "exp-456",
        "feature_added": "search_volume_7d",
        "tier": "production_with_trends"
    }
)
```

**Status**: `in_progress` → `shadow_testing`

#### **Week 4-5: Shadow Testing**

```sql
-- Shadow mode runs both models in parallel
SELECT
    AVG(ABS(champion_prediction - actual_demand)) AS champion_mae,
    AVG(ABS(challenger_prediction - actual_demand)) AS challenger_mae,
    COUNT(*) AS samples
FROM shadow_predictions
WHERE
    created_at >= NOW() - INTERVAL '14 days'
    AND forecast_date <= NOW() - INTERVAL '1 day';  -- Only compare actuals available

-- Results:
-- champion_mae: 12.8
-- challenger_mae: 11.5  (10.2% improvement!)
-- samples: 47,823
```

#### **Week 6: Review Results**

```bash
GET /api/v1/experiments/exp-456/results
{
  "experiment_id": "exp-456",
  "status": "shadow_testing",
  "shadow_test_duration_days": 14,
  "baseline_mae": 12.8,
  "experimental_mae": 11.5,
  "improvement_pct": 10.2,
  "samples": 47823,
  "recommendation": "PROMOTE — Exceeded hypothesis target (10.2% > 8% threshold)"
}
```

**DS Decision**: APPROVE

```bash
POST /api/v1/experiments/exp-456/complete
{
  "decision": "adopt",
  "decision_rationale": "Exceeded target (10.2% improvement). Latency impact minimal (avg +12ms per prediction). Recommend full rollout.",
  "results": {
    "baseline_mae": 12.8,
    "experimental_mae": 11.5,
    "improvement_pct": 10.2,
    "latency_impact_ms": 12,
    "api_cost_monthly": 0  // Free tier sufficient
  }
}
```

**System Actions**:
1. Promote v14 (with Google Trends) to champion
2. Update production feature tier → `production_with_trends`
3. Archive v12 (old champion)
4. Create ML Alert: "Experiment Complete — Google Trends feature adopted"
5. Update `model_experiments` table: `status='completed'`

---

## Summary: Logging for All Scenarios

| Scenario | Logged To | Human Approval | Alert Created |
|----------|-----------|----------------|---------------|
| **Weekly scheduled retrain** | `model_retraining_log` | NO | NO |
| **Drift-triggered retrain** | `model_retraining_log` + `ml_alerts` | YES | YES (critical) |
| **New data source added** | `model_retraining_log` + `model_experiments` | YES | YES (info) |
| **Human experiment (new feature)** | `model_experiments` + `ml_alerts` | YES (proposal + results) | YES (experiment_complete) |
| **Department segmentation** | `model_experiments` + `model_versions` (multiple) | YES | YES |
| **Manual retrain (no experiment)** | `model_retraining_log` | NO | NO |
| **Shadow test complete** | `shadow_predictions` + `ml_alerts` | MAYBE | YES (info) |
| **Backtest degradation** | `backtest_results` + `ml_alerts` | MAYBE | YES (warning) |

---

## Next Steps

1. **Run Migration 004** to create all 6 MLOps tables
2. **Implement ML Alerts API** (`/api/v1/ml-alerts`)
3. **Implement Experiments API** (`/api/v1/experiments`)
4. **Add Dashboard UI** for alerts + experiments
5. **Test Full Workflow** with mock experiment

**All logs are queryable** for compliance, audit trail, and "how did we get here?" debugging.
