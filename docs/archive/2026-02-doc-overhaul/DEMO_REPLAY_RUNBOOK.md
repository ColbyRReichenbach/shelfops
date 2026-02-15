# Demo Replay Runbook

## Goal

Run a deterministic time-travel replay on Favorita with a 1-year untouched holdout to demonstrate:

1. Forecast quality under historical replay.
2. Retrain trigger behavior.
3. HITL PO and model-promotion decisions.
4. Strategy decisioning (XGBoost-first, portfolio only if baseline gate fails).

## Prerequisites

- Python dependencies installed for backend.
- Dataset present: `data/kaggle/favorita`.
- Optional quick smoke dataset: `data/seed`.

## One-Command Replay (Favorita)

```bash
cd backend
PYTHONPATH=. python3 scripts/run_replay_simulation.py \
  --dataset-dir ../data/kaggle/favorita \
  --holdout-days 365 \
  --max-replay-days 365 \
  --retrain-cadence weekly \
  --forecast-horizon 14 \
  --portfolio-mode auto \
  --output-dir ../docs/productization_artifacts \
  --dry-run
```

## DB-Persisted Replay (Populate ML Ops Tables)

Use this mode when you want replay output visible in live API queries like
`/api/v1/ml/effectiveness` and `/api/v1/ml/models/health`.

```bash
cd backend
DATABASE_URL=sqlite+aiosqlite:///../docs/productization_artifacts/replay.sqlite3 \
PYTHONPATH=. python3 scripts/run_replay_simulation.py \
  --dataset-dir ../data/seed \
  --holdout-days 30 \
  --max-replay-days 14 \
  --retrain-cadence weekly \
  --portfolio-mode off \
  --db-max-rows-per-day 500 \
  --output-dir ../docs/productization_artifacts
```

Notes:
- Omit `--dry-run` to enable DB writes.
- `--db-max-rows-per-day` caps persisted rows per replay day for fast demos.
- Replay auto-creates missing customer/store/product reference rows with deterministic IDs.

## Fast Smoke Replay (Seed Synthetic)

```bash
cd backend
PYTHONPATH=. python3 scripts/run_replay_simulation.py \
  --dataset-dir ../data/seed \
  --holdout-days 30 \
  --max-replay-days 7 \
  --retrain-cadence weekly \
  --portfolio-mode off \
  --output-dir ../docs/productization_artifacts \
  --dry-run
```

## Artifacts Produced

- Partition manifest: `docs/productization_artifacts/replay_partition_manifest.json`
- Daily replay log: `docs/productization_artifacts/replay_daily_log.jsonl`
- Replay summary JSON: `docs/productization_artifacts/replay_summary.json`
- Replay summary markdown: `docs/productization_artifacts/replay_summary.md`
- HITL decisions: `docs/productization_artifacts/replay_hitl_decisions.json`
- Model strategy decision: `docs/productization_artifacts/replay_model_strategy_decision.md`
- DB persistence summary fields are included in `replay_summary.json` under `db_persistence`.

## Baseline Gate Definition

Replay baseline must pass all:

1. `mape_nonzero <= 0.22`
2. `stockout_miss_rate <= 0.08`
3. `overstock_rate <= 0.55`
4. `critical_failures == 0`

If baseline fails and `--portfolio-mode auto`, challenger weights are evaluated:

- `100/0`
- `90/10`
- `80/20`
- `65/35`

## Troubleshooting

1. `Holdout partition is empty`:
- Verify dataset has at least `holdout_days` of history.

2. Replay runs too slowly:
- Lower `--max-replay-days` for demo.
- Lower `--max-training-rows`.
- Use `--portfolio-mode off`.

3. Portfolio phase unexpectedly skipped:
- Baseline gate passed, or `--portfolio-mode off`.

## Demo Flows

### 10-Minute Version

1. Show `replay_summary.md` and baseline gate result.
2. Show `replay_hitl_decisions.json` sample entries.
3. Show `replay_model_strategy_decision.md`.

### 30-Minute Version

1. Walk through run command and assumptions.
2. Open `replay_daily_log.jsonl` and explain retrain trigger events.
3. Show HITL counts and example decisions.
4. Explain baseline-vs-portfolio branch behavior and final strategy recommendation.
