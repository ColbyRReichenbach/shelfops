# ShelfOps Full Demo Script (Comprehensive, Audited, No-Hallucination)

## 1. Demo Objective
Deliver a hiring-first, SMB-product-first story that still proves enterprise-relevant architecture.

What this demo must prove:
1. You understand real retail pain from store-floor operations through corporate planning.
2. ShelfOps is practical for SMB teams today (not just research metrics).
3. The system is auditable: every operational decision can be traced and reused in model iteration.
4. You can operate like a DS/ML engineer inside a production-style workflow.

## 2. Core Positioning (Use This Verbatim)
"ShelfOps gives smaller retailers the operating discipline large retailers get from expensive systems: better inventory visibility, guided purchase decisions, and an auditable model lifecycle. It is mid-market ready now, with enterprise adapters and governance implemented and actively hardened."

## 3. Audience Translation (What To Say in Plain Language)
Use these one-liners so non-technical viewers stay engaged:
- Forecasting: "We estimate what each store-product pair will likely sell next, so buying is proactive."
- Alerts: "We flag problems before they become missed sales or dead stock."
- HITL approvals: "Managers stay in control. The system suggests; humans decide."
- MLOps: "Models are monitored like employees: tracked, reviewed, and retrained when performance slips."
- Drift detection: "If reality changes and forecasts degrade, we detect it and trigger retraining review."

## 4. Demo Asset Split (What To Show vs Where)
- Slides (2-3 min): Problem, positioning, architecture, "live now vs hardening".
- Live frontend (6-7 min): Product workflow for operators.
- Live API/log terminal (4-5 min): HITL evidence + MLOps controls + experiment governance.
- Technical appendix (optional 5 min): DS hypothesis workflow and iteration evidence.
- Codebase deep-dive (Q&A only): Never start in code for external audiences.

## 5. Bring-Up Checklist
```bash
export MLFLOW_HOST_PORT=5001
docker compose up -d db redis mlflow redpanda api ml-worker sync-worker celery-beat
docker compose ps
curl -s http://localhost:8000/health
curl -s http://localhost:5001/health
```

If frontend is not running:
```bash
cd frontend
npm ci
npm run dev
```

## 6. Primary 15-Minute Script (Say + Show)

### 0:00-2:00 | Context + Why This Exists (Slides)
Say:
1. "I built ShelfOps because poor inventory decisions are usually manual, inconsistent, and expensive."
2. "From 4 years in retail operations, I saw visual checks replace data-driven planning, which causes stockouts, overstock, and ghost inventory."
3. "ShelfOps is built for SMB operators first, while preserving enterprise-style controls."

Show:
- Slide: stockout vs overstock problem.
- Slide: who uses ShelfOps.
  - Store manager: guided decisions.
  - Corporate ops: visibility and governance.
  - DS/ML team: reproducible experimentation + promotion controls.

### 2:00-8:30 | Product Workflow (Frontend Live)
Open `http://localhost:3000`.

Say and show in order:
1. Dashboard: "This is the operating snapshot: risk, forecast context, and where action is needed."
2. Alerts: "This is the daily queue. Teams acknowledge and resolve issues, not just view dashboards."
3. Inventory: "Inventory posture and reorder context are visible at the SKU/store level."
4. Forecasts: "Forecasts guide ordering decisions before shelves go empty."
5. Integrations: "Square is active now; broader integration surface is visible and staged."

Code-backed references:
- Routes: `frontend/src/App.tsx`
- Alerts workflow: `frontend/src/pages/AlertsPage.tsx`
- Integrations page behavior: `frontend/src/pages/IntegrationsPage.tsx`

### 8:30-12:30 | HITL + MLOps Evidence (Terminal/API Live)

#### A) HITL purchase decisions are auditable
List suggested POs:
```bash
curl -s "http://localhost:8000/api/v1/purchase-orders/suggested?limit=2"
```

Extract IDs:
```bash
PO_IDS=$(curl -s "http://localhost:8000/api/v1/purchase-orders/suggested?limit=2" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ".join([x["po_id"] for x in d[:2]]))')
PO1=$(echo "$PO_IDS" | awk '{print $1}')
PO2=$(echo "$PO_IDS" | awk '{print $2}')
echo "$PO1 $PO2"
```

Approve with edit:
```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/$PO1/approve" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 12, "reason_code":"budget_constraint", "notes":"Demo edited approval"}'
```

Reject with reason:
```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/$PO2/reject" \
  -H "Content-Type: application/json" \
  -d '{"reason_code":"forecast_disagree", "notes":"Demo rejection path"}'
```

Show decision history:
```bash
curl -s "http://localhost:8000/api/v1/purchase-orders/$PO1/decisions"
curl -s "http://localhost:8000/api/v1/purchase-orders/$PO2/decisions"
```

Optional DB proof:
```bash
docker compose exec -T db psql -U shelfops -d shelfops -c "select po_id,status,quantity,ordered_at from purchase_orders where po_id in ('$PO1','$PO2');"
docker compose exec -T db psql -U shelfops -d shelfops -c "select po_id,decision_type,original_qty,final_qty,reason_code,decided_at from po_decisions where po_id in ('$PO1','$PO2') order by decided_at desc;"
```

Say:
- "This is not black box automation; human decisions are explicit and stored."
- "Decision reasons are the bridge between operations and future model improvement."

Code-backed references:
- PO endpoints: `backend/api/v1/routers/purchase_orders.py`
- Decision persistence model: `backend/db/models.py`

#### B) MLOps controls are runnable and visible
Trigger alert pipeline:
```bash
docker compose exec -T ml-worker celery -A workers.celery_app call workers.sync.run_alert_check --kwargs '{"customer_id":"00000000-0000-0000-0000-000000000001"}'
```

Trigger drift check:
```bash
docker compose exec -T ml-worker celery -A workers.celery_app call workers.monitoring.detect_model_drift --kwargs '{"customer_id":"00000000-0000-0000-0000-000000000001"}'
```

Show logs:
```bash
docker compose logs --no-color --tail=80 sync-worker
docker compose logs --no-color --tail=80 ml-worker
```

Show model health:
```bash
curl -s http://localhost:8000/api/v1/ml/models/health
```

Code-backed references:
- Schedules and queues: `backend/workers/celery_app.py`
- Drift logic and retrain trigger path: `backend/workers/monitoring.py`
- Health endpoint: `backend/api/v1/routers/models.py`

### 12:30-14:00 | DS Experiment Governance (API Live)
Propose:
```bash
EXP_ID=$(curl -s -X POST http://localhost:8000/experiments \
  -H "Content-Type: application/json" \
  -d '{"experiment_name":"Department segmentation trial","hypothesis":"Category segmentation improves volatile demand fit","experiment_type":"segmentation","model_name":"demand_forecast","proposed_by":"demo@shelfops.com"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["experiment_id"])')
echo "$EXP_ID"
```

Approve:
```bash
curl -s -X PATCH "http://localhost:8000/experiments/$EXP_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"approved_by":"manager@shelfops.com","rationale":"Demo approval"}'
```

Complete:
```bash
curl -s -X POST "http://localhost:8000/experiments/$EXP_ID/complete" \
  -H "Content-Type: application/json" \
  -d '{"decision":"reject","decision_rationale":"No lift in this demo run","results":{"baseline_mae":21.59,"experimental_mae":21.80,"improvement_pct":-0.97},"experimental_version":"v_demo_exp_01"}'
```

Show artifact:
```bash
curl -s "http://localhost:8000/experiments/$EXP_ID"
curl -s "http://localhost:8000/ml-alerts?alert_type=experiment_complete&limit=5"
```

Say:
- "Experiments are hypotheses with approvals and outcomes, not ad-hoc notebook changes."

Code-backed references:
- Experiment endpoints: `backend/api/v1/routers/experiments.py`
- ML alerts actions: `backend/api/v1/routers/ml_alerts.py`

### 14:00-15:00 | Close + Limitation Framing
Say:
1. "ShelfOps today is a credible mid-market operating system with auditable AI workflows."
2. "Enterprise adapters and controls are implemented; hardening remains an active gate, not a claim."
3. "Current default training mode is LightGBM-first; legacy XGBoost/LSTM paths remain only for backward compatibility and older artifacts."
4. "Model quality will improve as tenant-specific customer data replaces synthetic/seed-only signals."

## 7. Optional Technical Appendix (5 Minutes): DS Hypothesis Loop
Use this when interviewers want to see your DS/ML workflow directly.

### Hypothesis Example
"Adding segment-aware features for volatile categories can reduce MAE in high-variance demand."

### What To Show
1. Propose experiment through API (already shown).
2. Run reproducible training iteration with notes.
3. Compare to baseline in logs.
4. Decide adopt/reject and document.

### Commands
Run one reproducible training iteration:
```bash
PYTHONPATH=backend python3 backend/scripts/run_training.py \
  --data-dir data/seed \
  --dataset demo_seed \
  --version v_demo_feature_01 \
  --holdout-days 14 \
  --write-partition-manifest docs/productization_artifacts/replay_partition_manifest.json
```

Run model strategy comparison cycle:
```bash
PYTHONPATH=backend python3 backend/scripts/run_model_strategy_cycle.py \
  --data-dir data/seed \
  --max-rows 25000 \
  --output-json docs/productization_artifacts/model_strategy_cycle.json \
  --output-md docs/productization_artifacts/model_strategy_cycle.md
```

Show evidence:
```bash
tail -n 20 backend/reports/iteration_runs.jsonl
cat backend/models/registry.json
cat backend/models/champion.json
cat docs/productization_artifacts/model_strategy_cycle.md
ls -1 backend/reports/iteration_notes | tail -n 10
```

## 8. What Is Automated vs Manual (Simple Explanation)
- Automated: scheduled sync, alert checks, drift checks, backtests, retrain jobs (via Celery beat and workers).
- Manual: business approvals, model promotion decisions, experiment sign-off.
- Hybrid design principle: "Automate detection and recommendation; keep high-impact decisions human-controlled."

## 9. Trigger Map (Source of Truth)
Source: `backend/workers/celery_app.py`

- Every 15 min: `workers.sync.sync_square_inventory` (queue `sync`)
- Every 30 min: `workers.sync.sync_square_transactions` (queue `sync`)
- Hourly: `workers.sync.run_alert_check` (queue `sync`)
- Daily 03:00 UTC: `workers.monitoring.detect_model_drift` (queue `ml`)
- Daily 06:00 UTC: `workers.monitoring.run_daily_backtest` (queue `ml`)
- Weekly Sunday 02:00 UTC: `workers.retrain.retrain_forecast_model` (queue `ml`)

## 10. Limitation Language (Say This Explicitly)
- "This demo uses seeded data and simulated integrations for reproducibility."
- "The metrics shown are baseline-quality for this dataset, not a universal production guarantee."
- "Planner feedback is integrated into feature generation for retraining/inference; promotion still remains human-governed through explicit gates."
- "Enterprise claims are bounded to implemented adapters and governance paths; we do not claim full enterprise SLA validation yet."

## 11. How To Split Slide/Video/Live Assets
- Live demo session: 15 minutes using Sections 6 and 7.
- Recorded video: use `docs/demo/VIDEO_SCRIPT_10MIN.md`.
- Deck: use `docs/demo/SLIDE_DECK_OUTLINE.md`.
- Evidence appendix: runbook + claims ledger + logs.

## 12. Presenter Rules
- Lead with decisions and outcomes, then show technical evidence.
- Never overclaim model performance or automation maturity.
- State limits once in the live demo and show details in docs.
- Use logs and database checks only to prove claims, not as primary storytelling.
