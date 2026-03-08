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

## Demo Narrative (10-15 min)

1. Problem and product intent (`implemented`).
2. Contract-driven onboarding and governance (`implemented`).
3. Forecast lifecycle and promotion controls (`implemented`).
4. Enterprise positioning boundary (`pilot_validated` + `blocked` for GA).

## What To Emphasize By Audience

### Recruiter
- End-to-end ownership
- practical business problem
- technical depth without overclaiming

### Hiring manager: MLOps / ML engineer
- retrain/forecast/monitor loop
- reliability and validation gates
- separation of queues, triggers, and promotion controls

### Hiring manager: DS / applied ML
- why the model exists in a retail workflow
- how decisions feed back into features
- why LightGBM is the current operating choice

### SMB owner / pilot discussion
- fewer manual decisions
- visibility + guided ordering
- humans stay in control
- onboarding can start from exports and staged integrations

## Required Boundary Statement

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).
