# ShelfOps Demo Sign-Off Checklist

- Last verified date: March 9, 2026
- Goal: close the remaining demo work with explicit commands, files, and pass/fail criteria
- Scope: challenger evidence, visual review, polish, and rehearsal

## 0. Preconditions

Run the local stack first:

```bash
export MLFLOW_HOST_PORT=5001
docker compose up -d db redis mlflow redpanda api ml-worker
curl -s http://localhost:8000/health | jq
```

Frontend:

```bash
cd frontend
npm run dev
```

Pin deterministic demo state:

```bash
cd /Users/colbyreichenbach/Downloads/shelfops_project
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
```

Pass criteria:
- API health endpoint responds successfully.
- Frontend loads at `http://localhost:3000`.
- `prepare_demo_runtime.py` writes `docs/productization_artifacts/demo_runtime/demo_runtime_summary.json`.

## 1. Real Challenger Evidence

### Goal
Replace as much seeded MLOps evidence as possible with a real Favorita baseline/challenger story.

### Files
- [backend/scripts/run_training.py](/Users/colbyreichenbach/Downloads/shelfops_project/backend/scripts/run_training.py)
- [backend/api/v1/routers/experiments.py](/Users/colbyreichenbach/Downloads/shelfops_project/backend/api/v1/routers/experiments.py)
- [backend/models/registry.json](/Users/colbyreichenbach/Downloads/shelfops_project/backend/models/registry.json)
- [backend/models/champion.json](/Users/colbyreichenbach/Downloads/shelfops_project/backend/models/champion.json)
- [docs/demo/CLAIMS_LEDGER.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/CLAIMS_LEDGER.md)

### Commands
Log the hypothesis:

```bash
curl -s -X POST http://localhost:8000/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_name":"favorita_lgbm_feature_set_v2_promo_velocity",
    "hypothesis":"Promo-aware interactions and recent demand velocity features will reduce overstock and stockout opportunity cost without regressing MASE or WAPE.",
    "experiment_type":"feature_set",
    "model_name":"demand_forecast",
    "proposed_by":"demo@shelfops.com",
    "lineage_metadata":{
      "dataset_id":"favorita",
      "forecast_grain":"store_nbr_family_date",
      "architecture":"lightgbm",
      "objective":"poisson",
      "feature_set_id":"favorita_baseline_v2",
      "segment_strategy":"global",
      "trigger_source":"manual_hypothesis"
    }
  }' | jq
```

Run the baseline reference:

```bash
PYTHONPATH=backend python3 backend/scripts/run_training.py \
  --data-dir data/kaggle/favorita \
  --dataset favorita \
  --version v_favorita_baseline_demo \
  --holdout-days 14 \
  --write-partition-manifest docs/productization_artifacts/favorita_baseline_partition.json
```

Run the challenger:

```bash
PYTHONPATH=backend python3 backend/scripts/run_training.py \
  --data-dir data/kaggle/favorita \
  --dataset favorita \
  --version v_favorita_challenger_demo \
  --holdout-days 14 \
  --write-partition-manifest docs/productization_artifacts/favorita_challenger_partition.json
```

Inspect the resulting evidence:

```bash
cat backend/models/registry.json | jq
cat backend/models/champion.json | jq
curl -s 'http://localhost:8000/api/v1/ml/effectiveness?window_days=30&model_name=demand_forecast' | jq
curl -s 'http://localhost:8000/experiments?limit=10' | jq
```

### Pass criteria
- A baseline version and challenger version both exist in `registry.json`.
- The experiment ledger entry exists and is readable.
- The metrics you plan to talk through are present and coherent:
  - `WAPE`
  - `MASE`
  - `bias_pct`
  - `overstock_dollars`
  - opportunity-cost metrics
- The final talk track is honest:
  - either “challenger improved and is pending promotion”
  - or “challenger did not clear gates and remained a challenger”

## 2. MLOps Surface Refresh

### Goal
Make sure the live MLOps page and API proof match the real challenger story.

### Files
- [frontend/src/pages/MLOpsPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/MLOpsPage.tsx)
- [frontend/src/components/mlops/ModelArena.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/components/mlops/ModelArena.tsx)
- [frontend/src/components/mlops/ExperimentWorkbench.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/components/mlops/ExperimentWorkbench.tsx)
- [backend/api/v1/routers/ml_ops.py](/Users/colbyreichenbach/Downloads/shelfops_project/backend/api/v1/routers/ml_ops.py)
- [backend/api/v1/routers/models.py](/Users/colbyreichenbach/Downloads/shelfops_project/backend/api/v1/routers/models.py)

### Commands
```bash
curl -s http://localhost:8000/api/v1/ml/models/health | jq
curl -s 'http://localhost:8000/api/v1/ml/effectiveness?window_days=30&model_name=demand_forecast' | jq
curl -s 'http://localhost:8000/experiments?limit=10' | jq
```

### Pass criteria
- ML Ops page loads without empty critical widgets.
- Champion/challenger lineage is visible.
- Governance scorecard values match the API.
- The experiment shown in the UI is the one you intend to talk through live.

## 3. Visual Review

### Goal
Confirm the live UI is presentable and no demo-breaking rough edges remain.

### Files / pages to inspect
- [frontend/src/pages/DashboardPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/DashboardPage.tsx)
- [frontend/src/pages/AlertsPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/AlertsPage.tsx)
- [frontend/src/pages/InventoryPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/InventoryPage.tsx)
- [frontend/src/pages/ForecastsPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/ForecastsPage.tsx)
- [frontend/src/pages/IntegrationsPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/IntegrationsPage.tsx)
- [frontend/src/pages/OperationsPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/OperationsPage.tsx)
- [frontend/src/pages/MLOpsPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/MLOpsPage.tsx)

### Manual checks
- Dashboard: no obviously empty cards or fake-looking copy.
- Alerts: anomaly-origin alerts are understandable in under 30 seconds.
- Inventory: filters and lists respond normally.
- Forecasts: charts/tables render without odd empty states.
- Integrations: Square/live providers are clearly distinct from roadmap-only providers.
- Operations: sync health, model health, and alert summary are readable.
- ML Ops: scorecard, model arena, and experiment workbench all load cleanly.

### Pass criteria
- No broken navigation.
- No dead buttons in the intended walkthrough.
- No stale or contradictory labels.
- No screen that would force an ad hoc explanation to cover a product flaw.

## 4. Polish Pass

### Goal
Fix only issues that affect the demo.

### Files
- whichever files fail visual review
- likely candidates:
  - [frontend/src/pages/AlertsPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/AlertsPage.tsx)
  - [frontend/src/pages/MLOpsPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/MLOpsPage.tsx)
  - [frontend/src/pages/OperationsPage.tsx](/Users/colbyreichenbach/Downloads/shelfops_project/frontend/src/pages/OperationsPage.tsx)
  - [docs/demo/BUSINESS_WALKTHROUGH.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/BUSINESS_WALKTHROUGH.md)
  - [docs/demo/TECHNICAL_WALKTHROUGH.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/TECHNICAL_WALKTHROUGH.md)

### Verification commands
```bash
cd frontend && npm run lint
cd frontend && npm run build
bash scripts/validate_docs.sh
```

### Pass criteria
- Any visual issues found in step 3 are fixed.
- Lint/build/docs validation are clean.
- No new demo scope is introduced.

## 5. Rehearsal

### Goal
Prove both live tracks can be delivered cleanly.

### Files
- [docs/demo/BUSINESS_WALKTHROUGH.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/BUSINESS_WALKTHROUGH.md)
- [docs/demo/TECHNICAL_WALKTHROUGH.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/TECHNICAL_WALKTHROUGH.md)
- [docs/demo/DEMO_RUNBOOK.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/DEMO_RUNBOOK.md)
- [docs/demo/DEMO_ONE_PAGE_CHEAT_SHEET.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/DEMO_ONE_PAGE_CHEAT_SHEET.md)
- [docs/demo/CLAIMS_LEDGER.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/CLAIMS_LEDGER.md)

### Commands
```bash
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py
cat docs/productization_artifacts/demo_runtime/demo_runtime_summary.json | jq
```

### Required rehearsal path
- Business walkthrough:
  - dashboard
  - alerts
  - inventory
  - forecasts
  - integrations
  - purchase-order flow
  - close with `Today / Pilot next / Later`
- Technical walkthrough:
  - architecture framing
  - integrations and Kafka
  - forecast/business-logic layer
  - anomaly-in-alerts flow
  - MLOps control loop
  - model choice and tradeoffs
  - close with `Today / Pilot next / Later`

### Pass criteria
- Both walkthroughs complete with no broken flow.
- Terminal/API proof commands work.
- No claim exceeds [CLAIMS_LEDGER.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/CLAIMS_LEDGER.md).
- You have one clear fallback path if a UI screen loads awkwardly:
  - API proof
  - terminal proof
  - claims-safe explanation

## 6. Final Sign-Off

Demo is ready when all of the following are true:
- Challenger evidence is real and presentable.
- The intended frontend path is visually clean.
- Both walkthroughs have been rehearsed end to end.
- Demo copy matches current runtime behavior.
- Remaining gaps are only post-demo / pre-pilot work.
