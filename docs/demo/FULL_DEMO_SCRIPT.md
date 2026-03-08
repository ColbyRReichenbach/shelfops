# ShelfOps Full Demo Script

## 1. Demo Strategy
Do not use one blended script for every audience.

Use two deliberate walkthroughs:
- Business walkthrough: for recruiters, general hiring managers, SMB owners, pilot conversations.
- Technical walkthrough: for engineering managers, ML/MLOps interviewers, data leaders, technical founders.

The business walkthrough should hook fast, stay product-first, and prove you understand retail.
The technical walkthrough should assume interest already exists and then go deep on architecture, ML, MLOps, and tradeoffs.

## 2. Positioning Anchor
Use this early:

> ShelfOps is an inventory intelligence platform for smaller retailers that still operate manually or with fragmented tooling. It helps them move from gut-feel replenishment to auditable, data-backed decisions.

Then add:

> The short version is: product for SMB, project for enterprise.

Meaning:
- Product for SMB: the actual user problem is smaller retail teams that need better inventory visibility, guided replenishment, and less manual spreadsheet work.
- Project for enterprise: the backend was intentionally built with enterprise patterns to prove production thinking, scalability, governance, and integration depth.

## 3. What You Must Prove
Every demo version should prove these:
1. You understand retail operations from real experience, not just from data.
2. You built a usable workflow, not just a model.
3. You know where AI helps and where business logic and human review still matter.
4. You can design production-style backend systems, not only notebooks.
5. You understand MLOps as a controlled operating loop, not just training.

## 4. Opening Hook
Use this structure in the first 60-90 seconds:

1. Problem:
   "A lot of smaller retailers still manage inventory with visual checks, spreadsheets, and reactive ordering."
2. Personal credibility:
   "I spent 4+ years in retail, so I built this from real operating pain points I saw repeatedly."
3. What the product does:
   "ShelfOps brings together inventory visibility, forecasts, alerts, and purchase-order decisions into one workflow."
4. Why it matters:
   "The goal is to reduce stockouts, reduce overstock, and make decisions traceable."
5. Why the project is interesting technically:
   "I built the backend with enterprise-style patterns to show how the same system could scale beyond a small pilot."

## 5. Demo Modes

### Mode A: Business Walkthrough
Use for:
- recruiters
- non-technical hiring managers
- SMB owners
- pilot discussions

Primary goal:
- convince them the product solves a real problem and that you are credible to build it

Secondary goal:
- leave them curious enough to ask for the technical deep dive

Recommended length:
- 10-15 minutes

### Mode B: Technical Walkthrough
Use for:
- ML engineers
- MLOps interviewers
- DS hiring managers
- engineering managers
- technical founders

Primary goal:
- prove architectural judgment, ML systems thinking, and pragmatic tradeoff decisions

Recommended length:
- 15-25 minutes

## 6. Runtime Commands
Prepare deterministic demo state first:

```bash
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
```

Optional terminal proof before live walkthrough:

```bash
PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py
```

If needed:

```bash
export MLFLOW_HOST_PORT=5001
docker compose up -d db redis mlflow redpanda api ml-worker sync-worker celery-beat
curl -s http://localhost:8000/health
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

## 7. Business Walkthrough Script

### 0:00-1:30 | Hook + Why You Built It
Say:
- "I built ShelfOps because smaller retailers often make inventory decisions manually, and that creates the same problems over and over: stockouts, overstock, and bad purchasing decisions."
- "I saw that firsthand over 4+ years in retail, so I wanted to build something that combines domain knowledge with automation instead of replacing operators with a black box."
- "This is meant to feel like intelligent inventory operations software, not just a forecasting model."

What to emphasize:
- you picked the problem from lived experience
- you understand store-level and planning-level pain
- the platform is about decisions, not only predictions

### 1:30-6:30 | Platform Walkthrough
Open `http://localhost:3000`.

#### Dashboard
Say:
- "This is the operating snapshot. If I were managing inventory, this is where I would start the day."
- "I care less about pretty charts and more about what requires action now."

#### Alerts
Say:
- "This is where domain knowledge matters. Retail teams do not need more dashboards; they need a triage queue."
- "The system surfaces issues before they become lost sales or excess stock."

#### Inventory
Say:
- "This is the operational layer. It shows where the inventory posture actually sits at the store and SKU level."
- "For SMBs, this replaces fragmented spreadsheets and reactive checks."

#### Forecasts
Say:
- "The forecast is useful only because it feeds decisions. A forecast by itself does not improve the business."
- "The point is to anticipate demand early enough to influence purchasing."

#### Integrations
Say:
- "This is important because smaller retailers rarely have perfect systems. They usually have partial systems and disconnected data."
- "I built the platform so onboarding can start simple, but the backend still supports broader enterprise-style integrations."

### 6:30-9:00 | Human-in-the-Loop Purchase Decisions
Say:
- "One of the most important design choices here is that humans stay in control."
- "The system suggests orders, but a planner can approve, reject, or edit them with a reason."
- "That matters because retail decisions often depend on vendor timing, shelf capacity, budget, promotions, and local context that raw demand prediction does not fully capture."

Show:

```bash
curl -s http://localhost:8000/api/v1/purchase-orders/suggested | jq
```

Then show one approve/edit path and one reject path using the deterministic IDs from:

```bash
cat docs/productization_artifacts/demo_runtime/demo_runtime_summary.json | jq
```

Suggested talk track while doing it:
- "This is the bridge between AI and operations."
- "I intentionally log reason codes because that creates a feedback loop for later model and policy improvement."

### 9:00-11:00 | Why This Matters to SMBs
Say:
- "If I were pitching this to a pilot customer, the value proposition is straightforward: less manual inventory work, better buying decisions, more visibility, and retained human control."
- "This is not positioned as replacing an ERP. It is positioned as giving smaller teams an intelligence layer they typically do not have."

### 11:00-12:00 | Close
Say:
- "So the business story is simple: this turns inventory from reactive manual work into a more consistent, data-backed workflow."
- "The deeper technical story is where the platform becomes more interesting, because I built the backend and MLOps structure to operate like a much larger system."

Transition line:
- "If useful, I can now walk through how it was actually built and why I made those technical choices."

## 8. Technical Walkthrough Script

### 0:00-1:00 | Technical Framing
Say:
- "From a technical perspective, I did not want this to be just a forecasting demo."
- "I wanted to show an end-to-end system: ingestion, tenant isolation, operational workflows, model lifecycle, experiment governance, and auditability."

### 1:00-4:00 | Architecture Overview
Talk through these areas:
- frontend for operator workflows
- FastAPI backend for product and control-plane APIs
- Postgres-backed multi-tenant data model
- Celery workers for background orchestration
- Redis for queueing/caching support
- ML worker and model lifecycle layer
- Redpanda/Kafka path to demonstrate event-driven integration capability

What to say:
- "The product surface looks simple, but the backend is intentionally layered."
- "I separated interactive product workflows from asynchronous operational tasks because that is how these systems stay reliable."
- "I wanted to show I understand the difference between demo UI and production-oriented backend design."

### 4:00-7:00 | Multi-Tenant and Security Thinking
Talk through:
- tenant-scoped database access
- org-level separation
- why multi-tenant context matters early

What to say:
- "Even though this is a portfolio project, I designed around tenant isolation because inventory data is inherently organization-specific."
- "That forced cleaner API patterns and makes the system more realistic than a single-tenant demo."
- "It also shows that I was thinking beyond 'just get the feature working'."

### 7:00-10:00 | Data Ingestion and Enterprise Logic
Talk through:
- Square-first practical path
- staged EDI/SFTP/Kafka integration breadth
- why Kafka was included

What to say:
- "For SMBs, onboarding may start from exports or simpler POS data."
- "But I also wanted to prove I could design for enterprise-style ingestion paths."
- "Kafka is especially useful here because it demonstrates event-driven thinking, decoupled ingest, and near-real-time integration patterns."
- "That is one reason this project is relevant for ML Ops, data engineering, and analytics engineering conversations."

Good live proof:

```bash
curl -s http://localhost:8000/api/v1/integrations/sync-health | jq
```

### 10:00-13:00 | Forecasting, Business Logic, and Why AI Is Only Part of the System
Talk through:
- forecasts are generated, but business rules shape actionability
- reorder thresholds, safety stock, lead time, approval logic
- human override is deliberate

What to say:
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

Live proof:

```bash
curl -s http://localhost:8000/api/v1/ml/models/health | jq
curl -s 'http://localhost:8000/ml-alerts?limit=5' | jq
curl -s 'http://localhost:8000/experiments?limit=10' | jq
```

If showing workers:

```bash
docker compose logs --no-color --tail=80 ml-worker
docker compose logs --no-color --tail=80 sync-worker
```

What to say:
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

### 20:00-22:00 | Why This Is Strong Hiring Signal
Say:
- "The part I would want a team to notice is not just the model. It is that I can connect business context, backend systems, data pipelines, and ML controls into one coherent product."
- "That makes this relevant across applied ML, MLOps, analytics engineering, and data product work."

## 9. Topics to Emphasize by Audience

### Recruiter
- real problem selection
- end-to-end ownership
- product plus technical depth
- clear communication

### SMB owner
- less manual inventory work
- guided ordering
- visibility without losing human control
- can start with limited data maturity

### Hiring manager, applied ML / DS
- problem framing
- feature and decision logic
- model choice tradeoffs
- experiments tied to business workflows

### Hiring manager, MLOps / ML platform
- workers and queues
- observability and retraining
- governed model lifecycle
- tenant-aware design

### Team lead / engineering manager
- architecture choices
- boundaries between sync and async work
- auditability and maintainability
- integration breadth and production thinking

## 10. Questions You Should Be Ready For
- Why did you choose this problem?
- Why is human review still in the loop?
- Why LightGBM?
- How would you improve model quality next?
- How would onboarding work for a real customer?
- Why build Kafka support for an SMB-facing product?
- What would you change before productionizing this further?

## 11. Best-Practice Notes
- Start broad, then go deep.
- Do not start with code unless explicitly asked.
- Do not lead with model metrics.
- Lead with user pain, workflow, and why the system exists.
- When technical interviewers lean in, then open up the architecture and MLOps story.
- Always keep the line between live capabilities and future hardening clear.
