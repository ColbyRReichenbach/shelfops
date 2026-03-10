# ShelfOps Demo One-Page Cheat Sheet

## Purpose
Use this as the presenter-side quick reference after the full scripts are already internalized.

Primary scripts:
- `docs/demo/BUSINESS_WALKTHROUGH.md`
- `docs/demo/TECHNICAL_WALKTHROUGH.md`

This sheet is not a replacement for those scripts. It is the fast memory aid for:
- opening lines
- page order
- exact proof commands
- non-negotiable claims
- clean close language

## Core Positioning
- Product for SMB, project for enterprise.
- Inventory intelligence for teams still operating manually or through fragmented systems.
- Forecasts matter only because they improve decisions.
- Human review is deliberate, not a missing feature.
- The backend is intentionally more mature than the buyer workflow because simple customer UX should sit on top of disciplined systems.

## Business Walkthrough

### Goal
Prove:
1. you understand the retail problem from lived experience
2. the product is operational, not just analytical
3. SMB value is clear without overclaiming enterprise readiness

### Timing
1. `0:00-1:30` Problem + why you built it
2. `1:30-3:30` Dashboard as shared operating surface
3. `3:30-5:30` Alerts + inventory workflow
4. `5:30-7:00` Forecasts as decision support
5. `7:00-8:00` Integrations and onboarding practicality
6. `8:00-9:30` HITL purchase decisions
7. `9:30-11:00` Team personas and page ownership
8. `11:00-12:00` Today / Pilot next / Later close

### Must-Show Pages
1. Dashboard
2. Alerts
3. Inventory
4. Forecasts
5. Integrations
6. Purchase-order proof

### Must-Say Themes
- 4+ years of retail experience shaped the product.
- Stockouts and inventory distortion are business problems, not just reporting problems.
- Different teams use different pages.
- This system helps smaller retailers operate with more discipline without removing human judgment.

### Business Stats To Use
- AlixPartners: 66% of shoppers likely go elsewhere if the product is out of stock.
- PwC: product availability is the biggest in-store experience factor.
- IHL Group: inventory distortion costs retailers more than $1.7T globally.

Sources:
- `docs/demo/BUSINESS_WALKTHROUGH.md`

## Technical Walkthrough

### Goal
Prove:
1. you built the full system, not just a model
2. your stack choices are pragmatic
3. your MLOps workflow is auditable and business-safe

### Timing
1. `0:00-1:30` Technical thesis
2. `1:30-4:30` Full stack overview
3. `4:30-7:00` Frontend role-based design
4. `7:00-10:30` Backend, tenant isolation, workers, integrations
5. `10:30-14:30` Forecast model, feature tiers, business rules
6. `14:30-16:30` Anomaly model
7. `16:30-18:30` Experiment workflow
8. `18:30-21:00` Promotion gates, archive, rollback, shadowing
9. `21:00-22:30` Operations and retriggers
10. `22:30-24:00` Today / Pilot next / Later close

### Must-Show Pages
1. Dashboard shell
2. Operations
3. Forecasts
4. Alerts
5. ML Ops

### Must-Say Stack
- Frontend: React, TypeScript, Vite, React Query, Recharts
- Backend: FastAPI, async SQLAlchemy, Postgres
- Workers: Celery + Redis
- Event-stream proof: Redpanda/Kafka path
- ML: LightGBM, scikit-learn, SHAP, Pandera, MLflow

### Must-Say Model Story
- Forecasting is LightGBM-first with Poisson objective.
- LightGBM was chosen for tabular retail demand because it is practical, cheap to run, explainable, and reliable.
- Feature tiers are deliberate: cold-start first, richer production tier later.
- Business rules sit on top of forecasts because retail actionability is not just a raw prediction problem.
- Anomaly detection uses Isolation Forest because the problem is unsupervised and speed plus reliability matters more than novelty.

### Must-Say MLOps Story
- Experiments are typed and logged.
- Challengers do not auto-promote.
- Promotion gates combine DS and business metrics.
- Archived champions are retained.
- Rollback is explicit.
- Retriggers include scheduled, drift, new data, and manual refresh paths.

## Exact Proof Commands

### Bring Up
```bash
export MLFLOW_HOST_PORT=5001
docker compose up -d db redis mlflow redpanda api ml-worker
curl -s http://localhost:8000/health | jq
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
```

### HITL PO Proof
```bash
curl -s "http://localhost:8000/api/v1/purchase-orders/suggested?limit=2" | jq
cat docs/productization_artifacts/demo_runtime/demo_runtime_summary.json | jq
```

### MLOps / Runtime Proof
```bash
curl -s http://localhost:8000/api/v1/integrations/sync-health | jq
curl -s http://localhost:8000/api/v1/ml/models/health | jq
curl -s 'http://localhost:8000/api/v1/ml/effectiveness?window_days=30&model_name=demand_forecast' | jq
curl -s 'http://localhost:8000/api/v1/alerts?alert_type=anomaly_detected&status=open' | jq
curl -s 'http://localhost:8000/api/v1/ml/anomalies?days=7&limit=5' | jq
curl -s 'http://localhost:8000/experiments?limit=10' | jq
```

### Worker Appendix
```bash
docker compose logs --no-color --tail=80 ml-worker
docker compose logs --no-color --tail=80 api
```

## Non-Negotiable Truths
- Do not imply enterprise GA readiness.
- Do not call the system real-time streaming if the behavior is scheduled or polled.
- Do not imply fully autonomous ordering.
- Do not oversell model maturity.
- Do say the architecture demonstrates enterprise-grade patterns.

## Best Transition Line
"The business story is the workflow. The technical story is the system design, governance, and operating discipline that make that workflow trustworthy."

## Limitation Line
"The demo runtime is deterministic so the walkthrough is repeatable. Business metrics shown in the MLOps view are modeled estimates from seeded demo evidence, while real customer ownership still relies on tenant-specific contracts, shadow evaluation, and gated promotion."

## Close Line
"Today is a truthful live workflow. Pilot next is operator visibility, integration resilience, and release confidence for a first SMB rollout. Later is broader enterprise hardening and richer model sophistication."
