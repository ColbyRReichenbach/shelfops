# ShelfOps Known Issues

- Last verified date: February 15, 2026
- Audience: engineering and operations
- Scope: active unresolved items only
- Source of truth: this file

## P0

1. Branch protection enforcement for required checks is not guaranteed from code alone (`partial`).
2. Staging-style runtime evidence should continue to be refreshed each release cycle (`partial`).

## P1

1. Frontend bundle size optimization remains pending (`partial`).
2. Additional tenant telemetry depth is needed for broader model confidence (`partial`).

## Deferred

1. Square normalization and mapping depth expansion (`partial`, deferred priority).
2. Broad enterprise onboarding availability (`blocked`, non-GA policy).

## Recently Closed (Examples)

- API namespace normalization and deprecation headers (`implemented`).
- Promotion gate fail-closed behavior (`implemented`).
- Model registry/champion artifacts synchronized to runtime DB lifecycle in retrain flow (`implemented`).
- Enterprise seed validation and integration test coverage (`pilot_validated`).
