# ShelfOps Productization Plan (Execution-Ready)

_Last updated: February 15, 2026_

## Goal

Move from pre-production hardening to:

1. SMB launch-candidate reliability.
2. Enterprise pilot-credible technical posture.
3. Senior DS/MLE recruiter-ready evidence quality.

## Locked Strategy

1. SMB-first remains primary delivery objective.
2. Enterprise remains pilot-validation (no broad GA onboarding claim).
3. Model strategy now:
- keep current ensemble/champion path stable,
- tune and govern it with runtime evidence,
- defer portfolio routing until explicit gates pass.

## 6-Week Execution Plan

### Week 1: Governance + Truth Lock

1. Enforce required status checks on `main` in GitHub settings.
2. Freeze readiness language to one canonical board.
3. Verify migration rollout plan for tenant readiness tables.

Exit criteria:

1. Branch protection checks required and documented.
2. Docs aligned to one readiness taxonomy.

### Week 2: Runtime Operations Validation

1. Validate full loop in staging:
- retrain -> forecast generation -> accuracy computation -> promotion gate.
2. Validate Celery multi-tenant dispatcher behavior under active/trial tenants.
3. Confirm incident runbook works with one forced failure simulation.

Exit criteria:

1. End-to-end runtime chain observed and logged.
2. Failure handling path executed with runbook evidence.

### Week 3: Onboarding Reliability

1. Run at least:
- 2 SMB schema onboarding dry runs,
- 1 enterprise-like dry run.
2. Capture artifacts:
- `contract_validation_report.json/.md`
- `column_lineage_map.json`
- `canonical_schema_snapshot.json`
3. Confirm `requires_custom_adapter` boundary behavior on non-representable schema.

Exit criteria:

1. All representable mappings onboard without code changes.
2. Non-representable case fails explicitly with reason.

### Week 4: SLO + Reliability Hardening

1. Define and publish SLOs:
- forecast freshness,
- accuracy-job freshness,
- sync-health freshness.
2. Add alerting thresholds and escalation path references.
3. Run rollback drill for challenger regression.

Exit criteria:

1. SLOs and escalation ownership documented.
2. Rollback workflow verified.

### Week 5: Model Effectiveness Iteration

1. Tune current champion path first (single + ensemble weights).
2. Include explicit weight sweep:
- `xgboost_weight`: 1.0 -> 0.0
- `lstm_weight`: complementary
3. Promote only through DS + business gate policy.

Exit criteria:

1. Best model choice justified by business + DS metrics.
2. Promotion decision artifact logged.

### Week 6: Recruiter Evidence Finalization

1. Update:
- `docs/ML_EFFECTIVENESS_REPORT.md`
- `docs/PRODUCTION_DECISION_LOG.md`
- `docs/ENTERPRISE_VS_SMB_ARCHITECTURE_BRIEF.md`
2. Run technical + recruiter demo scripts from repo docs.
3. Publish final “what is production-ready now” summary.

Exit criteria:

1. Non-technical and technical narratives point to the same evidence.
2. No unverified capability claim remains.

## Portfolio Migration Gate (Do Not Skip)

Only move to full model portfolio routing when all are true:

1. Productization weeks 1-4 are complete.
2. At least 2-3 tenants have stable runtime metric windows.
3. Challenger improvements repeat across multiple windows.
4. Ops team has rollback confidence for per-segment routing.

Until then, keep:

1. Stable champion path (current ensemble or XGBoost-only if it wins).
2. New candidates in shadow/challenger mode.

## Dependencies

1. GitHub branch protection access (manual setting).
2. Staging environment access for worker and scheduler validation.
3. Tenant-like sample schemas for onboarding dry runs.
