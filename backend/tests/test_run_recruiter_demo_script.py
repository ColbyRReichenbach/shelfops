from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _parse_json_output(stdout: str) -> dict:
    lines = [line for line in stdout.splitlines() if line.strip()]
    start = next(i for i in range(len(lines) - 1, -1, -1) if lines[i].lstrip().startswith("{"))
    return json.loads("\n".join(lines[start:]))


def test_run_recruiter_demo_quick_strategy_and_replay(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "backend" / "scripts" / "run_recruiter_demo.py"
    output_dir = tmp_path / "recruiter_demo"

    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    env["APP_ENV"] = "test"

    cmd = [
        sys.executable,
        str(script_path),
        "--quick",
        "--skip-single-benchmarks",
        "--skip-combo-benchmarks",
        "--strategy-data-dir",
        "data/seed",
        "--replay-data-dir",
        "data/seed",
        "--replay-holdout-days",
        "30",
        "--replay-max-days",
        "2",
        "--replay-max-training-rows",
        "6000",
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

    payload = _parse_json_output(completed.stdout)
    assert payload["status"] == "success"

    scorecard_json = Path(payload["scorecard_json"])
    scorecard_md = Path(payload["scorecard_md"])
    replay_summary_json = Path(payload["replay_summary_json"])

    assert scorecard_json.exists()
    assert scorecard_md.exists()
    assert replay_summary_json.exists()

    scorecard = json.loads(scorecard_json.read_text(encoding="utf-8"))
    assert "strategy_cycle" in scorecard
    assert "replay" in scorecard
    assert "commands_executed" in scorecard
    assert len(scorecard["commands_executed"]) >= 2
