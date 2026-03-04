# ShelfOps - AI-Powered Inventory Intelligence Platform

**Built by Colby Reichenbach** | Portfolio Project for Target/Lowe's Data Scientist Roles

> **Current engineering status (February 15, 2026):** pre-production hardening for SMB launch-candidate workflows. See `docs/product/production_readiness.md` and `docs/product/known_issues.md` for verified gate status and blockers.

---

## Executive Summary

### What This Project Demonstrates

**For Hiring Managers at Target/Lowe's**:

This is a production-style platform in launch-candidate hardening that demonstrates:

1. **Deep Retail Operations Knowledge** - I understand how your buyers, planners, and store teams actually work
2. **Advanced ML/AI Skills** - LSTM + XGBoost ensemble forecasting, anomaly detection, optimization
3. **Full-Stack Engineering** - FastAPI backend, React frontend, PostgreSQL + TimescaleDB, production deployment
4. **Business Acumen** - Identified $634B problem, designed solution with 139x ROI, built GTM strategy
5. **Human-in-the-Loop AI** - ML recommends, humans approve (no black box automation)

### The Problem I'm Solving

Retailers lose 5-8% of revenue to stockouts **despite having POS systems, ERPs, and inventory management software**.

**Why?**
- Current systems are **reactive** (tell you stock is out AFTER it happens)
- Reorder points are **static** (don't adapt to changing demand, seasonality, promotions)
- No **intelligence** (can't predict patterns, detect theft, optimize across stores)

**The Cost**:
- $634B/year in lost sales from stockouts
- $471B/year tied up in overstock
- $112B/year lost to shrinkage (theft, damage, errors)

### My Solution

**ShelfOps**: An AI layer that sits on top of existing retail systems and:

1. **Predicts stockouts 2-3 days early** (not after they happen)
2. **Optimizes reorder points dynamically** per SKU per store (learns from data)
3. **Detects anomalies** (theft patterns, data errors, demand spikes)
4. **Recommends actions** (reorder, transfer store-to-store, markdown)

**Key Insight**: No hardware needed. Uses existing POS/ERP data via APIs.

---

## Understanding Actual Retail Operations

### How Retailers Currently Work (The Manual Reality)

**Monday**: Store managers walk aisles, spot holes, submit restock requests  
**Tuesday**: DC allocates inventory (proportional to store size, not demand)  
**Wednesday**: Deliveries arrive, team stocks shelves (4-6 hours labor)  
**Thursday**: Planners review sell-through, adjust next week's orders  
**Friday**: Weekend prep, double-check promotional items  
**Saturday-Sunday**: Peak sales (40-50% of weekly volume), stockouts most visible

**The Pain Points**:
1. **Phantom Inventory**: System says in stock, but shelf is empty (misplaced, stolen, damaged)
2. **Promotional Chaos**: Demand spikes 3-10x during sales, hard to predict exactly
3. **Localized Demand**: Store near stadium needs different mix than suburban store
4. **Data Lag**: Decisions based on yesterday's data (nightly batch updates)
5. **Static Reorder Points**: Don't adapt to seasonality, weather, local events

### Where Humans Stay in the Loop (HITL)

**NOT Fully Automated** (for good reason):

**1. Order Approval** - Planner reviews AI recommendation before placing order
- **Why**: Budget constraints, supplier contracts, strategic decisions
- **Time**: 30 seconds per order (vs. 5 minutes manual research)
- **UI**: Dashboard shows recommendation, planner clicks "Approve" or "Edit & Approve"

**2. Exception Handling** - Alert triage, investigate anomalies
- **Why**: Context matters (theft vs. data error vs. legitimate spike)
- **Time**: 2-3 minutes per alert (vs. hours to notice problem)

**3. Promotional Planning** - AI forecasts demand, human decides strategy
- **Why**: Promotions are strategic (pricing, competitive, brand)
- **Time**: 15 minutes per promo (vs. hours manual modeling)

**4. Markdown Strategy** - AI identifies slow movers, human decides timing
- **Why**: Markdown timing is strategic (clear space, protect brand)
- **Time**: 5 minutes per category (vs. 30 minutes manual)

**5. New Item Introduction** - Cold start problem, human provides initial forecast
- **Why**: No historical data for new SKUs
- **Time**: 10 minutes to set up (vs. 30 minutes manual planning)

**6. Seasonal Transitions** - Human judgment critical for category changeovers
- **Why**: Strategic (Halloween → Christmas timing, space planning)
- **Time**: 30 minutes per category (vs. 2 hours manual)

---

## The AI/ML Implementation

ShelfOps runs **5 production models** with full MLOps pipelines. Each model has documented training, tracking, retraining, monitoring, and validation workflows.

### Model 1: Demand Forecasting — Ensemble (LSTM + XGBoost)

**Architecture**: Ensemble with 65/35 weight split (XGBoost primary, LSTM secondary)

**Why Ensemble**:
- **XGBoost**: Non-linear feature interactions (weather × category, promo × price), robust to noise
- **LSTM**: Temporal sequence patterns (weekly cycles, trends, multi-season periodicity)
- **Ensemble**: Weighted average reduces variance; XGBoost handles tabular features better, LSTM captures long-range dependencies

**Features** (Two-Phase Architecture):

| Phase | Features | When Used |
|-------|----------|----------|
| **Cold Start** | 27 features | Training on Kaggle data (no inventory/pricing) |
| **Production** | 45 features | After 90 days of real retailer data |

- Temporal (12): Day of week, month, `is_holiday` (NRF 4-5-4 calendar + 16 US holidays), fiscal_week, fiscal_period
- Sales history (15): Lag features (1d, 7d, 14d, 28d), rolling means/std (7d, 14d, 28d), trend, volatility
- Product (6): Category, subcategory, price tier, brand, shelf_life_days, is_perishable
- Store (5): Store size, type, lat/lon cluster, competition density *(production only)*
- Inventory (4): Stock levels, days-of-supply, stock-to-sales ratio *(production only)*
- Promotions (4): Active sales, discount %, duration, promo_sensitivity *(production only)*
- Weather (3): Temperature, precipitation forecast *(production only)*

Auto-upgrade: `detect_feature_tier()` in `ml/features.py` checks incoming data columns and automatically switches from cold-start to production features when real data fields are present.

**Category-Specific Models**: In addition to the global baseline, ShelfOps trains **3 category-tier models**:

| Tier | Categories | Model Name | Rationale |
|------|-----------|------------|-----------|
| Fresh | Produce, Dairy, Bakery, Meat & Seafood | `demand_forecast_fresh` | Short shelf life, high perishability, distinct demand curves |
| General Merchandise | Grocery, Frozen, Beverages, Household, Health & Beauty, Pet, Baby | `demand_forecast_gm` | Promo-driven, stable baseline demand |
| Hardware | Hardware | `demand_forecast_hardware` | Seasonal (spring/summer), project-driven, durable goods |

Category routing: `ml/predict.py:load_model_for_category()` checks the model registry for a tier-specific champion. Falls back to the global model if no tier model exists.

**Hyperparameters**:
- XGBoost: `n_estimators=500` (baseline) / `750` (tuned), `max_depth=6/8`, `learning_rate=0.05/0.03`, `subsample=0.8`, `colsample_bytree=0.8`
- LSTM: 2 layers, 64 hidden units, sequence_length=28, dropout=0.2, trained on normalized targets
- Cross-validation: 5-fold time-series split (no future leakage)

**Validation Pipeline** (Pandera gates):
1. **Raw data gate**: Non-null quantities, valid dates, positive prices
2. **Feature gate**: Expected column count, no NaN in critical features, value ranges
3. **Prediction gate**: Forecasts > 0, within 3σ of historical demand

**MLOps Workflow**:
- **Training**: `scripts/train_category_models.py` or Celery weekly retrain (Sunday 2:00 AM global, 3:00-4:00 AM per-tier)
- **Tracking**: Every run logged to MLflow (params, metrics, artifacts) + local JSON reports in `reports/{model_name}/`
- **Explainability**: SHAP feature importance generated per version, served via `/ml/models/{version}/shap`
- **Arena**: Champion/challenger with 5% MAE improvement threshold for auto-promotion
- **Backtesting**: Daily T-1 walk-forward validation, weekly 90-day lookback
- **Drift detection**: 15% MAE degradation threshold triggers retraining alert
- **Data freshness**: POS 24h / EDI 168h SLA monitoring

**Performance Targets**: MAE < 15%, MAPE < 20%

### Model 2: Reorder Point Optimization

**Algorithm**: Dynamic ROP with cluster-aware safety stock

**Formula**:
```
Reorder Point = (Forecasted Demand × Lead Time) + Safety Stock
Safety Stock = Z × √(LT × σ²_demand + D² × σ²_lead_time) × vendor_reliability × cluster_multiplier
EOQ = √(2 × D × S / H)   (Wilson formula, clamped to min_order_qty)
```

**Key innovations over static ROP**:
- Uses **ML-forecasted demand** (not historical average) — adapts to trends, seasonality, promos
- **Vendor reliability multiplier**: 90-day rolling on-time/in-full rate from PO receiving data. Late suppliers get higher safety stock (multiplier 1.0–1.5)
- **Store cluster multiplier**: K-Means clustering assigns stores to tiers (high-volume: 1.15×, mid: 1.00×, low: 0.85×). High-traffic urban stores carry more safety stock because stockout cost-per-customer is higher
- **Product lifecycle filtering**: Delisted and seasonal-out products skip reorders (planogram integration)
- **Min order qty**: Respects supplier minimum order constraints

**MLOps**: Nightly recalculation via Celery (2:30 AM). Rationale logged per SKU with all input factors for auditability.

### Model 3: Anomaly Detection (Isolation Forest)

**Algorithm**: Isolation Forest (unsupervised outlier detection)

**Features** (8 per product-store pair):
- `z_score_qty`: Sales quantity deviation from rolling mean
- `pct_change`: Day-over-day sales change
- `days_since_last_sale`: Gaps in transaction history
- `qty_vs_forecast`: Actual vs. predicted demand ratio
- `rolling_cv`: Coefficient of variation (28-day window)
- `inventory_ratio`: On-hand / reorder point
- `price_deviation`: Unit price vs. product average
- `day_of_week_deviation`: Sales vs. same-weekday average

**Hyperparameters**: `contamination=0.05` (5% expected anomaly rate), `n_estimators=200`, `random_state=42`

**MLOps Workflow**:
- **Training**: Trains fresh each run (stateless — appropriate for outlier detection where the anomaly distribution changes)
- **Tracking**: Each run logged to MLflow via `ExperimentTracker(model_name="anomaly_detector")` with params, metrics, and model artifact
- **Scoring**: Celery job runs every 6 hours, flags anomalies with severity (critical/warning/info) based on anomaly score thresholds
- **Effectiveness**: Alert outcomes tracking measures true/false positive rates over 30-day windows

**Limitation**: Stateless (no persisted model, no champion/challenger). Sufficient for outlier detection but not for learning long-term anomaly patterns. Documented as a known limitation.

### Model 4: Ghost Stock Detector (Rule-Based)

**Algorithm**: Threshold-based phantom inventory detection

**Logic**: If `forecasted_demand > 0` AND `actual_sales ≈ 0` for 7+ consecutive days, while `inventory_on_hand > 0`, flag as ghost stock (phantom inventory).

**Scoring**: Confidence = `min(1.0, consecutive_zero_days / 14)` — higher confidence for longer zero-sale streaks.

**Business Value**: In a single demo run, detected **$98,682 in ghost stock** across 15 stores — inventory that the system shows as available but likely isn't on the shelf (misplaced, damaged, stolen, or data error).

**MLOps**: Daily Celery job (4:30 AM). Generates cycle count recommendations with estimated revenue at risk. No ML training required — pure domain logic.

### Model 5: Store Clustering (K-Means)

**Algorithm**: K-Means clustering for store segmentation

**Features** (3 per store):
- `avg_daily_volume`: Mean daily sales quantity across all products
- `sales_volatility`: Coefficient of variation (std/mean) — demand stability
- `promo_sensitivity`: Ratio of promo-day sales to regular-day sales

**Clusters** (3 tiers, ordered by volume):

| Tier | Label | Safety Stock Multiplier | Characteristics |
|------|-------|------------------------|-----------------|
| 0 | High-volume | 1.15× | Urban flagships, high traffic, stable demand |
| 1 | Mid-volume | 1.00× (baseline) | Suburban stores, moderate traffic |
| 2 | Low-volume | 0.85× | Rural/smaller stores, lower traffic, higher volatility |

**Integration**: Cluster tier stored in `stores.cluster_tier` column. Used by `inventory/optimizer.py` to modulate safety stock — high-volume stores carry more buffer because stockout affects more customers.

**MLOps**: Run once via `scripts/assign_store_clusters.py`. Re-run periodically as store mix changes. Uses StandardScaler for feature normalization before clustering.

---

## Business Model & ROI

### Pricing (Value-Based SaaS)

| Tier | Stores | Price/Store/Month | Annual Example |
|------|--------|-------------------|----------------|
| Growth | 50-149 | $75 | $45K-134K |
| Professional | 150-299 | $60 | $108K-215K |
| Enterprise | 300+ | $50 | $180K+ |

### ROI Example (Why Target/Lowe's Would Buy This)

**100-store chain**:
- Revenue: $5M/store = $500M total
- Stockout rate: 5% = $25M lost sales
- **ShelfOps reduces by 50%** = $12.5M recovered
- **Cost**: $90K/year (100 × $75 × 12)
- **ROI**: 139x

Even if only 20% reduction, customer saves $5M and pays $90K.

### Unit Economics (SaaS Dream Metrics)

**Per Customer** (100 stores):
- MRR: $7,500
- COGS: $570 (infrastructure + support)
- **Gross Margin: 92%**

**Lifetime Value**:
- LTV: $230K (at 3% monthly churn)
- CAC: $10K (sales + marketing)
- **LTV:CAC = 23:1** (target >3:1)
- **Payback: 1.5 months** (target <12)

---

## Technical Architecture

### Tech Stack (Production-Ready)

**Backend**:
- **FastAPI** (Python 3.11) - Modern async framework
- **PostgreSQL 15 + TimescaleDB** - Time-series optimization
- **Redis 7.x** - Caching + real-time pub/sub
- **Celery** - Background jobs (forecasting, sync)
- **Vertex AI** - ML model training/hosting (Google Cloud)

**ML / MLOps**:
- **XGBoost + TensorFlow/LSTM** - Ensemble forecasting (65/35 weights)
- **MLflow** - Experiment tracking, model registry, artifact store
- **SHAP** - Model explainability (global + local explanations)
- **Pandera** - DataFrame validation at pipeline gates
- **Plotly + Seaborn** - Standardized analytics visualization

**Frontend**:
- **React 18 + TypeScript** - Web dashboard
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Data visualization

**Infrastructure**:
- **Docker Compose** - Multi-container orchestration (API, ML Worker, MLflow, Redis, TimescaleDB, Redpanda)
- **Google Cloud Platform** - Production deployment target
- **Cloud Run** - Serverless compute (auto-scales)
- **GitHub Actions** - CI/CD pipeline

**Container Architecture** (API ≠ ML):

| Container | Image Size | Runs |
|-----------|-----------|------|
| `api` | ~200MB | FastAPI, routes, alerts, WebSockets |
| `ml-worker` | ~1.5GB | Celery training, prediction, SHAP |
| `mlflow` | ~300MB | Experiment tracking UI + artifacts |

> **Decision**: We split API and ML into separate containers so the API stays lean
> (~200MB) and can scale independently. ML deps (TensorFlow, XGBoost, SHAP)
> add ~1.3GB that the API never needs.

**Cost at Scale**:
- 25 customers (2,500 stores): $500-1K/month infrastructure
- **92% gross margin** (pure software)

### Database Schema (15 Production Tables)

**Core Tables**:
- `customers` - Multi-tenant (customer accounts)
- `stores` - Store locations, metadata
- `products` - SKU master (50K+ per customer)
- `suppliers` - Vendor management
- `transactions` - POS sales (time-series, 1M+ rows/day)
- `inventory_levels` - Stock snapshots (time-series)
- `demand_forecasts` - ML predictions
- `forecast_accuracy` - Model monitoring
- `reorder_points` - Dynamic optimization
- `alerts` - Actionable notifications
- `actions` - Human responses (HITL)
- `purchase_orders` - Order management
- `promotions` - Sale/ad planning
- `integrations` - Connected systems
- `anomalies` - Detected irregularities

**Design Patterns**:
- TimescaleDB hypertables for time-series data
- Materialized views for analytics (hourly refresh)
- JSONB for flexible metadata
- Proper indexes (performance at scale)
- Multi-tenant with row-level security

---

## Complete Project Files

### What's Included

1. **PRODUCT_BLUEPRINT.md** (25,000+ words)
   - Complete market analysis, technical architecture, ML specs, API design, roadmap

2. **docs/DATA_STRATEGY.md** — Data architecture
   - Two-layer data strategy (Kaggle training + synthetic testing)
   - Cold start problem solution (two-phase feature tiers)
   - Feature gap analysis (27 cold-start vs 46 production features)

3. **docs/MLOPS_STANDARDS.md** — Engineering standards
   - MLflow experiment tracking protocol
   - SHAP explainability requirements
   - Model registry + champion/challenger deployment
   - Pandera data validation gates
   - Plotly chart design system + analytics standards
   - Container separation rationale (API vs ML worker)

4. **docs/RETAIL_DATA_ANALYSIS.md** — Kaggle feature audit
   - Feature availability per dataset (Favorita, Walmart, Rossmann)

5. **backend/ml/** — ML pipeline
   - `features.py` — Two-phase feature engineering (auto-detects tier)
   - `train.py` — XGBoost + LSTM with MLflow tracking, SHAP, validation
   - `predict.py` — Inference with tier-aware feature selection
   - `experiment.py` — MLflow wrapper + model registry
   - `explain.py` — SHAP explainability pipeline
   - `validate.py` — Pandera validation schemas
   - `charts.py` — Plotly chart design system

6. **backend/integrations/** — Enterprise data adapters
   - EDI X12, SFTP, Kafka/Redpanda, Square POS

7. **This README** (You Are Here)
   - Executive summary, retail ops, AI/ML, business model, architecture

---

## Development Roadmap (MVP in 8 Weeks)

### Week 1-2: Foundation ~90% Complete
- [x] PostgreSQL schema (15 tables with SQLAlchemy models)
- [x] Square POS integration (REST adapter with webhook handler)
- [x] Enterprise integrations (EDI X12, SFTP, Kafka, Square)
- [x] Synthetic data generator (500 products × 15 stores × 730 days)
- [x] Kaggle data downloader + preprocessor (Favorita, Walmart, Rossmann)
- [ ] Apply Alembic migrations + create TimescaleDB hypertables
- **Deliverable**: Data pipeline infrastructure complete

### Week 3-4: Analytics Engine ~85% Complete
- [x] Feature engineering (two-phase: 27 cold-start / 46 production)
- [x] XGBoost + LSTM ensemble model (65/35 weights, time-series CV)
- [x] Alert system (stockout + reorder detection, Redis pub/sub, email)
- [x] MLOps standards (MLflow tracking, SHAP explainability, Pandera validation)
- [x] Model registry + champion/challenger deployment pattern
- [x] Standardized analytics visualization (Plotly chart design system)
- [ ] End-to-end training run on Kaggle data
- [ ] Celery worker implementation (weekly retrain, data sync)
- **Deliverable**: ML pipeline with full instrumentation

### Week 5-6: Dashboard ~15% Complete
- [x] React + Vite + TypeScript scaffold
- [x] Basic Dashboard page (KPI cards, forecast chart)
- [x] Basic Alerts page (alert cards)
- [ ] Full inventory overview table
- [ ] Interactive forecast charts with confidence intervals
- [ ] Real-time WebSocket-connected alert feed
- [ ] User authentication
- **Deliverable**: Usable interface

### Week 7-8: Pilot Launch Not Started
- [ ] Deploy to GCP (Cloud Run + Cloud SQL)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Onboard first test dataset
- [ ] Document performance results
- **Deliverable**: Deployed and measurable

---

## Why Computer Vision Was Considered (Then Rejected)

### The Original Idea

Mount cameras on shelves to detect out-of-stocks visually in real-time.

**Pros**:
- Real-time detection (no POS lag)
- Catches "phantom inventory"
- Planogram compliance

**Why I Didn't Build It (Yet)**:

1. **Training Data Cost**: $50K-200K for labeled shelf images
2. **Hardware Deployment**: $20K-50K per store (cameras, installation)
3. **Edge Computing**: Need on-site processing, adds complexity
4. **Accuracy Challenge**: 99%+ required (false positives = alert fatigue)
5. **Privacy Concerns**: Customers uncomfortable, regulatory complexity
6. **ROI Timeline**: Hardware payback 12-18 months vs. software 2-4 months

### The Pragmatic Decision

**Phase 1** (Current): SaaS data intelligence (no hardware)
- Predict stockouts 2-3 days early (good enough)
- Fast deployment (2-4 weeks)
- Low cost ($50-75/store/month)

**Phase 2** (Future): Add CV as premium feature
- Once revenue-generating
- Partner with camera vendor
- Offer as add-on (+$25/store/month)

**Note in Product Specs**: "Computer vision considered but deferred due to training data costs and deployment complexity. SaaS-first approach provides 80% of value with 20% of complexity."

---

## Perfect for Target/Lowe's Case Study

### How I'd Present This in an Interview

**Scenario**: "I built ShelfOps as a portfolio project to show I understand retail operations AND can build AI solutions."

**Case Study Framework**:
1. **Problem**: Retailers lose $634B/year to stockouts despite having systems
2. **Root Cause**: Current systems reactive (not predictive), reorder points static
3. **Solution**: AI layer on existing data, forecasts demand, optimizes dynamically
4. **Results**: (Projected) 25-50% stockout reduction, 139x ROI
5. **Technical Depth**: LSTM + XGBoost ensemble, TimescaleDB, production-style architecture
6. **Business Acumen**: $1.5M ARR in 24 months, 92% margin, clear GTM

**Target Interview Questions**:
- **"Tell me about a project you built"** → This (ShelfOps)
- **"How would you reduce stockouts at Target?"** → Walk through the solution
- **"How do you prioritize features?"** → Show MVP → Pilot → Scale roadmap
- **"Describe a time you used ML"** → Demand forecasting ensemble
- **"How do you communicate with stakeholders?"** → Show HITL workflows

**Why This Impresses**:
- Solves Target's actual problem (inventory optimization)
- Shows technical depth (full-stack + ML + retail domain)
- Shows business thinking (ROI, pricing, GTM strategy)
- Shows I can ship (8-week MVP plan, launch-candidate hardening)
- Shows understanding of retail operations (HITL workflows, buyer personas)

---

## Success Metrics & Monitoring

### Product Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Forecast MAE | Mean absolute error | <15% |
| Forecast MAPE | Mean absolute percentage error | <20% |
| Alert Precision | % of alerts that were true positives | >80% |
| Alert Recall | % of stockouts we predicted | >90% |
| API Uptime | % of time APIs available | >99.5% |

### Business Metrics

| Metric | Month 6 | Month 12 | Month 24 |
|--------|---------|----------|----------|
| MRR | $5.6K | $30K | $187K |
| ARR | $67K | $360K | $2.25M |
| Customers | 1 | 4 | 25 |
| Gross Margin | 90% | 92% | 92% |

### Customer Success

| Metric | Target |
|--------|--------|
| Stockout Reduction | 25%+ |
| Overstock Reduction | 15%+ |
| Labor Savings | $31K/store/year |
| ROI (Year 1) | >50x |
| NPS | >50 |

---

## Competitive Advantages

### vs. Manual Spreadsheets (80% of market)
- Automated (no manual work)
- Predictive (not reactive)
- Learns from data

### vs. Generic BI Tools (Tableau, Looker)
- Purpose-built for inventory
- Prescriptive (tells you what to do)
- Automated alerts

### vs. Enterprise (Blue Yonder, o9 Solutions)
- 100x cheaper ($50K vs. $500K)
- 10x faster (1 month vs. 12 months)
- SMB-friendly

### vs. Point Solutions (Inventory Planner)
- ML-powered (not static formulas)
- Multi-source data (POS + ERP + WMS)
- Anomaly detection (unique)

---

## Project Status

**✅ Phase 5 - ML Enhancements & Command Center (COMPLETE)**:
- [x] Category model segmentation (fresh/general_merchandise/hardware tier-specific models)
- [x] Store clustering (K-Means, 3 tiers, cluster-aware safety stock multipliers)
- [x] MLOps for all models (anomaly detection MLflow tracking, multi-model retraining)
- [x] Data integration metadata (sync log table, 4-source SLA monitoring)
- [x] ML Ops API (6 endpoints: models, SHAP, backtests, experiments, registry, health)
- [x] ML Command Center frontend (4-tab dashboard: Models, Experiments, Backtests, Data Health)
- [x] Category model Celery retraining schedule (fresh/gm/hardware on Sundays)
- [x] Migration 006 (cluster_tier, category_tier, integration_sync_log with RLS)

**✅ Phase 4 - MLOps Infrastructure (COMPLETE)**:
- [x] Champion/Challenger Arena with auto-promotion (5% improvement threshold)
- [x] Continuous Backtesting (daily T-1 + weekly 90-day validation)
- [x] ML Alerts API for in-app notifications (drift, experiments, promotions)
- [x] Experiments API for hypothesis-driven testing (department segmentation, new features)
- [x] 6 MLOps tables (model_versions, backtest_results, shadow_predictions, retraining_log, ml_alerts, experiments)
- [x] Event-driven retraining (drift, new_data, manual triggers)

**✅ Phase 1 - Quick Wins: Anomaly Detection (COMPLETE)**:
- [x] ML Anomaly Detection — Isolation Forest with 8 features
- [x] Ghost Stock Detector — Phantom inventory detection (**$98,682 detected in single run**)
- [x] Alert Outcomes Tracking — Precision measurement, false positive rate, ROI calculation
- [x] Anomalies API (9 endpoints: detection, stats, ghost stock, outcomes)
- [x] 2 Celery jobs (6-hourly ML detection, daily ghost stock)

**✅ Foundation (COMPLETE)**:
- [x] Database schema (27+ tables, TimescaleDB hypertables, Row-Level Security)
- [x] API (13 routers: stores, products, forecasts, alerts, integrations, inventory, purchase_orders, models, ml_alerts, experiments, anomalies, outcomes, ml_ops)
- [x] ML pipeline (LSTM + XGBoost ensemble, 45 production features, cold-start tier, category-specific models)
- [x] Enterprise integrations (EDI X12, SFTP, Kafka, Square POS)
- [x] React frontend (9 pages, WebSocket alerts, ML Ops dashboard, skeleton loading, error boundaries)
- [x] Celery workers (17 scheduled jobs across 4 queues)
- [x] Docker Compose (PostgreSQL + TimescaleDB, Redis, API server)
- [x] Decision engine (dynamic ROP optimizer, PO workflows, supply chain logic)
- [x] Retail domain logic (4-5-4 calendar, shrinkage, planograms, vendor scorecards, store clustering)

**📈 Key Metrics**:
- **5 operational modeling components** (demand forecast, anomaly detection, ghost stock, ROP optimizer, store clustering)
- **3 category-specific forecast models** (fresh, general merchandise, hardware)
- **$98K ghost stock flagged** for cycle count verification
- **27+ database tables** across 6 migrations
- **17 Celery scheduled jobs** (sync, ml, monitoring queues)
- **13 API routers** with 65+ endpoints
- **9 frontend pages** (Dashboard, Alerts, Forecasts, Products, Inventory, Stores, Integrations, ML Ops, Product Detail)

**See**: [docs/product/roadmap.md](docs/product/roadmap.md) for the current implementation plan

### Architecture Decision Log

| Decision | Choice | Why |
|----------|--------|-----|
| Feature architecture | Two-phase (cold-start / production) | Kaggle has 27 of 46 features; auto-upgrades when real data available |
| Experiment tracking | MLflow (self-hosted) | Open-source, no vendor lock-in, shows MLOps competence |
| Data validation | Pandera | Lightweight, Pythonic, inline with pandas workflows |
| Model explainability | SHAP | Industry standard for tree models; enables feature importance narratives |
| Primary viz library | Plotly | Interactive HTML charts, embeddable in React via Plotly.js |
| Container split | API (~200MB) + ML Worker (~1.5GB) | API scales independently; ML deps don't bloat API image |
| Model metadata | JSON (not .joblib) | Human-readable; can be inspected without Python |

---

## Known Limitations

### Data Limitations
- **Synthetic training data**: v1 trained on Kaggle Favorita dataset (Ecuadorian grocery chain). Real US retailer data would have different demand patterns, seasonality, and product mix. Model would need retraining on actual retailer data before production use.
- **Single data source for training**: All demo data from seed script or Kaggle. In production, 4 adapters (EDI, SFTP, Kafka, REST) would ingest from separate enterprise systems. Integration sync metadata is simulated for architecture demonstration.
- **No real-time POS feed**: Square POS adapter implemented and tested but not connected to live account. Sync jobs run but return empty results without an active integration.
- **730 days of history**: Sufficient for seasonal pattern detection but not for multi-year trend analysis or rare event modeling (pandemics, supply chain disruptions).

### Model Limitations
- **Cold-start tier only**: v1 uses 27 features (Kaggle-compatible). Production tier (45 features) activates after 90 days of real retailer data, which is not available in a demo environment.
- **LSTM metrics require investigation**: v1 LSTM shows near-zero error on normalized data, likely due to normalization approach in sequence construction. XGBoost carries the majority of ensemble predictive power. Documented for transparency — this is an active investigation area.
- **Reorder quantity is unit-level, not casepack-aware**: Buy recommendations currently use EOQ/min order quantity logic but do not model vendor casepack or pallet constraints. Suggested quantities may be operationally invalid for suppliers that require pack-based ordering.
- **Perishable shrink risk not yet encoded in ordering policy**: The reorder flow uses stock/reorder/safety thresholds but does not yet cap order quantity by expected sell-through window (e.g., shelf life, recent daily velocity, spoilage cost). Human approval is required to prevent over-ordering on low-velocity perishables.
- **No computer vision**: Shelf compliance, planogram verification, and shrinkage detection via cameras deferred — requires GPU infrastructure and labeled image datasets not available for this project.
- **Anomaly detection is stateless**: Isolation Forest trains fresh each run (no persisted model, no champion/challenger). Sufficient for outlier detection but not for learning long-term anomaly patterns.
- **Ghost stock is rule-based**: Uses forecast-vs-actual ratio threshold, not ML. Effective for obvious cases (7+ consecutive zero-sale days with positive inventory) but misses subtle phantom inventory patterns.
- **Store clustering is static**: K-Means run once and stored. In production, would need periodic re-clustering as store performance changes (new stores, market shifts, renovations).

### Infrastructure Limitations
- **No cloud deployment**: Runs locally with Docker Compose (db + redis). Target deployment would be GCP Cloud Run + Cloud SQL + Memorystore.
- **No authentication**: RLS multi-tenancy exists but no JWT/OAuth login flow. All API requests use dev customer_id. Auth0 integration scaffolded in frontend but not connected.
- **MLflow local only**: Experiment tracking on localhost:5000. Production would use managed MLflow (Databricks, AWS SageMaker, or self-hosted on GKE).
- **No CI/CD for models**: Model training is manual or Celery-scheduled. Production would use Vertex AI Pipelines or Kubeflow for orchestrated training DAGs with data lineage.

---

## Future Additions (Production Roadmap)

### Additional ML Models
- **Promotion Lift Predictor**: XGBoost regressor trained on `promotion_results` table. Predicts actual_lift from discount_pct, duration, category, seasonality. Would replace manual expected_lift in promotion planning.
- **Lead Time Forecaster**: Gradient boosting on PO receiving data. Predicts actual_lead_time_days from supplier, season, order_qty, distance. Would replace static `supplier.lead_time_days` in safety stock calculation.
- **Shrinkage Predictor**: Classification model predicting shrinkage risk by product × store. Currently uses NRF benchmark rates (static per-category).
- **Demand Sensing (Real-Time)**: Sub-daily demand updates using POS streaming data via Kafka. Currently batch-only (daily forecasts).

### Authentication & Authorization
- **Store Manager Dashboard**: Filtered view of single store's metrics, alerts, inventory. Currently all stores visible to all users.
- **Corporate Dashboard**: Cross-store analytics, model health, vendor scorecards.
- **Role-based access**: JWT auth with roles (store_manager, district_manager, corporate_analyst, ml_engineer).

### Infrastructure
- **GCP Cloud Run deployment**: Containerized API + ML worker with auto-scaling.
- **Vertex AI Pipelines**: Orchestrated training DAGs replacing Celery beat for model training.
- **Feature Store**: Centralized feature computation and serving (Feast or Vertex AI Feature Store). Currently features re-engineered on every training run.
- **Model Monitoring SLAs**: Automated alerts when model performance drops below business thresholds (stockout rate > 5%, MAPE > 25%).

### Data Integration
- **Real EDI/AS2 connection**: Connect to retailer VAN (Value Added Network) for production EDI 846/856/810 document exchange.
- **Warehouse Management System**: WMS integration for real-time inventory movements, receiving, and put-away confirmation.
- **Weather API**: Real-time weather data for demand-weather correlation (currently uses static temperature/precipitation from Kaggle dataset).

---

## Contact

**Colby Reichenbach**
Data Scientist | Machine Learning Engineer
Portfolio Project for Target/Lowe's Applications

**This project demonstrates**:
- Retail operations expertise
- Advanced ML/AI skills
- Full-stack engineering
- Business acumen
- Human-in-the-loop AI
