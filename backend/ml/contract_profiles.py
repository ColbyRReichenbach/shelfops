"""Utilities for loading and validating versioned tenant data contract profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_SOURCE_TYPES = {
    "smb_csv",
    "smb_sftp",
    "enterprise_edi",
    "enterprise_sftp",
    "enterprise_event",
}

REQUIRED_KEYS = {
    "contract_version",
    "tenant_id",
    "source_type",
    "grain",
    "timezone",
    "id_columns",
    "field_map",
    "type_map",
    "unit_map",
    "null_policy",
    "dedupe_keys",
    "dq_thresholds",
}


@dataclass(frozen=True)
class ContractProfile:
    """Versioned tenant/source mapping profile."""

    contract_version: str
    tenant_id: str
    source_type: str
    grain: str
    timezone: str
    id_columns: dict[str, str]
    field_map: dict[str, str]
    type_map: dict[str, str]
    unit_map: dict[str, Any]
    null_policy: dict[str, Any]
    dedupe_keys: list[str]
    dq_thresholds: dict[str, float]
    country_code: str = "unknown"


class ContractProfileError(ValueError):
    """Raised when a contract profile is invalid."""


def _require_keys(payload: dict[str, Any], required: set[str]) -> None:
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ContractProfileError(f"Missing required contract keys: {missing}")


def _ensure_mapping(payload: dict[str, Any], key: str, *, allow_empty: bool = False) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ContractProfileError(f"Contract key '{key}' must be a mapping")
    if not allow_empty and not value:
        raise ContractProfileError(f"Contract key '{key}' must be a non-empty mapping")
    return value


def _ensure_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ContractProfileError(f"Contract key '{key}' must be a non-empty list")
    return value


def _coerce_float_thresholds(raw: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in raw.items():
        try:
            out[key] = float(value)
        except (TypeError, ValueError) as exc:
            raise ContractProfileError(f"dq_thresholds.{key} must be numeric") from exc
    return out


def _normalize_profile(payload: dict[str, Any]) -> ContractProfile:
    _require_keys(payload, REQUIRED_KEYS)

    source_type = str(payload["source_type"])
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise ContractProfileError(
            f"Unsupported source_type '{source_type}'. Supported: {sorted(SUPPORTED_SOURCE_TYPES)}"
        )

    contract_version = str(payload["contract_version"])
    if not contract_version.startswith("v"):
        raise ContractProfileError("contract_version must start with 'v' (example: v1)")

    type_map = _ensure_mapping(payload, "type_map")
    invalid_types = sorted(
        {str(v) for v in type_map.values() if str(v).lower() not in {"str", "string", "int", "float", "bool", "date"}}
    )
    if invalid_types:
        raise ContractProfileError(f"Unsupported type_map values: {invalid_types}")

    dedupe_keys = [str(v) for v in _ensure_list(payload, "dedupe_keys")]

    return ContractProfile(
        contract_version=contract_version,
        tenant_id=str(payload["tenant_id"]),
        source_type=source_type,
        grain=str(payload["grain"]),
        timezone=str(payload["timezone"]),
        id_columns={str(k): str(v) for k, v in _ensure_mapping(payload, "id_columns").items()},
        field_map={str(k): str(v) for k, v in _ensure_mapping(payload, "field_map").items()},
        type_map={str(k): str(v).lower() for k, v in type_map.items()},
        unit_map=_ensure_mapping(payload, "unit_map", allow_empty=True),
        null_policy=_ensure_mapping(payload, "null_policy", allow_empty=True),
        dedupe_keys=dedupe_keys,
        dq_thresholds=_coerce_float_thresholds(_ensure_mapping(payload, "dq_thresholds")),
        country_code=str(payload.get("country_code", "unknown")),
    )


def load_contract_profile(path: str | Path) -> ContractProfile:
    """Load and validate a YAML contract profile from disk."""
    profile_path = Path(path)
    if not profile_path.exists():
        raise ContractProfileError(f"Contract profile not found: {profile_path}")

    if profile_path.suffix.lower() not in {".yaml", ".yml"}:
        raise ContractProfileError("Contract profile must be a .yaml or .yml file")

    try:
        payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContractProfileError(f"Invalid YAML in contract profile: {exc}") from exc

    if not isinstance(payload, dict):
        raise ContractProfileError("Contract profile root must be a mapping")

    return _normalize_profile(payload)
