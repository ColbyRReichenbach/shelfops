"""
Replay partition utilities.

Provides a strict temporal split contract so model training can exclude an
untouched holdout window (for example, the final 365 days).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


def _coerce_date(value: str | date | datetime | pd.Timestamp) -> date:
    ts = pd.to_datetime(value, errors="raise")
    if isinstance(ts, pd.Series):
        raise ValueError("Expected scalar date value")
    return ts.date()


def fingerprint_paths(paths: list[str] | None) -> str | None:
    """
    Build a deterministic fingerprint over source files.

    Uses path + size + mtime nanoseconds to avoid hashing full large files in the
    normal replay flow.
    """
    if not paths:
        return None

    digest = hashlib.sha256()
    for raw_path in sorted(paths):
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        stat = path.stat()
        digest.update(str(path.resolve()).encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
        digest.update(str(stat.st_mtime_ns).encode("utf-8"))
    return digest.hexdigest()


def build_time_partition(
    df: pd.DataFrame,
    holdout_days: int = 365,
    *,
    train_end_date: str | date | datetime | pd.Timestamp | None = None,
    date_col: str = "date",
    dataset_id: str | None = None,
    source_paths: list[str] | None = None,
) -> dict[str, Any]:
    """
    Partition a frame into pre-holdout train rows and untouched holdout rows.

    Returns:
      {
        "train_df": <pd.DataFrame>,
        "holdout_df": <pd.DataFrame>,
        "metadata": {...}
      }
    """
    if date_col not in df.columns:
        raise ValueError(f"Missing required date column: {date_col}")

    if holdout_days < 0:
        raise ValueError("holdout_days must be >= 0")

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=[date_col]).sort_values(date_col).reset_index(drop=True)
    if out.empty:
        raise ValueError("No rows remain after date parsing; cannot partition")

    max_date = out[date_col].max().date()
    min_date = out[date_col].min().date()

    if train_end_date is not None:
        train_end = _coerce_date(train_end_date)
    elif holdout_days > 0:
        train_end = max_date - timedelta(days=holdout_days)
    else:
        train_end = max_date

    train_mask = out[date_col].dt.date <= train_end
    holdout_mask = ~train_mask

    train_df = out.loc[train_mask].copy()
    holdout_df = out.loc[holdout_mask].copy()

    if train_df.empty:
        raise ValueError("Training partition is empty; choose an earlier train_end_date")

    if holdout_days > 0 and holdout_df.empty:
        raise ValueError("Holdout partition is empty; dataset too short for requested holdout_days")

    train_max_date = train_df[date_col].max().date()
    if train_max_date > train_end:
        raise ValueError(
            f"Partition integrity failure: train data contains {train_max_date} beyond train_end_date {train_end}"
        )

    holdout_start = holdout_df[date_col].min().date() if not holdout_df.empty else None
    holdout_end = holdout_df[date_col].max().date() if not holdout_df.empty else None

    metadata = {
        "dataset_id": dataset_id,
        "date_column": date_col,
        "min_date": min_date.isoformat(),
        "max_date": max_date.isoformat(),
        "train_end_date": train_end.isoformat(),
        "holdout_start_date": holdout_start.isoformat() if holdout_start else None,
        "holdout_end_date": holdout_end.isoformat() if holdout_end else None,
        "holdout_days_requested": int(holdout_days),
        "train_rows": int(len(train_df)),
        "holdout_rows": int(len(holdout_df)),
        "train_unique_dates": int(train_df[date_col].nunique()),
        "holdout_unique_dates": int(holdout_df[date_col].nunique()) if not holdout_df.empty else 0,
        "source_file_fingerprint": fingerprint_paths(source_paths),
        "source_fingerprint_type": "path_size_mtime_sha256" if source_paths else None,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    return {
        "train_df": train_df,
        "holdout_df": holdout_df,
        "metadata": metadata,
    }


def write_partition_manifest(metadata: dict[str, Any], output_path: str) -> str:
    """Persist partition metadata artifact as JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return str(path)
