# ShelfOps — ML Model Improvement Plan

- Last verified date: March 10, 2026
- Audience: ML engineers and reviewers
- Scope: historical diagnosis that explains why the current LightGBM-first path replaced the older stack
- Author: DS Lead review, February 24, 2026
- Status: Historical analysis — not the current runtime contract
- Source of truth: use `backend/ml/train.py`, `backend/ml/arena.py`, `backend/workers/retrain.py`, and active engineering docs for current behavior
- Prerequisite reading: `docs/MLOPS_STANDARDS.md`, `backend/ml/train.py`, `backend/ml/features.py`

> Historical note: this document captures the February 2026 diagnosis that led to the
> current LightGBM-first pipeline. The live runtime contract now lives in
> `backend/ml/train.py`, `backend/ml/arena.py`, `backend/workers/retrain.py`,
> `docs/engineering/model_tuning_and_dataset_readiness.md`, and
> `docs/overview/technical_overview.md`.

---

## 1. Diagnosis — Where the Models Actually Are

Before designing improvements, we need to be honest about what the logged metrics are telling us.

### 1.1 The Weight Sweep Finding (Most Important)

A historical weight sweep on the old seed dataset logged the following result. The conclusion is clear:

| XGB Weight | LSTM Weight | Ensemble MAE | Ensemble MAPE |
|---|---|---|---|
| **1.00** | **0.00** | **36.36** | **1.12** |
| 0.90 | 0.10 | 38.32 | 1.20 |
| 0.80 | 0.20 | 40.27 | 1.28 |
| 0.65 | 0.35 | **43.21** | **1.40** |
| 0.50 | 0.50 | 46.15 | 1.52 |

**The LSTM is actively dragging down every metric.** The current production default (65/35) produces MAE 19% worse than pure XGBoost. Every additional point of LSTM weight makes the ensemble worse in a perfectly linear degradation. The system already flagged this — the `model_strategy_cycle` recommendation was `single_xgboost`, but it was held as challenger because business metrics were incomplete.

**The current champion (v1) has MAE 41.98, MAPE 0.286** — trained on only 27 rows of Favorita cold-start data. That is not a usable model.

### 1.2 MAPE Is Misleading Us

v2-v4 show MAE ~5 but MAPE ~1.13. A MAPE of 1.13 means the model is off by 113% on average. This is not a model that's "close" to the target — it's a signal that the dataset has a lot of near-zero actual sales days. When `actual ≈ 0`, even a small absolute error produces MAPE → ∞. The metric is failing us, not the model.

**Action**: Retire MAPE as the primary gate metric. Replace with WAPE or MASE (see Section 4).

### 1.3 Dataset Scale

The current live tenant training runs on 3,668 rows. That is a very small dataset for a gradient-boosted tree with 500 estimators, and it is nowhere near enough for the LSTM (which hit 55.9 MAE vs XGBoost's 36.4 on 20,000 rows). The LSTM is underfitting due to data starvation. This is likely the root cause of the ensemble degradation.

### 1.4 Overstock Rate at ~0.60

The replay simulation logged an overstock rate of 0.597 — 60% of inventory decisions resulted in excess stock. The model is systematically over-predicting demand. This is a bias problem (not a variance problem), and it won't be fixed by tuning hyperparameters. It likely comes from the hardcoded business rules in `predict.py` (seasonal +20%, promo lift multipliers) being applied without learned calibration, compounded by a model that hasn't seen enough real replenishment cycles.

### 1.5 Intermittent Demand — The Missing Problem

Retail SKU demand is frequently intermittent (long periods of zero sales, then bursts). The current feature set and model architecture treat all SKUs identically. XGBoost and LSTM both struggle with intermittent demand patterns — the series is too sparse for rolling windows to be meaningful. This category of SKU likely drives most of the MAPE blowup.

---

## 2. Immediate Actions (This Sprint)

These have near-zero implementation risk and directly address the most impactful issues found above.

### 2.1 Make Pure XGBoost the Default

The weight sweep already told us this. The ensemble is held in place by config, not by evidence. Change `ENSEMBLE_WEIGHTS` in `train.py` to `{"xgboost": 1.0, "lstm": 0.0}` and document the decision. The LSTM can run in shadow mode while we retrain it properly.

The arena gate already handles challenger routing. The LSTM path doesn't disappear — it just stops dragging the production output.

### 2.2 Replace MAPE with WAPE and MASE

```python
# WAPE: Weighted Absolute Percentage Error
# = sum(|actual - pred|) / sum(|actual|)
# Resistant to zero-actual blowup because error is weighted by actual magnitude

# MASE: Mean Absolute Scaled Error
# = MAE / MAE_naive_baseline
# where naive baseline = last observed value
# MASE < 1.0 means you're beating a naive forecast — MASE > 1.0 means you're not
```

Both metrics replace MAPE in the arena gate and in monitoring drift detection. This alone will make the model comparisons meaningful instead of dominated by near-zero SKU edge cases.

### 2.3 Add Bias Tracking

The model is systematically over-predicting (60% overstock). We have no metric for directional bias. Add Mean Error (ME = mean(pred - actual)) alongside MAE. If ME > 0, the model is over-predicting; if ME < 0, it's under-predicting. A model with low MAE but high positive ME is worse for inventory than one with slightly higher MAE and near-zero ME.

Add `mean_error` and `bias_pct` (ME / mean_actual) to `ForecastAccuracy` and to the arena gate.

### 2.4 Segment Intermittent SKUs Before Training

Before fitting any model, classify each SKU as:
- **Continuous**: fewer than 20% zero-sales days in training window
- **Intermittent**: 20–70% zero-sales days (Croston-applicable)
- **Lumpy**: 70%+ zero-sales days (treat separately)

The current architecture trains one model on all three types mixed together. At minimum, filter out lumpy SKUs from the XGBoost training set and generate fixed-rate reorder recommendations for them instead of ML forecasts. This will reduce noise in the training data significantly.

---

## 3. Model Architecture Improvements (Next 2 Sprints)

### 3.1 Switch Primary Booster: XGBoost → LightGBM

LightGBM consistently outperforms XGBoost on retail demand data for three reasons:
- Histogram-based splitting is ~10x faster, enabling more iterations in the same compute budget
- Native categorical feature handling — `product_id` and `store_id` can be passed as categoricals instead of label-encoded integers, which often captures store/SKU effects better
- `poisson` objective function is appropriate for count data (sales quantities) — XGBoost doesn't have this built in

The `train.py` interface stays the same; only the booster changes. This is a candidate/challenger comparison through the existing arena gate.

```python
# lgb.LGBMRegressor proposed config (tune with Optuna)
lgb.LGBMRegressor(
    objective='poisson',        # count data
    n_estimators=1000,
    learning_rate=0.02,
    num_leaves=127,
    min_child_samples=20,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    categorical_feature=['product_id_cat', 'store_id_cat'],  # native cats
    random_state=42,
)
```

### 3.2 Add Quantile Regression (Proper Prediction Intervals)

The current prediction intervals are computed from `std(xgb_preds - lstm_preds)`. This is not a proper confidence interval — it's the disagreement between two models, which is a completely different quantity. It is not calibrated and will not hold at the stated 90% coverage.

LightGBM has native quantile regression (`objective='quantile'`). Train three separate LightGBM models:
- `q10` (lower bound)
- `q50` (median forecast)
- `q90` (upper bound, for safety stock calculation)

This directly improves the reorder point optimizer, which currently uses an uncalibrated interval to set safety stock.

```python
# One training pass per quantile
for alpha in [0.10, 0.50, 0.90]:
    model = lgb.LGBMRegressor(objective='quantile', alpha=alpha, ...)
    model.fit(X_train, y_train)
```

Add a calibration check after training: on the holdout set, verify that the 90% interval contains the actual value ≥ 90% of the time. If not, isotonic regression can be applied to recalibrate the bounds.

### 3.3 Rethink the LSTM — N-HiTS or TFT

If we want a sequence model in the ensemble, the current LSTM is the wrong architecture:
- 64→32 units is too small to learn seasonal patterns over 30 days
- A 30-day lookback window misses the most important seasonality cycles for retail (7-day weekly, 28-day monthly, 365-day annual)
- The 50k sample cap prevents the model from seeing the full training set
- 20 epochs with patience=5 is not enough to converge on a meaningful sequence representation

Two alternatives to evaluate:

**Option A: N-HiTS (Neural Hierarchical Interpolation for Time Series)**
- Specifically designed for multi-rate seasonality decomposition
- Faster to train than LSTM, more interpretable
- Works well on the ~3k–50k sample ranges we're operating in
- PyTorch, similar complexity to replace existing LSTM code

**Option B: Temporal Fusion Transformer (TFT)**
- Designed explicitly for multi-horizon retail forecasting (originally developed at Google)
- Handles static covariates (product metadata: category, unit_cost, is_seasonal) + temporal covariates (lags, promotions) in a principled way
- Native quantile output — directly replaces the fake PI approach
- Attention weights are interpretable (shows which timesteps the model is using)
- More complex to train, higher data requirement (~50k+ sequences)
- Likely not worth it until we have more than 3.6k rows of live data

**Recommendation**: Hold both LSTM alternatives until we have at least 180 days of live tenant data. Use pure LightGBM + quantile regression as the production model in the interim. Re-evaluate sequence model when data scale justifies it.

### 3.4 Hierarchical / Per-Department Models (Federation)

The request to explore "dept specific with a global model" maps to hierarchical forecasting. The approach:

**Global model**: Trained on all tenants, all categories — captures universal temporal patterns (day-of-week, month, holiday effects, promo lift shapes).

**Department-level fine-tuned models**: The global model's output becomes an additional feature in a department-specific model. The department model learns residuals — what's different about dairy vs. apparel vs. electronics demand patterns.

This is a two-stage architecture:
```
Stage 1: global_model(features) → global_forecast
Stage 2: dept_model(features + global_forecast) → final_forecast
```

For ShelfOps this maps to:
- Global: one model per tenant, trained on all product categories
- Category-specific: one model per (tenant, category) with ≥ N training rows (e.g., ≥ 500 rows)
- Fallback: if category has insufficient data, use global model prediction as-is

The `detect_feature_tier()` pattern in `features.py` gives us the right abstraction — add a third tier: `detect_model_tier()` that selects between `global`, `category_specific`, and `sku_specific` based on data depth.

**Implementation note**: This adds complexity to `retrain.py` and requires the model registry to store a model tree (global + N category models) per version. The arena gate logic needs to compare ensemble trees, not individual models. Plan for a 3-sprint effort.

---

## 4. Feature Engineering Improvements (Ongoing)

### 4.1 Replace Label Encoding with Target Encoding for High-Cardinality Categoricals

`category_encoded` in `features.py` uses `LabelEncoder`, which assigns arbitrary integers to categories. For a tree model this is inefficient — the tree must learn which integers are similar by trial and error.

Target encoding replaces each category with the mean target value for that category, computed on the training fold only (to prevent leakage). This is particularly powerful for `product_id` and `store_id`, which currently are not encoded at all and are dropped before training.

```python
# Per fold in TimeSeriesSplit (computed on train, applied to val)
for col in ['store_id', 'product_id', 'category']:
    means = X_train.groupby(col)['quantity'].mean()
    X_train[f'{col}_target_enc'] = X_train[col].map(means)
    X_val[f'{col}_target_enc'] = X_val[col].map(means).fillna(global_mean)
```

### 4.2 Add Cross-SKU Store-Level Aggregates

Currently, features describe only the focal SKU. But store-level signals add important context:
- `store_total_sales_yesterday` — overall store traffic signal
- `store_category_sales_7d` — category-level velocity (rising tide)
- `category_rank_in_store` — is this SKU a top mover or a tail SKU in this store?

These are already computable from the existing transaction table. Add as new features to the production tier (46 → ~52 features).

### 4.3 Add Historical Forecast Error as a Feature

If the model was wrong last week, it is likely wrong in the same direction this week. Log the previous period's forecast error `(forecast_t-1 - actual_t-1)` as a feature called `last_forecast_error`. This gives the model a self-correction signal and should reduce systematic bias.

```python
forecast_error = forecast_quantity_prev - actual_quantity_prev  # signed
features['last_forecast_error'] = forecast_error.shift(1)
```

### 4.4 Improve Intermittent Demand Representation

For intermittent SKUs (≥ 20% zero-sales days), standard rolling features are misleading. A 7-day rolling average that spans 6 zero-sales days and 1 sale day looks very different from one with 7 regular low-volume days, but the rolling mean is the same.

Add two features specifically for intermittent demand:
- `avg_inter_demand_interval`: average number of days between non-zero sales events
- `cv2` (squared coefficient of variation of inter-demand intervals): classifies demand pattern (Croston's ADI/CV² grid)

These features inform the model when demand should be treated as intermittent vs. continuous, and are low-cost to compute.

### 4.5 Remove the Hardcoded Post-Prediction Multipliers

The current `apply_business_rules()` in `predict.py` applies:
- `+20%` for seasonal items in months 6, 7, 11, 12
- A `promotion_lift` multiplier from the promotions table

These are post-hoc adjustments that override model predictions with fixed rules. The problem: the model already receives `is_promotion_active`, `is_seasonal`, and `month` as features. If it has seen enough promotion and seasonal data, it learns the lift itself. The hardcoded multipliers stack on top of that, causing double-counting and the observed systematic over-prediction.

Audit which SKUs have both the model-learned effect and the multiplier applied. Remove the hardcoded multipliers and instead validate that the model's SHAP output for `is_seasonal` and `is_promotion_active` is plausible. If it is, the multipliers are redundant. If it isn't, the root fix is more promotion/seasonal data in training, not a hardcoded override.

---

## 5. Evaluation Framework Improvements

### 5.1 Business-Centric Metrics Alongside Statistical Metrics

The arena currently gates on MAE, MAPE, coverage, stockout miss rate, overstock rate, and overstock dollars. The statistical metrics (MAE, MAPE) measure forecast accuracy in isolation. The business metrics measure outcomes. These are not perfectly correlated.

Add an explicit **composite score** as the primary promotion gate criterion:

```
composite_score = w1 × WAPE_norm + w2 × stockout_miss_rate + w3 × overstock_rate + w4 × bias_abs
w1=0.35, w2=0.35, w3=0.20, w4=0.10  (starting weights; tune via cost analysis)
```

This makes the arena more like a business decision and less like a statistics test.

### 5.2 Per-Segment Evaluation

A model that performs well on average can fail badly on specific segments:
- **High-velocity SKUs** (top 20% by volume) — model errors here have the biggest financial impact
- **Seasonal SKUs** — performance should be measured in-season vs. out-of-season separately
- **New SKUs** (< 90 days history) — cold-start performance should be tracked separately

Add `evaluate_by_segment()` to `backtest.py`. The arena still uses aggregate metrics for the promotion decision, but segment breakdowns are logged for DS review and surfaced in the monitoring dashboard.

### 5.3 Calibration Testing for Prediction Intervals

Currently there is no test that the 90% prediction intervals actually contain the true value 90% of the time. Once quantile regression is in place, add a calibration curve to the backtest output: for each stated coverage level (70%, 80%, 90%), what is the empirical coverage on the holdout set? If the 90% interval only contains the truth 70% of the time, the safety stock calculations downstream are wrong.

### 5.4 Naive Baseline Benchmark (MASE Denominator)

Every evaluation run should also compute a naive last-value baseline. MASE < 1.0 means we're better than naive. If MASE > 1.0, we are worse than not having a model at all. Right now we do not compute this, so we cannot answer the question "is the ML model actually adding value over a simple average?"

---

## 6. Longer-Term Architecture (3+ Sprints Out)

### 6.1 LightGBM + Prophet Hybrid

For tenants with 1+ years of data, a two-stage pipeline:
1. **Prophet** decomposes trend and weekly/annual seasonality into explicit components
2. **LightGBM** is trained on the residuals from Prophet, along with all contextual features

This matches what large grocery and mass-market retailers use. The seasonality curve is handled analytically (Prophet is very good at this); the gradient booster handles everything else (promotions, cross-SKU, vendor effects, anomalies).

### 6.2 True Conformal Prediction Intervals

Replace quantile regression intervals with split conformal prediction. This provides distribution-free coverage guarantees regardless of the underlying model. After training the point-estimate model on the training set, calibrate on a held-out calibration fold:

```python
residuals = actual_calibration - predicted_calibration
q_level = np.ceil((1 + alpha) * n) / n  # adjusted quantile
q = np.quantile(np.abs(residuals), q_level)
# Interval: [pred - q, pred + q]
```

The coverage guarantee holds for any test point drawn from the same distribution, without assumptions about residual normality. This directly fixes the uncalibrated PI problem identified in Section 1.

### 6.3 Online Learning / Continual Adaptation

The current system retrains on a schedule. Between retrains, the model is static. For high-velocity SKUs, a lightweight online update (gradient boosting with warm start, or exponential smoothing of the model's residuals) would let the forecast adapt within hours of a demand shift.

This is a significant infrastructure change (requires a stateful model object, careful version management) but is the pattern that enables real-time accuracy at enterprise scale.

### 6.4 Foundation Model Evaluation

Amazon's Chronos (2024) and Nixtla's TimeGPT are pre-trained time-series foundation models. For short-history tenants (< 90 days), zero-shot inference from a foundation model may outperform a from-scratch XGBoost/LightGBM trained on limited data. Worth a benchmark evaluation once the rest of the pipeline is stable:

```python
# Evaluation protocol
for new_tenant_windows in [7d, 14d, 30d, 60d]:
    compare(
        our_model_fine_tuned_on_window,
        chronos_zero_shot,
        lightgbm_cross_tenant_pretrained,
    )
```

---

## 7. Phased Execution Plan

### Phase A — Immediate (Current Sprint)

| Action | File(s) | Effort | Impact |
|---|---|---|---|
| Set XGBoost weight to 1.0, LSTM to 0.0 | `train.py` | 1h | High — removes active degradation |
| Replace MAPE with WAPE + MASE | `metrics_contract.py`, `arena.py`, `monitoring.py` | 1d | High — makes comparisons meaningful |
| Add bias (ME, bias_pct) to accuracy tracking | `monitoring.py`, `models.py` | 0.5d | Medium — quantifies systematic over-prediction |
| Segment intermittent SKUs before training | `features.py`, `train.py` | 1d | Medium — reduces noise in training data |

### Phase B — Next Sprint

| Action | File(s) | Effort | Impact |
|---|---|---|---|
| LightGBM as primary booster (Poisson objective) | `train.py` | 2d | High — better model for count data |
| Optuna hyperparameter tuning | `train.py` | 1d | Medium — stop leaving perf on the table |
| Quantile regression (q10, q50, q90) | `train.py`, `predict.py` | 2d | High — proper PIs for safety stock |
| Target encoding for category/store/product | `features.py` | 1d | Medium — better categorical representation |
| Remove hardcoded business rule multipliers | `predict.py` | 0.5d | Medium — fixes double-counting bias |
| Naive baseline benchmark (MASE denominator) | `backtest.py` | 0.5d | Medium — know if model is adding value |

### Phase C — 2 Sprints Out

| Action | File(s) | Effort | Impact |
|---|---|---|---|
| Cross-SKU store-level aggregate features | `features.py` | 1d | Medium |
| Historical forecast error as feature | `features.py`, `forecast.py` | 1d | Medium |
| Per-segment evaluation in backtest | `backtest.py` | 1d | Medium |
| Calibration curve for prediction intervals | `backtest.py`, `arena.py` | 1d | Medium |
| Composite arena score | `arena.py` | 1d | Medium |

### Phase D — 3+ Sprints Out

| Action | Effort | Impact |
|---|---|---|
| Hierarchical per-department models | 3–4 sprints | High (but complex) |
| LightGBM + Prophet hybrid | 2 sprints | High (data-dependent) |
| N-HiTS or TFT sequence model (after data scale) | 3 sprints | High (when data justifies) |
| Conformal prediction intervals | 1 sprint | High |
| Foundation model benchmark (Chronos/TimeGPT) | 1 sprint | TBD |

---

## 8. What Large Retailers Actually Use

For reference — what the enterprise competition looks like:

**Walmart (M5 competition winner)**: LightGBM with hierarchical aggregation features (store-total, category-total, national-total as features for the SKU-level model). No LSTM. Heavy feature engineering on calendar effects, price changes, and snap benefits.

**Amazon**: AutoML ensemble internally. DeepAR+ (probabilistic LSTM) for externally facing forecasting services. Foundation model (Chronos) for zero-shot. The key pattern: they invest heavily in getting clean, complete data pipelines and use relatively standard models with excellent feature engineering.

**Kroger / large grocery**: Category-level hierarchical forecasting. Store-cluster models (stores grouped by size, demographics, geography). Heavy use of markdown/promotion event features. Conformal prediction for safety stock.

**The consistent takeaway across enterprise retail**: Feature engineering and clean data outperform architecture. LightGBM with good features beats LSTM with mediocre features in almost every benchmark. The sequence models earn their keep only when there is very long clean history (2+ years per SKU) and the seasonality patterns are complex. Our current data scale does not justify the LSTM complexity.
