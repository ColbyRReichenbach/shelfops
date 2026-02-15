# ShelfOps Recruiter Demo Runbook

- Last verified date: February 15, 2026
- Audience: recruiters, hiring managers, interviewers
- Scope: one-command demo, replay evidence, and talking points
- Source of truth: `backend/scripts/run_recruiter_demo.py`, replay scripts, active readiness docs

## One-Command Demo

```bash
PYTHONPATH=backend python3 backend/scripts/run_recruiter_demo.py --quick
```

## Expected Outputs

- Recruiter demo scorecard outputs: `pilot_validated`
- Replay summary and strategy artifacts: `pilot_validated`
- Runtime reliability framing anchored to active readiness docs: `implemented`

## Demo Narrative (10-15 min)

1. Problem and product intent (`implemented`).
2. Contract-driven onboarding and governance (`implemented`).
3. Forecast lifecycle and promotion controls (`implemented`).
4. Enterprise positioning boundary (`pilot_validated` + `blocked` for GA).

## Required Boundary Statement

Enterprise integration paths are in production code and validated in deterministic tests, but enterprise onboarding is not commercially available (non-GA).
