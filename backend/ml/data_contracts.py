"""
Canonical training-data contracts for multi-dataset forecasting.

This module normalizes public datasets and synthetic seed data into one
transaction-level schema used by feature engineering and retraining.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class DatasetReadiness:
    dataset_id: str
    status: str
    message: str
    forecast_grain: str
    required_files: list[str]
    missing_files: list[str]
    required_fields: list[str]
    missing_fields: list[str]
    date_min: str = ""
    date_max: str = ""
    row_count: int = 0

CANONICAL_REQUIRED_COLS = {"date", "store_id", "product_id", "quantity"}
CANONICAL_BASE_COLS = [
    "date",
    "store_id",
    "product_id",
    "quantity",
    "category",
    "is_promotional",
    "is_holiday",
    "dataset_id",
    "country_code",
    "frequency",
    "product_grain",
    "returns_adjustment",
    "is_return_week",
]


def _read_csv(path: Path) -> pd.DataFrame:
    """Read CSV with light dtype inference and optional date parsing."""
    header = pd.read_csv(path, nrows=0)
    date_cols = [c for c in header.columns if c.lower() in {"date", "trans_date"}]
    return pd.read_csv(path, parse_dates=date_cols if date_cols else False, low_memory=False)


def _finalize_contract(
    df: pd.DataFrame,
    *,
    dataset_id: str,
    country_code: str,
    frequency: str,
) -> pd.DataFrame:
    """Enforce canonical schema and metadata defaults."""
    missing = CANONICAL_REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required canonical columns: {sorted(missing)}")

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"])

    out["store_id"] = out["store_id"].astype(str)
    out["product_id"] = out["product_id"].astype(str)
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce").fillna(0.0)

    if "category" not in out.columns:
        out["category"] = out["product_id"]
    out["category"] = out["category"].astype(str)
    if "is_promotional" not in out.columns:
        out["is_promotional"] = 0
    if "is_holiday" not in out.columns:
        out["is_holiday"] = 0

    out["is_promotional"] = pd.to_numeric(out["is_promotional"], errors="coerce").fillna(0).astype(int)
    out["is_holiday"] = pd.to_numeric(out["is_holiday"], errors="coerce").fillna(0).astype(int)
    out["dataset_id"] = dataset_id
    out["country_code"] = country_code
    out["frequency"] = frequency
    if "product_grain" not in out.columns:
        out["product_grain"] = "sku_level"
    if "returns_adjustment" not in out.columns:
        out["returns_adjustment"] = 0.0
    if "is_return_week" not in out.columns:
        out["is_return_week"] = 0
    out["product_grain"] = out["product_grain"].astype(str)
    out["returns_adjustment"] = pd.to_numeric(out["returns_adjustment"], errors="coerce").fillna(0.0)
    out["is_return_week"] = pd.to_numeric(out["is_return_week"], errors="coerce").fillna(0).astype(int)

    for col in CANONICAL_BASE_COLS:
        if col not in out.columns:
            out[col] = 0

    out = out[CANONICAL_BASE_COLS]
    logger.info(
        "data_contract.ready",
        dataset_id=dataset_id,
        rows=len(out),
        stores=out["store_id"].nunique(),
        products=out["product_id"].nunique(),
        date_range=f"{out['date'].min()} → {out['date'].max()}",
        frequency=frequency,
    )
    return out


def _load_favorita(data_dir: Path) -> pd.DataFrame:
    train = _read_csv(data_dir / "train.csv")
    mapped = train.rename(
        columns={
            "store_nbr": "store_id",
            "family": "category",
            "family_id": "product_id",
            "sales": "quantity",
            "onpromotion": "is_promotional",
        }
    )
    if "product_id" not in mapped.columns:
        mapped["product_id"] = mapped["category"].astype(str)
    return _finalize_contract(mapped, dataset_id="favorita", country_code="EC", frequency="daily")


def inspect_dataset_readiness(data_dir: str | Path) -> DatasetReadiness:
    """Inspect dataset readiness without silently falling back across domains."""
    path = Path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    favorita_markers = {"holidays_events.csv", "oil.csv", "test.csv"}
    favorita_required = ["train.csv", "holidays_events.csv"]
    favorita_fields = ["date", "store_nbr", "family", "sales", "onpromotion"]

    looks_like_favorita = (
        "favorita" in path.name.lower()
        or "favorita" in str(path).lower()
        or bool(favorita_markers.intersection({p.name for p in path.glob("*.csv")}))
    )
    if looks_like_favorita:
        missing_files = [name for name in favorita_required if not (path / name).exists()]
        if missing_files:
            return DatasetReadiness(
                dataset_id="favorita",
                status="blocked",
                message=(
                    "Favorita dataset is not ready. Expected Kaggle transaction-grain files are missing; "
                    "the pipeline requires train.csv at store-family-day grain and will not fall back to generic CSV loading."
                ),
                forecast_grain="store_nbr x family x date",
                required_files=favorita_required,
                missing_files=missing_files,
                required_fields=favorita_fields,
                missing_fields=favorita_fields,
            )

        header = pd.read_csv(path / "train.csv", nrows=0)
        missing_fields = [field for field in favorita_fields if field not in header.columns]
        if missing_fields:
            return DatasetReadiness(
                dataset_id="favorita",
                status="invalid",
                message="Favorita train.csv is present but missing required fields for store-family-day modeling.",
                forecast_grain="store_nbr x family x date",
                required_files=favorita_required,
                missing_files=[],
                required_fields=favorita_fields,
                missing_fields=missing_fields,
            )

        frame = pd.read_csv(path / "train.csv", usecols=["date"], parse_dates=["date"], low_memory=False)
        if frame.empty:
            return DatasetReadiness(
                dataset_id="favorita",
                status="invalid",
                message="Favorita train.csv is empty.",
                forecast_grain="store_nbr x family x date",
                required_files=favorita_required,
                missing_files=[],
                required_fields=favorita_fields,
                missing_fields=[],
            )

        date_series = frame["date"].dropna().sort_values()
        if date_series.empty:
            return DatasetReadiness(
                dataset_id="favorita",
                status="invalid",
                message="Favorita train.csv does not contain parseable dates.",
                forecast_grain="store_nbr x family x date",
                required_files=favorita_required,
                missing_files=[],
                required_fields=favorita_fields,
                missing_fields=[],
            )

        coverage_days = int((date_series.max() - date_series.min()).days) + 1
        min_days = max(28, min(90, len(date_series)))
        status = "ready" if coverage_days >= min_days else "limited"
        message = (
            "Favorita dataset ready for store-family-day modeling."
            if status == "ready"
            else "Favorita source files are valid, but date coverage is short for full time-series validation."
        )
        return DatasetReadiness(
            dataset_id="favorita",
            status=status,
            message=message,
            forecast_grain="store_nbr x family x date",
            required_files=favorita_required,
            missing_files=[],
            required_fields=favorita_fields,
            missing_fields=[],
            date_min=str(date_series.min().date()),
            date_max=str(date_series.max().date()),
            row_count=int(len(frame)),
        )

    return DatasetReadiness(
        dataset_id="generic",
        status="unknown",
        message="Dataset domain inferred at load time.",
        forecast_grain="dataset_specific",
        required_files=[],
        missing_files=[],
        required_fields=[],
        missing_fields=[],
    )


def _load_walmart(data_dir: Path) -> pd.DataFrame:
    train = _read_csv(data_dir / "train.csv")
    mapped = train.rename(
        columns={
            "Store": "store_id",
            "Dept": "category",
            "Weekly_Sales": "quantity",
            "Date": "date",
            "IsHoliday": "is_holiday",
        }
    )
    # Walmart includes negative weekly sales values due to returns/adjustments.
    # Demand target uses non-negative net sales while preserving return signal.
    net_sales = pd.to_numeric(mapped["quantity"], errors="coerce").fillna(0.0)
    mapped["returns_adjustment"] = net_sales.clip(upper=0.0)
    mapped["is_return_week"] = (net_sales < 0).astype(int)
    mapped["quantity"] = net_sales.clip(lower=0.0)
    mapped["product_id"] = mapped["category"].astype(str)
    return _finalize_contract(mapped, dataset_id="walmart", country_code="US", frequency="weekly")


def _load_rossmann(data_dir: Path) -> pd.DataFrame:
    train = _read_csv(data_dir / "train.csv")
    mapped = train.rename(
        columns={
            "Store": "store_id",
            "Sales": "quantity",
            "Date": "date",
            "Promo": "is_promotional",
        }
    )
    mapped["product_id"] = "all"
    mapped["category"] = "all"
    mapped["product_grain"] = "store_level_only"
    return _finalize_contract(mapped, dataset_id="rossmann", country_code="DE", frequency="daily")


def _load_seed_transactions(data_dir: Path) -> pd.DataFrame:
    files = sorted((data_dir / "transactions").glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No transaction CSV files found under {(data_dir / 'transactions')}")

    frames = []
    for path in files:
        df = _read_csv(path)
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)

    mapped = combined.rename(
        columns={
            "STORE_NBR": "store_id",
            "ITEM_NBR": "product_id",
            "QTY_SOLD": "quantity",
            "TRANS_DATE": "date",
        }
    )
    mapped["category"] = mapped["product_id"].astype(str)
    mapped["is_promotional"] = 0
    return _finalize_contract(mapped, dataset_id="seed_synthetic", country_code="US", frequency="daily")


def _load_generic_flat_csvs(data_dir: Path) -> pd.DataFrame:
    """
    Legacy fallback for ad hoc CSV directories.

    Reads only CSVs that contain at least one date-like column and one quantity-like
    column, then applies broad column normalization.
    """
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames: list[pd.DataFrame] = []
    for f in csv_files:
        path = Path(f)
        header = pd.read_csv(path, nrows=0)
        cols = {c.lower() for c in header.columns}
        has_date = bool(cols & {"date", "trans_date"})
        has_qty = bool(cols & {"quantity", "qty_sold", "sales", "weekly_sales"})
        if not (has_date and has_qty):
            continue
        frames.append(_read_csv(path))

    if not frames:
        raise ValueError(f"No transaction-like CSV files found in {data_dir}")

    combined = pd.concat(frames, ignore_index=True)
    cols_lower = {c.lower(): c for c in combined.columns}

    rename_map = {}
    if "store_nbr" in cols_lower:
        rename_map[cols_lower["store_nbr"]] = "store_id"
    if "store" in cols_lower and "store_id" not in cols_lower:
        rename_map[cols_lower["store"]] = "store_id"
    if "family" in cols_lower:
        rename_map[cols_lower["family"]] = "category"
    if "dept" in cols_lower and "category" not in cols_lower:
        rename_map[cols_lower["dept"]] = "category"
    if "item_nbr" in cols_lower:
        rename_map[cols_lower["item_nbr"]] = "product_id"
    if "sales" in cols_lower:
        rename_map[cols_lower["sales"]] = "quantity"
    if "weekly_sales" in cols_lower:
        rename_map[cols_lower["weekly_sales"]] = "quantity"
    if "qty_sold" in cols_lower:
        rename_map[cols_lower["qty_sold"]] = "quantity"
    if "trans_date" in cols_lower and "date" not in cols_lower:
        rename_map[cols_lower["trans_date"]] = "date"
    if "onpromotion" in cols_lower:
        rename_map[cols_lower["onpromotion"]] = "is_promotional"
    if "promo" in cols_lower and "is_promotional" not in cols_lower:
        rename_map[cols_lower["promo"]] = "is_promotional"
    if "isholiday" in cols_lower:
        rename_map[cols_lower["isholiday"]] = "is_holiday"

    mapped = combined.rename(columns=rename_map)

    if "product_id" not in mapped.columns:
        if "category" in mapped.columns:
            mapped["product_id"] = mapped["category"].astype(str)
        else:
            mapped["product_id"] = "all"

    return _finalize_contract(mapped, dataset_id="generic", country_code="unknown", frequency="unknown")


def load_canonical_transactions(data_dir: str) -> pd.DataFrame:
    """Load a dataset directory into the canonical transaction contract."""
    path = Path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    readiness = inspect_dataset_readiness(path)
    if readiness.dataset_id == "favorita" and readiness.status in {"blocked", "invalid"}:
        raise FileNotFoundError(
            f"{readiness.message} Missing files: {readiness.missing_files or 'none'}. "
            f"Required fields: {readiness.required_fields}."
        )

    if (path / "train.csv").exists() and (path / "holidays_events.csv").exists():
        return _load_favorita(path)

    if (path / "train.csv").exists() and (path / "features.csv").exists():
        return _load_walmart(path)

    if (path / "train.csv").exists() and (path / "store.csv").exists():
        return _load_rossmann(path)

    if (path / "transactions").is_dir():
        return _load_seed_transactions(path)

    return _load_generic_flat_csvs(path)
