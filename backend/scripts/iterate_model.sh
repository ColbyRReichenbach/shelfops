#!/usr/bin/env bash
set -euo pipefail

# Iteration wrapper for reproducible model runs.
#
# Default flow:
#   1) Run ML pipeline tests
#   2) Train model with explicit version + dataset + data-dir
#   3) Compare candidate metadata against baseline metadata (if provided)
#
# Example:
#   ./backend/scripts/iterate_model.sh \
#     --data-dir data/seed \
#     --dataset enterprise_seed \
#     --version v3_iter1 \
#     --baseline v2_baseline

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

DATA_DIR="data/seed"
DATASET="enterprise_seed"
VERSION=""
BASELINE=""
HYPOTHESIS=""
NOTES=""
AUTO_NOTES=0
XGB_PARAMS=()
FEATURE_PHASE=0
PARAM_LOCK_VERSION=""
SKIP_TESTS=0
PROMOTE=0
XGB_ONLY=1
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
Usage:
  backend/scripts/iterate_model.sh --version <version> [options]

Required:
  --version <version>         Candidate model version to train (e.g., v3_iter1)

Optional:
  --data-dir <path>           Training data path (repo-relative or absolute). Default: data/seed
  --dataset <name>            Dataset label for tracking. Default: enterprise_seed
  --baseline <version>        Baseline model version for post-run comparison
  --xgb-param <key=value>     Override XGBoost param (repeatable)
  --xgb-only                  Run XGBoost-only training (default)
  --with-lstm                 Enable optional LSTM ensemble
  --feature-phase             Lock params to reference version; focus on feature deltas
  --param-lock-version <ver>  Reference version for parameter lock (defaults to --baseline)
  --hypothesis <text>         What you expect to improve in this run
  --notes <text>              Free-form run notes
  --auto-notes                Generate markdown run note in backend/reports/iteration_notes/
  --skip-tests                Skip pytest gate
  --promote                   Pass --promote to training script
  --python <bin>              Python executable (default: python3)
  --help                      Show this help

Environment:
  MLFLOW_TRACKING_URI         If set, run will log to that MLflow endpoint.
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
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --baseline)
      BASELINE="${2:-}"
      shift 2
      ;;
    --xgb-param)
      XGB_PARAMS+=("${2:-}")
      shift 2
      ;;
    --xgb-only)
      XGB_ONLY=1
      shift
      ;;
    --with-lstm)
      XGB_ONLY=0
      shift
      ;;
    --feature-phase)
      FEATURE_PHASE=1
      shift
      ;;
    --param-lock-version)
      PARAM_LOCK_VERSION="${2:-}"
      shift 2
      ;;
    --hypothesis)
      HYPOTHESIS="${2:-}"
      shift 2
      ;;
    --notes)
      NOTES="${2:-}"
      shift 2
      ;;
    --auto-notes)
      AUTO_NOTES=1
      shift
      ;;
    --skip-tests)
      SKIP_TESTS=1
      shift
      ;;
    --promote)
      PROMOTE=1
      shift
      ;;
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
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

if [[ -z "$VERSION" ]]; then
  echo "Error: --version is required." >&2
  usage
  exit 1
fi

if [[ "$DATA_DIR" != /* ]]; then
  DATA_DIR="$ROOT_DIR/$DATA_DIR"
fi

if [[ ! -d "$DATA_DIR" ]]; then
  echo "Error: data directory not found: $DATA_DIR" >&2
  exit 1
fi

LOCK_SOURCE_VERSION=""
if [[ "$FEATURE_PHASE" -eq 1 ]]; then
  if [[ "${#XGB_PARAMS[@]}" -gt 0 ]]; then
    echo "Error: --feature-phase cannot be combined with --xgb-param." >&2
    echo "       Feature phase locks params automatically from a reference version." >&2
    exit 1
  fi

  LOCK_SOURCE_VERSION="${PARAM_LOCK_VERSION:-$BASELINE}"
  if [[ -z "$LOCK_SOURCE_VERSION" ]]; then
    echo "Error: --feature-phase requires --baseline or --param-lock-version." >&2
    exit 1
  fi

  LOCK_META_PATH="$ROOT_DIR/backend/models/$LOCK_SOURCE_VERSION/metadata.json"
  if [[ ! -f "$LOCK_META_PATH" ]]; then
    echo "Error: lock-source metadata not found: $LOCK_META_PATH" >&2
    exit 1
  fi

  while IFS= read -r line; do
    XGB_PARAMS+=("$line")
  done < <(
    LOCK_SOURCE_VERSION="$LOCK_SOURCE_VERSION" ROOT_DIR="$ROOT_DIR" "$PYTHON_BIN" - <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
version = os.environ["LOCK_SOURCE_VERSION"]
meta_path = root / "backend" / "models" / version / "metadata.json"
meta = json.loads(meta_path.read_text())
params = meta.get("xgboost_params")
if not params:
    # Backward compatibility for older model metadata.
    params = {
        "n_estimators": 500,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "min_child_weight": 5,
        "early_stopping_rounds": 30,
        "random_state": 42,
    }
    print(f"[feature-phase] No xgboost_params in {meta_path}; using default lock set.", file=sys.stderr)

for key in sorted(params.keys()):
    value = params[key]
    if isinstance(value, bool):
        s = str(value).lower()
    else:
        s = str(value)
    print(f"{key}={s}")
PY
  )
fi

echo "============================================================"
echo "ShelfOps Model Iteration"
echo "============================================================"
echo "root:      $ROOT_DIR"
echo "backend:   $BACKEND_DIR"
echo "data-dir:  $DATA_DIR"
echo "dataset:   $DATASET"
echo "version:   $VERSION"
echo "baseline:  ${BASELINE:-<none>}"
echo "xgb-params:${#XGB_PARAMS[@]}"
echo "xgb-only:  $XGB_ONLY"
echo "phase:     $([[ "$FEATURE_PHASE" -eq 1 ]] && echo "feature" || echo "parameter")"
echo "param-lock:${LOCK_SOURCE_VERSION:-<none>}"
echo "hypothesis:${HYPOTHESIS:-<none>}"
echo "notes:     ${NOTES:-<none>}"
echo "auto-notes:$AUTO_NOTES"
echo "promote:   $PROMOTE"
echo "python:    $PYTHON_BIN"
if [[ -n "${MLFLOW_TRACKING_URI:-}" ]]; then
  echo "mlflow:    $MLFLOW_TRACKING_URI"
else
  echo "mlflow:    <not set; local JSON fallback still logs run>"
fi
echo "============================================================"

if [[ "$SKIP_TESTS" -eq 0 ]]; then
  echo
  echo "[1/3] Running ML pipeline tests..."
  (
    cd "$ROOT_DIR"
    PYTHONPATH=backend "$PYTHON_BIN" -m pytest backend/tests/test_ml_pipeline.py -q
  )
else
  echo
  echo "[1/3] Skipping tests (--skip-tests)."
fi

echo
echo "[2/3] Training candidate model..."
TRAIN_ARGS=(
  scripts/run_training.py
  --data-dir "$DATA_DIR"
  --dataset "$DATASET"
  --version "$VERSION"
)

if [[ "${#XGB_PARAMS[@]}" -gt 0 ]]; then
  for p in "${XGB_PARAMS[@]}"; do
    TRAIN_ARGS+=(--xgb-param "$p")
  done
fi

if [[ "$PROMOTE" -eq 1 ]]; then
  TRAIN_ARGS+=(--promote)
fi

if [[ "$XGB_ONLY" -eq 1 ]]; then
  TRAIN_ARGS+=(--xgb-only)
else
  TRAIN_ARGS+=(--with-lstm)
fi

(
  cd "$BACKEND_DIR"
  "$PYTHON_BIN" "${TRAIN_ARGS[@]}"
)

echo
echo "[3/3] Summarizing run metrics..."
(
  cd "$ROOT_DIR"
  BASELINE_VERSION="$BASELINE" \
  CANDIDATE_VERSION="$VERSION" \
  DATASET_NAME="$DATASET" \
  DATA_DIR_VALUE="$DATA_DIR" \
  PROMOTE_VALUE="$PROMOTE" \
  XGB_ONLY_VALUE="$XGB_ONLY" \
  AUTO_NOTES_VALUE="$AUTO_NOTES" \
  FEATURE_PHASE_VALUE="$FEATURE_PHASE" \
  LOCK_SOURCE_VERSION="$LOCK_SOURCE_VERSION" \
  HYPOTHESIS_TEXT="$HYPOTHESIS" \
  NOTES_TEXT="$NOTES" \
  "$PYTHON_BIN" - <<'PY'
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

root = Path("backend/models")
reports_dir = Path("backend/reports")
candidate = os.environ["CANDIDATE_VERSION"]
baseline = os.environ.get("BASELINE_VERSION") or ""
dataset_name = os.environ.get("DATASET_NAME", "")
data_dir = os.environ.get("DATA_DIR_VALUE", "")
promote = os.environ.get("PROMOTE_VALUE", "0") == "1"
xgb_only = os.environ.get("XGB_ONLY_VALUE", "0") == "1"
auto_notes = os.environ.get("AUTO_NOTES_VALUE", "0") == "1"
feature_phase = os.environ.get("FEATURE_PHASE_VALUE", "0") == "1"
lock_source_version = os.environ.get("LOCK_SOURCE_VERSION", "")
hypothesis = os.environ.get("HYPOTHESIS_TEXT", "")
notes = os.environ.get("NOTES_TEXT", "")


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True).strip()
    except Exception:
        return ""

def load_metrics(version: str) -> dict:
    path = root / version / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing metadata: {path}")
    data = json.loads(path.read_text())
    return {
        "ensemble_mae": data.get("ensemble_mae"),
        "xgb_mae": data.get("xgboost_metrics", {}).get("mae"),
        "xgb_mape": data.get("xgboost_metrics", {}).get("mape"),
        "tier": data.get("feature_tier"),
        "metadata": data,
    }

candidate_metrics = load_metrics(candidate)
candidate_meta = candidate_metrics.pop("metadata")
print(f"candidate={candidate} metrics={candidate_metrics}")

baseline_metrics = None
delta_pct = None
baseline_meta = None
if baseline:
    baseline_metrics = load_metrics(baseline)
    baseline_meta = baseline_metrics.pop("metadata")
    print(f"baseline={baseline} metrics={baseline_metrics}")

    b = baseline_metrics.get("ensemble_mae")
    c = candidate_metrics.get("ensemble_mae")
    if b is not None and c is not None and b != 0:
        delta_pct = ((b - c) / b) * 100.0
        direction = "improvement" if delta_pct >= 0 else "regression"
        print(f"ensemble_mae_delta_pct={delta_pct:.2f}% ({direction})")

lock_source_meta = None
if lock_source_version:
    lock_source_metrics = load_metrics(lock_source_version)
    lock_source_meta = lock_source_metrics.pop("metadata")

reference_version = None
reference_meta = None
if feature_phase and lock_source_version and lock_source_meta is not None:
    reference_version = lock_source_version
    reference_meta = lock_source_meta
elif baseline and baseline_meta is not None:
    reference_version = baseline
    reference_meta = baseline_meta


def dict_delta(candidate_dict: dict, baseline_dict: dict | None) -> dict:
    delta = {}
    if baseline_dict is None:
        for key in sorted(candidate_dict.keys()):
            delta[key] = {"candidate": candidate_dict.get(key), "baseline": None}
        return delta

    all_keys = sorted(set(candidate_dict.keys()) | set(baseline_dict.keys()))
    for key in all_keys:
        c_val = candidate_dict.get(key)
        b_val = baseline_dict.get(key)
        if c_val != b_val:
            delta[key] = {"candidate": c_val, "baseline": b_val}
    return delta


candidate_xgb_params = candidate_meta.get("xgboost_params", {})
candidate_lstm_config = candidate_meta.get("lstm_config", {})
reference_xgb_params = reference_meta.get("xgboost_params", {}) if reference_meta else None
reference_lstm_config = reference_meta.get("lstm_config", {}) if reference_meta else None
candidate_features = set(candidate_meta.get("feature_cols", []))
reference_features = set(reference_meta.get("feature_cols", [])) if reference_meta else set()
added_features = sorted(candidate_features - reference_features)
removed_features = sorted(reference_features - candidate_features)

record = {
    "logged_at": datetime.now(timezone.utc).isoformat(),
    "git_branch": git_value(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
    "git_commit": git_value(["git", "rev-parse", "HEAD"]),
    "phase": "feature" if feature_phase else "parameter",
    "version": candidate,
    "baseline_version": baseline or None,
    "feature_phase_locked_param_source_version": lock_source_version or None,
    "comparison_reference_version": reference_version,
    "dataset": dataset_name,
    "data_dir": data_dir,
    "promote": promote,
    "xgb_only": xgb_only,
    "hypothesis": hypothesis or None,
    "notes": notes or None,
    "candidate_metrics": candidate_metrics,
    "baseline_metrics": baseline_metrics,
    "ensemble_mae_delta_pct": delta_pct,
    "candidate_xgboost_params": candidate_xgb_params,
    "candidate_lstm_config": candidate_lstm_config,
    "xgboost_param_delta_vs_reference": {} if feature_phase else dict_delta(candidate_xgb_params, reference_xgb_params),
    "lstm_config_delta_vs_reference": {} if feature_phase else dict_delta(candidate_lstm_config, reference_lstm_config),
    "candidate_feature_count": len(candidate_features),
    "reference_feature_count": len(reference_features) if reference_version else None,
    "added_features_vs_reference": added_features,
    "removed_features_vs_reference": removed_features,
}

reports_dir.mkdir(parents=True, exist_ok=True)
log_path = reports_dir / "iteration_runs.jsonl"
with log_path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(record, default=str) + "\n")

print(f"iteration_log={log_path}")

if auto_notes:
    notes_dir = reports_dir / "iteration_notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    note_path = notes_dir / f"{candidate}_{ts}.md"

    lines = [
        "# Model Iteration Note",
        "",
        "## Run",
        f"- Logged At: {record['logged_at']}",
        f"- Phase: {record['phase']}",
        f"- Version: {candidate}",
        f"- Baseline: {baseline or 'None'}",
        f"- Comparison Reference: {reference_version or 'None'}",
        f"- Feature-Phase Param Lock Source: {lock_source_version or 'None'}",
        f"- Dataset: {dataset_name}",
        f"- Data Dir: {data_dir}",
        f"- Git Branch: {record['git_branch']}",
        f"- Git Commit: {record['git_commit']}",
        f"- Promote: {promote}",
        f"- XGB Only: {xgb_only}",
        "",
        "## Intent",
        f"- Hypothesis: {hypothesis or 'None'}",
        f"- Notes: {notes or 'None'}",
        "",
        "## Metrics",
        f"- Candidate Ensemble MAE: {candidate_metrics.get('ensemble_mae')}",
        f"- Candidate XGB MAE: {candidate_metrics.get('xgb_mae')}",
        f"- Candidate XGB MAPE: {candidate_metrics.get('xgb_mape')}",
    ]

    if baseline_metrics:
        lines.extend(
            [
                f"- Baseline Ensemble MAE: {baseline_metrics.get('ensemble_mae')}",
                f"- Baseline XGB MAE: {baseline_metrics.get('xgb_mae')}",
                f"- Baseline XGB MAPE: {baseline_metrics.get('xgb_mape')}",
                f"- Ensemble MAE Delta (%): {delta_pct}",
            ]
        )

    lines.extend(
        [
            "",
            "## Parameter Delta",
        ]
    )

    if feature_phase:
        lines.append(f"- Locked to parameter source: {lock_source_version or 'None'}")
        lines.append("- Parameter deltas are expected to be zero in feature-phase runs.")
    else:
        xgb_delta = record["xgboost_param_delta_vs_reference"]
        if xgb_delta:
            for key in sorted(xgb_delta.keys()):
                change = xgb_delta[key]
                lines.append(f"- XGB {key}: {change.get('baseline')} -> {change.get('candidate')}")
        else:
            lines.append("- XGB: no changes vs reference")

        lstm_delta = record["lstm_config_delta_vs_reference"]
        if lstm_delta:
            for key in sorted(lstm_delta.keys()):
                change = lstm_delta[key]
                lines.append(f"- LSTM {key}: {change.get('baseline')} -> {change.get('candidate')}")
        else:
            lines.append("- LSTM config: no changes vs reference")

    lines.extend(
        [
            "",
            "## Feature Delta",
            f"- Candidate Feature Count: {record['candidate_feature_count']}",
            f"- Reference Feature Count: {record['reference_feature_count']}",
            f"- Added Features: {len(added_features)}",
            f"- Removed Features: {len(removed_features)}",
        ]
    )

    if added_features:
        lines.append(f"- Added Feature Names: {', '.join(added_features)}")
    if removed_features:
        lines.append(f"- Removed Feature Names: {', '.join(removed_features)}")

    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"iteration_note={note_path}")
PY
)

echo
echo "Iteration run complete."
