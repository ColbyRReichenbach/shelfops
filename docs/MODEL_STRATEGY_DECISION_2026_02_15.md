# Model Strategy Decision

_Date: February 15, 2026_

## Cycle Summary

Executed a model strategy cycle on `data/seed` with a lightweight ensemble-vs-single sweep.

Evidence artifacts:

- `docs/productization_artifacts/model_strategy_cycle.json`
- `docs/productization_artifacts/model_strategy_cycle.md`

## Key Results

1. `xgboost_mae`: `36.358488`
2. `lstm_mae`: `55.932977`
3. Best sweep weight by estimated MAE: `xgboost=1.0`, `lstm=0.0`
4. Current heuristic `65/35` underperformed `100/0` in this cycle.

## Decision

1. Recommended serving mode now: `single_xgboost`.
2. Promotion decision this cycle: `hold_as_challenger`.
3. Promotion reason: business metric payload for this cycle is incomplete for promotion gate finalization.

## Implication

1. Keep ensemble capability implemented.
2. For current runtime, use measured strategy evidence rather than fixed heuristic defaults.
3. Re-run this cycle with tenant telemetry before changing production champion defaults.
