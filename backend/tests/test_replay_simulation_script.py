from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_replay_simulation_dry_run_generates_artifacts(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "backend" / "scripts" / "run_replay_simulation.py"

    output_dir = tmp_path / "replay_artifacts"
    cmd = [
        sys.executable,
        str(script_path),
        "--dataset-dir",
        str(repo_root / "data" / "seed"),
        "--holdout-days",
        "30",
        "--max-replay-days",
        "5",
        "--max-training-rows",
        "5000",
        "--portfolio-mode",
        "off",
        "--dry-run",
        "--output-dir",
        str(output_dir),
    ]

    completed = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )

    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    json_start = next(i for i in range(len(lines) - 1, -1, -1) if lines[i].lstrip().startswith("{"))
    result = json.loads("\n".join(lines[json_start:]))
    assert result["status"] == "success"

    summary_json = output_dir / "replay_summary.json"
    daily_log = output_dir / "replay_daily_log.jsonl"
    decisions_json = output_dir / "replay_hitl_decisions.json"
    strategy_md = output_dir / "replay_model_strategy_decision.md"

    assert summary_json.exists()
    assert daily_log.exists()
    assert decisions_json.exists()
    assert strategy_md.exists()

    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    assert payload["replay_days"] > 0
    assert "baseline_metrics" in payload


def test_replay_simulation_non_dry_run_writes_mlops_tables(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "backend" / "scripts" / "run_replay_simulation.py"

    output_dir = tmp_path / "replay_artifacts_db"
    db_path = tmp_path / "replay.sqlite3"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["APP_ENV"] = "test"

    cmd = [
        sys.executable,
        str(script_path),
        "--dataset-dir",
        str(repo_root / "data" / "seed"),
        "--holdout-days",
        "30",
        "--max-replay-days",
        "3",
        "--max-training-rows",
        "3000",
        "--portfolio-mode",
        "off",
        "--db-max-rows-per-day",
        "200",
        "--output-dir",
        str(output_dir),
    ]

    completed = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    json_start = next(i for i in range(len(lines) - 1, -1, -1) if lines[i].lstrip().startswith("{"))
    result = json.loads("\n".join(lines[json_start:]))
    assert result["status"] == "success"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    try:
        model_versions_count = conn.execute("SELECT COUNT(*) FROM model_versions").fetchone()[0]
        retrain_count = conn.execute("SELECT COUNT(*) FROM model_retraining_log").fetchone()[0]
        forecast_rows = conn.execute("SELECT COUNT(*) FROM demand_forecasts").fetchone()[0]
        accuracy_rows = conn.execute("SELECT COUNT(*) FROM forecast_accuracy").fetchone()[0]
    finally:
        conn.close()

    assert model_versions_count >= 1
    assert retrain_count >= 1
    assert forecast_rows > 0
    assert accuracy_rows > 0
