"""
Run a terminal-friendly read-only proof pass against the local ShelfOps demo.

This is intentionally lightweight: it hits the main runtime endpoints and
prints a concise operator view so the presenter can verify the environment
before screen sharing.

Run:
  PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen


def _get_json(url: str, timeout: float) -> object:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only terminal proof for the ShelfOps demo runtime.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Local API base URL.")
    parser.add_argument(
        "--summary-json",
        default="docs/productization_artifacts/demo_runtime/demo_runtime_summary.json",
        help="Runtime summary JSON emitted by prepare_demo_runtime.py",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds.")
    args = parser.parse_args()

    summary = _load_summary(Path(args.summary_json))
    base_url = args.base_url.rstrip("/")

    try:
        health = _get_json(f"{base_url}/health", args.timeout)
        sync_health = _get_json(f"{base_url}/api/v1/integrations/sync-health", args.timeout)
        suggested = _get_json(f"{base_url}/api/v1/purchase-orders/suggested", args.timeout)
        model_health = _get_json(f"{base_url}/api/v1/ml/models/health", args.timeout)
        alerts = _get_json(f"{base_url}/ml-alerts?limit=5", args.timeout)
    except HTTPError as exc:
        print(f"HTTP error from demo API: {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Could not reach demo API at {base_url}: {exc.reason}", file=sys.stderr)
        return 1

    _print_section("ShelfOps Demo Runtime")
    print(f"Base URL: {base_url}")
    if summary.get("prepared_at"):
        print(f"Prepared at: {summary['prepared_at']}")
    if summary.get("customer_name"):
        print(f"Tenant: {summary['customer_name']} ({summary.get('customer_id')})")

    _print_section("Health")
    _print_json(health)

    _print_section("Integration Sync Health")
    _print_json(sync_health)

    _print_section("Suggested Purchase Orders")
    spotlight_ids = (summary.get("purchase_orders", {}) or {}).get("targets", {})
    spotlight = [po for po in suggested if po.get("po_id") in set(spotlight_ids.values())]
    payload = {
        "count": len(suggested),
        "spotlight": spotlight[:3],
    }
    _print_json(payload)

    _print_section("Model Health")
    _print_json(model_health)

    _print_section("ML Alerts")
    _print_json(alerts[:3] if isinstance(alerts, list) else alerts)

    _print_section("Next Live Commands")
    commands = (summary.get("recommended_calls") or {}).copy()
    if commands:
        _print_json(commands)
    else:
        print(
            json.dumps(
                {
                    "suggested_pos": f"curl -s {base_url}/api/v1/purchase-orders/suggested | jq",
                    "model_health": f"curl -s {base_url}/api/v1/ml/models/health | jq",
                    "sync_health": f"curl -s {base_url}/api/v1/integrations/sync-health | jq",
                    "ml_alerts": f"curl -s '{base_url}/ml-alerts?limit=5' | jq",
                },
                indent=2,
            )
        )

    experiment_name = quote("Promo uplift feature trial")
    print()
    print("Tip: after the live approve/reject path, query experiments with:")
    print(f"curl -s '{base_url}/experiments?limit=10' | jq")
    print(f"curl -s '{base_url}/experiments?status=proposed&limit=10' | jq")
    print(f"curl -s '{base_url}/experiments?experiment_name={experiment_name}' | jq")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
