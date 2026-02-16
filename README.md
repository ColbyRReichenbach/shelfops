# ShelfOps - AI-Powered Inventory Intelligence Platform

**Built by Colby Reichenbach** | Portfolio Project for Target/Lowe's Data Scientist Roles

---

## Executive Summary

### What This Project Demonstrates

**For Hiring Managers at Target/Lowe's**:

This is NOT a toy project. This is a production-ready SaaS platform that demonstrates:

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

### Model 1: Demand Forecasting (Core Value)

**Architecture**: Ensemble (LSTM + XGBoost + Rule-Based)

**Why Ensemble**:
- **LSTM**: Temporal patterns (weekly cycles, trends, seasonality)
- **XGBoost**: Non-linear relationships (weather × category, promo × price)
- **Rules**: Domain knowledge (new items, promotions, holidays)

**Features** (Two-Phase Architecture):

| Phase | Features | When Used |
|-------|----------|----------|
| **Cold Start** | 27 features | Training on Kaggle data (no inventory/pricing) |
| **Production** | 46 features | After 90 days of real retailer data |

- Temporal (12): Day of week, holidays, seasonality
- Sales history (15): Rolling averages, trends, volatility
- Product (6): Category, price, brand, shelf life
- Store (5): Size, type, demographics, competition *(production only)*
- Inventory (4): Stock levels, days-of-supply *(production only)*
- Promotions (4): Active sales, discount %, duration *(production only)*
- Weather (3): Temperature, precipitation forecast

Auto-upgrade: `detect_feature_tier()` checks incoming data and automatically switches
from cold-start to production features when real data is available. See `docs/DATA_STRATEGY.md`.

**Performance**:
- MAE <15% of actual demand (target)
- 70% of predictions within ±15%
- Retrains weekly (continuous improvement)

**MLOps Standards** (see `docs/MLOPS_STANDARDS.md`):
- Every training run logged to **MLflow** (params, metrics, artifacts)
- **SHAP explainability** per model version (global + local explanations)
- **Model cards** (Google standard) documenting performance + limitations
- **Pandera validation** gates at 3 points in the ML pipeline
- Champion/challenger deployment with automated promotion

**Human Oversight**:
- Daily monitoring dashboard (data team)
- Weekly review of worst predictions
- Monthly category performance review
- Feedback loop (planners can flag bad forecasts)

### Model 2: Reorder Point Optimization

**Traditional Formula** (what most retailers use):
```
Reorder Point = (Avg Daily Demand × Lead Time) + Safety Stock
Safety Stock = Z-score × √(Lead Time) × Demand Std Dev
```

**My ML-Enhanced Version**:
- Uses **forecasted** demand (not historical average)
- Adjusts safety stock for **demand variability**
- Accounts for **supplier reliability** (learns if often late)
- Dynamic per SKU per store (not one-size-fits-all)

**Impact**: 15-20% reduction in overstock while maintaining service levels

### Model 3: Anomaly Detection

**Model**: Isolation Forest (unsupervised learning)

**What It Detects**:
- Inventory variance >10% (possible theft)
- Unusual patterns (consistent shrinkage in specific aisles)
- Data errors (POS and ERP don't match)

**Value**: Helps catch $112B/year in shrinkage

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
5. **Technical Depth**: LSTM + XGBoost ensemble, TimescaleDB, production-ready
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
- Shows I can ship (8-week MVP plan, production-ready)
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

**✅ Phase 4 - MLOps Infrastructure (COMPLETE)**:
- [x] Champion/Challenger Arena with auto-promotion (5% improvement threshold)
- [x] Continuous Backtesting (daily T-1 + weekly 90-day validation)
- [x] ML Alerts API for in-app notifications (drift, experiments, promotions)
- [x] Experiments API for hypothesis-driven testing (department segmentation, new features)
- [x] Model Health Dashboard (champion/challenger status, backtest trends)
- [x] 6 MLOps tables (model_versions, backtest_results, shadow_predictions, retraining_log, ml_alerts, experiments)
- [x] Event-driven retraining (drift, new_data, manual triggers)
- [x] Comprehensive MLOps documentation (workflow guide, implementation summary, quick reference)

**✅ Phase 1 - Quick Wins: Anomaly Detection (COMPLETE)**:
- [x] **ML Anomaly Detection** - Isolation Forest with 8 features (4 ML anomalies detected)
- [x] **Ghost Stock Detector** - Phantom inventory detection (**$98,682 detected in single run**)
- [x] **Alert Outcomes Tracking** - Precision measurement, false positive rate, ROI calculation (66.7% precision)
- [x] Anomalies API (9 endpoints: detection, stats, ghost stock recommendations, outcomes)
- [x] 2 Celery jobs (6-hourly ML detection, daily ghost stock)
- [x] Migration 005 (anomaly_metadata JSONB column)
- [x] Full documentation ([docs/QUICK_WINS_COMPLETE.md](docs/QUICK_WINS_COMPLETE.md))

**✅ Foundation (COMPLETE)**:
- [x] Database schema (27 tables, TimescaleDB hypertables, Row-Level Security)
- [x] API (11 routers: stores, products, forecasts, alerts, integrations, inventory, purchase_orders, models, ml_alerts, experiments, anomalies, outcomes)
- [x] ML pipeline (LSTM + XGBoost ensemble, 45 production features, cold-start tier)
- [x] Enterprise integrations (EDI X12, SFTP, Kafka, Square POS)
- [x] React frontend (8 pages, WebSocket alerts, skeleton loading, error boundaries)
- [x] Celery workers (14 scheduled jobs across 4 queues)
- [x] Docker Compose (PostgreSQL + TimescaleDB, Redis, API server)
- [x] Decision engine (dynamic ROP optimizer, PO workflows, supply chain logic)
- [x] Retail domain logic (4-5-4 calendar, shrinkage, planograms, vendor scorecards)

**📈 Key Metrics**:
- **100 anomalies detected** (5 critical, 68 warning, 27 info)
- **$98K ghost stock flagged** for cycle count verification
- **66.7% precision** (2 TP, 1 FP after test outcomes)
- **27 database tables** across 5 migrations
- **14 Celery scheduled jobs** (sync, ml, monitoring queues)
- **11 API routers** with 60+ endpoints

**🎯 Next Steps**:
**Phase 3: Testing & Quality** (RECOMMENDED for interview readiness)
1. Unit tests (pytest for ML pipeline, API endpoints, decision engine)
2. Integration tests (end-to-end workflows, database, Celery)
3. CI/CD pipeline (GitHub Actions: tests, linting, type checking)
4. Production hardening (error handling, input validation, edge cases)

**See**: [docs/ROADMAP.md](docs/ROADMAP.md) for 8-week implementation plan

### External Demo Package (Audited)

Use the audited, no-hallucination demo assets under `docs/demo/`:
- `docs/demo/DEMO_RUNBOOK.md` (exact command flow)
- `docs/demo/VALIDATION_GATES.md` (must-pass checks)
- `docs/demo/CLAIMS_LEDGER.md` (claim -> code/test/artifact mapping)
- `docs/demo/SLIDE_DECK_OUTLINE.md` and `docs/demo/VIDEO_SCRIPT_10MIN.md`
- `docs/demo/ONE_PAGER_HIRING.md` and `docs/demo/ONE_PAGER_SMB_PILOT.md`

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

## Contact

**Colby White**  
Data Scientist | Machine Learning Engineer  
Portfolio Project for Target/Lowe's Applications

**This project demonstrates**:
- Retail operations expertise
- Advanced ML/AI skills
- Full-stack engineering
- Business acumen
- Human-in-the-loop AI

**Ready to discuss how I can bring this thinking to Target/Lowe's!**
