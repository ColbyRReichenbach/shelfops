# ShelfOps — Strategy Brainstorm

- Status: **Living document — do not finalize until sections are explicitly closed**
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

### Multi-Location Store Clustering — Already Built

`backend/ml/segmentation.py` — K-Means clustering groups stores into 3 tiers
(high-volume, mid-volume, low-volume) for feature routing. This is the current
multi-location handling. It groups by **volume** but not by **geographic or
behavioral similarity**.

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

- Production: XGBoost (65%) + LSTM (35%) ensemble
- `ml_improvement_plan.md` already recommends switching to pure LightGBM (Poisson objective)
  — the LSTM is actively degrading every metric (weight sweep logged in model_strategy_cycle)
- Anomaly detection: Isolation Forest (separate model, `anomaly.py`)
- Category-specific models: Fresh, GM, Hardware (`segmentation.py`)
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

`segmentation.py` clusters stores by transaction volume into 3 tiers (K-Means).
This answers "how big is this store?" but not "which other stores are this store most
like?"

Volume tiers are useful for feature routing (high-volume stores get richer models)
but they don't capture **behavioral similarity** — two stores can have the same volume
but completely different demand patterns (one near a university, one in a suburb).

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
| KNN store similarity index | `segmentation.py`, `features.py` | Medium | 4.2 |
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
