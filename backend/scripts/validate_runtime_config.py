#!/usr/bin/env python3
"""Validate runtime configuration for pre-production/production deploys.

Examples:
  python backend/scripts/validate_runtime_config.py
  python backend/scripts/validate_runtime_config.py --require-square --pretty
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# Add backend/ to path when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import DEFAULT_ENCRYPTION_KEY, DEFAULT_JWT_SECRET, get_settings


def _is_local_env(raw_env: str) -> bool:
    env = raw_env.strip().lower()
    return env in {"", "local", "dev", "development", "test"}


def _validate_settings(
    *,
    require_square: bool,
    allow_demo_synthesis: bool,
) -> tuple[list[str], dict[str, Any]]:
    settings = get_settings()
    env = settings.app_env.strip().lower()
    local_env = _is_local_env(env)
    failures: list[str] = []

    if not local_env:
        if not settings.auth0_domain.strip():
            failures.append("AUTH0_DOMAIN is required outside local/dev/test")
        if not settings.auth0_audience.strip():
            failures.append("AUTH0_AUDIENCE is required outside local/dev/test")
        if settings.jwt_secret == DEFAULT_JWT_SECRET:
            failures.append("JWT_SECRET must not use the default value outside local/dev/test")
        if settings.encryption_key == DEFAULT_ENCRYPTION_KEY:
            failures.append("ENCRYPTION_KEY must not use the default value outside local/dev/test")
        if settings.debug:
            failures.append("DEBUG=true is not allowed outside local/dev/test")
        if settings.square_enable_demo_id_synthesis and not allow_demo_synthesis:
            failures.append("SQUARE_ENABLE_DEMO_ID_SYNTHESIS must be false outside local/dev/test")

        if require_square:
            if not settings.square_client_id.strip():
                failures.append("SQUARE_CLIENT_ID is required when --require-square is set")
            if not settings.square_client_secret.strip():
                failures.append("SQUARE_CLIENT_SECRET is required when --require-square is set")
            if not settings.square_webhook_secret.strip():
                failures.append("SQUARE_WEBHOOK_SECRET is required when --require-square is set")

    summary = {
        "status": "success" if not failures else "failed",
        "app_env": settings.app_env,
        "local_env": local_env,
        "require_square": bool(require_square),
        "allow_demo_synthesis": bool(allow_demo_synthesis),
        "failures": failures,
    }
    return failures, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate deployment runtime config")
    parser.add_argument(
        "--require-square",
        action="store_true",
        help="Require Square OAuth/webhook secrets for this deploy target",
    )
    parser.add_argument(
        "--allow-demo-synthesis",
        action="store_true",
        help="Allow SQUARE_ENABLE_DEMO_ID_SYNTHESIS in non-local environments",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    try:
        failures, summary = _validate_settings(
            require_square=bool(args.require_square),
            allow_demo_synthesis=bool(args.allow_demo_synthesis),
        )
    except Exception as exc:  # noqa: BLE001
        summary = {
            "status": "failed",
            "error": str(exc),
            "require_square": bool(args.require_square),
            "allow_demo_synthesis": bool(args.allow_demo_synthesis),
        }
        failures = [str(exc)]

    if args.pretty:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(json.dumps(summary))

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
