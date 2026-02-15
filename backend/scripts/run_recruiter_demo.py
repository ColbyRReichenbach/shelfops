#!/usr/bin/env python3
"""Run a recruiter-ready ML showcase pipeline and emit a single scorecard.

This orchestrates existing model/evaluation scripts into one reproducible flow:
  1) In-domain baseline benchmarks (single datasets)
  2) Pairwise combo benchmarks
  3) Model strategy cycle (XGBoost vs LSTM + ensemble sweep)
  4) Replay lifecycle simulation (retrain/trigger/HITL evidence)

Usage:
  PYTHONPATH=backend python3 backend/scripts/run_recruiter_demo.py
  PYTHONPATH=backend python3 backend/scripts/run_recruiter_demo.py --quick
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_cmd(cmd: list[str], *, env: dict[str, str], cwd: Path) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    finished = datetime.now(timezone.utc)
    payload = {
        "cmd": cmd,
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
    }
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(cmd)}\n{completed.stderr}")
    return payload


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _summarize_single_benchmarks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "skipped"}

    best_mape = min(rows, key=lambda row: float(row.get("mape_nonzero", float("inf"))))
    best_overstock = min(rows, key=lambda row: float(row.get("overstock_rate", float("inf"))))
    return {
        "datasets_evaluated": len(rows),
        "best_mape_nonzero": {
            "dataset_id": best_mape.get("dataset_id"),
            "value": float(best_mape.get("mape_nonzero", 0.0)),
        },
        "best_overstock_rate": {
            "dataset_id": best_overstock.get("dataset_id"),
            "value": float(best_overstock.get("overstock_rate", 0.0)),
        },
    }


def _summarize_combo_benchmarks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "skipped"}

    ranked = sorted(rows, key=lambda row: float(row.get("overall", {}).get("mape_nonzero", float("inf"))))
    best = ranked[0]
    return {
        "combos_evaluated": len(rows),
        "best_combo_by_mape_nonzero": {
            "combo_id": best.get("combo_id"),
            "mape_nonzero": float(best.get("overall", {}).get("mape_nonzero", 0.0)),
            "stockout_miss_rate": float(best.get("overall", {}).get("stockout_miss_rate", 0.0)),
            "overstock_rate": float(best.get("overall", {}).get("overstock_rate", 0.0)),
        },
    }


def _render_scorecard_md(summary: dict[str, Any], output_path: Path) -> None:
    strategy = summary.get("strategy_cycle", {})
    replay = summary.get("replay", {})
    single = summary.get("single_dataset_benchmarks", {})
    combos = summary.get("combo_benchmarks", {})

    lines = [
        "# Recruiter Demo Scorecard",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- quick_mode: `{summary['quick_mode']}`",
        "",
        "## Model Families Demonstrated",
        "",
        "- XGBoost baseline",
        "- LSTM challenger (when available)",
        "- Ensemble weight sweep (XGBoost/LSTM blend policy)",
        "",
        "## Initial Benchmark Snapshot",
        "",
        f"- single_datasets_evaluated: `{single.get('datasets_evaluated', 0)}`",
        f"- best_single_mape_nonzero: `{single.get('best_mape_nonzero', {})}`",
        f"- combos_evaluated: `{combos.get('combos_evaluated', 0)}`",
        f"- best_combo: `{combos.get('best_combo_by_mape_nonzero', {})}`",
        "",
        "## Strategy Cycle",
        "",
        f"- recommended_mode: `{strategy.get('decision', {}).get('recommended_mode')}`",
        f"- recommended_weights: `{strategy.get('decision', {}).get('recommended_weights')}`",
        f"- xgboost_metrics: `{strategy.get('xgboost_metrics')}`",
        f"- lstm_metrics: `{strategy.get('lstm_metrics')}`",
        "",
        "## Replay Lifecycle Proof",
        "",
        f"- replay_days: `{replay.get('replay_days')}`",
        f"- retrain_count: `{replay.get('retrain_count')}`",
        f"- baseline_gate_passed: `{replay.get('baseline_gate_passed')}`",
        f"- hitl_counts: `{replay.get('hitl_counts')}`",
        f"- baseline_metrics: `{replay.get('baseline_metrics')}`",
        "",
        "## Interview Narrative",
        "",
        "1. I can establish reproducible baseline metrics across datasets and combinations.",
        "2. I can evaluate model-family strategy decisions (single vs ensemble) with traceable criteria.",
        "3. I can operate an end-to-end lifecycle: retrain triggers, HITL decisions, and promotion evidence.",
        "4. I understand production boundaries: deterministic artifacts, gating, and auditable outputs.",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run recruiter-ready ML demo pipeline")
    parser.add_argument("--output-dir", default="docs/productization_artifacts/recruiter_demo")
    parser.add_argument("--strategy-data-dir", default="data/seed")
    parser.add_argument("--replay-data-dir", default="data/seed")
    parser.add_argument("--benchmark-max-rows", type=int, default=200000)
    parser.add_argument("--combo-max-rows-each", type=int, default=120000)
    parser.add_argument("--strategy-max-rows", type=int, default=25000)
    parser.add_argument("--replay-holdout-days", type=int, default=30)
    parser.add_argument("--replay-max-days", type=int, default=7)
    parser.add_argument("--replay-max-training-rows", type=int, default=25000)
    parser.add_argument("--replay-portfolio-mode", choices=["off", "auto"], default="auto")
    parser.add_argument("--no-replay-dry-run", action="store_true", help="Persist replay outputs to DB tables")
    parser.add_argument("--skip-single-benchmarks", action="store_true")
    parser.add_argument("--skip-combo-benchmarks", action="store_true")
    parser.add_argument("--skip-strategy", action="store_true")
    parser.add_argument("--skip-replay", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Run a faster demo profile for interviews")
    args = parser.parse_args()

    out_dir = (REPO_ROOT / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    replay_dir = out_dir / "replay"
    replay_dir.mkdir(parents=True, exist_ok=True)

    if args.quick:
        args.benchmark_max_rows = min(args.benchmark_max_rows, 80000)
        args.combo_max_rows_each = min(args.combo_max_rows_each, 60000)
        args.strategy_max_rows = min(args.strategy_max_rows, 10000)
        args.replay_max_days = min(args.replay_max_days, 3)
        args.replay_max_training_rows = min(args.replay_max_training_rows, 12000)

    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"

    command_log: list[dict[str, Any]] = []

    single_json = out_dir / "dataset_benchmark_baseline.json"
    combo_json = out_dir / "dataset_combo_benchmark.json"
    strategy_json = out_dir / "model_strategy_cycle.json"
    strategy_md = out_dir / "model_strategy_cycle.md"
    replay_summary_json = replay_dir / "replay_summary.json"

    if not args.skip_single_benchmarks:
        cmd = [
            sys.executable,
            "backend/scripts/benchmark_datasets.py",
            "--max-rows",
            str(args.benchmark_max_rows),
            "--output-json",
            str(single_json),
        ]
        command_log.append(_run_cmd(cmd, env=env, cwd=REPO_ROOT))

    if not args.skip_combo_benchmarks:
        cmd = [
            sys.executable,
            "backend/scripts/benchmark_dataset_combos.py",
            "--max-rows-each",
            str(args.combo_max_rows_each),
            "--output-json",
            str(combo_json),
        ]
        command_log.append(_run_cmd(cmd, env=env, cwd=REPO_ROOT))

    if not args.skip_strategy:
        cmd = [
            sys.executable,
            "backend/scripts/run_model_strategy_cycle.py",
            "--data-dir",
            args.strategy_data_dir,
            "--max-rows",
            str(args.strategy_max_rows),
            "--output-json",
            str(strategy_json),
            "--output-md",
            str(strategy_md),
        ]
        command_log.append(_run_cmd(cmd, env=env, cwd=REPO_ROOT))

    if not args.skip_replay:
        cmd = [
            sys.executable,
            "backend/scripts/run_replay_simulation.py",
            "--dataset-dir",
            args.replay_data_dir,
            "--holdout-days",
            str(args.replay_holdout_days),
            "--max-replay-days",
            str(args.replay_max_days),
            "--max-training-rows",
            str(args.replay_max_training_rows),
            "--portfolio-mode",
            args.replay_portfolio_mode,
            "--output-dir",
            str(replay_dir),
        ]
        if not args.no_replay_dry_run:
            cmd.append("--dry-run")
        command_log.append(_run_cmd(cmd, env=env, cwd=REPO_ROOT))

    single_rows = _load_json(single_json, [])
    combo_rows = _load_json(combo_json, [])
    strategy_payload = _load_json(strategy_json, {})
    replay_payload = _load_json(replay_summary_json, {})

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quick_mode": bool(args.quick),
        "output_dir": str(out_dir),
        "single_dataset_benchmarks": _summarize_single_benchmarks(single_rows),
        "combo_benchmarks": _summarize_combo_benchmarks(combo_rows),
        "strategy_cycle": strategy_payload,
        "replay": replay_payload,
        "commands_executed": command_log,
        "artifacts": {
            "single_benchmark_json": str(single_json),
            "combo_benchmark_json": str(combo_json),
            "strategy_json": str(strategy_json),
            "strategy_md": str(strategy_md),
            "replay_summary_json": str(replay_summary_json),
            "replay_summary_md": str(replay_dir / "replay_summary.md"),
            "recruiter_scorecard_json": str(out_dir / "recruiter_demo_scorecard.json"),
            "recruiter_scorecard_md": str(out_dir / "recruiter_demo_scorecard.md"),
        },
    }

    scorecard_json = out_dir / "recruiter_demo_scorecard.json"
    scorecard_md = out_dir / "recruiter_demo_scorecard.md"
    scorecard_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _render_scorecard_md(summary, scorecard_md)

    print(
        json.dumps(
            {
                "status": "success",
                "scorecard_json": str(scorecard_json),
                "scorecard_md": str(scorecard_md),
                "replay_summary_json": str(replay_summary_json),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
