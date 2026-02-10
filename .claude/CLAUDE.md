# ShelfOps - Project Context for Claude Code

**Project**: AI-Powered Inventory Intelligence Platform  
**Purpose**: Portfolio project demonstrating retail ops + ML expertise for Target/Lowe's roles  
**Status**: MVP in progress — ML pipeline + MLOps standards + integrations complete

---

## Quick Reference

**What This Is**: SaaS platform that predicts stockouts 2-3 days early using existing POS/ERP data

**NOT Computer Vision**: Uses API data, no cameras (deferred due to training costs)

**Core Value**: Retailers lose $634B/year to stockouts despite having systems. We predict BEFORE they happen.

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

## Database (16 Tables)

Core tables: customers, stores, products (with GTIN/UPC), suppliers, transactions, inventory_levels, demand_forecasts, forecast_accuracy, reorder_points, alerts, actions, purchase_orders, promotions, integrations (with `integration_type`), anomalies, **edi_transaction_log** (audit trail)

---

## ML Models

**1. Demand Forecasting**: LSTM + XGBoost ensemble
- Cold start: 27 features (Kaggle data) → Production: 46 features (real data)
- Auto-upgrades via `detect_feature_tier()` after 90 days of real data
- MAE <15%, MAPE <20% targets

**2. Reorder Optimization**: ML-enhanced safety stock  
**3. Anomaly Detection**: Isolation Forest (shrinkage, data errors)

**MLOps Standards** (see `docs/MLOPS_STANDARDS.md`):
- MLflow: Every training run tracked (params, metrics, artifacts)
- SHAP: Global + local explanations generated per model version
- Pandera: Validation at 3 pipeline gates (raw data → features → prediction)
- Model Registry: `models/registry.json` + champion/challenger pattern
- Charts: Plotly design system for consistent analytics viz

---

## Data Pipeline

- **Training data**: `scripts/download_kaggle_data.py` — Favorita (3.5M rows), Walmart, Rossmann
- **Synthetic data**: `scripts/seed_enterprise_data.py` — 500 products × 15 stores × 730 days
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
- **backend/ml/** (ML pipeline: features, train, predict, experiment, explain, validate, charts)
- **backend/integrations/** (enterprise adapter layer)
- **backend/scripts/** (data pipeline scripts)

---

**Status**: ML pipeline + MLOps standards + integrations complete, frontend in progress
