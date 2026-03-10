# ShelfOps Demo Runbook

## 1. Objective
This runbook is the environment and runtime companion to the two canonical teleprompter scripts:
- `docs/demo/BUSINESS_WALKTHROUGH.md`
- `docs/demo/TECHNICAL_WALKTHROUGH.md`

Use this file for setup, runtime prep, and proof commands.

Deliver a truthful recorded or live demo that proves:
- real retail workflow understanding
- operational product design, not just analytics
- practical AI integration with human control
- production-minded backend and MLOps discipline
- clear `Today / Pilot next / Later` boundaries

Support docs:
- `docs/demo/DEMO_ONE_PAGE_CHEAT_SHEET.md`
- `docs/demo/CLAIMS_LEDGER.md`
- `docs/demo/DEMO_SIGNOFF_CHECKLIST.md`

## 2. Preconditions
- Docker and Docker Compose installed
- Python environment available
- Node installed
- `.env` configured for local dev
- `DEBUG=true` in local dev if using auth bypass

## 3. Bring Up Local Stack
First run only:

```bash
docker compose build ml-worker
```

If `mlflow` cannot bind to `localhost:5000`, use:

```bash
export MLFLOW_HOST_PORT=5001
```

Bring up services:

```bash
docker compose up -d db redis mlflow redpanda api ml-worker
```

Verify:

```bash
docker compose ps
curl -s http://localhost:8000/health | jq
```

## 4. Initialize Local Data
Run migrations and local seed flows:

```bash
cd backend
PYTHONPATH=. alembic upgrade head
PYTHONPATH=. python scripts/seed_test_data.py
PYTHONPATH=. python scripts/seed_commercial_data.py
cd ..
```

Prepare deterministic demo state:

```bash
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
```

Optional terminal appendix proof:

```bash
PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py
```

Why this exists:
- the demo should not depend on leftover local state
- the seeded runtime gives you repeatable alerts, PO suggestions, anomaly evidence, and MLOps evidence

## 5. Start Frontend
```bash
cd frontend
npm ci
npm run dev
```

Frontend URL:

```text
http://localhost:3000
```

## 6. Recommended Recording Strategy
Use two recordings, not one blended script:

1. `Business walkthrough`
- target: recruiters, SMB owners, general hiring managers
- script: `docs/demo/BUSINESS_WALKTHROUGH.md`

2. `Technical walkthrough`
- target: ML, MLOps, DS, DE, engineering interviewers
- script: `docs/demo/TECHNICAL_WALKTHROUGH.md`

## 7. Business Walkthrough Runtime Path
Page order:
1. Dashboard
2. Alerts
3. Inventory
4. Forecasts
5. Integrations
6. HITL purchase-order proof

Key goal:
- explain the business problem, product workflow, team personas, and SMB value

Command proof block:

```bash
curl -s http://localhost:8000/api/v1/purchase-orders/suggested | jq
cat docs/productization_artifacts/demo_runtime/demo_runtime_summary.json | jq
```

## 8. Technical Walkthrough Runtime Path
Page order:
1. Dashboard shell
2. Operations
3. Forecasts
4. Alerts
5. ML Ops

Key goal:
- explain the stack, system design, model choices, governance workflow, and operational discipline

Core proof block:

```bash
curl -s http://localhost:8000/api/v1/integrations/sync-health | jq
curl -s http://localhost:8000/api/v1/ml/models/health | jq
curl -s 'http://localhost:8000/api/v1/ml/effectiveness?window_days=30&model_name=demand_forecast' | jq
curl -s 'http://localhost:8000/api/v1/alerts?alert_type=anomaly_detected&status=open' | jq
curl -s 'http://localhost:8000/api/v1/ml/anomalies?days=7&limit=5' | jq
curl -s 'http://localhost:8000/experiments?limit=10' | jq
```

Worker appendix:

```bash
docker compose logs --no-color --tail=80 ml-worker
docker compose logs --no-color --tail=80 api
```

## 9. HITL Purchase-Order Proof
Get suggested POs:

```bash
curl -s "http://localhost:8000/api/v1/purchase-orders/suggested?limit=2" | jq
```

If you need deterministic IDs:

```bash
cat docs/productization_artifacts/demo_runtime/demo_runtime_summary.json | jq
```

Approve:

```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/approve" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Reject:

```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/reject" \
  -H "Content-Type: application/json" \
  -d '{"reason_code":"forecast_disagree","notes":"Demo rejection path"}'
```

Decision log:

```bash
curl -s "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/decisions" | jq
```

## 10. Experiment Governance Proof
Create experiment:

```bash
curl -s -X POST http://localhost:8000/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_name":"favorita_lgbm_feature_set_v2_promo_velocity",
    "hypothesis":"Adding promo interactions and recent demand velocity features will reduce overstock and stockout opportunity cost on Favorita without regressing MASE or WAPE.",
    "experiment_type":"feature_set",
    "model_name":"demand_forecast"
  }' | jq
```

Approve experiment:

```bash
curl -s -X PATCH "http://localhost:8000/experiments/<EXPERIMENT_ID>/approve" \
  -H "Content-Type: application/json" \
  -d '{"rationale":"Demo approval"}' | jq
```

List experiments:

```bash
curl -s http://localhost:8000/experiments?limit=10 | jq
```

Use this section to explain:
- typed experiment taxonomy
- baseline vs challenger comparison
- auditability of model iteration

## 11. Evidence Artifacts To Show
- `docs/productization_artifacts/demo_runtime/demo_runtime_summary.json`
- `backend/models/registry.json`
- `backend/models/champion.json`
- `backend/reports/iteration_runs.jsonl`
- `docs/demo/CLAIMS_LEDGER.md`

## 12. Presentation Boundaries
Say clearly:
- the workflow is live and truthful today
- enterprise patterns are demonstrated, not fully commercialized
- business metrics in the seeded demo runtime are modeled estimates
- customer ownership still relies on tenant-specific onboarding, shadow evaluation, and gated promotion

Do not say:
- fully autonomous ordering
- real-time streaming everywhere
- full enterprise readiness

## 13. Demo Close
Use this close:

> Today, what is live is a truthful operating workflow: alerts, forecasts, anomaly-backed triage, purchase-order decisions, and a governed model lifecycle. Pilot next means operator visibility, integration resilience, and tighter release discipline for a first Square or CSV-first SMB rollout. Later is broader enterprise hardening and richer model sophistication, but I do not claim those pieces are fully production-ready today.
