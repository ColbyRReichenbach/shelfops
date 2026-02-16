#!/usr/bin/env python3
"""
Automated XGBoost hyperparameter search wrapper for ShelfOps.

Modes:
  - grid: deterministic grid (shuffled) over a narrowed search space
  - random: random samples from the narrowed search space
  - optuna: TPE/Bayesian search (if optuna is installed)

Each trial calls backend/scripts/iterate_model.sh and reads
backend/reports/iteration_runs.jsonl for the resulting delta metric.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
ITERATE_SCRIPT = REPO_ROOT / "backend" / "scripts" / "iterate_model.sh"
RUN_LOG_PATH = REPO_ROOT / "backend" / "reports" / "iteration_runs.jsonl"
MODEL_DIR = REPO_ROOT / "backend" / "models"


# Narrowed from manual + combo screening.
GRID_SPACE = {
    "max_depth": [6, 8],
    "min_child_weight": [5, 8, 12],
    "learning_rate": [0.05, 0.08],
    "subsample": [0.8, 0.9],
    "colsample_bytree": [0.8, 0.9],
    "reg_lambda": [0.5, 1.0],
}


@dataclass
class TrialResult:
    version: str
    delta_pct: float
    ensemble_mae: float
    params: dict[str, Any]


def _format_param_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        text = f"{value:.6f}".rstrip("0").rstrip(".")
        return text if text else "0"
    return str(value)


def _unique_version(prefix: str, trial_num: int) -> str:
    base = f"{prefix}_t{trial_num:03d}"
    candidate = base
    i = 1
    while (MODEL_DIR / candidate).exists():
        candidate = f"{base}_r{i}"
        i += 1
    return candidate


def _load_run_record(version: str) -> dict[str, Any]:
    if not RUN_LOG_PATH.exists():
        raise RuntimeError(f"Run log missing: {RUN_LOG_PATH}")

    lines = RUN_LOG_PATH.read_text().splitlines()
    marker = f'"version": "{version}"'
    for line in reversed(lines):
        if marker in line:
            return json.loads(line)
    raise RuntimeError(f"No log record found for version={version}")


def _run_iterate(
    *,
    version: str,
    params: dict[str, Any],
    data_dir: str,
    dataset: str,
    baseline: str,
    mode: str,
    auto_notes: bool,
    xgb_only: bool,
    python_bin: str,
    dry_run: bool,
) -> TrialResult:
    cmd = [
        str(ITERATE_SCRIPT),
        "--data-dir",
        data_dir,
        "--dataset",
        dataset,
        "--version",
        version,
        "--baseline",
        baseline,
        "--skip-tests",
        "--python",
        python_bin,
        "--hypothesis",
        f"Automated {mode} trial",
        "--notes",
        f"auto_tune_xgb:{mode}",
    ]

    if auto_notes:
        cmd.append("--auto-notes")

    if xgb_only:
        cmd.append("--xgb-only")
    else:
        cmd.append("--with-lstm")

    for key in sorted(params.keys()):
        cmd.extend(["--xgb-param", f"{key}={_format_param_value(params[key])}"])

    print(f"\n[trial] {version}")
    print(f"[params] {params}")

    if dry_run:
        print("[dry-run] " + " ".join(cmd))
        return TrialResult(version=version, delta_pct=float("-inf"), ensemble_mae=float("inf"), params=params)

    subprocess.run(cmd, check=True, cwd=REPO_ROOT)
    record = _load_run_record(version)
    delta = record.get("ensemble_mae_delta_pct")
    metrics = record.get("candidate_metrics", {})
    mae = metrics.get("ensemble_mae")
    if delta is None or mae is None:
        raise RuntimeError(f"Incomplete metrics for version={version}")

    result = TrialResult(
        version=version,
        delta_pct=float(delta),
        ensemble_mae=float(mae),
        params=params,
    )
    print(f"[result] delta={result.delta_pct:.3f}% mae={result.ensemble_mae:.6f}")
    return result


def _grid_params(seed: int) -> list[dict[str, Any]]:
    keys = list(GRID_SPACE.keys())
    values = [GRID_SPACE[k] for k in keys]
    combos = [dict(zip(keys, combo)) for combo in itertools.product(*values)]
    rng = random.Random(seed)
    rng.shuffle(combos)
    return combos


def _random_params(seed: int, n_trials: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    combos = []
    for _ in range(n_trials):
        combos.append(
            {
                "max_depth": rng.choice([6, 7, 8, 9]),
                "min_child_weight": rng.choice([4, 5, 6, 8, 10, 12]),
                "learning_rate": rng.choice([0.05, 0.06, 0.07, 0.08, 0.09]),
                "subsample": rng.choice([0.8, 0.85, 0.9]),
                "colsample_bytree": rng.choice([0.8, 0.85, 0.9]),
                "reg_lambda": rng.choice([0.5, 0.8, 1.0, 1.5]),
            }
        )
    return combos


def run_grid_or_random(args: argparse.Namespace) -> list[TrialResult]:
    if args.mode == "grid":
        candidates = _grid_params(args.seed)
    else:
        candidates = _random_params(args.seed, args.n_trials)

    trials = candidates[: args.n_trials]
    results: list[TrialResult] = []
    for idx, params in enumerate(trials, start=1):
        version = _unique_version(args.prefix, idx)
        result = _run_iterate(
            version=version,
            params=params,
            data_dir=args.data_dir,
            dataset=args.dataset,
            baseline=args.baseline,
            mode=args.mode,
            auto_notes=not args.no_auto_notes,
            xgb_only=args.xgb_only,
            python_bin=args.python,
            dry_run=args.dry_run,
        )
        results.append(result)
    return results


def run_optuna(args: argparse.Namespace) -> list[TrialResult]:
    try:
        import optuna
    except Exception as exc:
        raise RuntimeError("Optuna mode requested, but optuna is not available.") from exc

    results: list[TrialResult] = []

    def objective(trial: Any) -> float:
        params = {
            "max_depth": trial.suggest_int("max_depth", 6, 9),
            "min_child_weight": trial.suggest_int("min_child_weight", 4, 12),
            "learning_rate": trial.suggest_float("learning_rate", 0.05, 0.10),
            "subsample": trial.suggest_float("subsample", 0.8, 0.95),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.8, 0.95),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.5, 2.0),
        }
        version = _unique_version(args.prefix, trial.number + 1)
        result = _run_iterate(
            version=version,
            params=params,
            data_dir=args.data_dir,
            dataset=args.dataset,
            baseline=args.baseline,
            mode="optuna",
            auto_notes=not args.no_auto_notes,
            xgb_only=args.xgb_only,
            python_bin=args.python,
            dry_run=args.dry_run,
        )
        results.append(result)
        return result.delta_pct

    sampler = optuna.samplers.TPESampler(seed=args.seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=args.n_trials)
    return results


def print_summary(results: list[TrialResult]) -> None:
    if not results:
        print("\nNo results to summarize.")
        return

    ranked = sorted(results, key=lambda r: r.delta_pct, reverse=True)
    print("\n=== Auto-Tune Summary ===")
    for r in ranked:
        print(f"{r.version}\tdelta={r.delta_pct:.3f}%\tmae={r.ensemble_mae:.6f}\tparams={r.params}")
    best = ranked[0]
    print("\nBest:")
    print(f"  version={best.version}")
    print(f"  delta={best.delta_pct:.3f}%")
    print(f"  mae={best.ensemble_mae:.6f}")
    print(f"  params={best.params}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated XGBoost tuning runner.")
    parser.add_argument("--mode", choices=["grid", "random", "optuna"], default="optuna")
    parser.add_argument("--n-trials", type=int, default=4)
    parser.add_argument("--data-dir", default="data/seed")
    parser.add_argument("--dataset", default="enterprise_seed")
    parser.add_argument("--baseline", default="v2_baseline")
    parser.add_argument("--prefix", default="v_auto_01")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--python", default="python3")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--xgb-only", dest="xgb_only", action="store_true")
    mode_group.add_argument("--with-lstm", dest="xgb_only", action="store_false")
    parser.set_defaults(xgb_only=True)
    parser.add_argument("--no-auto-notes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.n_trials <= 0:
        print("n-trials must be > 0", file=sys.stderr)
        return 1

    data_dir_path = Path(args.data_dir)
    if not data_dir_path.is_absolute():
        data_dir_path = REPO_ROOT / data_dir_path
    args.data_dir = str(data_dir_path)

    if not data_dir_path.exists():
        print(f"Data dir not found: {data_dir_path}", file=sys.stderr)
        return 1

    baseline_meta = MODEL_DIR / args.baseline / "metadata.json"
    if not baseline_meta.exists():
        print(f"Baseline metadata not found: {baseline_meta}", file=sys.stderr)
        return 1

    print("=== Auto XGB Tuning ===")
    print(
        f"mode={args.mode} n_trials={args.n_trials} baseline={args.baseline} "
        f"prefix={args.prefix} xgb_only={args.xgb_only}"
    )
    print(f"data_dir={args.data_dir} dataset={args.dataset}")

    if args.mode in {"grid", "random"}:
        results = run_grid_or_random(args)
    else:
        results = run_optuna(args)

    print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
