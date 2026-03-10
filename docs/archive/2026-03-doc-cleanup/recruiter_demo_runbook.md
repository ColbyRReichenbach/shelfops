# ShelfOps Recruiter and Hiring-Manager Demo Runbook

- Last verified date: March 8, 2026
- Audience: recruiters, hiring managers, interviewers, pilot-stage SMB conversations
- Scope: entry-point demo package, audience framing, and recommended live paths
- Source of truth: `backend/scripts/run_recruiter_demo.py`, replay scripts, active readiness docs

## One-Command Demo

```bash
PYTHONPATH=backend python3 backend/scripts/run_recruiter_demo.py --quick
```

## Expected Outputs

- Recruiter demo scorecard outputs: `pilot_validated`
- Replay summary and strategy artifacts: `pilot_validated`
- Runtime reliability framing anchored to active readiness docs: `implemented`

## Positioning Anchor

Use this line early:

> ShelfOps is a product for SMB retailers built with enterprise-grade backend and MLOps patterns.

Explain it in plain terms:
- SMB product: inventory teams still doing manual replenishment, spreadsheet review, and reactive ordering
- Enterprise-grade project: multi-tenant security, queue-separated workers, auditable model lifecycle, and integration breadth that prove production thinking

## Recommended Demo Structure

Do not use the same track for every audience.

### Business Walkthrough
Use for recruiters, SMB owners, and broad hiring-manager screens.

Flow:
1. Problem and why you built it from retail experience.
2. Platform walkthrough: dashboard, alerts, inventory, forecasts, integrations.
3. HITL purchase-order decisions as proof this is workflow software, not just analytics.
4. SMB value proposition and close.

### Technical Walkthrough
Use after interest is established or when speaking with technical interviewers.

Flow:
1. Architecture and stack.
2. Multi-tenant security and backend design.
3. Integration breadth including Kafka/event-driven capability.
4. Forecasting + business-rule layer.
5. MLOps loop: health, drift, retraining, experiments, promotion controls.
6. Model-choice tradeoffs and next improvements.

## What To Emphasize By Audience

### Recruiter
- End-to-end ownership
- practical business problem
- technical depth without overclaiming
- ability to translate technical work into business value

### Hiring manager: MLOps / ML engineer
- retrain/forecast/monitor loop
- reliability and validation gates
- separation of queues, triggers, and promotion controls
- event-driven integration capability including Kafka path

### Hiring manager: DS / applied ML
- why the model exists in a retail workflow
- how decisions feed back into features
- why LightGBM is the current operating choice
- business logic and human review are part of the system design, not exceptions

### SMB owner / pilot discussion
- fewer manual decisions
- visibility + guided ordering
- humans stay in control
- onboarding can start from exports and staged integrations
- enterprise logic exists behind the scenes without forcing enterprise complexity on the buyer

## Required Boundary Statement

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).
