# ShelfOps Current-to-Standout Product + Engineering Specification

**Date:** 2026-04-19  
**Repo audited:** `shelfops-main`  
**Target outcome:** Convert ShelfOps from a broad demo/MLOps-heavy portfolio project into a credible, pilot-ready inventory decision platform with real data, defensible forecasting, measurable replenishment outcomes, and a clean public repo.

---

## 0. One-sentence product definition

**ShelfOps is an inventory decision control plane for SMB and mid-market retailers. It connects POS, inventory, supplier, and purchase-order data; trains auditable demand models; generates human-reviewed replenishment recommendations; and measures whether those recommendations reduce stockout risk, overstock exposure, forecast error, and buyer workload.**

This is the product center. Every backend route, ML artifact, UI screen, dataset, and document should support this loop:

```text
real data ingest
  -> data validation / readiness
  -> demand forecast + uncertainty
  -> stockout / overstock risk
  -> replenishment recommendation
  -> buyer accept/edit/reject
  -> actual outcome arrives
  -> measured business impact
  -> model / policy improvement
```

---

## 1. Why this roadmap is commercially aligned

Retail inventory distortion remains a major business problem. IHL Group reported in September 2025 that global retail loses about **$1.73T annually** to out-of-stocks and overstocks. RELEX's March 2026 supply-chain research says nearly half of organizations are investing in AI-driven inventory and supply optimization. This supports positioning ShelfOps around operational inventory decisions rather than generic forecasting.

Companies already building near this space validate the product direction. Afresh publicly frames its grocery platform around optimizing ordering, forecasting, store operations, food waste, and freshness; its careers page explicitly discusses forecasting under uncertainty, long-horizon planning, item perishability, and large-scale simulations. Focal Systems frames retail AI around real-time shelf visibility, availability, reduced out-of-stock duration, sales recapture, ordering, and operational accountability. These are not exact competitors to a solo-dev ShelfOps MVP, but they show the industry language a serious project should use.

The MLOps direction is also justified. Google Cloud's ML best-practices documentation frames production ML as a full workflow across custom data/code, training, evaluation, deployment, and monitoring. MLflow's Model Registry documentation emphasizes centralized model lifecycle management, lineage, versioning, aliases, metadata tagging, and stage management. NIST's AI RMF provides a useful governance frame for AI risk management. Evidently's monitoring materials emphasize data drift as changing feature distributions that can degrade production performance. ShelfOps already has parts of this; the roadmap below turns it into a coherent product.

---

## 2. Current repo state: what exists now

### 2.1 Backend

Implemented or substantially implemented:

- FastAPI application with async SQLAlchemy.
- API routers for stores, products, forecasts, alerts, integrations, inventory, purchase orders, ML models, ML alerts, experiments, anomalies, outcomes, ML ops, and reports.
- Multi-tenant patterns using `get_tenant_db()` and DB session context.
- Postgres/Timescale-style schema with operational, integration, forecast, PO, alert, model, and experiment tables.
- Celery workers for sync, forecast, retrain, monitoring, vendor metrics, promotion tracking, and scheduling.
- Purchase-order workflow: suggested orders, approval, quantity edits, rejection reason codes, receiving, and decision history.
- Square OAuth/webhook/sync scaffolding.
- EDI/SFTP/Kafka-style architecture proof and tests.
- Alert, anomaly, ML alert, outcome, ROI, and reporting endpoints.

Known issues to fix:

- `backend/api/main.py` registers `experiments.router` twice, once directly and once under `/api/v1`.
- Several docs refer to `get_tenant_db`, `app.current_tenant`, and `DEV_CUSTOMER_ID` constants that do not exactly match the current code, which uses `app.current_customer_id` patterns.
- There is too much enterprise/demo breadth relative to the single product loop that must be proven.

### 2.2 Data engineering

Implemented or substantially implemented:

- Canonical dataset loading for public datasets in `backend/ml/data_contracts.py`.
- Dataset-readiness script in `backend/scripts/validate_training_datasets.py`.
- Kaggle downloader/preprocessor in `backend/scripts/download_kaggle_data.py`.
- SFTP, EDI, Square, and Kafka/event adapter concepts.
- Integration sync health logs and API.

Known issues to fix:

- Public benchmark datasets are referenced but not fully established as the canonical evidence path.
- `backend/scripts/benchmark_datasets.py` still uses XGBoost even though the main training path is LightGBM-first.
- Square sync supports mappings, but the onboarding/mapping flow is not clean enough to be pilot-grade.
- Demo ID synthesis exists and must be clearly isolated from any production or evidence claim.
- There is no persistent inbound webhook event log with replay/dead-letter behavior.

### 2.3 ML / data science

Implemented or substantially implemented:

- LightGBM-first training in `backend/ml/train.py` with Poisson objective.
- TimeSeriesSplit validation and leakage-aware lag features.
- Feature tiers: `cold_start` and `production` in `backend/ml/features.py`.
- Metrics: MAE, MAPE-like nonzero, WAPE, MASE, bias.
- Feature validation and no-future-leakage tests.
- Model registry/champion file artifacts.
- Runtime DB model lifecycle tables and promotion gates.
- Shadow prediction and monitoring concepts.
- Feedback-loop features from PO decisions.
- Anomaly / ghost-stock modules.

Critical issues to fix:

- Current checked-in champion is not credible. `backend/models/registry.json` shows `rows_trained: 27`, dataset `favorita`, status `champion`, and promotion reason `experiment_rollback`.
- `backend/models/v1/metadata.json` still references old XGBoost/LSTM weights while current code is LightGBM-first.
- `backend/models/v1/lstm.keras` and `xgboost.joblib` are legacy artifacts that weaken the current ML story unless archived and labeled.
- Prediction intervals in `backend/ml/predict.py` are heuristic, not calibrated.
- Business-rule overlays are applied after model scoring but not evaluated separately from raw model output.
- There is no full model card showing data, split, baselines, segment metrics, interval calibration, business metrics, and limitations.
- Forecasting is not yet tied tightly enough to replenishment simulation and actual buyer outcomes.

### 2.4 Frontend / UI

Implemented or substantially implemented:

- React/Vite/TypeScript frontend.
- Pages for dashboard, alerts, forecasts, products, inventory, stores, integrations, operations, MLOps, and demo.
- MLOps components for model arena, feature importance, backtests, experiments, and data health.
- Forecast pages and SHAP-style explanations.

Known issues to fix:

- The product is not centered around a daily buyer decision queue.
- The existing UI is more dashboard-like than workflow-like.
- Purchase-order workflow exists in backend but is not the obvious main frontend surface.
- Forecast uncertainty is not buyer-facing.
- Model/data quality labels are not visible where buyers act.
- Demo mode should not look like the main product claim.

### 2.5 Docs / repo hygiene

Implemented or substantially implemented:

- Strong docs: `README.md`, `TECHNICAL.md`, `docs/product/known_limitations.md`, `docs/demo/CLAIMS_LEDGER.md`, model readiness docs, observability docs, operations runbooks, and demo scripts.
- Claims ledger has useful implemented / partial / do-not-claim structure.

Known issues to fix:

- Docs are too demo- and enterprise-heavy for a clean public product story.
- `.claude/` contains internal agent plans and workflow docs that should not be part of the public product repo.
- Demo artifacts and synthetic data are scattered.
- Some docs overstate readiness relative to model evidence.
- There is no single canonical `CURRENT_STATE.md` or public `MODEL_CARD.md` that resets the truth.

---

## 3. Standout target state

ShelfOps is standout when a reviewer can see all of this without guessing:

1. **Real evidence path:** benchmark training on a focused public retail dataset suite and a clear path to CSV/Square merchant ingestion.
2. **Credible model:** LightGBM baseline/champion trained on real benchmark data with baselines, time-based validation, calibrated intervals, segment metrics, and model card.
3. **Decision product:** a Replenishment Queue where a buyer sees what to order, why, uncertainty, risk, and expected cost.
4. **Outcome measurement:** every recommendation is tied to accept/edit/reject behavior and later stockout/overstock/forecast outcomes.
5. **MLOps discipline:** registry, lineage, model card, drift/data-quality monitoring, promotion gates, and rollback are coherent and true.
6. **Pilot readiness:** CSV onboarding and one real POS connector are credible enough for a small retailer pilot.
7. **Clean repo:** synthetic/demo artifacts are clearly isolated; public docs only claim what the code and evidence support.

---

## 4. Non-negotiable product scope

### 4.1 Primary user

A retail operator, inventory manager, buyer, owner, or store manager responsible for ordering and stock availability.

### 4.2 Primary workflow

The user logs in daily or weekly and answers:

1. What items are at risk?
2. What should I order?
3. How much should I order?
4. Why does the system recommend this?
5. What is the uncertainty?
6. What happens if I do nothing?
7. Did the previous recommendations work?

### 4.3 Primary product page

The primary page should be **Replenishment Queue**, not generic dashboard, forecasts, or MLOps.

### 4.4 Product KPI hierarchy

Do not lead with model metrics. Lead with business metrics, then show model evidence.

| Metric layer | Metrics |
|---|---|
| Business outcome | stockout events, stockout miss rate, lost-sales proxy, overstock exposure, overstock dollars, inventory turns, PO acceptance rate, buyer edit distance, time-to-decision |
| Forecast quality | WAPE, MASE, MAE, bias, MAPE_nonzero, horizon-level error, segment-level error |
| Uncertainty quality | interval coverage, interval width, pinball loss, undercoverage by segment |
| Data quality | freshness, missingness, SKU mapping coverage, inventory staleness, negative stock, duplicate sales, unmapped catalog IDs |
| MLOps quality | model version, dataset snapshot, feature tier, registry stage, drift status, promotion gate status, retrain reason |

---

## 5. Data strategy

### 5.1 Focused data plan

Do **not** over-saturate ShelfOps with every available retail dataset. The project should use the smallest dataset suite that proves the core product claims.

Active implementation scope:

| Scope | Dataset / source | Role in ShelfOps | Why it is included | What it cannot prove |
|---|---|---|---|---|
| **Primary public benchmark** | **M5 / Walmart** | Main demand-forecasting benchmark | U.S.-based Walmart retail sales benchmark; daily hierarchical item/store data; strong for model rigor, baselines, segment metrics, and uncertainty evaluation. | Does not include true inventory position, supplier lead times, purchase orders, or buyer decisions. |
| **Secondary public benchmark** | **FreshRetailNet-50K** | Stockout-aware / censored-demand benchmark | Adds stockout annotations, stock status, perishable SKUs, promotions, precipitation, and hourly demand context. It lets ShelfOps prove that sales-only forecasting can understate demand during stockouts. | Not U.S.-based and not a complete SMB merchant operating dataset. Use only for stockout/censoring methodology. |
| **Pilot / product validation** | **CSV onboarding + Square connector** | Real merchant ingestion and pilot outcomes | CSV gives flexible merchant onboarding; Square gives a concrete POS/catalog/orders/inventory integration path. This is the only layer that can produce actual merchant ROI claims. | Requires merchant authorization and sufficient historical data. Public repo cannot claim pilot outcomes until measured. |
| **Deferred optional backup** | **Dominick's Finer Foods** | Price / promo / margin retail DS backup | U.S. grocery scanner data with weekly UPC/store sales, prices, promotions/deal codes, and margin-like information. Useful if ShelfOps needs deeper price/promo/margin evidence later. | Older weekly data. Do not implement in the first pass unless the M5 + FreshRetailNet story is insufficient. |

Out of active scope for the first standout build:

- Favorita / Store Sales: keep as legacy/reference only; it should not be the active champion dataset.
- Rossmann: do not use for core ShelfOps because it is store-level, not SKU-replenishment centered.
- Instacart: useful for basket/reorder behavior, but not inventory/replenishment.
- 84.51° Complete Journey: useful for campaigns/coupons/baskets, but not required for the first ShelfOps business loop.
- UCI Online Retail: useful for simple transaction ETL, but too weak for the inventory-decision claim.
- Any leaked or unauthorized proprietary data: disallowed.

### 5.2 Release sequencing for data

#### Release 1: M5-only model reset

Purpose:

- replace the current weak/legacy champion,
- prove forecast rigor on a U.S.-based retail benchmark,
- create the first credible model card,
- prove baselines, segments, uncertainty, and time-based validation.

Required outputs:

- `backend/data_sources/m5.py`,
- M5 canonicalization into ShelfOps grain,
- dataset snapshot metadata,
- baseline comparison,
- LightGBM model card,
- segment metrics,
- calibrated interval report,
- active champion that no longer references old XGBoost/LSTM artifacts or 27-row training.

Allowed claim:

> ShelfOps trains and evaluates demand-forecasting models on the public M5/Walmart benchmark using time-based validation, baselines, segment metrics, uncertainty metrics, and reproducible dataset snapshots.

Disallowed claim:

> ShelfOps reduced real merchant stockouts.

#### Release 2: FreshRetailNet stockout/censored-demand track

Purpose:

- prove ShelfOps understands that observed sales are not always true demand,
- add stockout-aware evaluation,
- support perishable and stockout-censored demand language,
- improve the business credibility of stockout-risk claims.

Required outputs:

- `backend/data_sources/freshretailnet.py`,
- stockout/censoring labels in canonical data,
- non-stockout vs stockout-window evaluation,
- latent-demand recovery experiment or clearly labeled censored-demand adjustment,
- stockout-aware model card appendix.

Allowed claim:

> ShelfOps includes a stockout-aware evaluation track that distinguishes normal sales periods from stockout-censored periods and measures under-forecast bias during stockouts.

Disallowed claim:

> FreshRetailNet results prove U.S. merchant ROI.

#### Release 3: CSV + Square pilot path

Purpose:

- make ShelfOps usable for a real retailer pilot,
- ingest product, order, and inventory data,
- map external IDs to ShelfOps stores/products,
- generate recommendations only when data readiness gates pass,
- capture buyer decisions and outcomes.

Required outputs:

- CSV validator and canonical mapper,
- Square catalog/orders/inventory mapping preview,
- data-readiness page/API,
- recommendation eligibility gate,
- pilot metric instrumentation.

Allowed claim after a real pilot only:

> Across N SKUs and M weeks, ShelfOps measured forecast error, stockout exposure, overstock exposure, PO acceptance, buyer edit distance, and recommendation outcomes for a real merchant.

### 5.3 Data source registry

Create a source registry so every dataset has explicit provenance and claim boundaries.

```text
data_registry/
  datasets.yaml
  m5/
    README.md
    schema.yaml
  freshretailnet_50k/
    README.md
    schema.yaml
  square/
    README.md
    schema.yaml
  csv_onboarding/
    README.md
    schema.yaml
  dominicks_deferred/
    README.md
```

Each source entry must include:

```yaml
dataset_id:
name:
source_url:
license_or_terms:
access_method:
geography:
retail_type:
grain:
frequency:
date_range:
contains_sales:
contains_inventory:
contains_stockouts:
contains_price:
contains_promotions:
contains_weather:
contains_po:
contains_supplier_lead_time:
contains_buyer_decisions:
primary_use:
limitations:
allowed_claims:
disallowed_claims:
implementation_status: active | deferred | legacy | disallowed
```

Example for M5:

```yaml
dataset_id: m5_walmart
implementation_status: active
primary_use: primary_public_forecasting_benchmark
allowed_claims:
  - Evaluates SKU/store demand forecasting on a public U.S.-based Walmart benchmark.
  - Supports hierarchy-aware reporting, baselines, segment metrics, and forecast uncertainty evaluation.
disallowed_claims:
  - Proves real merchant stockout reduction.
  - Measures supplier lead-time improvement.
  - Validates buyer purchase-order workflow.
```

Example for FreshRetailNet:

```yaml
dataset_id: freshretailnet_50k
implementation_status: active_secondary
primary_use: stockout_censored_demand_benchmark
allowed_claims:
  - Evaluates stockout-aware and censored-demand behavior on a public fresh-retail benchmark.
  - Measures forecast bias during stockout periods separately from normal periods.
disallowed_claims:
  - Proves U.S. merchant ROI.
  - Replaces a real merchant inventory/PO pilot.
```

### 5.4 Live merchant data

Pilot ingestion should support two paths:

1. **CSV-first onboarding** for any retailer.
2. **Square-first POS connector** as the first production-grade integration path.

Square is a good first connector because Square exposes Catalog, Orders, and Inventory APIs. Square's Catalog API manages item libraries, the Orders API records commerce events and can update catalog inventory, and the Inventory API manages stock quantities and inventory changes.

Shopify should be deferred. It maps well to ShelfOps because Shopify's inventory model tracks inventory quantities per item and location, including states like available, committed, reserved, incoming, quality control, and safety stock. It should be added only after CSV + Square are clean.

### 5.5 Canonical schema

The canonical operational schema should distinguish these tables and grains:

| Table / object | Grain | Notes |
|---|---|---|
| `stores` | store | location, timezone, status |
| `products` | product/SKU | SKU, category, cost, price, perishability, supplier |
| `transactions` | order line | timestamp, store, product, quantity, price, discount, external ID |
| `inventory_levels` | store-product-timestamp | QOH, available, reserved, on-order, source |
| `stock_status_events` | store-product-timestamp/window | in stock, out of stock, censored-demand flag; benchmark-only or live-inventory derived |
| `suppliers` | supplier | lead-time, reliability, min order constraints |
| `purchase_orders` | PO line or PO header+line, depending current schema | recommendation and order lifecycle |
| `po_decisions` | buyer decision | accept/edit/reject, reason, actor, timestamp |
| `recommendations` | store-product-horizon action | recommended qty, risk, model version, policy version |
| `recommendation_outcomes` | recommendation after horizon closes | actual sales, stockout, overstock, value estimate |
| `dataset_snapshots` | dataset/version | immutable data snapshot metadata for training/evaluation |
| `model_cards` | model version | evidence package for public and internal model review |

### 5.6 Data quality gates

Create explicit gates before training, scoring, and recommending.

#### Gate A: ingest gate

Reject or quarantine data if:

- required columns missing,
- unparseable dates above threshold,
- duplicate external IDs above threshold,
- quantity cannot be parsed,
- product/store mapping coverage below threshold,
- inventory source older than configured SLA,
- negative inventory not labeled as correction/adjustment,
- sales timestamps not timezone-normalized.

#### Gate B: training readiness gate

A tenant or benchmark segment is trainable only if:

- minimum date coverage is met,
- minimum nonzero demand observations exist,
- SKU/store count is sufficient,
- sales and inventory are not mostly missing,
- stockout censoring is either absent, measured, or labeled as unknown,
- target grain is explicit,
- train/validation/test windows are valid.

Dataset-specific readiness:

- M5 can train the primary demand model without live inventory, but stockout and PO metrics must be labeled `not_available` or simulated.
- FreshRetailNet can train/evaluate stockout-aware logic, but U.S. retail and merchant ROI claims must be blocked.
- Square/CSV pilot tenants can generate recommendations only when inventory freshness, SKU mapping, lead-time assumptions, and buyer-decision capture are configured.

#### Gate C: recommendation gate

A recommendation can be shown only if:

- model version is known,
- feature tier is known,
- forecast horizon matches lead-time window,
- interval coverage exists or the confidence label says `uncalibrated`,
- SKU has current inventory or a data-quality warning,
- supplier/lead-time assumption is present,
- no unmapped integration fields affect the SKU/store.

---

## 6. Detailed ML / DS specification

This is the most important part of the upgrade.

### 6.1 Problem formulation

ShelfOps should not be framed as a generic demand predictor. It should be framed as a **replenishment decision system**.

Forecasting task:

```text
Predict future observed demand for product p at store s over horizon h.
```

Decision task:

```text
Recommend replenishment quantity q for product p at store s given:
- current inventory position,
- forecast demand distribution over lead time,
- supplier lead time distribution,
- service-level target,
- holding/stockout cost proxy,
- min order / pack-size constraints,
- buyer feedback history.
```

Important caveat: observed sales are not always true demand. If inventory reaches zero, observed sales can be censored because customers cannot buy unavailable products. The system should label this limitation and use stockout-aware metrics when inventory data exists.

### 6.2 Target grain

Use two grains:

1. **Benchmark grain:** dataset-specific, usually store-product-day or store-family-day.
2. **Production grain:** store-SKU-day, with forecast horizons of 7, 14, and 28 days.

Do not mix daily and weekly datasets in one champion without labeling. M5 should remain the primary daily benchmark. Dominick's, if implemented later, should stay as a separate weekly price/promo/margin experiment and must not be silently merged into the M5 champion.

### 6.3 Model families to implement

#### Baselines

Implement these first. They are required for credibility.

| Model | Use |
|---|---|
| naive last observation | minimum sanity baseline |
| seasonal naive, seasonality 7 | daily retail baseline |
| moving average 7/14/28 | practical operational baseline |
| category/store average | cold-start fallback |
| Croston/SBA or TSB | intermittent/slow-moving demand baseline |
| reorder-rule baseline | business baseline, not forecast baseline |

The model card must show whether LightGBM beats these baselines by segment.

#### Main model

Use **LightGBM Poisson/Tweedie** as the primary tabular forecasting model.

Rationale:

- works well with tabular lag/calendar/promo/inventory features,
- handles nonlinear interactions,
- practical for a solo-dev production-like platform,
- explainable enough through feature importance and SHAP-style tools,
- faster and more maintainable than deep learning for this stage.

Model variants to test:

1. `lightgbm_poisson_global`
2. `lightgbm_tweedie_global`
3. `lightgbm_l2_log1p_global`
4. `two_stage_hurdle`: classifier for nonzero demand + regressor for positive quantity
5. `segment_models`: separate models for fast / medium / slow / intermittent SKUs if enough data exists

Do not bring LSTM back unless you have a clear reason and evidence. The old LSTM artifact should be archived.

#### Uncertainty models

Replace heuristic intervals with one or both:

1. **LightGBM quantile models** for p10/p50/p90.
2. **Split conformal prediction** over time-based validation residuals.

A point forecast alone is not enough for replenishment. Prediction intervals must be calibrated and reported with actual coverage. A properly calibrated 95% interval should contain actual values about 95% of the time; if not, the product should say so.

### 6.4 Feature engineering specification

Current `backend/ml/features.py` is a good base. Upgrade it as follows.

#### Temporal features

Keep:

- day of week,
- week of year,
- month,
- quarter,
- weekend,
- holiday,
- month start/end,
- days since last sale.

Add:

- days to next holiday,
- days since last holiday,
- pay-period proxy if relevant,
- local timezone extraction always verified,
- retailer-specific closed days if available.

#### Demand-history features

Keep leakage-safe shifted rolling windows.

Add:

- lag_1, lag_2, lag_3, lag_7, lag_14, lag_28,
- rolling mean 7/14/28/56,
- rolling sum 7/14/28/56,
- rolling std 7/14/28,
- rolling max/min,
- zero-demand ratio over 28/56,
- intermittent demand classification,
- recent acceleration / deceleration,
- demand spike indicator.

All lag/rolling features must use only data available before the forecast timestamp.

#### Product features

Keep:

- category,
- unit cost,
- unit price,
- margin,
- shelf life,
- seasonal/perishable flags.

Add:

- price band,
- margin band,
- pack size,
- case pack / minimum order quantity,
- category hierarchy where available,
- new SKU age,
- SKU velocity segment.

#### Store features

Keep:

- location,
- average sales,
- product count,
- turnover.

Add:

- store velocity segment,
- store demand volatility,
- local timezone quality flag,
- store cluster from historical patterns.

#### Inventory features

Keep:

- current stock,
- days of supply,
- quantity on order,
- stockout count.

Add:

- inventory age / staleness,
- last count timestamp,
- recent adjustment count,
- phantom-stock risk score,
- reserved/committed/incoming quantities if available,
- stockout-censored target flag,
- on-order ETA.

#### Supplier / lead-time features

Add or formalize:

- historical lead-time mean / median / p90,
- lead-time variance,
- supplier fill rate,
- late-delivery rate,
- receiving discrepancy rate,
- minimum order quantity,
- case pack,
- vendor reliability multiplier.

#### Buyer-feedback features

Current feedback features are strong. Make them first-class:

- rejection rate 30d,
- average quantity adjustment percent,
- forecast trust score,
- buyer reason-code distribution,
- repeated manual override flag,
- recommendation acceptance streak.

Use these cautiously. They can encode organizational habits, not ground truth. They should inform recommendation presentation and policy, not silently distort demand forecasts without evaluation.

### 6.5 Segmentation strategy

Every model metric must be broken down by segment.

Required SKU segments:

| Segment | Definition |
|---|---|
| fast mover | high average demand and frequent nonzero sales |
| medium mover | moderate demand/frequency |
| slow mover | low but not highly intermittent |
| intermittent | many zero days, sporadic spikes |
| cold start | insufficient history |
| promoted | promotion-active or recently promoted |
| perishable | shelf-life constrained |
| high margin | margin above configured threshold |

The system should not pretend one global WAPE is enough. Global WAPE can hide poor behavior on slow/intermittent SKUs.

### 6.6 Evaluation protocol

#### Splits

Use expanding-window or rolling-origin time splits.

Example:

```text
train:      T0 -> T90
validate:   T91 -> T104
train:      T0 -> T104
validate:   T105 -> T118
train:      T0 -> T118
validate:   T119 -> T132
final test: last 28 days held out
```

Rules:

- no random shuffle,
- no future leakage,
- evaluate by horizon,
- keep final test locked until the candidate is chosen,
- report dataset date ranges and row counts.

#### Forecast metrics

Required:

- MAE,
- WAPE,
- MASE,
- MAPE_nonzero,
- bias percentage,
- RMSE only as secondary,
- horizon-specific WAPE and bias,
- segment-level WAPE/MASE/bias.

Rationale:

- WAPE is useful for sparse retail datasets because it normalizes absolute error by total demand and emphasizes high-volume items.
- MASE is scale-free and useful for comparing across series; Hyndman introduced it partly because traditional percentage metrics can fail on intermittent demand.
- MAPE must not be the primary metric where many values are zero.

#### Uncertainty metrics

Required:

- p50 WAPE,
- p10/p90 pinball loss,
- empirical interval coverage,
- average interval width,
- undercoverage rate,
- coverage by segment.

#### Business metrics

Required:

- stockout miss rate,
- overstock rate,
- overstock units,
- overstock dollars,
- lost-sales proxy,
- opportunity cost stockout,
- opportunity cost overstock,
- service level,
- fill-rate proxy,
- recommendation acceptance rate,
- buyer edit distance.

### 6.7 Replenishment simulation

Build a replay simulator before claiming business impact.

Inputs:

- historical demand,
- current/initial inventory assumption,
- supplier lead time,
- minimum order quantity,
- order cadence,
- holding cost proxy,
- stockout cost proxy,
- service-level target,
- forecast model output,
- uncertainty output.

Compare policies:

1. no model: static reorder point,
2. moving average reorder,
3. seasonal naive reorder,
4. ShelfOps forecast + static lead time,
5. ShelfOps forecast + dynamic lead time,
6. ShelfOps forecast + buyer-feedback policy, if enough data.

Simulation outputs:

- total stockout days,
- units short,
- lost-sales proxy,
- overstock units,
- overstock dollars,
- number of POs,
- average order quantity,
- service level,
- holding cost proxy,
- combined cost proxy.

Public wording:

- safe: “In benchmark replay, ShelfOps policy reduced simulated stockout exposure relative to static reorder baseline.”
- unsafe without real pilot: “ShelfOps reduced a merchant’s stockouts.”

### 6.8 Recommendation policy

Recommendation quantity should be generated by policy, not directly by the forecast.

Core formula:

```text
inventory_position = on_hand + on_order - committed/reserved
lead_time_demand = sum forecast distribution over expected lead time
safety_stock = z(service_level) * sqrt(lead_time) * demand_std * supplier_reliability_multiplier
reorder_point = lead_time_demand + safety_stock
recommended_qty = max(0, reorder_point - inventory_position)
recommended_qty = apply_case_pack_moq_constraints(recommended_qty)
```

Add dynamic lead time:

```text
lead_time_days = p50 or p90 historical supplier lead time by supplier/product/store
```

The UI must show the assumption used:

- “Lead time: 6 days, supplier p90 from last 12 deliveries.”
- “No supplier history; using category default.”

### 6.9 Promotion gates

Current `backend/ml/arena.py` is already strong. Keep fail-closed behavior, but update required metrics after the new model-card system.

Candidate promotion must require:

- dataset snapshot ID,
- train/validation/test date ranges,
- rows trained,
- feature tier,
- baseline comparison,
- WAPE non-regression,
- MASE non-regression,
- bias bound,
- interval coverage non-regression,
- stockout miss-rate non-regression,
- overstock exposure non-regression,
- no critical data-contract failures,
- model card generated,
- rollback pointer exists.

### 6.10 Monitoring

Production-like monitoring should track:

- data freshness,
- schema drift,
- feature drift,
- prediction drift,
- actual-vs-predicted error after ground truth arrives,
- interval coverage,
- SKU segment degradation,
- buyer acceptance/edit/rejection rates,
- recommendation outcome metrics,
- integration failure rates.

Distinguish:

- data drift: feature distribution changes,
- concept drift: relationship between features and demand changes,
- training-serving skew: production features differ from training features,
- delayed ground truth: actual outcomes arrive after recommendations.

---

## 7. Backend specification

### 7.1 API cleanup

Tasks:

- Fix duplicate experiment router registration.
- Normalize all routers under `/api/v1`.
- Add deprecation aliases only where needed, with explicit headers.
- Ensure frontend paths match backend paths.
- Make all tenant context naming consistent: either `app.current_customer_id` or `app.current_tenant`, not both.

### 7.2 New backend modules

Add or refactor these modules:

```text
backend/ml/baselines.py
backend/ml/calibration.py
backend/ml/segments.py
backend/ml/model_card.py
backend/ml/evaluation.py
backend/ml/replenishment_simulation.py
backend/ml/quantile.py
backend/ml/policy.py
backend/ml/dataset_snapshots.py
backend/ml/latent_demand.py
backend/data_sources/m5.py
backend/data_sources/freshretailnet.py
backend/data_sources/square.py
backend/data_sources/csv_onboarding.py
backend/data_sources/dominicks_deferred.py
backend/recommendations/service.py
backend/recommendations/outcomes.py
backend/recommendations/schemas.py
```

### 7.3 New or upgraded endpoints

#### Data readiness

```text
GET  /api/v1/data/readiness
POST /api/v1/data/validate-csv
GET  /api/v1/data/snapshots
GET  /api/v1/data/snapshots/{snapshot_id}
```

#### Model evidence

```text
GET  /api/v1/ml/model-cards
GET  /api/v1/ml/model-cards/{version}
GET  /api/v1/ml/evaluation/summary
GET  /api/v1/ml/evaluation/segments
GET  /api/v1/ml/calibration
GET  /api/v1/ml/baselines
```

#### Replenishment decisions

```text
GET  /api/v1/replenishment/queue
GET  /api/v1/replenishment/recommendations/{recommendation_id}
POST /api/v1/replenishment/recommendations/{recommendation_id}/accept
POST /api/v1/replenishment/recommendations/{recommendation_id}/edit
POST /api/v1/replenishment/recommendations/{recommendation_id}/reject
GET  /api/v1/replenishment/outcomes
GET  /api/v1/replenishment/impact
```

#### Simulation

```text
POST /api/v1/simulations/replenishment
GET  /api/v1/simulations/{simulation_id}
GET  /api/v1/simulations/{simulation_id}/policy-comparison
```

### 7.4 Database migrations

Add migrations for:

```text
dataset_snapshots
model_cards
model_evaluation_runs
model_segment_metrics
prediction_interval_calibration
replenishment_recommendations
recommendation_decisions
recommendation_outcomes
replenishment_policy_versions
lead_time_observations
supplier_reliability_metrics
data_quality_events
webhook_event_log
webhook_dead_letter_events
```

You may map some of these to existing tables if the current schema already covers the need. Do not duplicate existing `purchase_orders` and `po_decisions` unless a separate recommendation layer is required. The key is to preserve a distinction between:

```text
forecast -> recommendation -> buyer decision -> purchase order -> receiving -> outcome
```

### 7.5 Webhook replay / dead letter

Square webhooks should be stored before processing:

```text
webhook_event_log:
- event_id
- provider
- merchant_id
- customer_id nullable until resolved
- event_type
- payload_hash
- payload_json
- received_at
- processed_at
- status: received | processing | processed | failed | dead_letter
- retry_count
- error_message
```

This lets the system replay events rather than relying only on best-effort debounce.

---

## 8. Frontend / UI specification

### 8.1 Navigation changes

Primary navigation:

1. **Replenishment**
2. **Inventory Risk**
3. **Forecasts**
4. **Pilot Impact**
5. **Data Readiness**
6. **Integrations**
7. **MLOps**
8. **Operations**

Dashboard can remain as home, but the first actionable page must be Replenishment.

### 8.2 Replenishment Queue

Create `frontend/src/pages/ReplenishmentPage.tsx`.

Required table columns:

- risk rank,
- SKU / product,
- store,
- current inventory,
- inventory data freshness,
- lead time,
- supplier,
- forecasted lead-time demand,
- p10/p50/p90 demand,
- recommended quantity,
- expected cost,
- stockout risk if no order,
- overstock risk if ordered,
- confidence badge,
- data-quality badge,
- model version,
- action buttons: accept, edit, reject.

Recommendation detail drawer:

- why this recommendation exists,
- top drivers,
- forecast chart,
- inventory history,
- supplier lead-time history,
- previous buyer decisions,
- previous outcome,
- policy version,
- raw assumptions.

### 8.3 Pilot Impact page

Create `frontend/src/pages/PilotImpactPage.tsx`.

Show:

- baseline vs ShelfOps policy,
- forecast WAPE trend,
- stockout miss rate,
- overstock dollars,
- recommendation acceptance rate,
- buyer edit distance,
- confirmed anomaly count,
- time-to-decision,
- data coverage.

Every metric should have a label:

- measured,
- simulated benchmark,
- estimated,
- unavailable.

### 8.4 Data Readiness page

Create `frontend/src/pages/DataReadinessPage.tsx`.

Show:

- products mapped,
- stores mapped,
- transaction rows,
- inventory rows,
- date coverage,
- nonzero demand count,
- unmapped external IDs,
- stale inventory count,
- missing cost/price count,
- trainability status,
- recommendation eligibility status.

### 8.5 Model Evidence page

Upgrade `MLOpsPage` or create `ModelEvidencePage`.

Show:

- champion model card,
- dataset snapshot,
- train/validation/test date windows,
- baseline comparison,
- segment metrics,
- calibration chart,
- promotion-gate decision,
- model limitations,
- drift status,
- retraining history.

### 8.6 UI trust badges

Use consistent labels:

| Badge | Meaning |
|---|---|
| measured | based on observed actuals |
| estimated | based on model or cost proxy |
| simulated | benchmark replay or synthetic replay |
| provisional | waiting for actuals |
| uncalibrated | point forecast exists, interval not validated |
| low sample | sample below reliability threshold |
| stale data | source freshness outside SLA |
| unmapped | external data could not map to product/store |

---

## 9. Documentation and demo cleanup

### 9.1 Public doc hierarchy

Replace the current scattered story with this hierarchy:

```text
README.md
CURRENT_STATE.md
CLAIMS.md
PRODUCT_SPEC.md
MODEL_CARD.md
DATA_SOURCES.md
PILOT_PLAYBOOK.md
TECHNICAL.md
ROADMAP.md
docs/archive/
```

### 9.2 What to delete, move, or archive

Move to `docs/archive/internal_agent_artifacts/` or delete from public repo:

```text
.claude/
docs/demo/SLIDE_DECK_OUTLINE.md
docs/demo/VIDEO_SCRIPT_10MIN.md
docs/demo/DEMO_ONE_PAGE_CHEAT_SHEET.md
docs/productization_artifacts/*.json when generated/demo-only
backend/reports/walmart_transform_sensitivity.json if stale
backend/models/v1/lstm.keras
backend/models/v1/xgboost.joblib
backend/models/v1/metadata.json if not current
backend/models/v1/metadata.joblib if not current
```

Do not delete tests or source modules without checking references. The goal is not to shrink the repo blindly. The goal is to keep public evidence clean.

### 9.3 Synthetic/demo data policy

Keep synthetic data only under:

```text
data/demo/
```

Add a clear README:

```text
This directory contains synthetic data for UI/demo testing only. It is not used for model-performance claims, business-impact claims, or public evidence unless explicitly labeled as synthetic.
```

### 9.4 Claims policy

Update `CLAIMS.md` to say:

Safe claims after P0/P1 completion:

- ShelfOps includes a buyer-facing replenishment decision queue.
- ShelfOps trains LightGBM demand models on the M5/Walmart public benchmark using time-based splits.
- ShelfOps compares models against naive, seasonal naive, moving-average, and intermittent-demand baselines.
- ShelfOps reports WAPE, MASE, bias, interval coverage, and segment metrics on M5; stockout/censored-demand metrics are reported only where stockout status exists, such as FreshRetailNet or live merchant inventory data.
- ShelfOps records buyer accept/edit/reject feedback and links recommendations to outcomes.
- ShelfOps supports CSV onboarding and a Square-first integration path.

Do not claim yet:

- ShelfOps reduced a real merchant's stockouts, unless a pilot measured it.
- ShelfOps is enterprise GA.
- ShelfOps supports every POS/ERP.
- ShelfOps has autonomous ordering.
- ShelfOps guarantees forecast accuracy.

---

## 10. Codex agent execution plan

The Codex agent should complete the roadmap in this order. Each task includes acceptance criteria.

### Phase 0 — Repo truth reset

#### Task 0.1: Create a clean state report

Files:

```text
CURRENT_STATE.md
CLAIMS.md
```

Actions:

- Summarize implemented, partial, planned, and not-claimed capabilities.
- Replace broad demo language with product-loop language.
- Move claim source of truth from `docs/demo/CLAIMS_LEDGER.md` to root `CLAIMS.md`.

Acceptance:

- `README.md` links to `CURRENT_STATE.md` and `CLAIMS.md`.
- No public doc claims real business impact without evidence.
- Synthetic/demo status is explicit.

#### Task 0.2: Archive internal/demo artifacts

Files/directories:

```text
.claude/
docs/demo/
docs/productization_artifacts/
backend/models/v1/
backend/reports/*.json
```

Actions:

- Move `.claude/` to `docs/archive/internal_agent_artifacts/` or remove from public branch.
- Keep only a minimal `docs/demo/README.md` if needed.
- Move stale model artifacts to `backend/models/archive/v1_legacy_xgboost_lstm/`.
- Add `backend/models/archive/README.md` explaining these artifacts are not active.

Acceptance:

- Active `backend/models/champion.json` does not point to archived legacy model.
- `README.md` does not reference stale demo artifacts as evidence.
- Tests still pass or failing tests are documented with reason.

#### Task 0.3: Fix API/doc mismatches

Files:

```text
backend/api/main.py
backend/api/deps.py
TECHNICAL.md
docs/product/known_limitations.md
```

Actions:

- Remove duplicate `experiments.router` registration.
- Normalize experiment route under `/api/v1/experiments`.
- Make tenant context naming consistent in docs and code.
- Verify actual RLS/session variable names.

Acceptance:

- `pytest backend/tests/test_experiments_api.py -q` passes.
- `pytest backend/tests/test_security_guardrails.py -q` passes.
- Docs match current code.

---

### Phase 1 — Focused benchmark data and model reset

#### Task 1.0: Create focused data registry and remove active Favorita dependency

Files:

```text
DATA_SOURCES.md
data_registry/datasets.yaml
data_registry/m5/README.md
data_registry/freshretailnet_50k/README.md
data_registry/square/README.md
data_registry/csv_onboarding/README.md
backend/data_sources/legacy_favorita.py or docs/archive/data_sources/favorita.md
```

Actions:

- Declare M5/Walmart as the primary public benchmark.
- Declare FreshRetailNet-50K as the stockout/censored-demand secondary benchmark.
- Declare CSV + Square as the pilot/product validation path.
- Declare Dominick's as deferred optional only.
- Move Favorita out of the active champion path; keep it only as legacy/reference if needed.
- Mark Rossmann, Instacart, Complete Journey, UCI Online Retail, and leaked/unauthorized data as out of active scope.
- For every source, document allowed and disallowed claims.

Acceptance:

- `DATA_SOURCES.md` clearly states that the active build uses M5 + FreshRetailNet + CSV/Square only.
- No active model champion metadata names Favorita.
- Root `CLAIMS.md` distinguishes benchmark evidence from pilot evidence.

#### Task 1.1: Create dataset snapshot infrastructure

Files:

```text
backend/ml/dataset_snapshots.py
backend/db/models.py
backend/alembic/versions/<new>_dataset_snapshots.py
backend/tests/test_dataset_snapshots.py
```

Actions:

- Add `dataset_snapshots` table or reuse existing model metadata table if appropriate.
- Store dataset ID, source, row count, stores, products, date min/max, hash, schema version, frequency, grain, geography, and implementation status.
- Create a utility that hashes canonical data deterministically.
- Ensure snapshot metadata supports M5, FreshRetailNet, CSV, and Square tenants.

Acceptance:

- Dataset snapshot ID is returned by training scripts.
- Snapshot metadata appears in model metadata.
- Test validates stable hash for fixed fixture.
- Snapshot record includes dataset claim boundaries or a pointer to `data_registry/datasets.yaml`.

#### Task 1.2: Implement M5/Walmart adapter and canonicalization

Files:

```text
backend/data_sources/m5.py
backend/tests/test_m5_adapter.py
backend/scripts/prepare_m5.py
DATA_SOURCES.md
```

Actions:

- Convert M5 calendar, sell prices, and sales tables into canonical ShelfOps store-product-day records.
- Preserve hierarchy fields: item, department, category, store, state, and aggregate IDs where available.
- Attach sell price and calendar event features.
- Create a deterministic dataset snapshot.
- Add a small fixture for tests; do not commit the full dataset if large or license-sensitive.

Acceptance:

- Adapter emits canonical rows with `store_id`, `product_id`, `date`, `units_sold`, `price`, category hierarchy, and calendar/event fields.
- Adapter does not create fake inventory, PO, or supplier data without `simulated` provenance labels.
- M5 snapshot can be used by benchmark script.

#### Task 1.3: Replace XGBoost benchmark script with LightGBM + baselines on M5

Files:

```text
backend/ml/baselines.py
backend/scripts/benchmark_datasets.py
backend/tests/test_baselines.py
backend/tests/test_benchmark_datasets.py
```

Actions:

- Implement naive, seasonal naive, moving average, category/store average, and intermittent-demand baselines.
- Replace XGBoost in benchmark script with current LightGBM path.
- Make M5 the default benchmark dataset.
- Output baseline comparison JSON and Markdown.

Acceptance:

- Benchmark report includes each baseline and LightGBM.
- Report includes WAPE, MASE, MAE, bias, interval metrics if available, rows, date ranges, and segment coverage.
- Stockout, PO, and supplier metrics are labeled `not_available` for M5 unless generated by an explicitly labeled simulation.
- No XGBoost dependency is required for the current benchmark path.

#### Task 1.4: Create segment metrics

Files:

```text
backend/ml/segments.py
backend/ml/evaluation.py
backend/tests/test_segments.py
backend/tests/test_model_evaluation.py
```

Actions:

- Segment SKUs into fast, medium, slow, intermittent, cold-start, promoted, and high-volume categories where possible.
- For M5, use hierarchy and demand-frequency based segments.
- For FreshRetailNet, additionally support perishable and stockout-window segments.
- Compute metrics by segment.
- Include confidence labels for low sample sizes.

Acceptance:

- Evaluation report has global and segment metrics.
- Low sample segments are labeled.
- Empty or missing segment fields do not crash evaluation.

#### Task 1.5: Add calibrated intervals

Files:

```text
backend/ml/quantile.py
backend/ml/calibration.py
backend/ml/predict.py
backend/tests/test_prediction_intervals.py
backend/tests/test_calibration.py
```

Actions:

- Implement LightGBM quantile p10/p50/p90 models or split-conformal intervals.
- Store interval method in model metadata.
- Report empirical coverage and interval width.
- Remove or downgrade heuristic interval wording.

Acceptance:

- `predict_demand()` returns intervals with `interval_method` and `calibration_status`.
- Model card reports interval coverage.
- If intervals are heuristic, UI badge must say `uncalibrated`.

#### Task 1.6: Generate new M5 champion model and model card

Files:

```text
backend/models/champion.json
backend/models/registry.json
backend/models/<new_version>/metadata.json
MODEL_CARD.md
```

Actions:

- Train current LightGBM on the M5/Walmart benchmark.
- Use enough rows and enough time coverage to be credible.
- Include dataset snapshot ID.
- Archive legacy v1.
- Promote only if baselines and gates pass.
- Label M5 limitations: no live inventory, no PO decisions, no supplier lead-time history, no merchant ROI.

Acceptance:

- No active champion has `rows_trained: 27`.
- Active metadata uses `lightgbm`, not XGBoost/LSTM weights.
- Active dataset ID is `m5_walmart` or equivalent, not Favorita.
- `MODEL_CARD.md` exists and includes limitations.

#### Task 1.7: Add FreshRetailNet stockout/censored-demand track

Files:

```text
backend/data_sources/freshretailnet.py
backend/ml/latent_demand.py
backend/ml/stockout_metrics.py
backend/scripts/benchmark_stockout_censored_demand.py
backend/tests/test_freshretailnet_adapter.py
backend/tests/test_stockout_metrics.py
MODEL_CARD_STOCKOUT_APPENDIX.md
```

Actions:

- Convert FreshRetailNet into canonical ShelfOps records with hourly/daily handling explicitly documented.
- Preserve stockout status, promotions, precipitation, perishability/category fields, and temporal fields.
- Add metrics for stockout-window bias, non-stockout-window error, under-forecast rate during stockouts, and recovered-demand comparison if implemented.
- Add a clearly labeled latent-demand recovery experiment or a conservative censored-demand adjustment.
- Keep this as a secondary evidence track, not the active M5 champion unless explicitly selected.

Acceptance:

- FreshRetailNet benchmark report separates stockout and non-stockout periods.
- Stockout-aware report says the dataset is not U.S.-based and does not prove merchant ROI.
- UI/model evidence can show stockout-aware methodology without blending it into M5 metrics.

---

### Phase 2 — Replenishment decision loop
---

### Phase 2 — Replenishment decision loop

#### Task 2.1: Create recommendation service

Files:

```text
backend/recommendations/service.py
backend/recommendations/schemas.py
backend/recommendations/outcomes.py
backend/ml/policy.py
backend/tests/test_recommendation_service.py
```

Actions:

- Generate recommendations from forecast + inventory + lead time + supplier constraints.
- Store recommendation record with model version and policy version.
- Compute no-order stockout risk and order-overstock risk.

Acceptance:

- Service generates deterministic recommendation fixture.
- Recommendation includes model version, forecast horizon, interval method, lead time, quantity, cost estimate, and risk labels.

#### Task 2.2: Add replenishment API

Files:

```text
backend/api/v1/routers/replenishment.py
backend/api/main.py
backend/tests/test_replenishment_api.py
```

Actions:

- Add queue/list/detail/action endpoints.
- Record accept/edit/reject with reason codes.
- Link accepted recommendations to purchase orders.

Acceptance:

- `GET /api/v1/replenishment/queue` returns buyer-ready cards.
- Accept/edit/reject writes decision history.
- Edited quantity requires reason code.

#### Task 2.3: Recommendation outcomes

Files:

```text
backend/recommendations/outcomes.py
backend/workers/monitoring.py
backend/api/v1/routers/replenishment.py
backend/tests/test_recommendation_outcomes.py
```

Actions:

- After horizon closes, compute actual demand, stockout event, overstock event, forecast error, and estimated value.
- Update outcome table.
- Expose impact endpoint.

Acceptance:

- Fixture can create recommendation, simulate actuals, and compute outcome.
- Impact endpoint reports measured/estimated/provisional labels.

---

### Phase 3 — Replenishment simulation

#### Task 3.1: Build replay simulator

Files:

```text
backend/ml/replenishment_simulation.py
backend/scripts/run_replenishment_simulation.py
backend/tests/test_replenishment_simulation.py
```

Actions:

- Simulate policies over M5 historical demand first; add FreshRetailNet stockout-aware replay only after the stockout track is implemented.
- Compare static reorder, moving average, seasonal naive, and ShelfOps model policy.
- Output JSON and Markdown report.

Acceptance:

- Simulation output includes stockout days, overstock units, overstock dollars, service level, PO count, and combined cost proxy.
- Report clearly labels benchmark simulation, not real merchant impact.

#### Task 3.2: Add simulation API

Files:

```text
backend/api/v1/routers/simulations.py
backend/api/main.py
backend/tests/test_simulations_api.py
```

Actions:

- Run or retrieve simulation results.
- Return policy comparison table.

Acceptance:

- API returns simulation summary for frontend.
- Results include dataset snapshot and policy versions.

---

### Phase 4 — Integration hardening

#### Task 4.1: Square mapping/onboarding hardening

Files:

```text
backend/data_sources/square.py
backend/integrations/square.py
backend/workers/sync.py
backend/api/v1/routers/integrations.py
backend/tests/test_square_onboarding.py
```

Actions:

- Create explicit Square mapping preview for locations/products.
- Require user confirmation or mapping config before production sync.
- Isolate demo ID synthesis behind `DEMO_ONLY` settings.
- Record unmapped external IDs.

Acceptance:

- Production code never silently synthesizes mappings unless demo mode is true.
- Mapping coverage is reported.
- Unmapped IDs appear in data readiness.

#### Task 4.2: Webhook event log and replay

Files:

```text
backend/db/models.py
backend/alembic/versions/<new>_webhook_event_log.py
backend/api/v1/routers/integrations.py
backend/workers/sync.py
backend/tests/test_webhook_replay.py
```

Actions:

- Persist inbound webhook payloads.
- Add status/retry/dead-letter flow.
- Add replay endpoint or script.

Acceptance:

- Webhook stored before processing.
- Failed webhook can be replayed.
- Dead-letter events appear in operations page API.

#### Task 4.3: CSV onboarding

Files:

```text
backend/data_sources/csv_onboarding.py
backend/api/v1/routers/data.py
backend/tests/test_csv_onboarding.py
```

Actions:

- Validate products, stores, transactions, inventory CSVs.
- Show mapping requirements.
- Ingest only after validation.

Acceptance:

- Bad CSV returns actionable errors.
- Good CSV creates canonical records.
- Data readiness updates after ingest.

---

### Phase 5 — Frontend productization

#### Task 5.1: Replenishment Queue UI

Files:

```text
frontend/src/pages/ReplenishmentPage.tsx
frontend/src/components/replenishment/ReplenishmentTable.tsx
frontend/src/components/replenishment/RecommendationDrawer.tsx
frontend/src/components/replenishment/DecisionModal.tsx
frontend/src/lib/types.ts
frontend/src/lib/api.ts
frontend/src/App.tsx
```

Actions:

- Add page and route.
- Show recommendation table and detail drawer.
- Implement accept/edit/reject modals.
- Add uncertainty and data-quality badges.

Acceptance:

- User can review recommendation and take action.
- Edited quantity requires reason code.
- UI shows measured/estimated/provisional labels.

#### Task 5.2: Data Readiness UI

Files:

```text
frontend/src/pages/DataReadinessPage.tsx
frontend/src/components/data/DataReadinessSummary.tsx
frontend/src/components/data/MappingCoverageTable.tsx
frontend/src/components/data/DataQualityEvents.tsx
```

Actions:

- Show trainability and recommendation eligibility.
- Show mapping coverage and source freshness.

Acceptance:

- Page explains why a tenant can or cannot train/recommend.
- Unmapped/stale/missing data is visible.

#### Task 5.3: Pilot Impact UI

Files:

```text
frontend/src/pages/PilotImpactPage.tsx
frontend/src/components/impact/ImpactScorecard.tsx
frontend/src/components/impact/PolicyComparisonTable.tsx
frontend/src/components/impact/MetricProvenanceBadge.tsx
```

Actions:

- Show forecast and business metrics.
- Support benchmark simulation and measured pilot labels.

Acceptance:

- No metric appears without provenance label.
- Simulation results are not visually presented as real pilot results.

#### Task 5.4: Model Evidence UI

Files:

```text
frontend/src/pages/MLOpsPage.tsx
frontend/src/components/mlops/ModelCardPanel.tsx
frontend/src/components/mlops/CalibrationPanel.tsx
frontend/src/components/mlops/SegmentMetricsTable.tsx
```

Actions:

- Upgrade MLOps page into evidence surface.
- Add model card, baseline comparison, calibration, and promotion gates.

Acceptance:

- Active champion evidence is visible.
- Model limitations are visible.

---

### Phase 6 — Final public packaging

#### Task 6.1: README rewrite

Files:

```text
README.md
TECHNICAL.md
```

Actions:

- Rewrite README around product loop and evidence.
- Put technical stack lower than business workflow.
- Link to model card, data sources, claims, pilot playbook.

Acceptance:

- README answers: what it is, who it serves, what decision it improves, how it proves value.
- No stale enterprise/demo overclaim.

#### Task 6.2: Add pilot playbook

Files:

```text
PILOT_PLAYBOOK.md
```

Actions:

- Define 6-8 week pilot process.
- Include data requirements, privacy constraints, success metrics, weekly cadence, and public claim rules.

Acceptance:

- A real merchant can understand what data is needed and what results will be measured.

#### Task 6.3: Add case-study template

Files:

```text
docs/templates/CASE_STUDY_TEMPLATE.md
```

Actions:

- Create template for future pilot.
- Include before/after or baseline-vs-policy comparison.

Acceptance:

- Template prevents unsupported claims.

---

## 11. Suggested development timeline

### Week 1: truth reset

- Archive old model artifacts.
- Fix README/docs/claims.
- Fix duplicate routes and tenant naming mismatch.
- Create active roadmap and current state.

### Weeks 2-3: benchmark evidence

- Build baselines.
- Train LightGBM on M5/Walmart.
- Add segment metrics and model card.
- Add calibrated intervals.
- Replace active champion.

### Weeks 4-5: decision loop

- Build recommendation service and replenishment API.
- Build replenishment queue UI.
- Tie recommendations to PO decisions and outcomes.

### Weeks 6-7: simulation and pilot readiness

- Build replay simulator.
- Add pilot impact UI.
- Harden Square/CSV onboarding.
- Add data readiness UI.

### Week 8: public release

- Final docs.
- Final screenshots/video.
- Launch write-up.
- Outreach to retailers and retail AI companies.

---

## 12. Acceptance criteria for “standout”

ShelfOps is ready to market when all are true:

1. Active champion model is LightGBM or clearly documented alternative, trained on real benchmark data, not 27 rows.
2. Model card includes data snapshot, split dates, baselines, segment metrics, interval calibration, and limitations.
3. Replenishment Queue exists and is the main workflow.
4. Buyer actions are captured and linked to outcomes.
5. Replenishment simulation compares ShelfOps policy to simple baselines.
6. Data Readiness page explains whether tenant data is trainable and recommendable.
7. Square or CSV onboarding works without demo ID synthesis.
8. Synthetic/demo artifacts are isolated.
9. Public claims are true and evidence-backed.
10. README explains business impact path before tech stack.

---

## 13. Source list

- IHL Group, “Retail Inventory Crisis Persists Despite $172 Billion in Improvements,” 2025-09-10: https://www.ihlservices.com/news/analyst-corner/2025/09/retail-inventory-crisis-persists-despite-172-billion-in-improvements/
- RELEX, “AI Moves Into Core Supply Chain Decisions as Volatility Persists,” 2026-03-25: https://www.relexsolutions.com/news/relex-report-ai-moves-into-core-supply-chain-decisions-as-volatility-persists/
- Afresh careers and product language: https://www.afresh.com/about/careers and https://job-boards.greenhouse.io/afresh
- Focal Systems product language: https://focal.systems/
- Google Cloud, “Best practices for implementing machine learning on Google Cloud”: https://docs.cloud.google.com/architecture/ml-on-gcp-best-practices
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- MLflow Model Registry docs: https://mlflow.org/docs/latest/ml/model-registry/
- Evidently AI, data drift guide: https://www.evidentlyai.com/ml-in-production/data-drift
- M5 / Walmart forecasting benchmark paper: https://www.sciencedirect.com/science/article/pii/S0169207021001874
- Kaggle M5 Forecasting Accuracy data page: https://www.kaggle.com/competitions/m5-forecasting-accuracy
- FreshRetailNet-50K paper: https://arxiv.org/abs/2505.16319
- FreshRetailNet-50K dataset page: https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K
- Dominick's Finer Foods dataset: https://www.chicagobooth.edu/research/kilts/research-data/dominicks
- Square Inventory API docs: https://developer.squareup.com/docs/inventory-api/what-it-does
- Square Orders API docs: https://developer.squareup.com/docs/orders-api/what-it-does
- Square Catalog API docs: https://developer.squareup.com/docs/catalog-api/what-it-does
- Shopify Admin GraphQL InventoryQuantity docs: https://shopify.dev/docs/api/admin-graphql/latest/objects/InventoryQuantity
- Rob J. Hyndman, “Another Look at Forecast-Accuracy Metrics for Intermittent Demand”: https://robjhyndman.com/papers/foresight.pdf
- Nixtla StatsForecast conformal prediction tutorial: https://nixtlaverse.nixtla.io/statsforecast/docs/tutorials/conformalprediction.html
- AWS, “Measuring forecast model accuracy to optimize your business objectives with Amazon Forecast”: https://aws.amazon.com/blogs/machine-learning/measuring-forecast-model-accuracy-to-optimize-your-business-objectives-with-amazon-forecast/
