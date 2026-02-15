from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _parse_json_output(stdout: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_validate_runtime_config_fails_when_prod_auth0_missing(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "backend" / "scripts" / "validate_runtime_config.py"

    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["DEBUG"] = "false"
    env["JWT_SECRET"] = "non-default-jwt-secret"
    env["ENCRYPTION_KEY"] = "non-default-encryption-key"
    env["AUTH0_DOMAIN"] = ""
    env["AUTH0_AUDIENCE"] = ""

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    payload = _parse_json_output(completed.stdout)
    assert payload["status"] == "failed"
    assert any("AUTH0_DOMAIN" in message for message in payload["failures"])
    assert any("AUTH0_AUDIENCE" in message for message in payload["failures"])


def test_validate_runtime_config_passes_with_required_square_settings(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "backend" / "scripts" / "validate_runtime_config.py"

    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["DEBUG"] = "false"
    env["JWT_SECRET"] = "non-default-jwt-secret"
    env["ENCRYPTION_KEY"] = "non-default-encryption-key"
    env["AUTH0_DOMAIN"] = "example-tenant.us.auth0.com"
    env["AUTH0_AUDIENCE"] = "https://api.shelfops.com"
    env["SQUARE_CLIENT_ID"] = "sq0idp-demo-client-id"
    env["SQUARE_CLIENT_SECRET"] = "sq0csp-demo-secret"
    env["SQUARE_WEBHOOK_SECRET"] = "sqwhsec-demo-webhook-secret"
    env["SQUARE_ENABLE_DEMO_ID_SYNTHESIS"] = "false"

    completed = subprocess.run(
        [sys.executable, str(script_path), "--require-square"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = _parse_json_output(completed.stdout)
    assert payload["status"] == "success"
    assert payload["failures"] == []
