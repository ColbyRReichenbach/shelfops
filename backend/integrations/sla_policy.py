"""SLA policy resolution for integration sync-health."""

from __future__ import annotations

import json
from functools import lru_cache

from core.config import get_settings

DEFAULT_SLA_BY_TYPE = {
    "POS": 1,
    "EDI": 48,
    "SFTP": 48,
    "KAFKA": 2,
    "EVENT_STREAM": 2,
}

DEFAULT_SLA_BY_NAME = {
    "Square POS": 1,
    "EDI 846 Inventory": 48,
    "SFTP Product Catalog": 48,
    "Kafka Store Transfers": 2,
}


@lru_cache
def _load_override_policy() -> dict:
    """
    Optional override payload from env:
      INTEGRATION_SLA_OVERRIDES='{"by_name":{"My Feed":6},"by_type":{"EDI":36}}'
    """
    raw = get_settings().integration_sla_overrides
    if not raw:
        return {"by_name": {}, "by_type": {}}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"by_name": {}, "by_type": {}}
    if not isinstance(payload, dict):
        return {"by_name": {}, "by_type": {}}
    by_name = payload.get("by_name", {})
    by_type = payload.get("by_type", {})
    return {
        "by_name": by_name if isinstance(by_name, dict) else {},
        "by_type": by_type if isinstance(by_type, dict) else {},
    }


def resolve_sla_hours(integration_type: str, integration_name: str) -> int:
    policy = _load_override_policy()
    by_name = policy.get("by_name", {})
    by_type = policy.get("by_type", {})

    if integration_name in by_name:
        return int(by_name[integration_name])
    if integration_type in by_type:
        return int(by_type[integration_type])
    if integration_name in DEFAULT_SLA_BY_NAME:
        return int(DEFAULT_SLA_BY_NAME[integration_name])
    if integration_type in DEFAULT_SLA_BY_TYPE:
        return int(DEFAULT_SLA_BY_TYPE[integration_type])
    return 24
