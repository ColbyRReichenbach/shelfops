# Demo Replay Scorecard

## Operational Reliability

- Replay status: pass/fail
- Critical failures during replay: count
- Retrain events triggered: count
- Daily log completeness: pass/fail (`replay_daily_log.jsonl`)

## Forecast Effectiveness

- MAE (weighted)
- MAPE non-zero (weighted)
- Stockout miss rate (weighted)
- Overstock rate (weighted)
- Baseline gate result: pass/fail

## HITL Impact

- `po_approve` count
- `po_edit` count
- `po_reject` count
- `model_promote_approve` count
- `model_promote_reject` count
- Decision reason-code distribution

## Governance Outcome

- Champion version at replay end
- Promotion decisions with reason codes
- Trigger event timeline (scheduled/drift)

## Strategy Outcome

- Baseline mode: XGBoost-first
- Portfolio phase executed: yes/no
- Recommended serving weights
- Decision artifact: `docs/productization_artifacts/replay_model_strategy_decision.md`

## Artifact Checklist

- `docs/productization_artifacts/replay_partition_manifest.json`
- `docs/productization_artifacts/replay_daily_log.jsonl`
- `docs/productization_artifacts/replay_summary.json`
- `docs/productization_artifacts/replay_summary.md`
- `docs/productization_artifacts/replay_hitl_decisions.json`
- `docs/productization_artifacts/replay_model_strategy_decision.md`
