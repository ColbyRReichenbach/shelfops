<div align="center">

# ShelfOps — Technical Reference
**Architecture reference for engineers and technical hiring managers.**
**For the product story, see [README.md](./README.md).**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x%20async-D71F00)](https://www.sqlalchemy.org/)
[![Celery](https://img.shields.io/badge/Celery-5-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-2-FDB515?logo=timescale&logoColor=black)](https://www.timescale.com/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![LightGBM](https://img.shields.io/badge/LightGBM-Forecasting-FF6600)](https://lightgbm.readthedocs.io/)
[![MLflow](https://img.shields.io/badge/MLflow-Tracking-0194E2?logo=mlflow&logoColor=white)](https://mlflow.org/)
[![SHAP](https://img.shields.io/badge/SHAP-Explainability-FF6B6B)](https://shap.readthedocs.io/)
[![Pandera](https://img.shields.io/badge/Pandera-Schema%20Validation-1E90FF)](https://pandera.readthedocs.io/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![pytest](https://img.shields.io/badge/pytest-497%20passing-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)

</div>

---

## System Architecture

ShelfOps is an async-first multi-tenant SaaS platform. All heavy work — data ingestion, model training, forecast generation, PO decisions — runs through a Celery worker pool. FastAPI handles real-time queries and webhook processing. The React dashboard surfaces insights to operators.

```
POS / ERP / Kafka / SFTP / EDI X12
           │
  ┌────────▼────────┐
  │  Integration    │  Celery sync workers (Kafka, SFTP, EDI)
  │  Ingest Layer   │  IntegrationSyncLog per batch
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │  PostgreSQL 15  │  Row-level security (tenant isolation)
  │  + TimescaleDB  │  Hypertable: daily_inventory_snapshot
  └────┬───────┬────┘
       │       │
  ┌────▼───┐ ┌─▼──────────────┐
  │  ML    │ │  FastAPI REST  │
  │Pipeline│ │  + WebSocket   │
  └────┬───┘ └─▼──────────────┘
       │       │
  MLflow    React 18 + TypeScript
  Registry  Recharts dashboard
```

---

## Stack

| Layer | Technology | Notes |
|---|---|---|
| API | FastAPI 0.109 (async) | Auto OpenAPI docs, dependency injection, async request handlers |
| ORM | SQLAlchemy 2.x async | Fully async query paths; Alembic for schema migrations |
| Task queue | Celery 5 + Redis | 12 scheduled beat jobs across 3 queues (`ml`, `sync`, `default`) |
| Time-series | PostgreSQL 15 + TimescaleDB | Hypertable partitioning on `daily_inventory_snapshot` |
| Cache / broker | Redis 7 | Celery broker, result backend, debounce locks |
| ML — gradient boost | XGBoost | Short-term demand signals, promotional effects, vendor patterns |
| ML — sequence model | PyTorch LSTM | Longer-range seasonality and trend capture |
| ML lifecycle | MLflow | Experiment tracking, model registry, artifact versioning |
| Explainability | SHAP | Per-forecast feature importance, surfaced in dashboard and API |
| Data validation | Pandera | Schema contracts at 3 ingest/processing gates |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + Recharts | |
| Containerization | Docker Compose | Local dev |

---

## ML Pipeline

### Model Architecture

LSTM + XGBoost ensemble with a **65/35 weight split** (XGBoost dominant):

- **XGBoost** handles short-term demand signals: lag features, rolling averages, promotional indicators, day-of-week patterns, vendor reliability scores
- **LSTM** captures longer-range seasonality and trend patterns that gradient boosting misses
- Ensemble output passes through a **promotion gate** before a new model version can enter production

### Feature Engineering (`backend/ml/features.py`)

Two feature tiers selected automatically based on data depth available per tenant:

| Tier | Features | Activation |
|---|---|---|
| Baseline | 27 features: lags, rolling windows, store signals, day-of-week | Default |
| Enriched | 45 features: + promotion flags, vendor metrics, weather proxies | When history depth ≥ threshold |

`detect_feature_tier()` selects the tier per tenant at training time.

### Model Lifecycle

```
retrain.py ──► train + backtest ──► arena.py ──► (business gate + DS gate) ──► MLflow registry
                                                                                       │
forecast.py ◄──────────────────────────── promoted model ◄─────────────────────────────┘
     │
     ▼
daily_inventory_snapshot  ──►  monitoring.py (accuracy backfill, drift detection)
                                     │
                               feedback_loop.py (closed-loop calibration)
```

**Promotion gate** (`arena.py`) is fail-closed: a candidate model must pass both a business accuracy delta check and a statistical significance test before it replaces the current production model. A gate failure leaves the previous model in place.

### Data Validation (Pandera)

Three schema contracts enforced in sequence:

1. **Raw data gate** — schema conformance, type coercion, null rate thresholds
2. **Feature gate** — range checks, lag consistency, no future leakage
3. **Prediction gate** — confidence bound validation, business logic constraints (non-negative stock, reasonable reorder quantities)

---

## Integration Architecture

Three ingest pathways, all dispatched by Celery beat via `dispatch_active_tenants` (fan-out to active tenants only):

| Pathway | Schedule | Protocol |
|---|---|---|
| Kafka / Redpanda | every 5 min | Event stream — POS events, ASN shipment notifications |
| SFTP batch | every 15 min | File-based bulk sync — products, inventory, transactions |
| EDI X12 | every 15 min | 846 (inventory advice), 856 (advance ship notice), 810 (invoice) |

Each worker:
1. Queries `Integration` for an active, connected integration of the matching type for the tenant
2. Skips silently if none found (zero-dependency fan-out)
3. Runs the sync pipeline, writing records to core domain tables
4. Appends an `IntegrationSyncLog` row (records processed, status, duration, error details)
5. Stamps `Integration.last_sync_at`

---

## Multi-Tenancy

Tenant isolation is enforced at the **database layer** via PostgreSQL row-level security (RLS), not just the application layer.

- Every authenticated route uses `get_tenant_db` (not `get_db`), which sets `SET LOCAL app.current_tenant = '{customer_id}'` on the session
- RLS policies on all tenant tables filter all reads and writes to the current tenant automatically
- `DEV_CUSTOMER_ID` constant is used in all development/test contexts — no hardcoded UUIDs anywhere in the codebase

---

## Celery Workers

12 scheduled jobs across 3 queues:

| Queue | Jobs |
|---|---|
| `ml` | `retrain`, `run_forecasts`, `run_monitoring`, `run_feedback_loop`, `update_vendor_metrics`, `track_promotions` |
| `sync` | `ingest_kafka_events`, `ingest_sftp_batch`, `ingest_edi_batch`, `generate_purchase_orders` |
| `default` | `generate_reports`, `dispatch_active_tenants` |

---

## Running Locally

```bash
# 1. Infrastructure
docker-compose up db redis

# 2. Database migrations
PYTHONPATH=backend alembic upgrade head

# 3. API server
PYTHONPATH=backend uvicorn api.main:app --reload          # :8000

# 4. Worker (separate terminal)
PYTHONPATH=backend celery -A workers.celery_app worker --loglevel=info

# 5. Frontend
cd frontend && npm install && npm run dev                  # :5173
```

---

## Test Suite

```bash
PYTHONPATH=backend pytest backend/tests/ -v
```

**497 passing, 1 skipped, 0 failing.** Key coverage areas:

| Area | What's tested |
|---|---|
| ML pipeline | Retrain, forecast, monitoring, arena promotion gate, feedback loop |
| Integration ingest | Kafka, SFTP, EDI — deterministic fixture-based tests, skip-if-no-integration |
| Data validation | Pandera gates at all 3 checkpoints |
| API | Auth, tenant isolation, all major endpoints |
| Domain logic | Vendor metrics, promo tracking, reorder optimization, PO workflows |
| Scripts | Seed scripts, replay simulation, demo runners |

Time-series CV split is enforced throughout — no `shuffle=True` anywhere in the ML test paths.

---

## CI Pipeline (GitHub Actions)

| Job | Check |
|---|---|
| Frontend Lint | ESLint |
| Backend Lint | `ruff check` + `ruff format --check` |
| Backend Tests | Full pytest suite |
| EDI Fixture E2E | Parse + validate EDI X12 fixtures end-to-end |
| Postgres Parity | Schema drift detection |
| Enterprise Seed Validation | Seed scripts and contract profiles |
| Contract Validation Suite | Data contract schema conformance |
| Release Gate | All above jobs must pass |

---

## Key Files

| File | Purpose |
|---|---|
| `backend/api/main.py` | FastAPI entry point, middleware, router registration |
| `backend/db/models.py` | All 27 SQLAlchemy ORM models |
| `backend/ml/features.py` | `detect_feature_tier()`, 27/45-feature architecture |
| `backend/ml/arena.py` | Model promotion gate (business + DS checks) |
| `backend/inventory/optimizer.py` | Dynamic ROP + EOQ decision engine |
| `backend/workers/celery_app.py` | Celery app, 12 beat schedule entries, task routes |
| `backend/workers/retrain.py` | Full retrain → MLflow → promotion pipeline |
| `backend/workers/forecast.py` | Runtime inference, 2–3 day lookahead |
| `backend/integrations/edi_adapter.py` | EDI X12 parser (846, 856, 810) |
| `backend/core/constants.py` | `DEV_CUSTOMER_ID` and shared constants |
| `docs/MLOPS_STANDARDS.md` | MLflow, SHAP, and Pandera conventions |
