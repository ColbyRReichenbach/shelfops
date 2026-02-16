#!/usr/bin/env bash
set -euo pipefail

# Run a one-at-a-time XGBoost manual parameter screen around baseline.
# Designed to launch multiple runs in parallel with safe registry locking.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ITERATE_SCRIPT="$ROOT_DIR/backend/scripts/iterate_model.sh"

DATA_DIR="data/seed"
DATASET="enterprise_seed"
BASELINE="v2_baseline"
PARALLEL=2
RUN_PRETEST=1
AUTO_NOTES=1
DRY_RUN=0
PREFIX="v_manual_$(date +%m%d_%H%M)"

usage() {
  cat <<'EOF'
Usage:
  backend/scripts/manual_xgb_screen.sh [options]

Options:
  --data-dir <path>      Training data path (default: data/seed)
  --dataset <name>       Dataset label (default: enterprise_seed)
  --baseline <version>   Baseline version to compare against (default: v2_baseline)
  --parallel <n>         Parallel workers (default: 2)
  --prefix <str>         Version prefix (default: v_manual_<MMDD_HHMM>)
  --no-pretest           Skip one-time pytest gate before launching batch
  --no-auto-notes        Disable markdown note creation
  --dry-run              Print generated commands only
  --help                 Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-dir)
      DATA_DIR="${2:-}"
      shift 2
      ;;
    --dataset)
      DATASET="${2:-}"
      shift 2
      ;;
    --baseline)
      BASELINE="${2:-}"
      shift 2
      ;;
    --parallel)
      PARALLEL="${2:-}"
      shift 2
      ;;
    --prefix)
      PREFIX="${2:-}"
      shift 2
      ;;
    --no-pretest)
      RUN_PRETEST=0
      shift
      ;;
    --no-auto-notes)
      AUTO_NOTES=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$DATA_DIR" != /* ]]; then
  DATA_DIR="$ROOT_DIR/$DATA_DIR"
fi

if [[ ! -d "$DATA_DIR" ]]; then
  echo "Error: data directory not found: $DATA_DIR" >&2
  exit 1
fi

if [[ ! -f "$ROOT_DIR/backend/models/$BASELINE/metadata.json" ]]; then
  echo "Error: baseline metadata not found: backend/models/$BASELINE/metadata.json" >&2
  exit 1
fi

if [[ "$RUN_PRETEST" -eq 1 ]]; then
  echo "[pretest] Running ML pipeline tests once..."
  (
    cd "$ROOT_DIR"
    PYTHONPATH=backend python3 -m pytest backend/tests/test_ml_pipeline.py -q
  )
fi

declare -a RUNS=(
  "md4|max_depth=4|Shallower trees may reduce overfit"
  "md8|max_depth=8|Deeper trees may improve nonlinear fit"
  "mcw3|min_child_weight=3|Allow finer leaf splits"
  "mcw8|min_child_weight=8|Constrain leaf splits moderately"
  "mcw12|min_child_weight=12|Constrain leaf splits strongly"
  "lr003|learning_rate=0.03|Smaller step size may generalize better"
  "lr008|learning_rate=0.08|Larger step size may fit faster"
  "sub07|subsample=0.7|More row sampling regularization"
  "sub09|subsample=0.9|Less row sampling regularization"
  "col07|colsample_bytree=0.7|More feature sampling regularization"
  "col09|colsample_bytree=0.9|Less feature sampling regularization"
  "rl05|reg_lambda=0.5|Lower L2 regularization"
  "rl30|reg_lambda=3.0|Higher L2 regularization"
)

commands_file="$(mktemp)"
trap 'rm -f "$commands_file"' EXIT

for run in "${RUNS[@]}"; do
  IFS="|" read -r tag param hypothesis <<< "$run"
  version="${PREFIX}_${tag}"

  cmd=(
    "$ITERATE_SCRIPT"
    --data-dir "$DATA_DIR"
    --dataset "$DATASET"
    --version "$version"
    --baseline "$BASELINE"
    --skip-tests
    --xgb-param "$param"
    --hypothesis "$hypothesis"
    --notes "manual_xgb_screen:$tag"
  )

  if [[ "$AUTO_NOTES" -eq 1 ]]; then
    cmd+=(--auto-notes)
  fi

  printf '%q ' "${cmd[@]}" >> "$commands_file"
  printf '\n' >> "$commands_file"
done

echo "Prepared ${#RUNS[@]} runs with prefix '$PREFIX' (parallel=$PARALLEL)."

if [[ "$DRY_RUN" -eq 1 ]]; then
  cat "$commands_file"
  exit 0
fi

running_jobs() {
  jobs -rp | wc -l | tr -d ' '
}

while IFS= read -r cmd; do
  # Respect parallel limit with portable job polling.
  while [[ "$(running_jobs)" -ge "$PARALLEL" ]]; do
    sleep 1
  done
  bash -lc "$cmd" &
done < "$commands_file"

wait

echo "Manual XGBoost screen complete."
