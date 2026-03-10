# ShelfOps — Strategy Brainstorm

- Last verified date: March 10, 2026
- Audience: builders and planners
- Scope: open ideas, unresolved questions, and future strategy threads
- Status: **Active planning document — not a source of truth for current runtime behavior**
- Source of truth: verify all current-state claims against `docs/README.md`, active docs, and code before reusing them externally
- Started: February 24, 2026
- Purpose: Capture all open ideas, questions, and strategy threads before splitting into
  specific specs, runbooks, or improvement plans. Nothing here is a commitment yet.

---

## How to Use This File

- Add ideas freely, mark open questions with `[ ]`, resolved ones with `[x]`
- When a section is ready to become a real doc, move it to the appropriate place in `docs/`
  and replace the section here with a pointer
- Reference existing docs to avoid duplicating what is already decided

---

## 0. What Already Exists (Ground Truth)

Before brainstorming forward, a quick audit of what is actually in the codebase and docs.
Knowing this prevents us from designing things that are already built.

### Feedback Loop — Already Built

`backend/ml/feedback_loop.py` converts PO decision outcomes into forecast model features.
It is **not a separate model** — it enriches the training feature matrix.

Three features produced:
- `rejection_rate_30d` — % of model suggestions buyer rejected in last 30 days
- `avg_qty_adjustment_pct` — how much buyers are adjusting recommended quantities on average
- `forecast_trust_score` — composite signal of buyer agreement with model

These are computed per-tenant, per-SKU, and fed back into the next training cycle via
`features.py`. The loop is: PO decision → `PODecision` table → `feedback_loop.py` at
training time → feature matrix → model retrain.

**Important edge case not yet handled**: Not all buyer overrides are corrections.
See Section 3.3 (Feedback Quality) for open questions here.

### Arena — Already Built

`backend/ml/arena.py` — 7-gate promotion system:
1. Minimum rows threshold
2. MAE improvement gate
3. Business metric gates (stockout miss rate, overstock rate, overstock dollars)
4. SHAP stability check
5. Shadow canary window (14-day holdback)
6. Optional human DS sign-off
7. Auto-promotion on full pass

Shadow mode and canary routing are operational. The arena is already per-tenant
(uses `customer_id` on `ModelVersion`).

**Gaps identified**:
- No per-segment evaluation (high-velocity vs. intermittent vs. seasonal SKUs)
- No minimum hold period before a newly promoted champion can be unseated
- No composite score — gates are sequential pass/fail, not weighted
- Champion staleness detection not implemented (model degrading on live data post-promotion)

### Multi-Location Store Clustering — Open Design Space

The earlier store-tier segmentation prototype was removed during the March 2026 cleanup
because it was not part of the active runtime. The open need is still valid: model
stores by something richer than raw volume.

**Gap**: KNN-based regional similarity is not implemented. See Section 4 (Multi-Location).

### Retrain Pipeline — Already Built

`backend/workers/retrain.py` — 4 trigger types:
- `scheduled` (Celery periodic)
- `drift_detected` (monitoring threshold breach)
- `new_products` (new SKU onboarded)
- `manual` (DS-triggered)

Milestone-based triggers (fire when a tenant crosses 30d / 90d / 180d / 365d of data)
are **not implemented**. See Section 2 (Model Lifecycle).

### Current Model Architecture

- Production: LightGBM-first forecast path with business-first promotion gates
- Legacy XGBoost/LSTM comparisons remain only as historical evaluation artifacts
- Anomaly detection: Isolation Forest (separate model, `anomaly.py`)
- Segmented/category-specific forecasting is a future experiment area, not part of the active runtime
- `promo_lift` and `lead_time` models referenced in `arena.py` — not yet implemented

### SMB Onboarding — Partially Built

`docs/operations/smb_onboarding_runbook.md` — covers the data ingestion and validation
path (CSV/SFTP → contract profile → Pandera gates → candidate training → DS/business gates).
SLA target: first valid forecast within 3-5 business days.

**Gap**: This runbook is about getting data in. It does not describe the model lifecycle
after onboarding (how the model improves, when it graduates off cold-start, what the
buyer experiences during that journey). See Section 2.

---

## 1. The SMB Value Proposition Problem

### 1.1 Core Question

Why would an SMB pay for this product if the model isn't good on day 1?

ShelfOps serves two distinct buyer types:
- **Platform buyers**: want the all-in-one dashboard (inventory, orders, PO workflows,
  supplier communication, decision feedback). The ML is a bonus.
- **DS/ML buyers (SMBs without a data team)**: the whole point is that we run the DS
  function for them. They are buying model quality and improving accuracy over time.
  A bad model is a broken product for this buyer.

For the DS/ML buyer, the demo question is: *can you show me this actually works?*
The answer requires **real metrics at every stage**, not just a nice UI.

### 1.2 The Pre-Trained Model Must Be Demonstrably Good

The cold-start model is the first impression. Currently it is trained on 27 rows of
Favorita data — this is not a usable model (`ml_improvement_plan.md` Section 1.1 confirms).

**Target for a credible pre-trained model:**
- Train on full Favorita + M5 (Walmart hierarchical) + Rossmann datasets
  (~54M rows Favorita, ~42k series M5, ~1M rows Rossmann)
- Objective: LightGBM with Poisson objective (count data, not MSE)
- Target metrics: MASE < 0.9 on held-out test set, WAPE < 0.35
- These are numbers that can go in a demo slide and mean something

**Why these datasets work for cold-start:**
- Favorita: 54M rows, 3400 stores, Ecuador grocery — real weekly/holiday/promo cycles
- M5: Walmart hierarchical — 5 aggregation levels, 42k series, US calendar events
- Rossmann: 1M+ rows, German drug store chain — strong promotional effects
- Together they give the model a wide prior over retail demand patterns
- A real SMB's data will look different but the temporal patterns (weekly cycles, holiday
  spikes, promo lifts) transfer well

**Key feature families needed for transfer:**
- Lags: 1d, 7d, 14d, 28d
- Rolling mean/std: 7, 14, 28 windows
- Calendar: day-of-week, month, is_holiday, days_to_holiday (lead/lag)
- Promo flag + promo duration
- Price if available (elasticity signal)
- Category-level aggregated demand (hierarchical signal from M5)

**Open questions:**
- [ ] Do we train one global pre-trained model or separate ones per retail vertical
  (grocery, drug, hardware, apparel)? Vertical-specific might transfer better.
- [ ] How do we validate that the pre-trained model generalizes to a new tenant's data
  before we deploy it as their cold-start baseline? Need a held-out evaluation protocol.
- [ ] MASE requires a naive baseline denominator — define the naive baseline consistently
  across pre-training and live tenant evaluation.

### 1.3 The Demo Story (Three Required Moments)

For the demo to land with an SMB, three things must be visible:

**Moment 1 — Cold start credibility**: Day 0. Load their SKU/transaction data. Run the
pre-trained model on their last 30 days (held out). Show MASE < 1.0, beating naive
baseline. Answer the question: *the product works on day 1, before you've committed.*

**Moment 2 — Graduation event**: Show 30/90-day milestone firing (see Section 2).
Shadow training runs on screen. Arena comparison shown: tenant-specific model vs.
cold-start global model. New model wins because it has learned this retailer's specific
patterns. Answer: *your data is making the model smarter.*

**Moment 3 — A prevented stockout**: Walk through one SKU. Model flagged it 48h before
it would have hit zero. Reorder suggestion generated. Buyer approved. Stock arrived.
Answer: *this is the ROI.* Everything else is means to this end.

---

## 2. Per-Tenant Model Lifecycle

### 2.1 The Core Gap

The current onboarding runbook covers data ingestion. There is no documented lifecycle
for what happens to the model after onboarding. The buyer doesn't know when their model
will improve, what triggers it, or how they'll know when it has.

This section is a brainstorm toward a `MODEL_LIFECYCLE.md` doc (not written yet).

### 2.2 Proposed Lifecycle Stages

```
Onboarding
    │
    ▼
[Stage 0] Cold Start — < 30 days of tenant data
  Active model: pre-trained global LightGBM (Favorita + M5 + Rossmann)
  Training: none (zero-shot inference only)
  Arena: not yet active for this tenant
  Buyer experience: forecasts are "category-calibrated" — not yet personalized
    │
    ▼  30 days of transaction data
[Stage 1] Early Tenant — 30–90 days
  Trigger: milestone at 30d (see Section 2.3 on milestone triggers)
  Shadow: first tenant-specific LightGBM trained from scratch on tenant data
  Arena: compare shadow vs. cold-start global on held-out tenant data
  Expected winner: fine-tuned global for most SMBs (not enough data for pure fresh)
  Buyer experience: model starts personalizing — rejection feedback begins mattering
    │
    ▼  90 days of transaction data  ← current production_tier activation threshold
[Stage 2] Established Tenant — 90–365 days
  Trigger: milestone at 90d
  Shadow A: tenant-specific LightGBM (Poisson, Optuna-tuned per tenant)
  Shadow B: per-category sub-models for high-volume categories
  Arena: compare all candidates, segment-aware evaluation
  Expected: tenant-specific model graduates to champion
  Buyer experience: clearly personalized, correction feedback has measurable effect
    │
    ▼  1 year of transaction data
[Stage 3] Mature Tenant — 1yr+
  Trigger: milestone at 365d
  Architecture candidates (see Section 5 — not one-size-fits-all):
    - LightGBM + Prophet hybrid (grocery, mass market — strong annual seasonality)
    - Hierarchical per-department models (category-heavy retailers)
    - TFT or N-HiTS (fashion, multi-store complex patterns) [data-dependent]
  Arena: per-segment evaluation, composite score gate
  Buyer experience: the model is now genuinely theirs
```

### 2.3 Milestone Triggers — Not Yet Implemented

The current retrain pipeline fires on schedule or on drift. It does not fire on data
depth milestones. This is needed for the lifecycle to work.

**What needs to be built in `retrain.py`:**

```python
def _check_data_milestones(customer_id: UUID) -> list[int]:
    """
    Returns list of milestone days crossed since last check.
    e.g. [30] if just crossed 30d, [30, 90] if both crossed.
    """
    # Query: SELECT MIN(transaction_date), MAX(transaction_date) FROM transactions
    # WHERE customer_id = ? AND data_gap = FALSE
    # Compute data_span_days — NOT calendar days since signup, actual data depth
    # Compare against [30, 90, 180, 365] thresholds
    # Return newly crossed thresholds (not previously triggered)
```

**Edge case — data density check**: A tenant can have 90 calendar days of data but only
20% of SKUs with complete history (sparse onboarding, partial ETL). Graduating to Stage 2
on sparse data produces a worse model. Milestone should require **both**:
- Data span ≥ threshold in calendar days
- Data density ≥ 60% (% of active SKUs with ≥ threshold days of signal)

**Edge case — retroactive milestones**: A tenant migrates 2 years of historical data on
day 1. They should jump straight to Stage 3, not wait 12 months. The milestone check
should fire all thresholds in sequence at onboarding if historical data covers them.

### 2.4 New SKU Cold Start Within Established Tenant

Even a Stage 3 tenant launches new products. A new SKU in a mature tenant should not
force the entire model to cold-start.

**Per-SKU cold start logic:**
- New SKU detected → tag `sku_data_age_days` in feature matrix
- For SKUs with < 30 days: fall back to category-level mean as forecast prior
- Blend in per-SKU signal as data accumulates (weighted average, weight → 1.0 at 90d)
- The global tenant model continues unchanged — only the new SKU's prediction is
  affected until it has enough history

**Not implemented anywhere currently.** Would go in `features.py` and `predict.py`.

---

## 3. Feedback Loop — What Exists and What's Missing

### 3.1 What's Already Working

`feedback_loop.py` converts PO decisions into features. This is architecturally correct.
The loop:
1. Buyer approves / rejects / edits a PO suggestion
2. Decision + reason code stored in `PODecision` table
3. At next training cycle, `feedback_loop.py` computes per-SKU signals
4. Those signals become features in the next model training run
5. Model learns: "buyer consistently rejects this SKU → adjust prior"

### 3.2 Feedback Loop Latency Problem

**Current gap**: A buyer rejects a PO suggestion today. The next scheduled retrain is
in 7 days. The model will issue the same suggestion again tomorrow.

**Fix needed**: A short-term override cache (Redis or in-memory) that suppresses
re-issuing a PO suggestion that was rejected within the last N days, independent of
when the next training cycle fires. This is not a model change — it is a prediction
serving change in `predict.py` or the API layer.

The override cache should respect `rejection_reason`. A `supplier_constraint` rejection
should suppress the suggestion for 30 days. A `budget_constraint` rejection should
suppress for 7 days. A `model_error` rejection should suppress until next retrain.

### 3.3 Feedback Quality — The Critical Edge Case

**Not all buyer overrides are model corrections.** Training on all feedback uncritically
teaches the model to mimic buyer behavior, not to predict demand.

The `PODecision` table has a `rejection_reason` field. Currently it exists but there is
no logic enforcing which reason codes flow back into training vs. which are logged only.

**Proposed rule — what flows into training labels:**
- `model_error` → YES, use as corrective training signal
- `data_entry_mistake` → YES, but validate before using

**Proposed rule — what does NOT flow into training labels:**
- `supplier_constraint` → log only (the model was right, supplier was the constraint)
- `budget_constraint` → log only (financial, not demand signal)
- `buyer_preference` → log only (policy preference, not demand signal)
- `lead_time_change` → flag for lead_time model, not forecast model

**Risk if not enforced**: A buyer who is consistently conservative will train a model
that systematically under-orders. Over time the model learns buyer policy, not reality.
The `rejection_rate_30d` feature becomes a proxy for buyer conservatism, not for model
quality — which corrupts the feedback signal.

**Where to implement**: `feedback_loop.py` — add a filter before computing the training
signal features. Log all decisions; only use `model_error` and `data_entry_mistake` for
label correction.

### 3.4 Promotional Intent as Forward-Looking Feedback

**Not currently implemented.** A buyer knows next week's promo before the model does.

If a buyer enters "I'm running a BOGO on item X next week" in the UI, that is a
high-signal forward-looking feature. Currently there is no way to capture this.

**Needed**: A `planned_event` input in the buyer UI (promo type, SKU, date range,
expected uplift if known). These get written to a `PlannedPromotions` table and picked
up as features at prediction time — not just training time. This is qualitatively
different from the historical promo flag in the current feature set.

This closes the loop between what the buyer knows and what the model knows, and is one
of the highest-value UX additions for the SMB segment (buyers know their promos;
they just have no way to tell the model).

---

## 4. Multi-Location — Regional Similarity via KNN

### 4.1 Current State

The earlier `segmentation.py` prototype was removed because it was not part of the live
Favorita workflow and its fixed tier taxonomy did not match the current dataset strategy.
The open question remains the same: "which other stores are this store most like?"

Behavioral similarity is still an unsolved feature opportunity — two stores can have the
same volume but completely different demand patterns (one near a university, one in a suburb).

### 4.2 The KNN Regional Similarity Idea

For multi-location tenants (a small chain with 3–15 stores), the key problem is that
individual stores have sparse per-SKU data but the chain as a whole has richer data.

**The KNN approach:**
- Define a store feature vector: geographic region, avg basket size, top category mix,
  weekly traffic pattern shape, proximity to competitors, local event density
- For a new or sparse store, find its K nearest neighbor stores in this feature space
- Borrow their demand signal (weighted by similarity) as additional training data for
  the sparse store's model

This is fundamentally different from the current K-Means approach. K-Means groups stores
for routing. KNN borrows signal from similar stores for data-sparse situations.

**Where it fits in the lifecycle:**
- Relevant at Stage 0 and Stage 1 (data-sparse stores)
- At Stage 2+, a store's own data is sufficient — KNN signal weight decreases as
  own-store data accumulates (same blending logic as new-SKU cold start in Section 2.4)

**Implementation sketch:**
```python
# In features.py, for stores with < 90 days of data:
neighbor_stores = knn_store_index.query(store_feature_vector, k=5)
neighbor_signal = transactions.where(store_id.in_(neighbor_stores)).weighted_avg(
    weights=similarity_scores
)
features['neighbor_demand_signal'] = neighbor_signal
features['neighbor_weight'] = max(0.0, 1.0 - (own_data_days / 90.0))
```

**Edge cases:**
- [ ] Stores in different regions may have systematically different demand patterns
  (regional preference, local holidays). Need to bound KNN search to same region or
  weight similarity scores by geographic distance.
- [ ] If a chain opens a store in a new market with no similar stores in the system,
  KNN falls back to category-level global prior — same as single-location cold start.
- [ ] KNN index needs to be rebuilt when new stores onboard or when store profiles
  change significantly. How often does this rebuild happen? Who triggers it?

### 4.3 Hierarchical Forecasting for Multi-Location

KNN is for cold-start borrowing. The longer-term architecture for mature multi-location
tenants is hierarchical forecasting (already in `ml_improvement_plan.md` Section 3.4):

```
Level 0: Global tenant model (all stores, all categories)
Level 1: Store-cluster models (grouped by KNN similarity, not just volume)
Level 2: Per-store model (once data is sufficient)
```

Reconciliation (bottom-up vs. top-down) becomes important when you have store-level
models that need to sum to chain-level totals for procurement. This is a complex
forecasting problem. Not in current architecture at all.

---

## 5. Not One-Size-Fits-All — Architecture Selection Per Retailer

### 5.1 The Core Idea

Different retail verticals have structurally different demand patterns. The winning model
architecture varies by retailer type, not just by data depth. The arena should be free
to select different architectures for different tenants.

**Demand structure by vertical:**
| Vertical | Key pattern | Likely champion at Stage 3 |
|---|---|---|
| Grocery / FMCG | Strong weekly cycle, promo-driven, high volume | LightGBM + calendar features |
| Apparel / fashion | Long seasonal arcs, trend-driven, sparse mid-season | LightGBM + Prophet or TFT |
| Hardware / home improvement | Weather-correlated, project-driven bursts | LightGBM + weather features |
| Electronics | Product lifecycle curves, launch spikes, markdown cliffs | XGBoost/LGB + launch-age features |
| Foodservice supply | Daily perishable cycles, 1–3 day horizon | Different loss function entirely |

**The point**: when two tenants in different verticals end up with different champion
architectures, that is the arena working correctly — not a product inconsistency.

### 5.2 `detect_model_tier()` — Parallel to `detect_feature_tier()`

`features.py` already has `detect_feature_tier()` that selects the 27-feature vs.
45-feature set based on data depth. We need a parallel function that selects which
**architecture candidates** to spin up as shadow models at each milestone.

```python
def detect_model_tier(
    customer_id: UUID,
    data_depth_days: int,
    data_density_pct: float,
    retailer_vertical: str,  # set at onboarding: grocery | apparel | hardware | etc.
) -> list[str]:
    """
    Returns list of architecture IDs to spin up as shadow candidates at this milestone.
    Does not spin up architectures the current data depth cannot support.
    """
    candidates = ["lightgbm_poisson"]  # always available

    if data_depth_days >= 90 and data_density_pct >= 0.6:
        candidates.append("lightgbm_optuna_tuned")

    if data_depth_days >= 180:
        if retailer_vertical in ("grocery", "mass_market"):
            candidates.append("lightgbm_prophet_hybrid")
        if data_density_pct >= 0.8:
            candidates.append("per_category_federated")

    if data_depth_days >= 365 and data_density_pct >= 0.8:
        if retailer_vertical in ("apparel", "fashion"):
            candidates.append("tft")  # data-hungry, not before 365d
        candidates.append("nhits")

    return candidates
```

**Not implemented anywhere currently.** This is the key function needed to make the
multi-architecture lifecycle work.

### 5.3 Model Registry — Architecture Tagging

Currently `ModelVersion` in `models.py` stores model metadata but all versions are
implicitly the same architecture (XGBoost/LSTM ensemble). The registry needs an
`architecture` field to track which architecture a version uses, enabling:
- Arena to compare architectures fairly (compare within data-depth tier)
- Monitoring to detect when a tenant's champion architecture changes (graduation event)
- Audit trail for DS review (why did tenant X switch from LightGBM to Prophet hybrid?)

**What to add to `ModelVersion`:**
```python
architecture: str  # e.g. "lightgbm_poisson" | "lightgbm_prophet_hybrid" | "tft"
architecture_version: str  # semantic version of the architecture config
data_depth_days_at_training: int  # how much data the model was trained on
retailer_vertical: str  # vertical at training time
```

---

## 6. Arena Edge Cases — Hardening

The arena is mostly built (7 gates). These are the gaps and edge cases that need to
be closed before the demo.

### 6.1 Minimum Champion Hold Period

A model promoted yesterday should not be demotion-eligible until it has seen at least
one full weekly cycle. Currently there is no minimum hold period.

**Fix**: Add `promoted_at` timestamp to `ModelVersion`. Arena gate 5 (canary window)
should enforce: if `now - promoted_at < 14 days`, do not evaluate for demotion.
14 days ensures two full weekly cycles.

### 6.2 Per-Segment Evaluation in Arena

A challenger that beats the champion on aggregate MAE but performs worse on
high-velocity SKUs should not be promoted — errors on high-velocity SKUs have
the largest financial impact.

**Fix**: Add `evaluate_by_segment()` to `backtest.py`. Arena evaluates:
- High-velocity (top 20% by volume) — must not regress
- Seasonal (tagged by `is_seasonal` flag) — in-season evaluation only
- Intermittent (≥ 20% zero-sales days) — separate MASE denominator
- New SKUs (< 90 days history) — cold-start segment

Challenger must not regress on any critical segment. Currently the arena uses only
aggregate metrics. This is the biggest gap in the current evaluation framework.

### 6.3 Champion Staleness Detection

A model promoted 6 months ago may be degrading on live data (concept drift, seasonal
shift, business change). Currently there is no monitoring for post-promotion decay.

**Fix**: Add a rolling performance check in `monitoring.py`. If the champion's rolling
MASE (14-day window) degrades > 15% from its baseline (MASE at promotion time),
trigger a `drift_detected` retrain regardless of the scheduled cycle. This is distinct
from the current drift detection which watches for distribution shift in features — this
watches for **output quality decay** on live actuals vs. predictions.

### 6.4 Composite Promotion Score

The current 7 gates are sequential pass/fail. A model that barely passes all gates
and a model that dominates all gates are treated identically.

**Fix** (from `ml_improvement_plan.md` Section 5.1 — already spec'd, not implemented):
```
composite_score = 0.35 × WAPE_norm + 0.35 × stockout_miss_rate +
                  0.20 × overstock_rate + 0.10 × bias_abs
```
Use this as the tiebreaker when multiple challengers pass all gates in the same cycle.

---

## 7. MLflow Namespacing Per Tenant

**Current state**: All experiments log to a single `shelfops_demand_forecast` experiment
in MLflow. When we have multiple tenants running shadow training simultaneously,
the experiment view becomes uninterpretable — runs from different tenants with different
data depths and architectures are mixed.

**Fix**: Namespace experiments per tenant:
```python
experiment_name = f"shelfops/{customer_id}/demand_forecast"
```

Sub-runs within a tenant experiment:
```
shelfops/{customer_id}/demand_forecast
  ├── run: lightgbm_poisson_milestone_90d_2026-02-24
  ├── run: lightgbm_optuna_milestone_90d_2026-02-24
  └── run: global_cold_start_baseline
```

This also makes it possible to compare a tenant's model history over time — answer the
question "when did this tenant's model get good?" which is a key demo narrative moment.

**What changes**: `train.py` and `retrain.py` — the `mlflow.set_experiment()` call.
Low-effort change, high payoff for observability and demo narrative.

---

## 8. Codebase Changes Master List

Everything we've identified that needs to be built. Roughly prioritized.
Cross-reference with `ml_improvement_plan.md` which covers Phases A–D in detail.
This list adds what is NOT already in that plan.

### New (not in `ml_improvement_plan.md`)

| Change | File(s) | Priority | Section |
|---|---|---|---|
| Milestone-based retrain triggers (30/90/180/365d) | `retrain.py` | High | 2.3 |
| Data density check in milestone evaluation | `retrain.py` | High | 2.3 |
| Retroactive milestone handling at onboarding | `retrain.py`, `run_onboarding_flow.py` | Medium | 2.3 |
| Per-SKU cold start logic within established tenant | `features.py`, `predict.py` | Medium | 2.4 |
| Feedback quality filter (reason codes → training or not) | `feedback_loop.py` | High | 3.3 |
| PO suggestion override cache (suppress re-issue of rejected suggestion) | `predict.py` / API layer | High | 3.2 |
| Planned promotions input (buyer forward-looking event entry) | UI, `PlannedPromotions` model, `features.py` | Medium | 3.4 |
| KNN store similarity index | new segmentation module, `features.py` | Medium | 4.2 |
| KNN neighbor signal feature (weighted demand borrowing) | `features.py` | Medium | 4.2 |
| `detect_model_tier()` — architecture candidate selection | `features.py` | High | 5.2 |
| `architecture` field on `ModelVersion` | `models.py`, Alembic migration | High | 5.3 |
| Minimum champion hold period (14d) | `arena.py` | Medium | 6.1 |
| Per-segment arena evaluation | `backtest.py`, `arena.py` | High | 6.2 |
| Champion staleness detection (rolling MASE decay trigger) | `monitoring.py` | Medium | 6.3 |
| MLflow experiment namespacing per tenant | `train.py`, `retrain.py` | Low | 7 |

### Already Spec'd in `ml_improvement_plan.md` (Do Not Duplicate)

Phases A–D of `ml_improvement_plan.md` cover: XGBoost → LightGBM, MAPE → WAPE/MASE,
bias tracking, intermittent SKU segmentation, quantile regression, target encoding,
hardcoded multiplier removal, hierarchical models, Prophet hybrid, N-HiTS/TFT,
conformal prediction, online learning, Chronos/foundation model benchmark.

---

## 10. Infrastructure Gaps

### 10.1 Celery Beat — Single Point of Failure

**Current state**: All 12 scheduled jobs run through a single Celery beat process.
No HA configuration. If beat crashes, all scheduled work stops: retrains, vendor metrics
updates, forecast jobs, monitoring checks — everything.

**Known limitation** (`known_limitations.md`). The fix is RedBeat (Redis-backed Celery
beat scheduler with distributed locking). Two beat instances can run simultaneously;
only one acquires the lock per interval. No custom Celery changes needed.

**Impact on ML**: If beat crashes at midnight when the nightly retrain is scheduled,
no tenant gets an updated model. No alert fires. The champion is silently stale.
This is a demo-day risk and a reliability risk.

**Fix needed**: Add RedBeat to `celery_app.py` config, add a beat health check
endpoint, add alerting when a scheduled job hasn't fired within 2× its expected interval.

### 10.2 No Staging Environment

**Current state**: Local dev only (docker-compose). CI is fixture-based and replay
simulations. No persistent staging tier.

**Risk**: The gap between "passing CI" and "working in production" is handled by
deterministic tests and replay, which is good — but any stateful behavior (Celery
job timing, Redis cache expiry, Postgres connection pooling under load) is invisible
until production.

**For the demo specifically**: If we're running a live demo from the same environment
that's under development, a broken commit the night before takes down the demo.
Need at minimum a frozen demo environment that is independent of active dev.

**Fix needed**: A GCP Cloud Run staging deployment (separate project or namespace)
that is updated on merge to main, not continuously. The demo runs from staging, not
local. This also validates the Docker → Cloud Run deployment path.

### 10.3 No Horizontal Autoscaling for ML Workers

**Current state**: The `ml` Celery queue runs on a fixed worker pool. No autoscaling.

**Scenario**: 50 tenants all trigger milestone retrains at the 90-day mark simultaneously
(e.g., a batch onboarding cohort). All retrain jobs queue behind each other.
The last tenant waits hours for their graduation event.

**Fix needed**: Cloud Run worker autoscaling for the `ml` queue. GCP Cloud Run already
supports this — the Celery worker container can scale to N instances based on queue
depth (Cloud Tasks or Redis queue length metric). This is infrastructure config,
not code changes.

### 10.4 Webhook Dead-Letter Queue

**Current state**: Inbound webhook events (Square POS, custom) are processed
synchronously. If the processing pipeline fails after acknowledgment, the event is
lost — no replay, no dead-letter queue.

**Risk**: A Square webhook fires at 9pm (large sale event that would trigger a reorder
alert). Processing fails due to a transient DB error. The event is gone. The model
never sees the sale. The next forecast is wrong.

**Fix needed**: Persist all inbound webhook payloads to a `WebhookEvent` table on
receipt (before any processing). The processing pipeline reads from this table.
On failure, the event stays in the table with `status = failed` and retries on next
Celery beat cycle. Dead-letter after N failures with an alert.

This is also valuable for debugging — a complete audit trail of every event received.

### 10.5 Data Freshness / ETL Staleness Alerting

**Not in any current doc.** This is a major silent failure mode.

If a tenant's ETL integration stops flowing data (Square API key rotated, SFTP
credentials changed, webhook endpoint changed), the model keeps running and issuing
forecasts — based on increasingly stale data. The model looks like it's working;
it's actually forecasting from data that's 5 days old.

**How this surfaces in production without detection**: Forecasts degrade silently.
Stockout alerts stop firing (model thinks inventory is at pre-disruption levels).
Buyer trusts the dashboard. Stockouts happen. Buyer blames the model.

**Fix needed**: A `data_freshness_check` Celery job (runs every hour) that checks
`MAX(transaction_date)` per tenant against `NOW()`. If the gap exceeds:
- 6 hours (Kafka/webhook tenant): raise `data_staleness_warning` alert
- 24 hours (SFTP/EDI tenant): raise `data_staleness_critical` alert
- 48 hours: suppress forecast recommendations with a UI banner ("Data connection
  interrupted — forecasts may be unreliable")

This is the difference between a product that fails silently and one that fails
visibly and gracefully.

### 10.6 No Tenant-Level Observability Dashboard

**Confirmed gap** (`known_limitations.md`). Monitoring data exists in the DB
(`IntegrationSyncLog`, accuracy backfill tables, `ModelVersion`) but is not surfaced
in the UI for operators or tenants.

**Two surfaces needed:**
1. **Operator view**: Per-tenant health grid. For each tenant: data freshness,
   last retrain timestamp, current champion MASE, active integration status, open
   alerts count. This is the DS/operator view.
2. **Tenant buyer view** (connects to demo): Model performance trend over time.
   "Your forecast accuracy has improved from MASE 0.95 to MASE 0.71 since onboarding."
   This is the ROI proof surface for the SMB buyer — make the model improvement visible
   without requiring them to understand MASE.

### 10.7 Forecast Horizon Too Short for Seasonal Planning

**Current state**: `ml_forecast_horizon_days = 14` in `core/config.py`. The stockout
risk report can query up to 90 days (`horizon_days: int = Query(7, ge=1, le=90)`) but
only 14 days of forecast data actually exists.

**Business impact**: A retailer who needs to place Christmas inventory orders in
October needs a 60–90 day demand view. A 14-day horizon doesn't support this buying
cycle at all. The buyer can't use ShelfOps for their most important procurement
decisions of the year.

**Fix needed**: Make forecast horizon configurable per tenant (up to 90 days).
Longer horizons need explicit confidence decay communicated to the buyer
(a 90-day forecast is less certain than a 14-day one). The `detect_model_tier()`
function (Section 5.2) should also factor in horizon length — a tenant requesting
a 60-day horizon needs a model that's been validated at that horizon, not just at 14.

**For seasonal SKUs specifically**: `is_seasonal` flag already exists on the Product
model. For `is_seasonal=True` SKUs, the system should automatically generate a
longer-horizon forecast during the relevant lead-up period (e.g., Q4 planning window
for holiday items). The horizon extension is SKU-scoped, not tenant-wide.

---

## 11. Retail Business Logic Gaps

### 11.1 Perishables — Data Exists, Optimizer Doesn't Use It

**Current state**: `is_perishable` and `shelf_life_days` exist on the Product model
and are included in the 45-feature set in `features.py`. The optimizer does **not**
treat perishable SKUs differently from non-perishable ones.

**The problem**: For a perishable SKU with a 5-day shelf life, safety stock of 30 units
is not conservative — it's wasteful. You'll discard most of it. EOQ math that minimizes
holding cost vs. order cost is also wrong for perishables (holding cost is not 25% per
year — if it expires in 5 days, holding cost is 100% per cycle).

**What the optimizer needs for perishable SKUs:**
- Cap safety stock: `safety_stock ≤ floor(shelf_life_days / 2 × avg_daily_demand)`
  — don't buffer more than half a shelf life cycle's worth
- Adjust effective holding cost: `holding_cost = unit_cost / shelf_life_days × 365`
  (full write-off risk if not sold, not 25% of cost)
- Use shorter effective lead time horizon: for a 5-day shelf life item, a 7-day
  lead time means you can never hold safety stock — this is a sourcing problem,
  not a model problem, and should surface as an alert

**Not complex to implement** — the optimizer already has all the inputs. It's a
conditional branch on `is_perishable` in `calculate_dynamic_reorder_point()`.

### 11.2 Returns and Reverse Logistics

**Not found anywhere in the codebase.** This is a silent inventory corruption source.

When goods are returned, they go back into inventory. From the system's perspective,
a return looks like a large negative demand event (or just an inventory level jump).
Without explicit handling:
- The model may interpret returns as low demand periods (training signal pollution)
- Safety stock calculations see artificially inflated available inventory
- Reorder triggers don't fire when they should because on-hand looks high

**What's needed:**
- A `return_type` field on inventory adjustments: `customer_return | vendor_return |
  damaged_return | recall`
- `customer_return` stock: add back to available inventory, exclude from demand signal
- `damaged_return`: never add back to available inventory, log as shrinkage
- `vendor_return`: remove from inventory and create a negative PO event
- In the training pipeline: mask return events from demand calculation
  (returns are not demand signal — they're corrections)

### 11.3 Substitution and Cannibalization Effects

**Not in the codebase.** One of the most impactful gaps for multi-SKU retailers.

When Product A is out of stock, some customers buy Product B (substitution).
When a store expands Product A's shelf space and promotes it, Product C loses sales
(cannibalization). The current model treats every SKU as independent.

**Why this matters for stockout prediction**: If Product A's forecast is low because
Product B was substituting for it (and Product B is now being discontinued), Product A's
true demand will spike. The model trained on historical data will under-forecast.

**Practical approach for initial implementation**:
- Don't model the full substitution matrix (exponentially complex)
- Instead: detect high correlation between stockout periods of one SKU and demand
  spikes in category neighbors — flag these pairs
- Add `substitute_sku_id` as an optional field on Product (buyer-managed)
- When a substitute SKU is in stockout, add a feature `substitute_in_stockout` = True
  to the correlated SKU's feature vector

**The KNN store idea (Section 4) applies here too**: K nearest SKUs in feature space
(same category, similar price tier, similar velocity) can be used to estimate
substitution signal without requiring explicit buyer annotation.

### 11.4 Dropship SKUs — Should Skip ROP/EOQ Entirely

**Not found in the codebase.** No `is_dropship` flag exists.

Dropship SKUs are never held in inventory — the supplier ships direct to customer on
order. Running ROP/EOQ on a dropship SKU is meaningless and will generate false
reorder alerts. This is a data quality issue that would confuse buyers immediately.

**Fix needed**:
- Add `fulfillment_type: owned | dropship | consignment` to the Product model
  (Alembic migration)
- The optimizer's batch run should skip `fulfillment_type = dropship` SKUs entirely
- For `consignment` SKUs: the ROP logic is different — you're not ordering from a
  supplier, you're just triggering a replenishment request to the consignor. The cost
  model changes (no purchase cost, no holding cost in the traditional sense)

### 11.5 Per-SKU Service Level Policy

**Current state**: A single `DEFAULT_SERVICE_LEVEL = 0.95` applies to all SKUs.
The parameter can be passed per-call but there's no UI or data model to support
buyer-configured service level policies.

**Why this matters**: A high-margin, high-velocity SKU (e.g., a flagship product)
warrants a 0.99 service level — the cost of a stockout is very high. A slow-moving
tail SKU (e.g., an obscure specialty item) might warrant only 0.85 — excess holding
cost for a rarely-sold item is worse than an occasional stockout.

**Using a flat 0.95 for all SKUs**:
- Over-stocks tail SKUs (high holding cost on low-movers)
- Under-protects critical SKUs (0.95 means a 5% stockout rate on your best seller)

**Fix needed**: A `service_level_tier: critical | standard | tail` field on Product
(or Category). Buyer can classify their SKUs. Optimizer maps tiers to Z-scores:
`critical → 0.99`, `standard → 0.95`, `tail → 0.90`.

### 11.6 Inventory Strategy Modes — Normal vs. Clearance vs. Pre-Season Buildup

**Not in the codebase.** The optimizer has one objective: maintain service level.
Retailers have three distinct buying modes depending on season position:

- **Normal mode**: minimize stockouts while minimizing holding cost. Current behavior.
- **Clearance mode**: end-of-season / markdown — goal is to sell through remaining
  stock by a target date. Do NOT reorder. The optimizer should flip to a sell-through
  target: "at current velocity, will we sell through by [date]?" and alert if not.
- **Pre-season buildup mode**: before a peak season, intentionally overbuy to a target
  stock level for SKUs expected to run out mid-season. The optimizer should support
  a "build to X units by Y date" goal, not just maintain ROP.

**Fix needed**: An `inventory_strategy` field on `ReorderPoint` or `Product`:
`normal | clearance | buildup`. When `clearance`, suppress reorder recommendations.
When `buildup`, the optimizer targets a stock level, not a ROP.

For the model: clearance mode also means the demand signal changes — markdowns spike
demand. If `clearance_mode=True` and a price reduction is active, the model should
be aware that current demand is not representative of normal demand (affects future
training signal quality — mark these transactions as `is_clearance=True` in the
transaction table and exclude from normal demand training).

### 11.7 Vendor Reliability — Dynamic Update Is Built, But Is It Wired?

**Positive finding**: `backend/workers/vendor_metrics.py` exists and updates supplier
reliability scores based on actual delivery performance. This is better than expected.

**Open question**: Is `vendor_metrics.py` wired into the Celery beat schedule in
`celery_app.py`? If not, the worker exists but never runs. Need to verify.

**Second gap**: When `vendor_metrics.py` updates a supplier's `reliability_score` and
it drops below a threshold (e.g., from 0.95 to 0.72), does that automatically trigger
a ROP recalculation for all affected SKUs? Currently the ROP is only recalculated on
the nightly batch. A supplier reliability drop mid-day is not reflected until the
next nightly run — potentially too late for a buyer to react.

**Fix needed**: When `vendor_metrics.py` updates a reliability score that crosses a
tier boundary (see `RELIABILITY_MULTIPLIERS` in `optimizer.py`), publish a
`vendor_reliability_changed` event that triggers an on-demand ROP recalculation for
affected SKUs. This closes the loop from actual delivery data → adjusted safety stock.

---

## 12. Demo and Product Experience Gaps

### 12.1 Model Improvement History Not Visible in the UI

**The biggest demo gap.** The data to tell this story exists in the DB:
- `ModelVersion` table: champion history, promotion timestamps, MASE at promotion
- `ForecastAccuracy` table: rolling accuracy over time

But there is no UI surface that shows a buyer their model's performance improving
over time. From the buyer's perspective, the model just... runs. They can't see
that it's getting better.

**For the SMB DS/ML buyer specifically**, this is the core value prop. They hired
ShelfOps (or the DS lead) because they don't have a data team. They want to see
that the investment is working.

**What's needed in the UI:**
- A "Model Health" card on the main dashboard showing current MASE and a sparkline
  trend (last 90 days). Arrow up/down. Plain language: "Your forecast accuracy
  has improved 23% since onboarding."
- A "Model History" timeline — key events annotated: "Model updated (your data)",
  "Graduation: model now trained on your transactions", "Milestone: 90-day model"
- The "graduation event" should generate a notification/alert to the buyer:
  "Your model was just updated with 90 days of your data. Accuracy improved from
  MASE 0.87 → 0.71."

### 12.2 Feedback Loop Impact Not Quantified

**Current state**: Buyer corrections flow into training but there's no UI feedback
that tells them "your corrections improved the model."

**What's needed**: A `FeedbackImpact` metric in the monitoring pipeline:
- Track MASE on SKUs where the buyer provided `model_error` corrections
  vs. MASE on uncorrected SKUs
- Surface this in the UI: "You've provided 47 corrections this month. On those SKUs,
  forecast accuracy improved 18% vs. uncorrected SKUs."
- This closes the psychological loop for the buyer — their input is visibly valued

### 12.3 SHAP Not in the UI Dashboard

**Confirmed gap** (`known_limitations.md`). The MLOps page shows a global feature
importance bar chart (top 15 features for the champion model), but there are no
per-prediction SHAP values exposed anywhere.

**Correction to prior notes**: The statement "the data is already there" is inaccurate.
Per-prediction SHAP values are not stored in the database, not returned by any forecast
endpoint, and `ForecastResponse` has no `shap_values` field. The local waterfall PNGs
generated by `explain.py` are written to disk and not reachable via any API route. This
is a backend + frontend task, not frontend only.

**For the buyer**: The SHAP waterfall chart is the most compelling "explainability"
visual. A buyer asking "why is the model recommending I order 200 units of Product X?"
can see: "Lead time (45%), Promo event next week (30%), Low current stock (15%), ..."

**What's needed**:
- Backend: a `GET /api/v1/forecasts/{forecast_id}/explain` endpoint that runs
  `TreeExplainer` on the champion model at inference time and returns signed per-feature
  SHAP values for that specific prediction
- Schema: add `shap_values: dict[str, float] | None` to `ForecastResponse` (optional —
  only populated when the explain endpoint is called, not on bulk forecast queries)
- Frontend: a collapsible waterfall panel in `ProductDetailPage.tsx` below the forecast
  chart, rendered with Recharts horizontal bars (positive = demand-increasing driver,
  negative = demand-suppressing driver)
- Caching: SHAP computation is ~50ms per prediction for XGBoost; cache results in Redis
  keyed by `(forecast_id, model_version)` with a 1-hour TTL to avoid recomputing on
  repeated views

### 12.4 Prediction Intervals Not Visible

**Confirmed gap** (`known_limitations.md`). Once quantile regression is implemented
(`ml_improvement_plan.md` Phase B), the q10/q50/q90 values should be surfaced
in the forecast chart as a confidence band, not just the point estimate.

**For the buyer**: A narrow band means the model is confident. A wide band on a
specific SKU is a signal to the buyer that this item is hard to predict — they should
hold extra safety stock or pay closer attention. This is actionable uncertainty.

### 12.5 Integration Health Not Visible to Buyers

**Gap confirmed**. If a buyer's Square integration starts dropping events, there is
no UI indicator. From their perspective, the dashboard looks normal. Data is silently
stale (Section 10.5 covers the backend alerting). The frontend needs:
- An integration status indicator per connected source
- Last sync timestamp prominently displayed
- A banner when data is stale: "Last transaction received 18 hours ago —
  check your Square connection"

---

## 13. Security and Data Isolation Gaps

### 13.1 RLS Is Developer-Discipline-Dependent

**Confirmed** (`known_limitations.md`). Row-level security is enforced via
`SET LOCAL app.current_tenant` and the `get_tenant_db` convention. There is no
external audit layer.

**Risk**: Any route that accidentally uses `get_db` instead of `get_tenant_db`
returns data for all tenants. CLAUDE.md explicitly lists this as forbidden, but
there's no automated check that enforces it.

**Fix needed**: A CI lint rule (or a custom Ruff rule) that flags any import of
`get_db` in files under `api/v1/routers/` or `api/v1/`. This turns a discipline
requirement into an automated check that fails CI. Low effort, high confidence gain.

### 13.2 PII Handling in ML Training Data

**Not found in any doc or code review.** Open question.

Transaction data may contain `customer_id` fields from loyalty programs. If a
retailer's POS data includes loyalty card IDs, those IDs flow into the training
pipeline. ML models trained on PII-containing datasets have regulatory implications
(GDPR if any EU tenant, CCPA for California retailers).

**What to check:**
- Does the transaction data ingested via SFTP/EDI/webhook include customer-level
  loyalty IDs or any PII beyond SKU/quantity/timestamp?
- Is there a PII scrubbing step in the contract mapper / normalization pipeline
  before data reaches `DemandForecast` or training datasets?
- If loyalty IDs are used as features (they shouldn't be — they're individual
  customer identifiers, not demand signals), that's a data misuse issue.

**Action**: Audit `contract_profiles.py` and the normalization pipeline for
any field mappings that might pass through customer-level PII.

### 13.3 Model Artifacts Per-Tenant Access Control

**Open question.** MLflow model artifacts store trained weights for each tenant's
champion model. These artifacts implicitly encode information about the tenant's
business (demand patterns, seasonal effects, promotion responses).

If MLflow artifact storage is not access-controlled per tenant (i.e., all artifacts
live in the same bucket/directory with no tenant isolation), then:
- A compromised DS account could pull another tenant's model artifacts
- Cross-tenant artifact reads would not be caught by RLS (RLS is DB-level,
  not file-level)

**What to check**: The MLflow artifact store configuration. Are artifacts stored
in a path that includes `customer_id`? Is read access scoped per tenant?

---

## 14. Updated Codebase Changes Master List

Additions to Section 8 from new findings in Sections 10–13.

| Change | File(s) | Priority | Section |
|---|---|---|---|
| RedBeat HA scheduler for Celery beat | `celery_app.py`, `docker-compose.yml` | High | 10.1 |
| Beat health check + missed-job alerting | `monitoring.py`, new endpoint | Medium | 10.1 |
| Frozen demo environment (staging Cloud Run) | infra / CI | High | 10.2 |
| Cloud Run autoscaling for `ml` Celery queue | GCP config | Medium | 10.3 |
| Webhook dead-letter queue (`WebhookEvent` table) | `models.py`, Alembic, webhook processors | High | 10.4 |
| Data freshness check job + staleness alerting | `workers/`, `monitoring.py` | High | 10.5 |
| Operator tenant health dashboard | frontend | Medium | 10.6 |
| Buyer-facing model improvement history card + timeline | frontend | High | 12.1 |
| Configurable forecast horizon per tenant (up to 90d) | `config.py`, `train.py`, `predict.py` | Medium | 10.7 |
| Seasonal SKU extended horizon (auto, scoped by is_seasonal) | `predict.py`, `workers/` | Medium | 10.7 |
| Perishable-aware optimizer (capped SS, adjusted holding cost) | `optimizer.py` | Medium | 11.1 |
| Returns handling (`return_type` field, mask from demand signal) | `models.py`, Alembic, `features.py` | Medium | 11.2 |
| SKU substitution signal (correlated stockout feature) | `features.py`, `models.py` | Low | 11.3 |
| `fulfillment_type` on Product (owned/dropship/consignment) | `models.py`, Alembic, `optimizer.py` | Medium | 11.4 |
| Per-SKU service level tier (critical/standard/tail) | `models.py`, Alembic, `optimizer.py`, UI | Medium | 11.5 |
| Inventory strategy mode (normal/clearance/buildup) | `models.py`, Alembic, `optimizer.py`, UI | Medium | 11.6 |
| Verify `vendor_metrics.py` is wired to Celery beat | `celery_app.py` | High | 11.7 |
| Reliability tier-crossing → on-demand ROP recalculation trigger | `vendor_metrics.py`, `optimizer.py` | Medium | 11.7 |
| SHAP waterfall panel in product detail view | frontend | Medium | 12.3 |
| Prediction interval confidence band in forecast chart | frontend | Medium | 12.4 |
| Integration health / data staleness indicator in UI | frontend | High | 12.5 |
| Feedback loop impact metric + UI surface | `monitoring.py`, frontend | Medium | 12.2 |
| Graduation event notification to buyer | `workers/retrain.py`, alerts, frontend | High | 2 / 12.1 |
| CI lint rule blocking `get_db` in authenticated routers | CI / Ruff config | Medium | 13.1 |
| PII audit of contract mapper / normalization pipeline | `contract_profiles.py`, ETL | High | 13.2 |
| MLflow artifact path tenant isolation audit | MLflow config | Medium | 13.3 |

---

## 9. Open Questions — Not Yet Resolved

- [ ] **Pre-training vertical split**: One global pre-trained model or separate models
  per retail vertical (grocery, apparel, hardware)? Vertical-specific likely transfers
  better but requires more maintenance.
- [ ] **KNN feature vector**: What goes into the store similarity vector? Geographic
  region encoding, traffic pattern shape, basket size, category mix. Need to define
  exactly — and these features must be available at onboarding, not just post-hoc.
- [ ] **Multi-store reconciliation**: When a chain has per-store models, do chain-level
  procurement totals come from summing store-level forecasts (bottom-up) or from a
  chain-level model (top-down)? Bottom-up is more accurate per store; top-down is
  more stable for procurement planning. Probably need both and a reconciliation step.
- [ ] **LSTM path**: Does the LSTM ever come back? `ml_improvement_plan.md` says hold
  until 180d+ of tenant data and data scale justifies it. N-HiTS is the preferred
  replacement. When is the decision point?
- [ ] **Retailer vertical capture at onboarding**: `detect_model_tier()` needs a
  `retailer_vertical` field set at tenant onboarding. Where does this live in the
  data model? Who sets it? Can it be inferred from their product category distribution?
- [ ] **PlannedPromotions UX**: How does a buyer enter a planned promotion? Is this
  a separate UI surface, or part of the PO approval flow? What fields are required?
  (promo type, affected SKUs, date range, expected lift %)
- [ ] **Demo data**: Do we use a real pilot tenant's data for the demo, or construct
  a realistic anonymized dataset? Real data is more credible; synthetic is safer for
  privacy. If real, we need tenant consent and data masking at minimum.
- [ ] **Foundation model cold start**: `ml_improvement_plan.md` Section 6.4 suggests
  benchmarking Chronos/TimeGPT for sub-90d tenants. At what data threshold does the
  foundation model become worth evaluating? When do we schedule this experiment?
- [x] **Vendor metrics wiring**: CONFIRMED wired. `update_vendor_scorecards` is
  registered in `celery_app.py` beat schedule on the `sync` queue.
- [ ] **PII audit**: Do any contract mapper / normalization pipelines pass through
  loyalty card IDs or other customer-level PII into the training dataset?
- [ ] **MLflow artifact isolation**: Are model artifacts stored under tenant-scoped
  paths? Is read access controlled per tenant?
- [ ] **Fulfillment type capture at onboarding**: When a retailer onboards, how do we
  know which SKUs are dropship vs. owned vs. consignment? Is this in the data they
  provide, or does the buyer have to manually classify post-onboarding?
- [ ] **Clearance mode trigger**: Who triggers clearance mode for a SKU or category?
  Buyer-initiated via UI? Auto-detected by model (demand declining + high on-hand)?
  Both? What's the handoff?
- [ ] **Substitution data source**: The `substitute_sku_id` field on Product — buyer
  annotated or inferred from correlation analysis? Buyer annotation is more accurate
  but requires effort. Inference is automatic but will produce false positives.
- [ ] **Forecast horizon by vertical**: Should seasonal retailers (apparel, holiday)
  get a longer default horizon automatically based on `retailer_vertical`, or is it
  always buyer-configured?
- [ ] **Staging environment ownership**: Who maintains the staging Cloud Run
  environment and ensures it stays in sync with main? Needs an owner before demo.

---

## 15. What the Codebase Audit Corrected

Second-pass findings that close or update earlier assumptions.

### 15.1 Data Freshness Check — Exists, But Suppression Does Not

`workers/monitoring.py` has `check_data_freshness()` wired to the Celery beat
schedule. It checks `last_sync_at` per integration and flags stale ones with
structured log warnings. **Good.**

**Gap that remains**: The check logs and warns but does not suppress forecast
recommendations or show a UI banner when data is critically stale. The backend
alerting is there; the buyer-facing consequence is not. Section 10.5's remaining
work is the UI layer and the forecast suppression gate, not the detection logic.

### 15.2 Vendor Metrics — Wired and Running

`vendor_metrics.py` (updates `reliability_score` from actual delivery performance)
IS registered in `celery_app.py` on the `sync` queue. **Close the open question.**

Gap that remains: tier-boundary-crossing does not trigger on-demand ROP recalculation.
Section 11.7's second point still stands.

### 15.3 Perishable Cap — In Predict Layer, Not Optimizer

`test_ml_pipeline.py::test_perishable_cap` confirms there IS a perishable cap in
`apply_business_rules()` in `predict.py`. The forecasted demand output is capped
based on `shelf_life_days`.

**Gap that remains**: The cap is on the forecast output, not on the optimizer's
safety stock calculation. The ROP/EOQ in `optimizer.py` still treats perishable
SKUs identically to non-perishable ones. Safety stock and holding cost in the
optimizer are uncorrected. Section 11.1's fix is specifically to `optimizer.py`.

### 15.4 Returns — Sign Convention Handled, Semantics Are Not

`contract_profiles.py` has a `quantity_sign_policy` field. At ingest, negative
quantities are handled by sign convention (flip, keep, or error). Tests confirm this.

**Gap that remains**: The system handles the sign of a return but not its type.
A `-10` on a damaged item and a `-10` on a customer return are treated identically
(both become 0 demand or negative demand depending on policy). The semantic types
(`customer_return | damaged | vendor_return | recall`) and their different
implications for training signal are still missing. Section 11.2 stands.

### 15.5 Feature Engineering Is Not Timezone-Aware

`features.py` has no `localize()` or `astimezone()` calls. The `Store` model has
a `timezone` field (defaulting to `America/New_York`), but it is not consumed
anywhere in the feature computation pipeline.

**Impact**: `day_of_week`, `hour_of_day`, `is_weekend` features are computed from
UTC timestamps. For a store in PST (UTC-8), a transaction at 4am UTC (8pm PST the
prior day) gets assigned to the wrong calendar day and wrong weekday. Weekly
seasonality features are systematically wrong for any tenant not in Eastern time.

**Fix needed**: In `features.py`, join `Store.timezone` and localize all
`transaction_timestamp` values before extracting temporal features. Low-effort
fix, high accuracy impact for any non-Eastern tenant.

### 15.6 Arena Has Only 3 Test Cases for 7 Gates

`test_arena_promotion_gates.py` has three tests: promote on non-regression, block
on MAPE regression, fail-closed on missing metrics. The 7-gate system has no
individual gate tests, no interaction tests, no concurrent promotion test.

This is the highest-risk untested area in the system — the arena is the gatekeeper
for what model buyers see, and it has thin coverage.

---

## 16. Loop Logic and Concurrency Edge Cases

### 16.1 Concurrent Retrain — No Protection

**Confirmed gap.** No Redis-based task lock or Celery task deduplication exists for
the retrain worker. Two triggers can fire simultaneously for the same tenant:
- Scheduled nightly + manual DS trigger at the same time
- `drift_detected` + `new_products` triggers firing within the same minute
- Multiple milestone checks evaluating simultaneously after a bulk historical import

**What happens without a lock**: Both training jobs run in parallel on the same
dataset, both produce a `ModelVersion` record, both attempt to write to the arena.
The second write wins. The first job's work is silently discarded. No error.
No audit trail of the collision.

**Fix needed**: A per-tenant Redis lock in the retrain worker:
```python
lock_key = f"retrain_lock:{customer_id}"
with redis_client.lock(lock_key, timeout=3600, blocking_timeout=5):
    # training job
```
If the lock is already held, the second job should either queue with a delay
or log a `retrain.skipped.already_running` event and exit cleanly.

### 16.2 Retrain Failure — State Left Inconsistent

**Scenario**: A retrain job starts, creates a `ModelVersion` record with
`status = training`, then crashes at feature engineering (OOM, DB timeout, etc.).
The record is left with `status = training` indefinitely. No cleanup. No retry
with correct state.

**Impact**: The next retrain for this tenant may see the orphaned `training` record
and either skip (thinking a retrain is already running) or create a second record
without cleaning up the first.

**Fix needed**: The retrain worker needs a try/except that sets `status = failed`
with an error message on any unhandled exception. A separate cleanup job (or startup
check) should scan for `ModelVersion` records stuck in `status = training` for
> 2 hours and mark them as `failed`. This prevents state accumulation.

### 16.3 Arena Race Condition on Champion Promotion

**Scenario**: Two challenger models both pass all 7 gates in the same evaluation
cycle for the same tenant (e.g., a milestone fires two shadow models simultaneously
and both are ready). Both attempt to set themselves as champion.

**What happens**: The second write wins. The first champion is silently demoted
and orphaned. The arena's audit trail doesn't record the collision. The demoted
"champion" may still have its artifacts used if there's a caching layer.

**Fix needed**: Champion promotion should be an atomic database operation:
```sql
UPDATE model_versions SET status = 'champion'
WHERE customer_id = ? AND id = ?
AND NOT EXISTS (
    SELECT 1 FROM model_versions
    WHERE customer_id = ? AND status = 'champion'
    AND promoted_at > NOW() - INTERVAL '5 minutes'
)
```
Only promote if no other model was just promoted in the last 5 minutes.
Alternatively: Redis lock on `champion_lock:{customer_id}` during promotion.

### 16.4 Feedback Loop Idempotency

**Current state**: The feedback loop test suite covers feature computation
correctness but NOT idempotency. Running `compute_feedback_features()` twice
on the same `PODecision` dataset could double-count rejections in the training
signal if the function is called multiple times before a retrain.

**Specific risk**: If Celery `acks_late=True` causes a task retry (worker dies
after computing but before acknowledging), the feedback computation runs twice.
The `rejection_rate_30d` window query is based on a time window, so it's
naturally idempotent for reads — but if there's any write path in the loop
(updating a `feedback_processed` flag), that write could duplicate.

**What to verify**: Does `feedback_loop.py` write any state between calls, or is
it purely a read+compute function? If purely read-based, it's inherently idempotent
and this concern is low. If there are writes, add idempotency guards.

### 16.5 Milestone Trigger Firing Multiple Times

**Scenario**: A milestone check runs and determines tenant has crossed the 90-day
threshold. It queues a shadow training job. Before the job completes, another
milestone check runs and queues a second shadow training job for the same tenant
at the same threshold.

**Fix needed**: A `milestone_triggered` table (or a flag on tenant settings) that
records which milestones have already been triggered per tenant. The milestone check
should be: "has this tenant crossed this threshold AND NOT already triggered it?"
The record is written atomically before queuing the job to prevent double-triggering.

### 16.6 Historical Data Import — Cascading Trigger Problem

**Scenario**: A new tenant imports 2 years of historical data on onboarding day.
The milestone check fires and sees the tenant has data spanning 730 days. It
triggers milestones for 30d, 90d, 180d, and 365d simultaneously — four retrain
jobs queued at once for the same tenant.

**What happens**: All four jobs run in parallel (or sequentially if locked), but
they're all training on the same dataset. The 30d job produces a worse model than
the 365d job. If the arena evaluates them in the wrong order, the 30d model could
accidentally win (it finishes faster, gets evaluated first, promotes before the
better model is ready).

**Fix needed**: For retroactive milestone handling, fire milestones sequentially
with gates between them: only trigger the 90d milestone after the 30d model has
been evaluated. Or: suppress all milestones except the highest applicable one on
initial import (if 2 years of data, go straight to 365d milestone, skip the others).

### 16.7 Model File / DB State Desync

**Scenario**: Retrain job completes. MLflow artifact is written successfully.
Then the DB write of `ModelVersion` fails (network timeout, transaction rollback).
The model file exists in MLflow; the DB doesn't know about it.

**Impact**: The next retrain sees no recent `ModelVersion` record and trains again
from scratch, wasting compute. Worse: if someone manually queries MLflow, they see
a model that the DB doesn't know is there. Manual intervention required.

**Fix needed**: The retrain worker's DB write should be the last step, after all
artifact writes succeed. If the DB write fails, log a `retrain.artifact_orphan`
event with the MLflow run ID so it can be manually reconciled. Consider a
reconciliation script that can re-register orphaned MLflow artifacts.

---

## 17. Testing Gaps

### 17.1 No Model Quality Regression Test in CI

**Confirmed gap.** The test suite has 60+ test files covering API, arena gates,
feature engineering, scheduler dispatch, etc. There is no test that runs a
mini training job on a fixture dataset and asserts that MASE stays below a threshold.

**Why this matters**: A developer could refactor `features.py`, accidentally change
a lag calculation, and all code tests would pass — but the model quality would have
regressed. The regression would only surface when someone looks at production metrics.

**Fix needed**: A `test_model_quality_regression.py` that:
1. Loads a small frozen fixture dataset (Favorita 500-row sample, stored in `tests/fixtures/`)
2. Runs the full training pipeline on it
3. Asserts `MASE < 1.0` (model beats naive baseline) and `MAE < X` (fixed threshold)
4. Marked as `@pytest.mark.slow` and run in CI but not in dev fast-test mode

This is the "does the model add value?" gate in the test suite. Currently missing.

### 17.2 Arena Gate Individual Tests

**Current state**: 3 tests for the 7-gate arena. Missing:
- Individual tests for gates 3–7 (business metrics, SHAP stability, canary window,
  human sign-off, auto-promotion)
- Gate interaction: a model that fails gate 3 but would have passed all others
- Minimum hold period: newly promoted champion should not be demotable for 14 days
- Per-segment evaluation: challenger beats aggregate but regresses on high-velocity SKUs
- Concurrent promotion: two challengers ready simultaneously — only one should win

### 17.3 Timezone Feature Tests

**No test exists** for the timezone-localization gap identified in Section 15.5.
Once the fix is implemented (localizing timestamps before feature extraction):
- Add a test with a PST store: verify `day_of_week` for a 4am UTC timestamp
  (8pm prior day PST) returns the prior day's weekday, not Tuesday when it's Monday
- Add a parameterized test across all IANA timezones that have significant retailer
  populations (America/Los_Angeles, America/Chicago, Europe/London, Asia/Tokyo)

### 17.4 Feedback Loop Idempotency Test

**Not in current test suite.** Once Section 16.4 is verified/fixed:
- Test: run `compute_feedback_features()` twice with identical input → output is identical
- Test: run with a `PODecision` record added between calls → only the new record
  affects the output, no double-counting of the original records

### 17.5 Concurrent Retrain Test

Once the Redis lock (Section 16.1) is implemented:
- Test: fire two retrain tasks simultaneously for the same tenant in a test environment
- Assert: only one training job runs to completion, the second either queues or
  logs a `skipped` event
- Assert: only one `ModelVersion` record is created per cycle

### 17.6 Data Freshness Suppression Test

Once the UI suppression gate is added (Section 10.5):
- Test: mock `MAX(transaction_date)` as 72 hours ago → verify forecast API returns
  a `data_stale` warning flag in the response
- Test: at the 48-hour threshold, verify recommendations are suppressed (empty reorder
  list with a `data_interruption` reason code, not a normal empty list)

### 17.7 Milestone Trigger Deduplication Test

Once Section 16.5 is implemented:
- Test: call the milestone check twice for a tenant at the same data depth
- Assert: only one shadow training job is queued, not two
- Test: for retroactive historical import (2 years of data), assert only the
  highest applicable milestone fires

### 17.8 What the Test Suite Covers Well (Do Not Break)

For context — what already has solid coverage:
- Feature leakage: `test_feature_leakage.py` — lag features properly lagged
- Feedback loop feature computation: 10 test cases, correctness well covered
- Inventory optimizer: `test_inventory_optimizer.py` exists
- Shrinkage: `test_shrinkage.py` exists
- Contract profiles and mapper: solid test coverage
- EDI adapter: E2E and unit tests
- Security/auth: `test_security_guardrails.py` and `test_security_auth0.py`
- Rollback drill: `test_model_rollback_drill.py`

---

## 18. Automation Opportunities

Beyond what's already automated (scheduled retrains, vendor metrics, monitoring).

### 18.1 Automated Pre-Training Dataset Pipeline

Currently the pre-trained model is trained manually. This should be a reproducible
pipeline:
1. Download Favorita + M5 + Rossmann from public sources (Kaggle API or cached GCS)
2. Run standard preprocessing + feature engineering
3. Train LightGBM (Poisson objective) with Optuna tuning
4. Validate: assert MASE < 0.9 on held-out test set
5. If passes, push to MLflow as `global_pretrained_v{date}` and tag as cold-start default

This pipeline should be a Makefile target or a CI job that can be re-run when the
architecture changes. The current cold-start model was trained once manually on 27 rows.
A proper pre-training pipeline is what gives the SMB buyer confidence on day 1.

### 18.2 Automated Model Quality Gate in CI

Separate from the pre-training pipeline. A fast CI check (< 2 minutes):
- Train on a tiny frozen fixture (500 rows from Favorita)
- Assert MASE < 1.0
- Assert bias (ME / mean_actual) < 0.20 (not systematically over-predicting by > 20%)
- Fails CI if either assertion breaks

This catches feature engineering regressions before they reach production.

### 18.3 Automated Feature Importance Drift Detection

After each retrain cycle, compare the top-5 SHAP features of the new model vs.
the outgoing champion. If a feature that was in the top-5 drops out of the top-10,
or a new feature enters the top-3 for the first time, generate a
`feature_importance_drift` alert to the DS lead.

**Why this matters**: Sudden SHAP shifts often indicate a data quality change
(a field stopped being populated, a category got relabeled) or a structural demand
shift (promotions stopped, a major supplier changed). Catching this automatically
prevents silent model degradation between human reviews.

### 18.4 Automated SKU Lifecycle Detection

Detect when a SKU is being phased out and auto-suggest clearance mode:
- Rule: if `avg_daily_demand` (30d rolling) < 10% of the SKU's lifetime average
  AND `on_hand_stock > 2 × avg_daily_demand × lead_time_days`
  → generate a `sku_phase_out_candidate` alert

Buyer confirms (or ignores). If confirmed, system sets `inventory_strategy = clearance`
and stops generating reorder recommendations for that SKU.

This can run as a weekly Celery job scanning all active SKUs per tenant.

### 18.5 Automated Anomaly-to-Retrain Bridge

Currently `anomaly.py` (Isolation Forest) detects unusual demand events. Currently
it only generates alerts. It should also check: is this anomaly indicative of a
structural shift or a one-off event?

**Heuristic**: If anomaly score crosses threshold AND the anomaly has persisted for
> 3 consecutive days on the same SKU → trigger a `structural_shift_detected` retrain.
One-off events (single-day spike) → alert only, no retrain.

The distinction matters: retraining on a one-off anomaly will teach the model that
a single-day spike is normal. Training on a structural shift is exactly what we want.

### 18.6 Automated Holdout Window Rotation

The arena's backtest holdout should always evaluate on the most recent 20% of data,
not a fixed historical slice. As new transactions arrive, the holdout window should
automatically slide forward.

Currently the holdout is set at training time and may be stale by the time the
next challenger is evaluated. An automated holdout rotation ensures the arena is
always comparing models on recent reality, not historical conditions that may no
longer apply.

### 18.7 Automated New-Feature A/B Testing

When a feature engineering change is merged (new feature added to `features.py`),
automatically trigger a shadow training run with the new feature set vs. the existing
champion's feature set. The arena evaluates them on the current holdout.

This makes feature changes go through the same quality gate as model changes —
no feature engineering change silently reaches production without a tracked
comparison. Currently feature changes are deployed as code changes with no
automated quality comparison.

---

## 19. Priority Framework

Everything in this document, now explicitly prioritized. The goal is a working
demo first, first customer second, scalable platform third.

### P0 — Before Demo (Days, Not Weeks)

These are either demo blockers or correctness issues that would make the demo
embarrassing.

| Item | Why P0 | Section |
|---|---|---|
| Switch to pure LightGBM (LSTM weight → 0.0) | LSTM actively degrades every metric; demo would show a worse model than we have | ml_improvement_plan.md §2.1 |
| Replace MAPE with WAPE + MASE | Current metrics are misleading; demo metrics will look bad even if model is good | ml_improvement_plan.md §2.2 |
| Train pre-trained LightGBM on full Favorita + M5 datasets | Current cold-start model trained on 27 rows — not demoable | §1.2 |
| Timezone-aware feature engineering | All temporal features wrong for non-Eastern tenants | §15.5 |
| Model improvement history in UI | Core demo moment 2; buyers can't see the model getting better | §12.1 |
| Graduation event notification to buyer | Demo narrative requires showing the milestone firing | §2, §12.1 |
| Data freshness UI banner + forecast suppression | Silent stale data failure would undermine demo trust | §10.5, §15.1 |
| Concurrent retrain Redis lock | Two jobs running simultaneously could corrupt ModelVersion state | §16.1 |
| Retrain failure → `status = failed` cleanup | Orphaned `training` records break subsequent retrains | §16.2 |
| Model quality regression test in CI | Can't demo without knowing the model is good after code changes | §17.1 |
| SHAP waterfall in product detail UI | Most compelling explainability visual; data already exists in API | §12.3 |

### P1 — Before First Customer (Weeks, Not Months)

Correctness and reliability issues that matter once real customers are in the system.

| Item | Why P1 | Section |
|---|---|---|
| Automated pre-training dataset pipeline | Reproducible cold-start model; not dependent on manual runs | §18.1 |
| Milestone triggers (30/90/180/365d) with density check | Required for per-tenant lifecycle to work | §2.3 |
| Feedback quality filter (reason codes → training or not) | Without this, buyer conservatism corrupts the model | §3.3 |
| PO suggestion override cache | Buyer rejects suggestion; system re-issues it tomorrow | §3.2 |
| Arena per-segment evaluation | Aggregate MASE can hide regression on critical high-velocity SKUs | §6.2 |
| Champion minimum hold period (14d) | Arena can demote a model that hasn't seen a full weekly cycle | §6.1 |
| Champion staleness detection (rolling MASE decay) | Model silently degrades post-promotion with no trigger | §6.3 |
| Webhook dead-letter queue | Lost events mean wrong model signals at critical demand moments | §10.4 |
| Perishable optimizer fix (capped SS + adjusted holding cost) | Current optimizer over-buffers perishables — visible waste | §11.1 |
| Returns semantic typing (mask from demand signal) | Current sign policy handles the number but not the meaning | §11.2 |
| Fulfillment type (dropship/consignment) on Product | Dropship SKUs generate false reorder alerts | §11.4 |
| Staging environment (GCP Cloud Run, deploy on main merge) | Demo runs from same env as dev — one bad commit breaks demo | §10.2 |
| AI-assisted observability (error tracking + log anomaly detection) | Prerequisite before first onboarding — enables fix-fast loop | `docs/engineering/observability_spec.md` |
| RLS CI lint rule blocking `get_db` in routers | Multi-tenancy correctness should be automated, not manual | §13.1 |
| MLflow experiment namespacing per tenant | Required for multi-tenant shadow training observability | §7 |
| Arena gate individual test coverage (gates 3–7) | Current 3 tests for 7 gates is not sufficient for a gatekeeper | §17.2 |
| Milestone trigger deduplication test | Prevents double-training on historical imports | §17.7 |
| Automated feature importance drift detection | Catches silent data quality changes between human reviews | §18.3 |
| Verify MLflow artifact tenant isolation | Model artifacts encode business intelligence; should be scoped | §13.3 |

### P2 — Post-Launch, First Quarter

Real improvements once the platform is stable and we have pilot data to learn from.

| Item | Why P2 | Section |
|---|---|---|
| `detect_model_tier()` + per-tenant architecture selection | Enables not-one-size-fits-all model selection | §5.2 |
| Planned promotions buyer input (forward-looking features) | High SMB value but requires new UI surface | §3.4 |
| Per-SKU service level tier (critical/standard/tail) | Material impact on holding cost vs. stockout rate | §11.5 |
| KNN regional store similarity for multi-location | Better cold-start for chain tenants | §4.2 |
| Inventory strategy modes (clearance/buildup) | Needed for seasonal retailers to use the platform fully | §11.6 |
| Configurable forecast horizon per tenant (up to 90d) | Seasonal retailers can't plan with 14-day window | §10.7 |
| Substitution/cannibalization detection | High value for multi-SKU retailers, complex to build | §11.3 |
| Automated SKU lifecycle detection → clearance suggestion | Reduces buyer manual work for end-of-season | §18.4 |
| Automated anomaly-to-retrain bridge | Faster response to structural demand shifts | §18.5 |
| RedBeat HA Celery beat scheduler | Reliability at scale; acceptable risk for SMB launch | §10.1 |
| Reliability tier-crossing → on-demand ROP recalculation | Nice-to-have real-time response; nightly batch is acceptable | §11.7 |
| Feedback loop impact metric in UI | Useful engagement but not critical path | §12.2 |
| Prediction interval confidence band in forecast chart | Requires quantile regression (Phase B) first | §12.4 |

### P3 — Future Platform Investments

Longer-term, requires scale or data that doesn't exist yet.

| Item | Section / Reference |
|---|---|
| Hierarchical per-department models | ml_improvement_plan.md §3.4 |
| LightGBM + Prophet hybrid | ml_improvement_plan.md §6.1 |
| N-HiTS or TFT sequence model | ml_improvement_plan.md §3.3 |
| Conformal prediction intervals | ml_improvement_plan.md §6.2 |
| Foundation model benchmark (Chronos/TimeGPT) | ml_improvement_plan.md §6.4 |
| Federated learning across tenants | future_integrations.md §4 |
| Multi-region / data residency | future_integrations.md §1 |
| Weather + supply chain disruption signals | future_integrations.md §3 |
| Social sentiment pipeline | future_integrations.md §2 |
| LLM natural language insights (SHAP → plain language) | future_integrations.md §4 |
| Multi-echelon inventory optimization | §4.3 (brainstorm idea only) |
| Online learning / continual adaptation | ml_improvement_plan.md §6.3 |
| Domain generalization — LLM-as-domain-expert | §20 (brainstorm idea only) |

---

## 20. Domain Generalization — Vertical Expansion Strategy

**Status: Future iteration — research thread, not a near-term commitment**

### 20.1 The Problem

ShelfOps' current ML stack encodes retail assumptions at multiple layers:

- EOQ/ROP formulas assume bulk replenishment from distributors with multi-day lead times
- Feature engineering (`detect_feature_tier()`, perishability windows, seasonality cadences) is calibrated for retail POS cadence
- Pandera schema bounds reflect retail-range values (daily units, supplier lead times, etc.)
- LSTM temporal patterns assume regular, high-frequency sales events

A florist, restaurant, or custom fabricator breaks most of these. The stockout economics, demand distributions, supplier relationships, and replenishment cycles are all structurally different.

### 20.2 Why "Hire Domain Experts Per Vertical" Doesn't Scale

The naive solution — embed domain knowledge by hiring vertical experts — creates an org model that doesn't scale:

- TAM fragments into a collection of vertical SaaS products with shared infrastructure
- The ML team accumulates permanent domain-expert headcount per vertical
- Codebase accumulates if/else branching by `business_type` throughout the pipeline
- Each new vertical is a full product investment, not a configuration change

### 20.3 The Proposed Approach: LLM as Domain Reasoning Layer

Rather than encoding domain knowledge into training logic, treat it as a **pipeline configuration generation problem**. The LLM doesn't train the model — it produces a domain config object at onboarding time that parameterizes the existing pipeline.

```
Business Description (onboarding questionnaire)
        ↓
   LLM Domain Reasoner
        ↓
  Domain Config Object (saved as tenant config)
  ├── feature_preset: "food_service" | "specialty_retail" | "general"
  ├── seasonality_windows: [7, 30, 90]        ← LLM-suggested
  ├── demand_distribution_prior: "heavy_tail" | "normal" | ...
  ├── lead_time_range_days: [1, 5]
  ├── perishability_window_days: 3
  └── pandera_bounds: { daily_units_max: 200, lead_time_max: 7 }
        ↓
   Existing ML Pipeline (reads config, not hardcoded retail values)
```

Human-in-the-loop review of the generated config before it's saved. LLM is proposing, not deciding.

### 20.4 Feature Engineering Implications

`detect_feature_tier()` is the primary impact point. Currently detects data richness (27 vs. 45 features). Could also accept a domain context object that activates/deactivates feature modules:

| Feature Module | Large Retail | Food Service | Specialty / Boutique |
|---|---|---|---|
| Bulk order cycle | ✓ | ✗ | partial |
| Time-of-day demand | ✗ | ✓ | ✗ |
| Weather correlation | partial | ✓ | ✓ |
| Event-driven demand spikes | ✓ | ✓ | ✓ |
| Lot expiry / freshness | partial | ✓ | ✗ |
| Long-tail slow-mover handling | ✗ | ✗ | ✓ |

SHAP already provides the signal for which features actually matter per tenant. Over time, clusters of tenants in the same vertical will converge on similar SHAP importance distributions — that's how domain feature presets could be **discovered empirically** rather than hardcoded.

### 20.5 Meta-Learning Path (Much Longer Term)

Once enough tenants exist across verticals:

1. Cluster tenants by demand behavior patterns (not stated business type — let the data decide)
2. Use cluster centroids as Bayesian priors for new tenants with sparse history
3. Fine-tune pretrained weights on new verticals rather than training from scratch (transfer learning)

The discovered clusters may not map to intuitive categories. A boutique and a specialty pharmacy might share enough demand structure to use the same prior. That's a research finding worth pursuing.

### 20.6 Platform vs. Intelligence Product Split

The cleanest way to handle verticals at a product level is to make the split explicit:

- **Platform tier**: Domain-agnostic. Data ingestion, storage, API, alerting, dashboards. No domain assumptions baked in. Suitable for any business type with structured inventory data.
- **Intelligence tier**: The ML stack + LLM domain reasoner. This is where vertical-specific value is added on top of the platform. A new vertical = "can the LLM domain reasoner produce a valid, sensible config for this business type?" — a much smaller lift than rearchitecting the pipeline per vertical.

Customers who just want the platform don't touch the intelligence layer. Customers who want forecasting get the LLM-configured pipeline. This also creates a clear upsell path.

### 20.7 Open Research Questions

[ ] How do companies like Relex, Blue Yonder, and o9 Solutions actually handle vertical generalization — rule-based presets, customer-configured parameters, or something more dynamic?

[ ] Is there published work on LLM-assisted ML pipeline configuration (AutoML adjacent but domain-driven rather than search-driven)?

[ ] What does few-shot demand forecasting look like for sparse, high-variance SKUs (specialty retail) — is there a usable prior from the retail training data?

[ ] At what tenant count does clustering-based prior discovery become statistically meaningful?

[ ] Is the LLM domain config approach already being used in production somewhere, or is this genuinely novel?

### 20.8 Prioritization Assessment

This is **firmly P3 — future platform investment**, not because it's unimportant but because:

- Current target market (retail SMB) doesn't require it
- The architecture to support it (modular feature presets, domain config object) can be stubbed in incrementally without committing to the full system
- The research questions in §20.7 should be answered before architectural decisions are made
- It's a strong candidate for a dedicated research spike after Phase 3 closes

**Suggested next step**: Research spike (1-2 days) focused on §20.7 questions before this moves to a spec.
See `docs/engineering/domain_generalization_spike.md` for the full spike plan, execution schedule, and go/no-go criteria.

---

## 21. Measurement and Observability Gaps

Three gaps surfaced during a codebase audit (February 2026) that don't fit neatly into
existing sections. All are grounded in confirmed missing code — not speculation.

### 21.1 "2–3 Days Early" Claim Has No Supporting Metric

**Confirmed gap**. The claim that ShelfOps predicts stockouts "2–3 days early" appears
in `README.md` and `CLAUDE.md` as a core value proposition. No code anywhere measures
or validates it.

The existing backtest tracks `stockout_miss_rate` (did we predict zero when actual > 0?),
which measures detection, not timing. The alert engine's `days_of_supply` thresholds
(critical ≤1d, high ≤3d) determine severity, but don't record when the alert fired
relative to when the stockout actually occurred.

**What would validate the claim**: For each confirmed stockout event (a date where
`available_inventory` hit zero for a given product/store), look up the earliest alert
that fired for the same product/store before that date. Compute
`lead_time_days = stockout_date - alert_fire_date`. Track the distribution: median,
p25, p75. If the median lead time is ≥2 days, the claim holds. If it's 0.5 days, the
claim is wrong and we're over-promising.

**What's needed**:
- A `StockoutEvent` table or query that identifies actual zero-inventory dates from
  `InventorySnapshot`
- A `compute_alert_lead_time()` function in `backtest.py` that joins alert timestamps
  to stockout events per `(store_id, product_id)`
- A `median_alert_lead_days` metric added to the weekly backtest report and the
  monitoring dashboard
- A gate in `arena.py`: new champion must not degrade `median_alert_lead_days` vs.
  the existing champion

**Priority**: High — this is the headline claim of the product. If it's not measured,
it's undefendable in any customer or investor conversation.

[ ] Is `InventorySnapshot` populated densely enough to reliably detect zero-inventory
    dates, or do we need to infer stockouts from a run of zero-sales days?

[ ] Should the gate be median ≥ 2.0 days, or should we define a minimum % of alerts
    that fire with ≥ 2 days lead time?

---

### 21.2 Alert Throttling — No Cooldown After Resolution

**Confirmed gap** (`alerts/engine.py`). Deduplication exists for *open* alerts: if
an alert for `(store_id, product_id, alert_type)` is already open or acknowledged,
a duplicate is not created. But the moment an alert is resolved or dismissed, the
next hourly alert run can immediately re-fire an identical alert if the stockout
condition still exists.

In practice this means a resolved alert can re-appear every hour indefinitely, because
the underlying inventory condition (low days_of_supply) hasn't changed — the buyer
just cleared the alert to work through later. This is alert fatigue.

**Additional gaps**:
- No severity escalation as days_of_supply decreases: an alert that fires at `medium`
  (≤5 days supply) stays `medium` even as it crosses into `high` (≤3 days) territory.
  A new alert is only created if the original is resolved first.
- No per-user notification throttling: if 50 SKUs hit reorder point simultaneously,
  50 WebSocket pushes fire at once in `publish_alerts()`.
- No digest/batching mode: no "send one summary at 8 AM" vs. "push each alert
  immediately" configuration.

**What's needed**:
- A `resolved_at` + `cooldown_until` field on `Alert`. After resolution, set
  `cooldown_until = resolved_at + N hours` (configurable per severity; e.g., critical=2h,
  high=4h, medium=8h). The deduplication check in `deduplicate_alerts()` should also
  suppress creation if `cooldown_until > now`.
- An escalation pass in the alert pipeline: for each open alert, check if
  `days_of_supply` has crossed a higher-severity threshold since the alert was created.
  If so, update severity and push a single escalation notification.
- Batch notification mode: buffer alerts per-user for a configurable window (e.g., 5
  minutes) before WebSocket push, then send as a grouped message.

**Priority**: Medium — doesn't break the product but will be the first thing a real
buyer complains about once the alert engine is running live.

[ ] What's the right default cooldown window? 4 hours is a common starting point in
    operational alerting systems. Should it be configurable per severity or per tenant?

[ ] Escalation raises UX questions: does the buyer see the original alert updated in
    place, or a new alert? Updating in place preserves history; new alert is simpler
    to implement.

---

### 21.3 Input Distribution Drift — No Feature-Level Detection

**Confirmed gap** (`workers/monitoring.py`). The daily `detect_model_drift` task
measures output-based drift only: it compares last-7-day average MAE against the
all-time baseline MAE. If degradation exceeds 15%, it triggers emergency retraining.

The problem with output-only drift detection is that accuracy degrades *after* the
input distribution has already shifted. By the time MAE spikes 15%, the model may have
been producing bad forecasts for days. Common root causes that output monitoring
catches late:
- A supplier changing product codes (new product IDs the model has never seen)
- A store opening or closing (sudden appearance/disappearance of a `store_id`)
- A seasonal category switch (the distribution of `category` changes dramatically)
- Data pipeline breakage causing sparse or missing features (many NaN-imputed values)

**What feature-level drift detection looks like**:
- **Population Stability Index (PSI)** on key numeric features (rolling_mean_7d,
  rolling_std_7d, days_since_last_sale, inventory_level). PSI < 0.1 = stable,
  0.1–0.25 = minor shift, > 0.25 = major shift.
- **KS-test** for continuous features: compare training distribution vs. last-7-day
  inference distribution.
- **Missing value rate tracking**: if `promotion_active` or `supplier_lead_days` starts
  arriving as NaN more than 10% of the time, the feature is broken upstream.

**What's needed**:
- At training time, serialize the feature distribution summary (mean, std, p10, p25,
  p50, p75, p90, null_rate) per feature alongside the model artifact in MLflow.
- A daily `detect_feature_drift` task in `monitoring.py` that computes the same
  summary over last-7-day inference rows and computes PSI against the training
  distribution.
- A new `FeatureDriftAlert` (or reuse the `MLAlert` type with `alert_type='feature_drift'`)
  with the feature name, PSI score, and direction of shift.
- The hardcoded 15% MAE threshold in `monitoring.py` line 91 should be tenant-configurable
  (a fast-moving fashion retailer may need a tighter threshold than a slow-moving
  industrial supplier).

**Priority**: Low-Medium — adds defense-in-depth to the monitoring stack. Not urgent
until we have live tenants with real data pipelines that can break.

[ ] Should feature drift alerts trigger automatic retraining (same as MAE drift) or
    only notify the DS team for investigation? Automatic retraining on feature drift
    could mask a data pipeline bug rather than fix it.

[ ] PSI requires binning continuous features. Use training distribution quantiles as
    bin edges. This needs to be serialized per model version, not computed on the fly.

---

## 22. Enterprise Patterns — ShelfOps Spin

Real workflows from companies with serious ML and supply chain infrastructure.
The pattern: enterprise tools solve these problems at enterprise scale with enterprise
complexity. The question for each one is: what does the SMB version of this look like,
and how does ShelfOps' existing architecture give us a head start?

---

### 22.1 Demand Sensing — Real-Time Forecast Adjustment

**What enterprise retailers do**

Blue Yonder, Relex, and o9 Solutions all have a dedicated "demand sensing" layer that sits
on top of the statistical forecast. The statistical model (LSTM, LightGBM) produces a
7–90 day baseline. The sensing layer is a short-horizon (0–72 hour) real-time adjustment.
It watches current POS velocity and asks: is today's actual sell-through rate running
ahead of or behind the forecast? If a store is selling through a SKU 35% faster than
the model expected by noon, the sensing layer raises the demand estimate for the next
48 hours proportionally. This adjustment feeds directly into the replenishment trigger
without waiting for the next full retraining cycle.

The enterprise version involves complex statistical corrections, demand decomposition, and
hierarchy-level adjustments across thousands of stores simultaneously.

**What ShelfOps currently has**

The statistical forecast runs nightly. Alerts check `days_of_supply` on the most recent
`InventorySnapshot`. There is no intraday velocity signal that adjusts reorder thresholds
between forecast cycles. If a promotion fires Tuesday morning and demand spikes, the model
doesn't know until the next forecast run.

**The ShelfOps SMB spin**

Not a separate ML model — an adjustment multiplier that runs hourly on top of the
existing forecast:

```
velocity_ratio = actual_sales_last_6h / forecast_sales_last_6h

# If running 30%+ ahead: raise the effective demand estimate for the next 48h
if velocity_ratio > 1.30:
    adjusted_daily_demand = base_forecast × velocity_ratio × decay_factor
    # decay_factor smooths the adjustment back to baseline over 48h
```

The adjusted estimate feeds into the `days_of_supply` calculation for alert generation only
— it does not contaminate the training data or the base forecast. The buyer sees:
"Running 38% above forecast today — reorder point threshold adjusted."

This is a single Celery job in `workers/`. It reads from `InventorySnapshot` (already
populated hourly), compares to the stored `ForecastResult`, applies the multiplier, and
updates a `velocity_adjusted_demand` field on the `InventorySnapshot` record. The alert
engine reads this field instead of the raw forecast during high-velocity periods.

**The ShelfOps angle over the enterprise version**: we don't need the full demand sensing
pipeline. For an SMB with one or a few locations, the velocity signal is already close
to the truth. The added value is speed-to-alert, not hierarchical decomposition.

[ ] At what velocity divergence threshold does it make sense to trigger an intraday alert
    vs. just adjusting the reorder threshold? Suggest: >30% divergence for > 3 consecutive
    hourly readings = alert; single-hour divergence = threshold adjustment only.

[ ] Should velocity sensing suppress as well as amplify? If demand is running 50% below
    forecast (e.g., weather event killed foot traffic), the system should also delay an
    impending reorder trigger — otherwise it fires a reorder for a slowdown, generating
    excess inventory.

---

### 22.2 Buyer Copilot — Natural Language Over Model Outputs

**What enterprise tools are building**

Oracle Fusion, SAP Joule, Microsoft Copilot for Supply Chain, Blue Yonder's Co-Pilot:
all use an LLM as a conversational interface over supply chain data. The buyer types
"why is this SKU's reorder point so high?" and the system retrieves: lead time history,
vendor reliability score, recent demand variance, current safety stock formula inputs,
and produces a plain English answer.

The enterprise version is a full RAG system over the ERP's data warehouse with auth
scoping per user role. It handles everything from "who is my largest supplier by spend?"
to "what would happen to my stockout rate if I reduced safety stock by 10%?"

**What ShelfOps currently has**

Section 20 (AI Domain Expert) uses an LLM to *configure the ML pipeline at onboarding*:
the LLM reads a business description and generates a domain config object that
parameterizes `detect_feature_tier()`, seasonality windows, Pandera bounds, etc. That's
an internal, pipeline-facing LLM. It runs once at setup.

**The ShelfOps SMB spin**

A buyer-facing copilot is a different use of the same LLM infrastructure — not pipeline
configuration, but *output narration*. The LLM doesn't make decisions; it translates
what the model has already decided into language the buyer can interrogate.

The architecture is thin. For any product detail page, the copilot endpoint assembles a
structured context object and asks the LLM to narrate it:

```python
context = {
    "forecast": forecast_result,           # from ForecastResult
    "shap_values": shap_for_forecast,      # from §12.3 explain endpoint
    "alert": current_alert_for_sku,        # from Alert
    "vendor": vendor_reliability_for_sku,  # from SupplierMetrics
    "promotion": upcoming_promotions,      # from PlannedPromotions
    "last_po": last_po_decision,           # from PODecision
}
# LLM prompt: "Given this context, answer the buyer's question in plain language.
# Do not speculate beyond the data provided."
```

The buyer's natural language question is passed alongside the structured context. The LLM
has no access to anything beyond the context object for that tenant/SKU. This is important:
the LLM is a narrator, not a retrieval system. All retrieval happens in Python before the
LLM is called.

**The ShelfOps angle over the enterprise version**: enterprise copilots need to handle
arbitrary schema queries, multi-table joins, and cross-tenant comparisons. For ShelfOps
the context is bounded and structured — the LLM's job is much simpler. It converts a
pre-assembled dict into sentences. This is achievable with a small model (Haiku) at low
cost per query.

The connection to Section 20: the LLM domain expert configures the pipeline; the buyer
copilot explains its outputs. They're the internal and external faces of the same AI layer.
When the domain expert generates a config that activates the `food_service` feature preset,
the buyer copilot knows to describe stockout risk in terms of "freshness days" rather than
"days_of_supply."

[ ] Where does the copilot live in the UI? Options: (a) a floating chat icon on every page
    — answers questions about whatever is currently on screen; (b) a dedicated "Ask"
    button per SKU/alert that opens a pre-framed answer using the SHAP + alert context;
    (c) a standalone Copilot page. Option (b) is the most targeted and lowest scope.

[ ] What's the fallback when SHAP values aren't available for a specific forecast (cold-start
    model, or SHAP not yet computed)? The copilot should degrade gracefully: "I don't have
    a detailed breakdown for this SKU yet — it needs more data before I can explain the
    individual drivers."

---

### 22.3 Promotional Post-Mortem — Closing the Lift Feedback Loop

**What enterprise retailers do**

Walmart, Kroger, and CPG companies run formal promotion post-mortems. After every
promotional event ends, an analytics team (or an automated pipeline) computes:
- Baseline demand: what would have sold without the promotion (counterfactual)
- Actual demand during the event
- Lift = actual / baseline
- Incremental revenue and margin
- Whether the lift justified the markdown cost

This feeds back into promotional planning for the next cycle. It's how they calibrate
"we know a 15% off on this category generates a 22% volume lift" rather than guessing.
Companies like Nielsen and IRI sell this as a standalone product (Trade Promotion
Effectiveness). Large retailers build it internally.

**What ShelfOps currently has**

`is_promotion_active` and `promotion_lift` are features in `features.py`. Planned
promotions exist as a brainstorm item (Section 3.4 — not yet built). The model learns
promotion effects from historical data, but there's no explicit measurement of whether
the model's learned lift coefficients are accurate. If the model consistently
under-estimates a seasonal promotion by 30%, there's no automated signal of this.

**The ShelfOps SMB spin**

An automated post-mortem job that fires 48 hours after a promotion's `end_date`:

```python
# For each completed promotion event:
baseline = rolling_mean_demand_pre_promo(sku, days=14)   # 14-day pre-promo average
actual_during_promo = sum(daily_demand_during_promo)
expected_during_promo = baseline × promo_duration_days
actual_lift_pct = (actual_during_promo / expected_during_promo) - 1.0

# Model's predicted lift (from ForecastResult during promo period):
modeled_lift_pct = (avg_forecast_during_promo / baseline) - 1.0

lift_error = actual_lift_pct - modeled_lift_pct
```

If `lift_error` is consistently positive (model under-forecasting promotions), write a
`promotion_lift_bias` feature for that `(product_category, promotion_type)` pair into
the feature matrix. This becomes a learned correction at the next retrain cycle.

The buyer-facing version: "Your 20% off sale on beverages in January generated a 31% volume
lift. The model predicted 18%. We've updated our forecast parameters for your next promo."

**The ShelfOps angle over enterprise**: enterprise post-mortems require holdout panels,
synthetic control groups, and geo-matched comparisons to isolate the promotion effect from
external noise (weather, competitive activity). For an SMB with one or a few stores, the
14-day pre-promo rolling mean is a reasonable counterfactual — imprecise but directionally
correct and zero additional infrastructure. The key is flagging that the model is
systematically wrong about promos, not producing a research-grade causal estimate.

Note: this requires `PlannedPromotions` (Section 3.4) to exist first. Without promotion
events recorded in the system, the post-mortem job has nothing to query. These are
sequentially dependent.

[ ] Should post-mortem results trigger a retrain, or just update a bias coefficient that
    gets picked up at the next scheduled retrain? Triggering an immediate retrain after
    every promotion creates a lot of training churn. Prefer: accumulate bias corrections
    in a `PromotionLiftBias` table, apply at the next retrain, don't trigger early.

[ ] Counterfactual baseline is noisy for promotions that happen during other demand events
    (holidays, competitor stockouts). Flag these as `confounded_baseline = True` and
    exclude from the bias correction calculation.

---

### 22.4 Markdown Optimization — ML-Driven Clearance Timing

**What enterprise retailers do**

Zara pioneered data-driven markdown timing in fast fashion. Relex and Blue Yonder sell
"markdown optimization" as a dedicated module. The problem: given a fixed sell-by date
(end of season, product discontinuation), find the markdown schedule that clears inventory
while maximizing recovered margin. Markdown too early = recovered margin is lower than
necessary. Markdown too late = residual inventory at end of season.

The enterprise version uses a price elasticity model per category, a sell-through
simulation that computes the distribution of outcomes under different markdown schedules,
and an optimization objective (maximize expected revenue given the constraint of 0 units
on date X). It's a full revenue management system.

**What ShelfOps currently has**

Section 11.6 introduces `inventory_strategy: normal | clearance | buildup` as a field
on `ReorderPoint`. When `clearance`, reorder recommendations are suppressed. Section 18.4
describes automated SKU phase-out detection. But the clearance mode is passive: it stops
ordering, but it doesn't do anything active to improve sell-through.

**The ShelfOps SMB spin**

Two steps, the second builds on the first:

**Step 1 — Sell-through trajectory projection** (lower complexity, immediate value)

When `inventory_strategy = clearance` and `clearance_target_date` is set (new field),
compute daily:

```python
days_remaining = clearance_target_date - today
units_remaining = current_on_hand
projected_daily_velocity = forecast_daily_demand  # from existing model
projected_sell_through_pct = (units_remaining - projected_daily_velocity × days_remaining) / units_remaining

if projected_sell_through_pct > 0.15:  # ≥15% residual at end of clearance period
    alert_type = "clearance_at_risk"
    # "At current velocity, 23 units (18%) will remain unsold by April 30."
```

This requires no new model — just arithmetic on existing forecast outputs.

**Step 2 — Markdown recommendation** (medium complexity, requires price elasticity)

Add a simple price elasticity coefficient per product category, buyer-editable
(seeded from Favorita data, refined per tenant):

```python
# e.g., beverages elasticity = -1.3: a 10% price drop → 13% demand increase
expected_demand_at_discount = base_demand × (1 + abs(elasticity) × discount_pct)
revenue_at_discount = (unit_price × (1 - discount_pct)) × expected_demand_at_discount

# Simulate: at what discount level does clearance_at_risk go away?
for discount in [0.10, 0.15, 0.20, 0.25, 0.30]:
    if simulate_sell_through(discount, days_remaining) >= 0.95:
        recommend_markdown(discount)
        break
```

The buyer sees: "To clear remaining inventory by April 30, we recommend a 15% markdown
starting today. Expected sell-through: 97%."

**The ShelfOps angle over the enterprise version**: we're not building a full revenue
management system. We're adding a projection + a recommendation heuristic on top of
the existing forecast. The price elasticity coefficient is a single float per category
— a placeholder that gets refined over time. The enterprise version would model demand
distribution stochastically with hundreds of parameters. The SMB version needs to answer
one question: "will I sell through, and if not, how much do I need to mark down?"

[ ] Where does the buyer enter `clearance_target_date`? Options: (a) on the product
    detail page when setting `inventory_strategy = clearance`; (b) auto-detected from
    the seasonal calendar (e.g., winter clearance always ends March 15). Both should
    eventually exist.

[ ] Price elasticity coefficients need to come from somewhere at cold start. Sourcing
    academic retail elasticity estimates by category (beverages: -0.8 to -1.5, apparel:
    -1.1 to -2.0, etc.) as defaults is a reasonable first step. BRAINSTORM: could these
    also be outputs of the LLM domain expert (Section 20) at onboarding?

---

### 22.5 Cost-Aware Order Optimization — Quantity Break Pricing

**What enterprise procurement tools do**

SAP Materials Management, Coupa, Oracle Purchasing: all handle tiered supplier pricing
(volume discounts). When a buyer is generating a PO, the system evaluates whether
buying into the next pricing tier makes financial sense: the savings on unit cost may
exceed the additional holding cost of the surplus inventory. Large retailers negotiate
these tiers explicitly. The math is well-understood but requires the system to know
the pricing schedule.

**What ShelfOps currently has**

`unit_cost` is a flat value on `Product`. The EOQ formula in `optimizer.py` minimizes
`(order_cost × demand / order_qty) + (holding_cost × order_qty / 2)` using this flat
cost. There is no concept of tiered pricing. A supplier offering 20% off at 500 units
looks identical to a flat-rate supplier.

**The ShelfOps SMB spin**

A `SupplierPricingTier` table:

```python
class SupplierPricingTier(Base):
    supplier_id: UUID
    product_id: UUID
    min_quantity: int        # minimum units to qualify for this tier
    unit_price: Decimal      # price per unit at this tier
    effective_from: date
    effective_until: date | None
```

Buyer enters pricing tiers manually (or from a supplier quote PDF — future LLM parsing
opportunity). The optimizer then evaluates EOQ at each available tier and computes:

```
For each tier where min_qty > standard_EOQ:
    surplus_units = min_qty - standard_EOQ
    surplus_holding_cost = surplus_units × holding_cost_per_unit × expected_days_to_sell
    unit_cost_savings = (flat_price - tier_price) × min_qty
    net_benefit = unit_cost_savings - surplus_holding_cost - opportunity_cost
```

Surface the comparison in the PO suggestion UI:
- **Standard order**: 120 units @ $5.00 = $600
- **Volume tier**: 250 units @ $4.25 = $1,063 — surplus sells through in ~11 days at
  current velocity — **net saving vs. standard: $74**

Buyer clicks "accept volume tier" or "use standard." Decision logged in `PODecision` with
the tier reasoning attached. Over time, whether buyers accept or reject volume tier
suggestions becomes a feature in the feedback loop (§3.1).

**The ShelfOps angle over the enterprise version**: enterprise systems also model
opportunity cost of working capital, multi-tier supplier negotiations, and currency
hedging. The ShelfOps version skips all of that. The key insight for SMBs is that most
small retailers negotiate volume discounts informally and track them in spreadsheets. We
make the math visible and tie it to the actual velocity forecast, which a spreadsheet can't.

A related extension: **freight consolidation**. If the buyer has three POs from the same
supplier ready to send, combining them into one shipment may unlock a freight tier discount.
ShelfOps could flag: "3 POs to Supplier X ready — consolidating saves $120 in freight."
This is purely a presentation-layer suggestion, not a new optimization problem.

[ ] The LLM parsing opportunity is real: many SMBs receive supplier price lists as PDFs
    or Excel files. An LLM-assisted "upload your supplier's price list" flow that extracts
    pricing tiers and populates `SupplierPricingTier` automatically would remove significant
    friction. This connects the LLM domain expert (§20) to a concrete buyer-facing workflow.

[ ] At what point does holding cost + working capital tie-up outweigh the volume discount?
    The formula above captures this, but the `holding_cost_per_unit` assumption matters
    a lot. For a retailer with expensive storage, holding cost is high. For one with a
    large warehouse, it's low. This should be a configurable tenant parameter, not a
    platform default.

---

## 23. API Coverage Audit — Untested Endpoints

**Method**: Cross-referenced every file in `backend/api/v1/routers/` against
`backend/tests/test_*api*.py`. Routers with no corresponding test file:

| Router | Endpoints | Test file |
|---|---|---|
| `anomalies.py` | GET /, GET /stats, GET /ghost-stock, POST /detect | None |
| `experiments.py` | GET /, GET /{id}, POST /, PATCH /{id}/approve, PATCH /{id}/reject, POST /{id}/complete, GET /{id}/results | None |
| `ml_alerts.py` | GET /, GET /stats, GET /{id}, PATCH /{id}/read, PATCH /{id}/action | None |
| `ml_ops.py` | GET /models, GET /models/{ver}/shap, GET /backtests, GET /experiments, GET /registry, GET /health, GET /effectiveness | None |
| `outcomes.py` | POST /alert/{id}, POST /anomaly/{id}, GET /alerts/effectiveness, GET /anomalies/effectiveness, GET /roi | None |
| `reports.py` | GET /inventory-health, GET /forecast-accuracy, GET /stockout-risk, GET /vendor-scorecard | None |

**Total untested endpoints: 32** out of the full API surface. These aren't minor
plumbing routes — they include the ROI endpoint (buyer's primary value proof), SHAP
explainability endpoint (used in the demo), ghost-stock detection, and the experiment
approval workflow.

### 23.1 Coverage Priority Order

Not all gaps are equally important to close for Phase 3.

**P1 — Test now, blocks demo or correctness guarantees:**

- `GET /outcomes/roi` — this is the ROI calculation the SMB buyer sees. If it returns
  incorrect data (wrong time windows, double-counting), the demo is misleading.
  A test that asserts the ROI calculation against a known PO outcome fixture is essential.

- `GET /ml_ops/models/{version}/shap` — the SHAP endpoint drives the explainability
  demo. Tests should assert: (a) it returns values for all features, (b) the feature
  names match the current training feature set (drift guard), (c) tenant isolation
  holds (Tenant A cannot retrieve Tenant B's SHAP values).

- `GET /reports/stockout-risk` — the primary alert surface. Tests should cover:
  query param validation, time horizon filtering, empty response when no risk SKUs,
  and the response when `inventory_strategy = clearance` SKUs are present (they
  should be excluded from risk alerts).

- `GET /reports/inventory-health` — the dashboard summary metric. Tests need to
  verify the aggregation logic produces correct `days_of_supply` calculations against
  known fixture data.

**P2 — Test before production, important but not demo-blocking:**

- `POST /anomalies/detect` — on-demand anomaly detection. Main risk: what happens
  when called against a tenant with < 30 rows of history? Should return a
  graceful error, not a 500 from the Isolation Forest.

- `GET /anomalies/ghost-stock` — ghost stock detection. Test: known fixture where
  a SKU has `on_hand = 50` but zero sales velocity for 14 days → assert it appears
  in the ghost-stock response.

- `GET /outcomes/alerts/effectiveness` and `GET /outcomes/anomalies/effectiveness` —
  these compute how often alerts led to buyer action. Test: seed a fixture with
  known alert → acknowledge sequences and assert the effectiveness rate calculation
  is correct.

- `PATCH /ml_alerts/{id}/action` — buyer acts on an ML alert. Tests: valid action
  types accepted, invalid action type returns 422, double-action on same alert
  is idempotent or returns 409.

**P3 — Test eventually, low correctness risk:**

- `GET /ml_ops/experiments` and `GET /ml_ops/registry` — primarily read-through
  from MLflow. Risk is MLflow connectivity, not logic bugs. Integration test
  (with mocked MLflow client) is sufficient.

- `PATCH /experiments/{id}/approve` and `PATCH /experiments/{id}/reject` —
  the state transitions matter. Test: approve a non-pending experiment → 409.
  Approve → reject same experiment → 409. Idempotent approval.

### 23.2 Tenant Isolation Tests — Missing for Several Endpoints

The existing security test suite (`test_security_guardrails.py`) covers the primary
auth paths. But the untested routers above have no tenant isolation assertions.
For each P1 endpoint, the test suite should include:

```python
# Pattern: Tenant B cannot see Tenant A's data
def test_{endpoint}_tenant_isolation(client, tenant_a_token, tenant_b_token, tenant_a_fixture):
    # seed data for Tenant A
    response = client.get("/v1/{endpoint}", headers={"Authorization": f"Bearer {tenant_b_token}"})
    assert response.status_code == 200
    assert len(response.json()) == 0  # Tenant B sees nothing of Tenant A's data
```

The `get_tenant_db` pattern enforces this at the DB layer — but test coverage confirms
the router is actually using `get_tenant_db` and not accidentally using `get_db`.

### 23.3 What's Currently Tested Well (API Layer)

For completeness, the routers with solid test coverage:

- `forecasts.py` → `test_forecasts_api.py`
- `inventory.py` → `test_inventory_api.py`
- `purchase_orders.py` → `test_purchase_orders_api.py`
- `alerts.py` → `test_alerts_api.py`
- `integrations.py` → `test_integrations_api.py`
- `products.py` → `test_products_api.py`
- `stores.py` → `test_stores_api.py`
- `models.py` → `test_models_api.py`

These routers are lower risk. Focus test-writing effort on the 32 untested endpoints above.

---

## 24. End-to-End Integration Test Strategy

Section 17 covers unit-level test gaps. This section addresses a different layer:
**workflow-level integration tests** that simulate what a buyer actually does, end to end.

Unit tests catch logic bugs in isolation. Integration tests catch broken workflows —
cases where all the units work individually but the sequence doesn't produce the right
outcome. ShelfOps has 63 test files and 0 end-to-end buyer workflow tests.

### 24.1 The Three Buyer Journeys to Test

**Journey 1: Stockout Alert → PO Creation → Outcome Recording**

This is the core ShelfOps value chain. The sequence:

1. `POST /v1/inventory/snapshot` — simulate a new inventory reading
2. Assert: stockout alert created for at-risk SKU
3. `GET /v1/forecasts/stockout-risk` — buyer reviews risk report
4. `GET /v1/purchase_orders/suggested` — buyer views suggested PO
5. `POST /v1/purchase_orders/` — buyer creates PO from suggestion
6. `PATCH /v1/purchase_orders/{id}/approve` — buyer approves
7. `POST /v1/outcomes/alert/{alert_id}` — outcome recorded (stockout avoided)
8. `GET /v1/outcomes/roi` — buyer sees ROI from avoided stockout

If any step in this chain is broken, the buyer's primary workflow fails. Currently
no test covers this sequence from step 1 to step 8.

**Journey 2: Model Improvement Visibility**

The "your model is getting better" story that justifies ongoing subscription:

1. Seed `ModelVersion` records: champion at MASE 0.95 → MASE 0.80 → MASE 0.71
2. `GET /v1/ml_ops/models` — assert list returns champion + history
3. `GET /v1/reports/forecast-accuracy` — assert accuracy trend data is correct
4. `GET /v1/ml_ops/effectiveness` — assert effectiveness score reflects improvement

This journey is currently untestable because the accuracy trend and effectiveness
endpoints are untested (§23, P2 above).

**Journey 3: Data Integration → First Forecast**

The onboarding flow that every new tenant goes through:

1. `POST /v1/integrations/` — create a new integration (Square test mode)
2. `GET /v1/integrations/{id}/sync-health` — verify connection
3. Simulate data ingestion (fixture: 30 days of transaction data)
4. Assert: Pandera validation passes (no schema violations)
5. `GET /v1/forecasts/` — assert first forecast exists for a SKU
6. `GET /v1/inventory/` — assert reorder points calculated

This tests the data path from integration to usable forecast. The individual components
have unit tests; the end-to-end sequence does not.

### 24.2 Test Infrastructure Needed

These integration tests require a persistent test DB (not just in-memory fixtures).
Options:

**Option A: Docker Compose test environment** — spin up Postgres + TimescaleDB in CI,
seed with fixture data, run the full API test suite against the live DB. Slower (adds
2-3 minutes to CI) but catches real DB behavior (connection pooling, TimescaleDB
hypertable partitioning, RLS policies).

**Option B: TestContainers** — programmatic Docker containers in pytest. Each test
class gets a fresh DB instance. Slower startup than fixtures but eliminates the
"shared DB state leaks between tests" problem that plagues session-scoped fixtures.

**Option C: Extend existing `conftest.py`** — the current conftest already sets up
a test DB. The blocker is that multi-step journey tests need to chain requests with
stateful side effects. SQLAlchemy's `rollback()` between tests resets state, breaking
step 3 → step 4 sequences.

**Recommendation**: Use a pytest `module` scope fixture for integration tests that
creates a test DB, seeds it once, runs all steps in order, and tears down. Keep unit
tests with function scope and `rollback`. Separate the two test layers clearly:
`tests/unit/` and `tests/integration/`.

### 24.3 Integration Test Priority

| Journey | Business impact | Implementation effort | Priority |
|---|---|---|---|
| Stockout → PO → Outcome → ROI | Core value chain | Medium (needs outcome seeding) | P1 |
| First Forecast Onboarding | Every new tenant | Low (ETL fixtures exist) | P1 |
| Model Improvement Visibility | Demo story | Medium (accuracy trend fixture) | P2 |
| Multi-tenant data isolation | Security | Low (pattern is simple) | P1 |
| Clearance mode suppression | Business logic | Low | P2 |

### 24.4 What Makes Integration Tests Different From Replay Tests

`test_replay_simulation_script.py` exists and simulates demand replay scenarios.
That's different from a buyer workflow integration test:

- Replay tests: validate model predictions across a simulated time horizon
- Integration tests: validate that the API + DB + business logic produce the right
  buyer-facing outcomes for a given sequence of actions

Both are needed. They're testing different layers of the system. The replay tests
are already doing their job — the integration tests are the gap.

---

## 25. Performance and Load Testing Targets

Neither a load test plan nor performance benchmarks appear anywhere in the current
test suite or docs. For a SaaS product, performance regressions are invisible until
they hit a buyer in production. This section captures baseline targets and the
tests needed to enforce them.

### 25.1 Latency Targets for Buyer-Facing Endpoints

Derived from what's reasonable for a dashboard-driven SMB tool:

| Endpoint | Target p95 latency | Notes |
|---|---|---|
| `GET /forecasts/stockout-risk` | < 500ms | Primary dashboard load |
| `GET /purchase_orders/suggested` | < 800ms | Blocking buyer action |
| `GET /reports/inventory-health` | < 1000ms | Dashboard summary |
| `GET /ml_ops/models/{ver}/shap` | < 2000ms | SHAP is compute-heavy |
| `POST /anomalies/detect` | < 3000ms | On-demand, acceptable wait |
| WebSocket alert push | < 200ms from event | Real-time UX expectation |

These targets are not currently measured or asserted anywhere. A buyer experiencing
5-second dashboard loads will churn.

### 25.2 Concurrency and Multi-Tenant Load

The main multi-tenancy risk isn't individual request latency — it's **one tenant's
heavy query degrading another tenant's experience**.

The TimescaleDB chunk architecture + RLS should prevent cross-tenant query interference
at the DB level. But the Celery worker pool is shared: a large tenant running a 45-feature
retrain job consumes the same `ml` queue as a small tenant's 27-feature retrain.

**Test needed**: Fire 5 simultaneous retrain jobs for different tenants. Assert that
the p95 job-start-to-completion time for the smallest job doesn't exceed 3× its
single-tenant baseline. If it does, the ML worker pool needs priority routing
(e.g., a separate `ml_small` queue for < 1000-row retrains).

### 25.3 Database Query Performance

The TimescaleDB `InventorySnapshot` and `SalesTransaction` hypertables will grow fast.
Performance targets that need `EXPLAIN ANALYZE` verification:

- `stockout-risk` query: should use the time-partitioned index, not a full scan.
  Target: < 50ms at 1M rows per tenant.
- Feedback loop `PODecision` window query (30-day lookback): should use the
  `(customer_id, created_at)` index. Target: < 20ms.
- SHAP feature aggregation query: this is the most join-heavy query in the system.
  Target: < 200ms at 500K inventory snapshots.

**What to do**: Add a `tests/performance/` directory with pytest-benchmark tests that
run these queries against a seeded fixture of known size and assert against time bounds.
Fail CI if a query regresses beyond the target.

### 25.4 Cold-Start Forecast Latency

A new tenant's first forecast request (before any tenant-specific model is trained)
falls through to the pre-trained global model. This cold-start path may have different
latency characteristics than the warm path (tenant model cached in memory).

**Risk**: The global pre-trained model may not be cached the same way as tenant models.
If it's loaded from MLflow artifact store on every cold-start request, a new tenant's
first dashboard load is extremely slow.

**What to verify**: Is the global pre-trained model loaded into memory at startup, or
on first use? If on first use, add a startup preload. Cold-start p95 target: < 2 seconds.

### 25.5 WebSocket Alert Delivery Under Load

`backend/alerts/websocket.py` handles real-time alert delivery. Under load (multiple
tenants with active WebSocket connections), the delivery latency and connection stability
are unknown.

**Test needed**: Simulate 20 concurrent WebSocket connections across 5 tenants. Fire
a batch of 10 alerts per tenant. Assert: all alerts delivered, median delivery time
< 200ms, no dropped connections.

This test requires a proper async test harness (pytest-asyncio + asyncio WebSocket
client). It's not in the current test suite.

[ ] Does the WebSocket implementation handle authentication token expiry mid-connection?
    If the JWT expires while a buyer has the dashboard open, the WebSocket should
    reconnect transparently, not silently drop alerts.

[ ] Is there a backpressure mechanism if the WebSocket client is slow to consume?
    Under high alert volume (a major stockout event affecting 50 SKUs simultaneously),
    the server-side buffer could fill and drop messages if not handled.
