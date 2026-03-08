# ShelfOps Technical Walkthrough

## Audience
Use this walkthrough for:
- ML engineers
- MLOps interviewers
- DS hiring managers
- engineering managers
- technical founders

## Goal
Prove these:
1. You built an end-to-end system, not just a model.
2. You understand backend boundaries, tenant-aware design, and operational reliability.
3. You understand MLOps as monitoring, retraining, and governance, not just training.
4. Your technical choices are pragmatic and defensible.

## Technical Framing
Use this up front:

> From a technical perspective, I did not want this to be just a forecasting demo. I wanted to show an end-to-end system: ingestion, tenant isolation, operational workflows, model lifecycle, experiment governance, and auditability.

## Runtime Prep
Before the walkthrough:

```bash
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
```

Optional terminal proof:

```bash
PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py
```

## Suggested Timing
1. 0:00-1:00 Technical framing.
2. 1:00-4:00 Architecture and stack.
3. 4:00-7:00 Multi-tenant and backend design.
4. 7:00-10:00 Integrations including Kafka/event-stream capability.
5. 10:00-13:00 Forecasting plus business logic.
6. 13:00-17:00 MLOps operating loop.
7. 17:00-20:00 Model choice and tradeoffs.

## Script

### 0:00-1:00 | Technical Framing
Say:
- "From a technical perspective, I did not want this to be just a forecasting demo."
- "I wanted to show an end-to-end system: ingestion, tenant isolation, operational workflows, model lifecycle, experiment governance, and auditability."

### 1:00-4:00 | Architecture Overview
Talk through:
- frontend for operator workflows
- FastAPI backend for product and control-plane APIs
- Postgres-backed multi-tenant data model
- Celery workers for background orchestration
- Redis for queueing/caching support
- ML worker and model lifecycle layer
- Redpanda/Kafka path to demonstrate event-driven integration capability

Say:
- "The product surface looks simple, but the backend is intentionally layered."
- "I separated interactive product workflows from asynchronous operational tasks because that is how these systems stay reliable."
- "I wanted to show I understand the difference between demo UI and production-oriented backend design."

### 4:00-7:00 | Multi-Tenant and Security Thinking
Talk through:
- tenant-scoped database access
- org-level separation
- why multi-tenant context matters early

Say:
- "Even though this is a portfolio project, I designed around tenant isolation because inventory data is inherently organization-specific."
- "That forced cleaner API patterns and makes the system more realistic than a single-tenant demo."
- "It also shows that I was thinking beyond just getting the feature working."

### 7:00-10:00 | Data Ingestion and Enterprise Logic
Talk through:
- Square-first practical path
- staged EDI/SFTP/Kafka integration breadth
- why Kafka was included

Say:
- "For SMBs, onboarding may start from exports or simpler POS data."
- "But I also wanted to prove I could design for enterprise-style ingestion paths."
- "Kafka is especially useful here because it demonstrates event-driven thinking, decoupled ingest, and near-real-time integration patterns."
- "That is one reason this project is relevant for ML Ops, data engineering, and analytics engineering conversations."

Show:

```bash
curl -s http://localhost:8000/api/v1/integrations/sync-health | jq
```

### 10:00-13:00 | Forecasting, Business Logic, and Why AI Is Only Part of the System
Talk through:
- forecasts are generated, but business rules shape actionability
- reorder thresholds, safety stock, lead time, approval logic
- human override is deliberate

Say:
- "I do use ML, but I do not treat ML as the whole solution."
- "Retail inventory decisions live at the intersection of predictions and operational constraints."
- "That is why the platform includes thresholds, reorder logic, approval workflows, and reason-coded overrides."
- "A useful inventory system has to respect business logic, not just maximize model elegance."

### 13:00-17:00 | MLOps Operating Loop
Talk through:
- champion/challenger model states
- model health endpoint
- drift detection
- retraining logs
- experiment approval and completion flow

Show:

```bash
curl -s http://localhost:8000/api/v1/ml/models/health | jq
curl -s 'http://localhost:8000/ml-alerts?limit=5' | jq
curl -s 'http://localhost:8000/experiments?limit=10' | jq
```

Optional worker/log proof:

```bash
docker compose logs --no-color --tail=80 ml-worker
docker compose logs --no-color --tail=80 sync-worker
```

Say:
- "This is what I mean by MLOps in practice: monitored models, retraining triggers, audit logs, and governed promotion decisions."
- "I wanted to move beyond 'I trained a model' into 'I built a controllable ML system.'"
- "That is also why experiments are first-class objects here instead of informal notebook changes."

### 17:00-20:00 | Model Choice and Tradeoffs
Say:
- "The current default path is LightGBM-first because it is a practical choice for tabular retail demand data."
- "I care more about reliability, feature support, and operational simplicity than chasing a flashy model that is harder to run."
- "If I kept iterating, model improvement would come from better features, better per-tenant signals, and cleaner evaluation loops, not only architecture changes."

If asked why not something more complex:
- "Because complexity has to earn its keep. In this domain, deployability and controllability matter."

## Questions to Expect
- Why LightGBM?
- Why human review?
- Why Kafka for an SMB-facing product?
- How does retraining get triggered?
- How would you harden this for production?
- What would you improve next on the model side?
