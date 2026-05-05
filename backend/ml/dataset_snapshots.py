from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import is_scalar

SNAPSHOT_SCHEMA_VERSION = "v1"
DEFAULT_CLAIM_BOUNDARIES_REF = "data_registry/datasets.yaml"
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "models" / "dataset_snapshots"


def _stringify_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), sort_keys=True)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    if hasattr(value, "tolist") and not is_scalar(value):
        try:
            return json.dumps(value.tolist(), sort_keys=True)
        except Exception:  # noqa: BLE001
            pass
    if is_scalar(value) and pd.isna(value):
        return "<NULL>"
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            pass
    return str(value)


def _sorted_snapshot_frame(transactions_df: pd.DataFrame) -> pd.DataFrame:
    frame = transactions_df.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    order_cols = [col for col in ["date", "store_id", "product_id"] if col in frame.columns]
    if order_cols:
        frame = frame.sort_values(order_cols, kind="mergesort")
    cols = sorted(frame.columns)
    return frame[cols].reset_index(drop=True)


def compute_dataset_snapshot_hash(
    transactions_df: pd.DataFrame, *, schema_version: str = SNAPSHOT_SCHEMA_VERSION
) -> str:
    frame = _sorted_snapshot_frame(transactions_df)
    digest = hashlib.sha256()
    digest.update(f"schema_version={schema_version}\n".encode())
    digest.update(f"columns={','.join(frame.columns)}\n".encode())
    for row in frame.itertuples(index=False, name=None):
        digest.update(("|".join(_stringify_value(value) for value in row) + "\n").encode("utf-8"))
    return digest.hexdigest()


def _infer_frequency(transactions_df: pd.DataFrame) -> str:
    if "frequency" in transactions_df.columns and len(transactions_df) > 0:
        return str(transactions_df["frequency"].iloc[0])
    return "unknown"


def _infer_forecast_grain(transactions_df: pd.DataFrame, *, fallback: str = "dataset_specific") -> str:
    frequency = _infer_frequency(transactions_df)
    product_grain = (
        str(transactions_df["product_grain"].iloc[0])
        if "product_grain" in transactions_df.columns and len(transactions_df) > 0
        else "sku_level"
    )
    if product_grain == "store_level_only":
        return f"store_level_{frequency}"
    if frequency in {"daily", "weekly", "hourly"}:
        return f"store_product_{frequency}"
    return fallback


def _resolve_snapshot_profile(dataset_id: str, source_type: str | None = None) -> dict[str, str]:
    normalized = str(dataset_id or "").strip().lower()
    if normalized in {"m5", "m5_walmart"}:
        return {
            "source_type": source_type or "benchmark",
            "geography": "US",
            "implementation_status": "benchmark_active",
        }
    if normalized in {"freshretailnet", "freshretailnet_50k"}:
        return {
            "source_type": source_type or "benchmark",
            "geography": "non_us_mixed",
            "implementation_status": "benchmark_active",
        }
    if "square" in normalized:
        return {
            "source_type": source_type or "square",
            "geography": "tenant_defined",
            "implementation_status": "pilot_validation_active",
        }
    if any(token in normalized for token in {"csv", "onboarding", "tenant"}):
        return {
            "source_type": source_type or "csv",
            "geography": "tenant_defined",
            "implementation_status": "pilot_validation_active",
        }
    if normalized == "favorita":
        return {
            "source_type": source_type or "legacy_reference",
            "geography": "EC",
            "implementation_status": "legacy_reference",
        }
    return {
        "source_type": source_type or "unknown",
        "geography": "unknown",
        "implementation_status": "unknown",
    }


def create_dataset_snapshot(
    transactions_df: pd.DataFrame,
    *,
    dataset_id: str,
    source_type: str | None = None,
    schema_version: str = SNAPSHOT_SCHEMA_VERSION,
    forecast_grain: str | None = None,
    geography: str | None = None,
    implementation_status: str | None = None,
    claim_boundaries_ref: str = DEFAULT_CLAIM_BOUNDARIES_REF,
) -> dict[str, Any]:
    if len(transactions_df) == 0:
        raise ValueError("Cannot create dataset snapshot for empty dataframe")

    profile = _resolve_snapshot_profile(dataset_id, source_type=source_type)
    content_hash = compute_dataset_snapshot_hash(transactions_df, schema_version=schema_version)
    snapshot_id = f"dsnap_{content_hash[:16]}"
    dates = (
        pd.to_datetime(transactions_df["date"], errors="coerce") if "date" in transactions_df.columns else pd.Series()
    )

    return {
        "snapshot_id": snapshot_id,
        "dataset_id": dataset_id,
        "source_type": source_type or profile["source_type"],
        "row_count": int(len(transactions_df)),
        "store_count": int(transactions_df["store_id"].nunique()) if "store_id" in transactions_df.columns else 0,
        "product_count": int(transactions_df["product_id"].nunique()) if "product_id" in transactions_df.columns else 0,
        "date_min": str(dates.min().date()) if len(dates.dropna()) else "",
        "date_max": str(dates.max().date()) if len(dates.dropna()) else "",
        "content_hash": content_hash,
        "schema_version": schema_version,
        "frequency": _infer_frequency(transactions_df),
        "forecast_grain": forecast_grain or _infer_forecast_grain(transactions_df),
        "geography": geography or profile["geography"],
        "implementation_status": implementation_status or profile["implementation_status"],
        "claim_boundaries_ref": claim_boundaries_ref,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def persist_dataset_snapshot(snapshot: dict[str, Any], output_dir: Path | None = None) -> Path:
    target_dir = Path(output_dir or SNAPSHOT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{snapshot['snapshot_id']}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return path
