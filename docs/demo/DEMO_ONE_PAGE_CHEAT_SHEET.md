# ShelfOps Demo One-Page Cheat Sheet (Local Use)

## Goal
Use two modes, not one blended pitch:
1. Business walkthrough: prove product value, retail credibility, and SMB fit.
2. Technical walkthrough: prove backend depth, MLOps design, and production thinking.

## Business Walkthrough Timing
1. 0:00-1:30 Hook: retail pain + why you built it.
2. 1:30-6:30 Frontend: dashboard -> alerts -> inventory -> forecasts -> integrations.
3. 6:30-9:00 HITL PO decisions.
4. 9:00-11:00 SMB value and pilot framing.
5. 11:00-12:00 Close and transition.

## Technical Walkthrough Timing
1. 0:00-1:00 Technical framing.
2. 1:00-4:00 Architecture and stack.
3. 4:00-7:00 Multi-tenant and backend design.
4. 7:00-10:00 Integrations including Kafka/event-stream path.
5. 10:00-13:00 Forecasting plus business logic layer.
6. 13:00-17:00 MLOps health, drift, retraining, experiments.
7. 17:00-20:00 Model choice and tradeoffs.

## Core Opening Line
"ShelfOps gives smaller retailers the operating discipline large retailers get from expensive systems: better inventory visibility, guided purchase decisions, and an auditable model lifecycle."

## Core Framing Line
"This is a product for SMB retailers, built with enterprise-grade backend and MLOps patterns."

## Must-Hit Themes
1. 4+ years of retail experience shaped the problem selection.
2. Forecasts are only useful because they connect to purchase-order decisions.
3. Human review is deliberate, not a missing feature.
4. LightGBM is the current default because it is the most practical fit for this data and runtime.
5. Enterprise adapters exist to prove scale and technical depth, not to overclaim GA enterprise readiness.
6. Kafka matters as proof of event-driven/backend engineering ability, not because every SMB needs Kafka on day one.

## Bring-Up
```bash
export MLFLOW_HOST_PORT=5001
docker compose up -d db redis mlflow redpanda api ml-worker sync-worker celery-beat
curl -s http://localhost:8000/health
curl -s http://localhost:5001/health
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
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

## Technical Proof (MLOps + integrations)
```bash
curl -s http://localhost:8000/api/v1/integrations/sync-health | jq
curl -s http://localhost:8000/api/v1/ml/models/health
curl -s 'http://localhost:8000/ml-alerts?limit=5' | jq
curl -s 'http://localhost:8000/experiments?limit=10' | jq
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

## Best Transition Line
"The business story is the workflow. The technical story is how I built the backend, MLOps loop, and integrations so that workflow can actually be trusted."

## Limitation Line (Say Once)
"Metrics shown here come from seeded/simulated data for reproducibility. Customer onboarding adds tenant-specific data contracts, shadow evaluation, and gated promotion before production ownership transfer."

## Close Line
"Today’s live demo is optimized for mid-market operations. Enterprise adapters and governance are implemented and actively being hardened."
