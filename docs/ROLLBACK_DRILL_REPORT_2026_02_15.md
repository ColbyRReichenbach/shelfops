# Rollback Drill Report

_Date: February 15, 2026_

## Drill Objective

Verify that a newly promoted champion can be rolled back to a previous champion version quickly and deterministically.

## Drill Procedure

1. Register `v1` as champion.
2. Register `v2` as candidate.
3. Promote `v2` to champion (expect `v1` archived).
4. Roll back by promoting `v1` again (expect `v2` archived).

## Evidence

- Test: `backend/tests/test_model_rollback_drill.py`
- Command:

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_model_rollback_drill.py -q
```

- Result: `1 passed`

## Outcome

1. Champion rollback path works using existing `promote_to_champion` mechanism.
2. Archive semantics are preserved during rollback.
3. Rollback readiness for model routing is validated at unit/integration-test depth.

## Follow-up

1. Execute the same drill in staging with real worker orchestration enabled.
2. Attach staging run ID/log to `docs/PRODUCTIZATION_TRACKER.md` when complete.
