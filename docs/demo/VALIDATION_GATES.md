# Validation Gates (Must Pass Before External Demo)

## 1. ML Pipeline Gate
```bash
PYTHONPATH=backend pytest backend/tests/test_ml_pipeline.py -q
```
Expected: all pass.

## 2. PO HITL API Gate
```bash
PYTHONPATH=backend pytest backend/tests/test_purchase_orders_api.py -q
```
Expected: all pass.

## 3. Enterprise Adapter Gate
```bash
PYTHONPATH=backend pytest tests/test_enterprise_integrations.py -q
```
Expected: all pass.

## 4. Frontend Build Gate
```bash
cd frontend
npm ci
npm run build
```
Expected: production build succeeds.

## 5. Runtime Orchestration Gate
```bash
docker compose build ml-worker
docker compose up -d db redis mlflow redpanda api ml-worker sync-worker celery-beat
docker compose logs --tail=200 ml-worker sync-worker celery-beat
```
If `mlflow` fails to bind `:5000`, re-run with:
```bash
MLFLOW_HOST_PORT=5001 docker compose up -d db redis mlflow redpanda api ml-worker sync-worker celery-beat
```

Expected:
- `ml-worker` consumes `ml` queue tasks.
- `sync-worker` consumes `sync` queue tasks.
- `celery-beat` publishes scheduled jobs without errors.

## 6. Demo Dry-Run Gate
Run the sequence in `docs/demo/DEMO_RUNBOOK.md` three times.

Expected:
- No manual hotfixes during run.
- All referenced artifacts exist and match commands.
