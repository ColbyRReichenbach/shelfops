# ShelfOps - Project Context for Claude Code

**Project**: AI-Powered Inventory Intelligence Platform
**Purpose**: Portfolio project demonstrating retail ops + ML expertise for Target/Lowe's roles
**Status**: ~95% feature-complete — decision engine, supply chain, retail domain logic, ML pipeline, frontend all functional. Next: testing, CI/CD, deployment.

---

## Quick Reference

**What This Is**: SaaS platform that predicts stockouts 2-3 days early using existing POS/ERP data, then **acts on predictions** with dynamic reorder optimization, PO workflows, and vendor-adjusted safety stock.

**NOT Computer Vision**: Uses API data, no cameras (deferred due to training costs)

**Core Value**: Retailers lose $634B/year to stockouts despite having systems. We predict BEFORE they happen AND automate the response.

---

## Tech Stack

- **Backend**: FastAPI, PostgreSQL + TimescaleDB, Redis, Celery
- **ML**: LSTM + XGBoost ensemble (65/35 weights), two-phase feature architecture
- **MLOps**: MLflow (experiment tracking), SHAP (explainability), Pandera (validation), Plotly (viz)
- **Frontend**: React + TypeScript, Tailwind CSS
- **Infrastructure**: Docker Compose (API + ML Worker + MLflow), GCP target
- **Integrations**: EDI X12, SFTP, Kafka/Redpanda, Square POS

---

## Enterprise Integration Architecture

ShelfOps connects to retailer data through a **pluggable adapter pattern**:

| Protocol | Use Case | Retailers | Adapter |
|----------|----------|-----------|---------|
| EDI X12 | Document exchange (846/856/810/850) | Target, Walmart | `edi_adapter.py` |
| SFTP | Batch file ingestion (CSV, fixed-width) | Regional chains | `sftp_adapter.py` |
| Kafka/Pub/Sub | Real-time event streaming | Lowe's, digital-first | `event_adapter.py` |
| REST API | POS webhooks & polling | Square, Shopify | `square.py` |

**Key standards**: EDI X12, GS1/GTIN-14, UPC-12, AS2

All adapters implement `RetailIntegrationAdapter` (see `integrations/base.py`).

---

## Database (27 Tables)

**Original 16**: customers, stores, products, suppliers, transactions, inventory_levels, demand_forecasts, forecast_accuracy, reorder_points, alerts, actions, purchase_orders, promotions, integrations, anomalies, edi_transaction_log

**Commercial Readiness 11**: distribution_centers, product_sourcing_rules, dc_inventory, store_transfers, shrinkage_rates, planograms, promotion_results, receiving_discrepancies, reorder_history, po_decisions, opportunity_cost_log

**Extended tables**: suppliers (reliability tracking), purchase_orders (sourcing + receiving), products (lifecycle + holding cost)

**Migrations**: `001_initial_schema.py`, `002_commercial_readiness.py`

---

## Decision Engine & Supply Chain

**Inventory Optimizer** (`inventory/optimizer.py`):
- Dynamic ROP = (Avg Demand × Lead Time) + Safety Stock
- Safety stock: Z × √(LT×σd² + D²×σLT²) × vendor reliability multiplier
- EOQ (Wilson formula) with min_order_qty constraints
- Nightly recalculation via Celery (`workers/inventory_optimizer.py`)

**Supply Chain** (`supply_chain/`):
- `sourcing.py`: Priority-based DC vs vendor selection, DC stock availability check
- `transfers.py`: Cross-store emergency rebalancing (haversine distance)
- `receiving.py`: PO receiving with discrepancy tracking

**PO Workflow** (`api/v1/routers/purchase_orders.py`):
- Approve (with optional qty modification), reject (with reason code), receive
- Reason codes fed back to ML via `ml/feedback_loop.py`

---

## Retail Domain Logic

**Calendar** (`retail/calendar.py`): NRF 4-5-4 fiscal calendar + 16 US holidays (fixed + floating)
**Shrinkage** (`retail/shrinkage.py`): Category-based NRF benchmarks (Bakery 8%, Produce 4.8%, etc.)
**Planograms** (`retail/planogram.py`): Product lifecycle filtering (delisted/seasonal_out skip reorders)
**Vendor Scorecards** (`workers/vendor_metrics.py`): 90-day rolling reliability → safety stock multiplier
**Promo Tracking** (`retail/promo_tracking.py`): Actual vs expected lift measurement

---

## ML Models

**1. Demand Forecasting**: LSTM + XGBoost ensemble
- Cold start: 27 features (Kaggle data) → Production: 45 features (real data)
- Auto-upgrades via `detect_feature_tier()` after 90 days of real data
- `is_holiday` feature uses `RetailCalendar.is_holiday()` (NRF 4-5-4 + floating holidays)
- MAE <15%, MAPE <20% targets

**2. Reorder Optimization**: Dynamic ROP with vendor-adjusted safety stock (`inventory/optimizer.py`)
**3. Anomaly Detection**: Isolation Forest (shrinkage, data errors)

**MLOps Standards** (see `docs/MLOPS_STANDARDS.md`):
- MLflow: Every training run tracked (params, metrics, artifacts)
- SHAP: Global + local explanations generated per model version
- Pandera: Validation at 3 pipeline gates (raw data → features → prediction)
- Model Registry: `models/registry.json` + champion/challenger pattern
- Charts: Plotly design system for consistent analytics viz
- Drift detection: 15% MAE degradation threshold (`workers/monitoring.py`)
- Data freshness: POS 24h / EDI 168h SLAs
- Opportunity cost: Stockout + overstock quantification (`business/counterfactual.py`)

---

## API Routers (7)

| Router | Prefix | Key Endpoints |
|--------|--------|--------------|
| stores | `/api/v1/stores` | List, get by ID |
| products | `/api/v1/products` | List, get, detail |
| forecasts | `/api/v1/forecasts` | List, accuracy |
| alerts | `/api/v1/alerts` | List, summary, acknowledge, resolve |
| integrations | `/api/v1/integrations` | List, connect, disconnect |
| inventory | `/api/v1/inventory` | List, summary |
| purchase_orders | `/api/v1/purchase-orders` | List, approve, reject, receive |

---

## Celery Beat Schedule (12 jobs)

| Job | Schedule | Queue |
|-----|----------|-------|
| Square inventory sync | Every 15 min | sync |
| Square transaction sync | Every 30 min | sync |
| Alert check | Hourly | sync |
| Data freshness check | Hourly (:30) | sync |
| Vendor scorecard update | Daily 1:00 AM | sync |
| Reorder point optimization | Daily 2:30 AM | ml |
| Weekly model retrain | Sunday 2:00 AM | ml |
| Drift detection | Daily 3:00 AM | sync |
| Opportunity cost analysis | Daily 4:00 AM | sync |
| Promo effectiveness | Monday 5:00 AM | sync |

---

## Data Pipeline

- **Training data**: `scripts/download_kaggle_data.py` — Favorita (3.5M rows), Walmart, Rossmann
- **Synthetic data**: `scripts/seed_enterprise_data.py` — 500 products × 15 stores × 730 days
- **Commercial data**: `scripts/seed_commercial_data.py` — DCs, sourcing rules, shrinkage rates, planograms
- **Validation**: Pandera schemas enforce data quality at pipeline gates
- **EDI samples**: Auto-generated EDI 846/856/810 documents
- **Kafka events**: Sample transaction event JSON files

See `docs/DATA_STRATEGY.md` for the full two-layer architecture.

---

## Key Files

- **README.md** (executive summary + architecture decision log)
- **docs/DATA_STRATEGY.md** (two-layer data architecture + cold start solution)
- **docs/MLOPS_STANDARDS.md** (MLflow, SHAP, Pandera, model registry, chart standards)
- **docs/RETAIL_DATA_ANALYSIS.md** (Kaggle feature audit)
- **docs/COMMERCIAL_PRODUCT_AUDIT.md** (gap analysis that drove Phase 2.5)
- **backend/ml/** (ML pipeline: features, train, predict, experiment, explain, validate, charts)
- **backend/inventory/** (decision engine: optimizer)
- **backend/supply_chain/** (sourcing, transfers, receiving)
- **backend/retail/** (calendar, shrinkage, planogram, promo tracking)
- **backend/business/** (counterfactual analysis)
- **backend/integrations/** (enterprise adapter layer)
- **backend/workers/** (Celery jobs: sync, retrain, optimizer, monitoring, vendor, promo)
- **backend/scripts/** (data pipeline scripts)
