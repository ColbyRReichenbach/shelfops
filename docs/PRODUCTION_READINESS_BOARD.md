# ShelfOps Production Readiness Board

_Last updated: February 15, 2026_

## Status Taxonomy

- `implemented`: Built, test-covered, and running in primary workflow.
- `pilot_validated`: Built and validated with deterministic fixtures/simulations, but not broad production onboarding.
- `partial`: Present but gated by data sufficiency, calibration, or rollout controls.
- `blocked`: Not acceptable for production claim until explicit dependency is closed.

## Current Production Statement

- ShelfOps is in **pre-production hardening**.
- **SMB/mid-market workflows are launch target**.
- Enterprise integrations are **pilot-validation depth** (not broad enterprise GA onboarding).
- Public datasets are development assets; production calibration claims require tenant telemetry.

## Capability Board

| Capability | Status | Evidence | Notes |
|---|---|---|---|
| Forecast train/register loop | `implemented` | `backend/workers/retrain.py`, `backend/tests/test_arena_promotion_gates.py` | Champion/challenger registration active. |
| Runtime forecast generation | `implemented` | `backend/workers/forecast.py` | Daily + post-retrain generation writes `demand_forecasts`. |
| Runtime forecast accuracy loop | `implemented` | `backend/workers/monitoring.py`, `backend/tests/test_forecasts_api.py` | Accuracy rows written from realized demand. |
| Promotion gate (DS + business) | `implemented` | `backend/ml/arena.py`, `backend/tests/test_arena_promotion_gates.py` | Fail-closed on missing required gate inputs. |
| Promotion precondition on sample sufficiency | `implemented` | `backend/workers/retrain.py` | Blocks promotion when candidate/champion windows lack minimum samples. |
| Tenant ML readiness state machine | `implemented` | `backend/ml/readiness.py`, `backend/db/models.py`, `backend/tests/test_readiness_state_machine.py` | `cold_start -> warming -> production_tier_candidate -> production_tier_active`. |
| Multi-tenant worker dispatch | `implemented` | `backend/workers/scheduler.py`, `backend/workers/celery_app.py`, `backend/tests/test_scheduler_dispatch.py` | Beat jobs fan out across active/trial tenants. |
| Contract-driven schema-flex onboarding | `implemented` | `backend/ml/contract_profiles.py`, `backend/ml/contract_mapper.py`, `backend/scripts/validate_customer_contract.py` | Added representable vs `requires_custom_adapter` boundary. |
| Onboarding artifact package | `implemented` | `backend/scripts/validate_customer_contract.py`, `backend/workers/retrain.py` | Emits validation report + canonical schema snapshot + lineage map. |
| Enterprise EDI path (`846/850/856/810`) | `pilot_validated` | `backend/tests/test_edi_worker_e2e.py`, `backend/tests/test_sync_worker_pipeline.py` | Fixture deterministic, pilot-style credibility. |
| Branch protection enforcement on `main` | `blocked` | GitHub repo settings (manual) | Required checks must be enforced in GitHub UI. |

## Claim Policy

1. Every metric claim must point to a reproducible artifact (test output, report, or source file).
2. Any feature without evidence is downgraded to `partial` or `blocked`.
3. Enterprise wording remains pilot-validation unless onboarding breadth is demonstrated with live partner data.

## Required Checks on `main` (Target)

- `enterprise-seed-validation`
- `postgres-parity`
- `edi-fixture-e2e`
- `contract-validation-suite`
- `backend-test`
- `backend-lint`
- `frontend-lint`
- `frontend-build`
