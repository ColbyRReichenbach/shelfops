# ShelfOps Demo One-Page Cheat Sheet (Local Use)

## Goal (15 min)
Show product value first, then prove controls:
1. SMB-ready inventory decision workflow.
2. Human-in-the-loop approvals with audit trail.
3. MLOps monitoring + experiment governance.
4. Reproducible model iteration evidence.

## Timing
1. 0:00-2:00 Slides: problem + positioning.
2. 2:00-8:30 Frontend: dashboard -> alerts -> inventory -> forecasts -> integrations.
3. 8:30-12:30 Terminal/API: PO decisions + logs + model health.
4. 12:30-14:00 Experiment flow: propose -> approve -> complete.
5. 14:00-15:00 Close: today vs roadmap + limits.

## Core Opening Line
"ShelfOps gives smaller retailers the operating discipline large retailers get from expensive systems: better inventory visibility, guided purchase decisions, and an auditable model lifecycle."

## Bring-Up
```bash
export MLFLOW_HOST_PORT=5001
docker compose up -d db redis mlflow redpanda api ml-worker sync-worker celery-beat
curl -s http://localhost:8000/health
curl -s http://localhost:5001/health
```

## Frontend Path (http://localhost:3000)
1. Dashboard: "What needs attention now."
2. Alerts: "Teams acknowledge and resolve, not just monitor."
3. Inventory: "Store/SKU-level stock posture."
4. Forecasts: "Predicted demand guides buying."
5. Integrations: "Square works now; others staged."

## HITL Proof (PO approve/reject + audit)
```bash
PO_IDS=$(curl -s "http://localhost:8000/api/v1/purchase-orders/suggested?limit=2" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ".join([x["po_id"] for x in d[:2]]))')
PO1=$(echo "$PO_IDS" | awk '{print $1}')
PO2=$(echo "$PO_IDS" | awk '{print $2}')

curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/$PO1/approve" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 12, "reason_code":"budget_constraint", "notes":"Demo edited approval"}'

curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/$PO2/reject" \
  -H "Content-Type: application/json" \
  -d '{"reason_code":"forecast_disagree", "notes":"Demo rejection path"}'

curl -s "http://localhost:8000/api/v1/purchase-orders/$PO1/decisions"
curl -s "http://localhost:8000/api/v1/purchase-orders/$PO2/decisions"
```

## MLOps Proof (trigger + logs + health)
```bash
docker compose exec -T ml-worker celery -A workers.celery_app call workers.sync.run_alert_check --kwargs '{"customer_id":"00000000-0000-0000-0000-000000000001"}'
docker compose exec -T ml-worker celery -A workers.celery_app call workers.monitoring.detect_model_drift --kwargs '{"customer_id":"00000000-0000-0000-0000-000000000001"}'
docker compose logs --no-color --tail=60 sync-worker
docker compose logs --no-color --tail=60 ml-worker
curl -s http://localhost:8000/api/v1/ml/models/health
```

## Experiment Governance Proof
```bash
EXP_ID=$(curl -s -X POST http://localhost:8000/experiments \
  -H "Content-Type: application/json" \
  -d '{"experiment_name":"Department segmentation trial","hypothesis":"Category segmentation improves volatile demand fit","experiment_type":"segmentation","model_name":"demand_forecast","proposed_by":"demo@shelfops.com"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["experiment_id"])')

curl -s -X PATCH "http://localhost:8000/experiments/$EXP_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"approved_by":"manager@shelfops.com","rationale":"Demo approval"}'

curl -s -X POST "http://localhost:8000/experiments/$EXP_ID/complete" \
  -H "Content-Type: application/json" \
  -d '{"decision":"reject","decision_rationale":"No lift in this demo run","results":{"baseline_mae":21.59,"experimental_mae":21.80,"improvement_pct":-0.97},"experimental_version":"v_demo_exp_01"}'

curl -s "http://localhost:8000/experiments/$EXP_ID"
curl -s "http://localhost:8000/ml-alerts?alert_type=experiment_complete&limit=5"
```

## DS/ML Appendix (Optional, 5 min)
```bash
tail -n 20 backend/reports/iteration_runs.jsonl
cat backend/models/registry.json
cat backend/models/champion.json
ls -1 backend/reports/iteration_notes | tail -n 10
```

## Limitation Line (Say Once)
"Metrics shown here come from seeded/simulated data for reproducibility. Customer onboarding adds tenant-specific data contracts, shadow evaluation, and gated promotion before production ownership transfer."

## Close Line
"Today’s live demo is optimized for mid-market operations. Enterprise adapters and governance are implemented and actively being hardened."
