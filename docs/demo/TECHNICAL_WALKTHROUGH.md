# ShelfOps Technical Demo Script

## Purpose
This is the full technical teleprompter script for a prerecorded ShelfOps demo.

Use this file if you want one self-contained technical walkthrough that includes:
- full spoken narration
- exact page and terminal flow
- architecture reasoning woven into the explanation
- model and MLOps details
- promotion gates, archive, rollback, shadowing, and retriggers
- the specific reasons the stack and model choices matter

Use this for:
- ML engineers
- MLOps interviewers
- data scientists
- data / analytics engineers
- engineering managers
- technical hiring leads

## Recording Goal
By the end of this recording, the viewer should believe:
1. you built the full system, not just a model
2. you can explain why each part of the stack exists
3. your AI and MLOps choices are pragmatic, auditable, and business-safe
4. you understand how internal product surfaces map to different user roles
5. you know how to operate model iteration responsibly

## Preflight

### Runtime Prep
Run this before recording:

```bash
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
```

Optional terminal appendix:

```bash
PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py
```

### Open Windows
Have these ready before you start:
- browser on `http://localhost:3000`
- terminal for API proof
- optional second terminal for docker logs

### What This Script Assumes
- the app is already running locally
- the demo runtime has already seeded anomaly alerts, PO suggestions, model history, and effectiveness evidence
- you are recording this, so the script is written as a continuous explanation rather than a live Q&A

## Full Teleprompter Script

### 0. Technical Thesis
**Action**
- Start on the dashboard
- Keep the whole shell visible for a few seconds

**Say**
"Technically, I did not want ShelfOps to be a forecasting notebook wrapped in a dashboard. I wanted it to behave like a real operating system: tenant-aware APIs, asynchronous workers, auditable model lifecycle, governed promotion, archive and rollback, and product surfaces that make sense for different internal users."

"So in this walkthrough, I am going to explain not just what I built, but how I built it, why I chose this stack, why I chose these models, and how I designed the workflow so it can be trusted rather than just demoed."

### 1. Full Stack Overview
**Action**
- Stay on the dashboard while speaking
- Optionally gesture across the navigation

**Say**
"On the frontend, this is a React and TypeScript application built with Vite. I used React Query for server-state synchronization and Recharts for the dashboard visualizations."

"On the backend, the API layer is FastAPI with async SQLAlchemy against Postgres."

"For asynchronous work, I split forecasting, retraining, monitoring, and other background tasks into Celery workers backed by Redis. I did that because interactive product requests and long-running ML tasks should not compete for the same execution path."

"For broader integration proof, I also included Kafka-compatible event streaming through Redpanda. That was important because I wanted the project to show event-driven ingest capability and not just CSV upload logic."

"On the ML side, the worker environment includes LightGBM, scikit-learn, SHAP, Pandera, and MLflow."

"Each of those choices is pragmatic. FastAPI gives me typed APIs and fast development. Postgres gives me transactional audit trails and strong relational workflows. Celery and Redis are inexpensive and reliable for this scale. LightGBM is a strong fit for tabular retail demand data and much easier to operate than a more fragile deep learning stack."

### 2. Frontend by Internal Role, Not One Generic User
**Action**
- Click through the nav deliberately:
  - Dashboard
  - Alerts
  - Inventory
  - Forecasts
  - Operations
  - ML Ops

**Say**
"One frontend decision I care about is that not every user in a company should have the same view."

"The dashboard is a shared summary surface."

"Alerts, inventory, and forecasts are the more operational pages. Those are for buyers, inventory leads, or store operations."

"Operations is the pilot-support and runtime status surface."

"ML Ops is intentionally deeper. That page is not for a store manager or a general stakeholder. It is for the technical owner or data team."

"I made that distinction because product structure is part of system design. If the UI ignores internal team roles, the product stops feeling believable."

### 3. Backend Design and Tenant Isolation
**Action**
- Click `Operations`
- Keep the runtime status and integration freshness visible
- Optional terminal:

```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/api/v1/integrations/sync-health | jq
```

**Say**
"On the backend, I treated tenant context as a first-class concern."

"Even though this is a portfolio project, I did not want a fake single-tenant demo because inventory, forecasts, contracts, and purchasing are all organization-specific."

"So the API layer uses tenant-scoped access patterns, and the data model is organized around customer-level isolation. That forces cleaner boundaries and makes the system more realistic."

"I also separated the interactive product surface from the asynchronous operational work. Forecasting, retraining, monitoring, and integration handling all belong in worker flows because they should not block the user experience."

"That design choice matters in the product too. The operations page gives a tenant-safe control view for pilot support: open alerts, sync breaches, champion model, last retrain, runtime status, and integration freshness."

"That is what I mean when I say I wanted this to be operable, not just technically interesting."

### 4. Integration Model: Start Simple, Prove More
**Action**
- Click `Integrations`
- Highlight Square
- Mention the broader adapters without overselling them

**Say**
"The integration strategy is intentionally split between product practicality and backend proof."

"For an SMB rollout, I would start with the simplest realistic path, which is Square or CSV-based ingest."

"At the same time, I wanted to show enterprise-style thinking, so the architecture also demonstrates patterns for SFTP, EDI-oriented inputs, and Kafka-style event streams."

"I did that because I wanted the system to show both ends of the problem: how to onboard a smaller retailer quickly, and how to design a backend that can eventually absorb more complex data flows."

"Kafka matters here mostly as proof of event-driven engineering ability. I am not claiming every SMB needs Kafka on day one. I am showing that I know how to design for decoupled ingest when the environment requires it."

### 5. Forecasting Model: Why LightGBM, Why This Feature Pipeline
**Action**
- Click `Forecasts`
- Show the trend, category distribution, top products, and explainability section if visible
- Optional API proof:

```bash
curl -s 'http://localhost:8000/api/v1/ml/effectiveness?window_days=30&model_name=demand_forecast' | jq
```

**Say**
"The live forecast path is LightGBM-first."

"I chose LightGBM because this is a tabular retail demand problem, and the practical requirements are strong baseline performance, low compute cost, fast training, explainability, and easy serving."

"I care more about a model that is reliable and governable than one that is more complex but harder to justify operationally."

"The baseline objective is Poisson because demand is count-like, and I wanted the model objective to better fit the problem than a generic squared-error setup."

"The feature pipeline is tiered. There is a cold-start tier for limited data environments and a richer production tier for customers with more complete inventory, product, and store context."

"That matters because new customers and mature customers do not have the same signal richness. I wanted the system to respect that instead of pretending every deployment starts with perfect data."

"At inference time, the worker now respects the model's trained feature tier and only falls back if the required runtime context is actually unavailable. That was an important fix because the runtime story should match the training story."

"On top of the raw forecast, I also apply business rules. That includes promotion lift, seasonal adjustment, new-item handling, and a perishable cap."

"I built that layer because raw prediction quality and operational safety are not the same thing. A retail system has to support decisions, not just output numbers."

"One truth boundary I keep explicit in the demo is that the per-forecast explainability panel is a deterministic demo proxy for repeatable walkthroughs. It is useful for showing how I designed the trust surface, but I do not present it as a live production TreeExplainer running on every click."

### 6. Why Forecasting and Anomaly Detection Are Separate
**Action**
- Click `Alerts`
- Highlight an anomaly-backed alert
- Optional terminal proof:

```bash
curl -s 'http://localhost:8000/api/v1/alerts?alert_type=anomaly_detected&status=open' | jq
curl -s 'http://localhost:8000/api/v1/ml/anomalies?days=7&limit=5' | jq
```

**Say**
"I treat forecasting and anomaly detection as separate model problems because they answer different operational questions."

"Forecasting answers: what do I expect demand to be?"

"Anomaly detection answers: what looks unusual right now, even if it does not fit the normal forecast cycle?"

"For anomaly detection, I used Isolation Forest over features like recent sales behavior, inventory on hand, unit price, stock turnover, day of week, holiday context, and price versus category average."

"I chose Isolation Forest because the anomaly problem is largely unsupervised in a system like this. I do not have a perfect labeled anomaly dataset, so I wanted a fast, practical, low-cost method that can still surface unusual behavior reliably."

"Then I route those anomalies into the standard alerts workflow because a model output only becomes useful when an operator can act on it."

### 7. Human-in-the-Loop Purchase Decisions
**Action**
- Switch to terminal
- Run:

```bash
curl -s http://localhost:8000/api/v1/purchase-orders/suggested | jq
cat docs/productization_artifacts/demo_runtime/demo_runtime_summary.json | jq
```

Optional:

```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/approve" \
  -H "Content-Type: application/json" \
  -d '{}'
```

```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/reject" \
  -H "Content-Type: application/json" \
  -d '{"reason_code":"forecast_disagree","notes":"Demo rejection path"}'
```

**Say**
"This is where the ML layer connects to actual operations."

"The system can recommend purchase orders, but I intentionally kept a human approval path because a forecast is only one input to a real replenishment decision."

"Vendor timing, budget constraints, space, promotions, and local context all matter."

"So instead of treating human review as a temporary workaround, I made it part of the product."

"That also helps the ML lifecycle, because approvals, edits, and rejections create structured feedback the system can later learn from."

"In other words, this is not just a forecast app. It is an auditable decision-support workflow."

### 8. Experiment Workflow: How Model Iteration Is Tracked
**Action**
- Click `ML Ops`
- Open the `Experiments` tab
- Show the experiment workbench
- Optional API proof:

```bash
curl -s http://localhost:8000/experiments?limit=10 | jq
```

**Say**
"One MLOps decision I cared about was not letting model iteration turn into an untracked notebook habit."

"So I built an experiment workflow where a hypothesis is proposed, typed, reviewed, and completed with a recorded decision."

"The experiment taxonomy matters. The system distinguishes architecture changes, feature-set changes, hyperparameter tuning, data-contract changes, segmentation experiments, objective-function changes, post-processing changes, rollback events, and baseline refreshes."

"That gives the model lifecycle real auditability. You can tell not just that a version changed, but what kind of change it actually was and why."

"This is also the workflow I would use for an SMB customer. Log the hypothesis, run the challenger, compare it to the baseline, and make a governed decision instead of shipping changes informally."

### 9. Promotion Gates: Business-Safe, Not Metric Vanity
**Action**
- Stay on `ML Ops`
- Go back to the `Models` tab
- Highlight:
  - champion cards
  - governance scorecard
  - model arena
  - model lineage table

Optional API proof:

```bash
curl -s http://localhost:8000/api/v1/ml/models/health | jq
curl -s 'http://localhost:8000/api/v1/ml/effectiveness?window_days=30&model_name=demand_forecast' | jq
```

**Say**
"This is where the model governance story becomes concrete."

"A challenger does not get promoted just because one metric got better."

"The promotion policy combines DS gates and business gates."

"On the DS side, the candidate cannot materially degrade MAE, MAPE, WAPE, MASE, bias, or coverage."

"On the business side, it also has to clear stockout miss, overstock rate, lost sales quantity, stockout opportunity cost, overstock opportunity cost, and overstock dollars gates."

"The policy fails closed if the required business inputs are missing, because I do not want a statistically cleaner model promoted if the economic picture is incomplete."

"There are also concrete thresholds. MAE and MAPE are allowed at most two percent degradation. Stockout miss and overstock rate are allowed at most half a percentage point drift. And overstock dollars has to improve by at least one percent, or stay nearly flat while stockout cost improves."

"That is important because model selection should reflect business safety, not just benchmark vanity."

### 10. Archive, Rollback, and Why Lineage Matters
**Action**
- Keep the model lineage table visible
- If available, point to archived entries or recent lifecycle history

**Say**
"Another choice I care about is that the old champion is archived, not deleted."

"If a promoted challenger later regresses badly, I want a clean rollback path to a known prior version."

"That is why the lineage table, lifecycle events, and archive state exist."

"Rollback should be a first-class operating path, not an emergency scramble."

"This is one of the reasons I think of the platform as a governed system rather than a set of model files."

### 11. Shadow Evaluation, Retriggers, and Runtime Monitoring
**Action**
- Click `Operations`
- Highlight:
  - drift detected
  - new data waiting
  - challenger eligible
  - last retrain
  - WAPE / MASE / opportunity cost

**Say**
"To me, MLOps is not just training automation. It is operating behavior."

"The system tracks retraining triggers such as scheduled refreshes, drift, new data, and manual retrains."

"New versions can enter challenger evaluation rather than silently replacing the champion."

"The runtime health view is important because if I were supporting an SMB pilot, I would need a fast answer to basic questions: Is the pipeline healthy? Is there drift? Is there new data waiting? Is the challenger eligible? What does recent performance look like?"

"That is why the operations page exists. It turns technical model state into something a human operator can manage."

### 12. Honest Close
**Action**
- Keep the Operations or ML Ops page open
- Stop moving the mouse for the final lines

**Say**
"Today, what is live is a truthful end-to-end system: tenant-aware APIs, async workers, forecasting, anomaly detection, alert triage, human-reviewed purchasing, experiment governance, business-safe promotion, archive, rollback, and operator visibility."

"Pilot next means continuing model iteration with real challenger evidence, tightening integration resilience, and strengthening release validation for a first Square or CSV-first SMB rollout."

"Later is deeper enterprise hardening, richer uncertainty modeling, and broader integration expansion."

"What I wanted this walkthrough to prove is that I can build and explain the full lifecycle around ML, not just the model itself."

"If you have any questions, please feel free to contact me. I would be glad to answer them."

## Terminal Appendix
Use this only if you want a short proof block at the end:

```bash
curl -s http://localhost:8000/api/v1/integrations/sync-health | jq
curl -s http://localhost:8000/api/v1/ml/models/health | jq
curl -s 'http://localhost:8000/api/v1/ml/effectiveness?window_days=30&model_name=demand_forecast' | jq
curl -s 'http://localhost:8000/api/v1/alerts?alert_type=anomaly_detected&status=open' | jq
curl -s 'http://localhost:8000/api/v1/ml/anomalies?days=7&limit=5' | jq
curl -s 'http://localhost:8000/experiments?limit=10' | jq
```

Optional worker proof:

```bash
docker compose logs --no-color --tail=80 ml-worker
docker compose logs --no-color --tail=80 api
```

## Truth Boundaries
- Do not call the system fully autonomous ordering.
- Do not imply enterprise GA readiness.
- Do not imply universal real-time streaming behavior.
- Do say the system demonstrates enterprise-grade patterns and governed ML operations.
- Do say the seeded demo runtime includes modeled business metrics rather than claiming live customer economics.
