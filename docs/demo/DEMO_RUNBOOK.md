# ShelfOps Demo Runbook (15 Minutes)

## 1. Objective
Deliver a hiring-first, product-level demo that proves:
- Retail workflow understanding.
- ML + HITL operating model.
- Reproducible model iteration and MLOps controls.
- Clear "today vs roadmap" boundaries without overclaiming.

For a minute-by-minute presenter script with narration + DB/log proof steps, use:
- `docs/demo/FULL_DEMO_SCRIPT.md`

## 2. Preconditions
- Docker + Docker Compose installed.
- Python environment available for local commands.
- Node installed for frontend.
- `.env` has `DEBUG=true` (dev auth bypass).

## 3. Bring Up Local Stack
First run only (ML image is large):
```bash
docker compose build ml-worker
```
If `mlflow` cannot bind to `localhost:5000`, stop the conflicting process or remap the port in `docker-compose.yml` before continuing.
Quick fix without editing files:
```bash
export MLFLOW_HOST_PORT=5001
```

```bash
docker compose up -d db redis mlflow redpanda api ml-worker sync-worker celery-beat
```

Check services:
```bash
docker compose ps
curl http://localhost:8000/health
```

## 4. Initialize Data
```bash
cd backend
PYTHONPATH=. alembic upgrade head
PYTHONPATH=. python scripts/seed_test_data.py
PYTHONPATH=. python scripts/seed_commercial_data.py
cd ..
```

## 5. Start Frontend
```bash
cd frontend
npm ci
npm run dev
```

Frontend URL: `http://localhost:3000`

## 6. Demo Script (Live)

### Segment A: Product UX (5 min)
1. Dashboard: risk KPI summary and accuracy context.
2. Alerts page: acknowledge/resolve workflow + live websocket indicator.
3. Inventory page: status filtering and reorder-point context.
4. Forecasts page: category trend and product demand movers.
5. Integrations page: Square-first path and connection status model.

### Segment B: HITL Operations via API (4 min)
Get one suggested PO:
```bash
curl -s http://localhost:8000/api/v1/purchase-orders/suggested
```

Approve:
```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/approve" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Reject (reason required):
```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/reject" \
  -H "Content-Type: application/json" \
  -d '{"reason_code":"forecast_disagree","notes":"Demo rejection path"}'
```

Decision audit trail:
```bash
curl -s "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/decisions"
```

### Segment C: MLOps Control Loop via API (3 min)
Model health:
```bash
curl -s http://localhost:8000/api/v1/ml/models/health
```

Propose experiment:
```bash
curl -s -X POST http://localhost:8000/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_name":"Department segmentation trial",
    "hypothesis":"Category-aware modeling improves error in volatile departments",
    "experiment_type":"segmentation",
    "model_name":"demand_forecast",
    "proposed_by":"demo@shelfops.com"
  }'
```

List experiments:
```bash
curl -s http://localhost:8000/experiments
```

ML alerts list:
```bash
curl -s http://localhost:8000/ml-alerts
```

### Segment D: Reproducible Iteration Evidence (3 min)
Registry snapshot:
```bash
cat backend/models/registry.json
```

Champion state:
```bash
cat backend/models/champion.json
```

Iteration logs:
```bash
tail -n 10 backend/reports/iteration_runs.jsonl
```

Sample iteration note:
```bash
ls -1 backend/reports/iteration_notes | tail -n 5
```

### Segment E (Optional Technical Appendix): DS Hypothesis Loop (5 min)
Use if interviewers ask how you iterate on model quality:
```bash
PYTHONPATH=backend python3 backend/scripts/run_training.py \
  --data-dir data/seed \
  --dataset demo_seed \
  --version v_demo_feature_01 \
  --holdout-days 14 \
  --write-partition-manifest docs/productization_artifacts/replay_partition_manifest.json
```
```bash
PYTHONPATH=backend python3 backend/scripts/run_model_strategy_cycle.py \
  --data-dir data/seed \
  --max-rows 25000 \
  --output-json docs/productization_artifacts/model_strategy_cycle.json \
  --output-md docs/productization_artifacts/model_strategy_cycle.md
```

## 7. Optional: Trigger a New Iteration Run
```bash
PYTHONPATH=backend python3 backend/scripts/run_training.py \
  --data-dir data/seed \
  --dataset demo_seed \
  --version v_demo_iter_01
PYTHONPATH=backend python3 backend/scripts/generate_model_performance_log.py \
  --output backend/reports/MODEL_PERFORMANCE_LOG.md
```

## 8. Evidence Artifacts to Show
- `docs/productization_artifacts/replay_partition_manifest.json`
- `backend/reports/iteration_runs.jsonl`
- `backend/models/registry.json`
- `backend/models/champion.json`
- `docs/demo/CLAIMS_LEDGER.md`

## 9. Demo Close Statement (Use Verbatim)
"Current live demo is optimized for mid-market operations. Enterprise adapters and governance are implemented, and currently being hardened with full parser test coverage and scheduled orchestration."

## 10. Limitation Statement (Say Once During Demo)
"Metrics shown here are from seeded/simulated data for reproducibility. Customer onboarding adds tenant-specific data contracts, shadow evaluation, and gated promotion before production ownership is transferred."
