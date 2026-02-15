# Productization Tracker

_Last updated: February 15, 2026_

## Status Legend

- `open`
- `in_progress`
- `blocked`
- `done`

## Tracker

| id | workstream | task | status | evidence | owner |
|---|---|---|---|---|---|
| PZ-001 | Week 1 | Enforce required checks on `main` branch protection | `blocked` | GitHub settings screenshot/link | owner |
| PZ-002 | Week 1 | Align readiness language to canonical board | `done` | `docs/PRODUCTION_READINESS_BOARD.md` | owner |
| PZ-003 | Week 1 | Validate migration rollout for readiness tables | `in_progress` | migration run log | owner |
| PZ-004 | Week 2 | Stage run: retrain -> forecast -> accuracy -> promotion | `open` | staging run artifact | owner |
| PZ-005 | Week 2 | Validate multi-tenant dispatch fan-out | `in_progress` | `backend/tests/test_scheduler_dispatch.py` + staging evidence | owner |
| PZ-006 | Week 2 | Incident simulation + runbook validation | `open` | incident test notes | owner |
| PZ-007 | Week 3 | SMB onboarding dry run #1 | `open` | onboarding artifact bundle | owner |
| PZ-008 | Week 3 | SMB onboarding dry run #2 | `open` | onboarding artifact bundle | owner |
| PZ-009 | Week 3 | Enterprise-like onboarding dry run | `open` | onboarding artifact bundle | owner |
| PZ-010 | Week 3 | Non-representable schema boundary test | `done` | `backend/tests/test_contract_mapper.py` | owner |
| PZ-011 | Week 4 | Define/publish runtime SLOs | `open` | SLO doc update | owner |
| PZ-012 | Week 4 | Rollback drill for challenger regression | `open` | drill report | owner |
| PZ-013 | Week 5 | Ensemble-vs-single tuning cycle completed | `open` | tuning run artifact | owner |
| PZ-014 | Week 5 | Promotion decision recorded with business + DS gate | `open` | model promotion log | owner |
| PZ-015 | Week 6 | Recruiter evidence docs refreshed | `in_progress` | `docs/ML_EFFECTIVENESS_REPORT.md` etc. | owner |
| PZ-016 | Week 6 | Final production-ready statement published | `open` | README/docs alignment | owner |
