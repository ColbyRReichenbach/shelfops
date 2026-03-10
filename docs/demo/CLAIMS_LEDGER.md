# Claims Ledger (Audit Map)

Use this file as the source of truth for demo, resume, and hiring-manager claims.

## Implemented (Safe To Claim)

| Claim | Status | Evidence |
|---|---|---|
| HITL PO workflow exists (approve/reject/receive + decision history) | implemented | `backend/api/v1/routers/purchase_orders.py:210`, `backend/api/v1/routers/purchase_orders.py:269`, `backend/api/v1/routers/purchase_orders.py:311`, `backend/api/v1/routers/purchase_orders.py:395` |
| Planner identity is captured in PO decision rows | implemented | `backend/api/v1/routers/purchase_orders.py:251`, `backend/api/v1/routers/purchase_orders.py:260`, `backend/api/v1/routers/purchase_orders.py:293`, `backend/api/v1/routers/purchase_orders.py:302` |
| Model ops endpoints exist for health/models/backtests/registry/effectiveness | implemented | `backend/api/v1/routers/ml_ops.py:37`, `backend/api/v1/routers/ml_ops.py:108`, `backend/api/v1/routers/ml_ops.py:205`, `backend/api/v1/routers/ml_ops.py:234`, `backend/api/v1/routers/ml_ops.py:293` |
| Champion/challenger health + manual promotion endpoints exist | implemented | `backend/api/v1/routers/models.py:61`, `backend/api/v1/routers/models.py:272`, `backend/api/v1/routers/models.py:390` |
| ML alert review workflow exists (list/stats/read/action) | implemented | `backend/api/v1/routers/ml_alerts.py:41`, `backend/api/v1/routers/ml_alerts.py:98`, `backend/api/v1/routers/ml_alerts.py:185`, `backend/api/v1/routers/ml_alerts.py:228` |
| Alerts-centered anomaly workflow exists (standard alerts + anomaly detail API) | implemented | `backend/api/v1/routers/alerts.py:51`, `backend/api/v1/routers/anomalies.py:29`, `backend/db/models.py:392`, `backend/db/models.py:564` |
| Experiment lifecycle endpoints exist (propose/approve/reject/complete) | implemented | `backend/api/v1/routers/experiments.py:168`, `backend/api/v1/routers/experiments.py:231`, `backend/api/v1/routers/experiments.py:289`, `backend/api/v1/routers/experiments.py:337` |
| Planner feedback signals are integrated into training and inference feature generation | implemented | `backend/ml/feedback_loop.py:29`, `backend/ml/features.py:457`, `backend/workers/retrain.py:661`, `backend/workers/forecast.py:236` |
| Shadow prediction loop is active (champion vs challenger logged, later reconciled with actuals) | implemented | `backend/workers/forecast.py:341`, `backend/workers/monitoring.py:503` |
| Drift monitoring is champion-version-specific and can trigger retraining | implemented | `backend/workers/monitoring.py:53`, `backend/workers/monitoring.py:82`, `backend/workers/monitoring.py:147` |
| Multi-tenant scheduled orchestration exists | implemented | `backend/workers/celery_app.py:38`, `backend/workers/scheduler.py:20`, `backend/workers/scheduler.py:52`, `backend/workers/scheduler.py:62` |
| Contract-driven onboarding/validation path exists | implemented | `backend/scripts/validate_customer_contract.py:183`, `backend/scripts/run_onboarding_flow.py:20`, `backend/ml/contract_profiles.py:19`, `backend/ml/contract_mapper.py:241` |
| Registry/champion artifacts are persisted in repo files | implemented | `backend/models/registry.json`, `backend/models/champion.json` |

## Partial (Claim Only With Caveat)

| Claim | Status | Safe Wording | Evidence |
|---|---|---|---|
| Data ingestion from integrations | partial | "OAuth/webhook entry points and sync health checks exist; full event processors are not complete." | `backend/api/v1/routers/integrations.py:176`, `backend/api/v1/routers/integrations.py:200`, `backend/api/v1/routers/integrations.py:234` |
| ML health endpoint | partial | "Health is based on champion + recent backtest checks; not a full SLO/SLA monitor." | `backend/api/v1/routers/ml_ops.py:234`, `backend/api/v1/routers/ml_ops.py:281` |

## Do Not Claim Yet

- "Fully automated end-to-end integration processing for all provider events."
- "Fully autonomous online learning with no approval gates or governance."
- "Enterprise SLA-grade validation/performance guarantees."
- "Universal model performance guarantees across retailer datasets."

## Test Evidence Commands

- `PYTHONPATH=backend python3 -m pytest backend/tests/test_purchase_orders_api.py -q`
- `PYTHONPATH=backend python3 -m pytest backend/tests/test_ml_effectiveness_api.py -q`
- `PYTHONPATH=backend python3 -m pytest backend/tests/test_arena_promotion_gates.py -q`
- `PYTHONPATH=backend python3 -m pytest backend/tests/test_feedback_shadow_loops.py -q`
- `PYTHONPATH=backend python3 -m pytest tests/test_enterprise_integrations.py -q`
- `npm --prefix frontend run lint && npm --prefix frontend run build`

## Rule

If a claim is not listed above with specific evidence, do not use it in slides, video, outreach, or interviews.
