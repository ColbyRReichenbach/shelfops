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
| PZ-001 | Week 1 | Enforce required checks on `main` branch protection | `blocked` | `docs/PRODUCTIZATION_EVIDENCE_INDEX.md` (Week 1), GitHub settings screenshot/link | owner |
| PZ-002 | Week 1 | Align readiness language to canonical board | `done` | `docs/PRODUCTION_READINESS_BOARD.md` | owner |
| PZ-003 | Week 1 | Validate migration rollout for readiness tables | `done` | `docs/PRODUCTIZATION_EVIDENCE_INDEX.md` (Week 1), `docs/productization_artifacts/migration_rollout_validation.md` | owner |
| PZ-004 | Week 2 | Stage run: retrain -> forecast -> accuracy -> promotion | `done` | `docs/PRODUCTIZATION_EVIDENCE_INDEX.md` (Week 2), `docs/productization_artifacts/staging_runtime_chain_validation.md` | owner |
| PZ-005 | Week 2 | Validate multi-tenant dispatch fan-out | `done` | `backend/tests/test_scheduler_dispatch.py`, `docs/PRODUCTIZATION_EVIDENCE_INDEX.md` | owner |
| PZ-006 | Week 2 | Incident simulation + runbook validation | `done` | `backend/tests/test_contracts.py`, `docs/INTEGRATION_INCIDENT_RUNBOOK.md`, `docs/PRODUCTIZATION_EVIDENCE_INDEX.md` | owner |
| PZ-007 | Week 3 | SMB onboarding dry run #1 | `done` | `docs/productization_artifacts/smb_tenant_a/*`, `docs/PRODUCTIZATION_EVIDENCE_INDEX.md` | owner |
| PZ-008 | Week 3 | SMB onboarding dry run #2 | `done` | `docs/productization_artifacts/smb_tenant_b/*`, `docs/PRODUCTIZATION_EVIDENCE_INDEX.md` | owner |
| PZ-009 | Week 3 | Enterprise-like onboarding dry run | `done` | `docs/productization_artifacts/enterprise_like/*`, `docs/PRODUCTIZATION_EVIDENCE_INDEX.md` | owner |
| PZ-010 | Week 3 | Non-representable schema boundary test | `done` | `backend/tests/test_contract_mapper.py` | owner |
| PZ-011 | Week 4 | Define/publish runtime SLOs | `done` | `docs/OPERATIONS_SLO.md` | owner |
| PZ-012 | Week 4 | Rollback drill for challenger regression | `done` | `docs/ROLLBACK_DRILL_REPORT_2026_02_15.md`, `backend/tests/test_model_rollback_drill.py` | owner |
| PZ-013 | Week 5 | Ensemble-vs-single tuning cycle completed | `done` | `docs/productization_artifacts/model_strategy_cycle.*` | owner |
| PZ-014 | Week 5 | Promotion decision recorded with business + DS gate | `done` | `docs/MODEL_STRATEGY_DECISION_2026_02_15.md` | owner |
| PZ-015 | Week 6 | Recruiter evidence docs refreshed | `done` | `docs/ML_EFFECTIVENESS_REPORT.md`, `docs/PRODUCTION_DECISION_LOG.md`, `docs/ENTERPRISE_VS_SMB_ARCHITECTURE_BRIEF.md` | owner |
| PZ-016 | Week 6 | Final production-ready statement published | `done` | `README.md`, `docs/PRODUCTION_READINESS_BOARD.md`, `docs/RELEASE_READINESS.md` | owner |
| PZ-017 | Week 6 | Time-travel replay framework (holdout + HITL + strategy gate) | `done` | `backend/scripts/run_replay_simulation.py`, `docs/DEMO_REPLAY_RUNBOOK.md`, `docs/productization_artifacts/replay_summary.md` | owner |
| PZ-018 | Week 6 | Replay partition contract enforcement in training/retraining paths | `done` | `backend/ml/replay_partition.py`, `backend/scripts/run_training.py`, `backend/workers/retrain.py`, `backend/tests/test_replay_partition.py` | owner |
