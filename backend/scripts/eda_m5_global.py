"""Generate a reproducible global EDA report for the M5/Walmart benchmark.

The report is intentionally product-facing: it turns raw benchmark behavior
into candidate ShelfOps hypotheses without making merchant-impact claims.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_DATA_DIR = Path("data/benchmarks/m5_walmart/subset_20spc")
DEFAULT_OUTPUT_DIR = Path("backend/reports/experiments/manual_ds/00_m5_global_eda")
SERIES_KEYS = ["store_id", "product_id"]


@dataclass(frozen=True)
class EDAPaths:
    output_dir: Path
    json_path: Path
    markdown_path: Path
    charts_dir: Path


def _load_frame(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "canonical_transactions.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing canonical M5 transactions at {path}")

    frame = pd.read_csv(path, low_memory=False)
    required = {"date", "store_id", "product_id", "quantity"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"M5 canonical transactions missing required columns: {sorted(missing)}")

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"].notna()].copy()
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0.0).clip(lower=0.0)
    frame["category"] = frame.get("category", frame.get("cat_id", "UNKNOWN")).fillna("UNKNOWN").astype(str)
    frame["dept_id"] = frame.get("dept_id", frame["category"]).fillna(frame["category"]).astype(str)
    frame["state_id"] = frame.get("state_id", frame["store_id"].astype(str).str[:2]).fillna("UNKNOWN").astype(str)
    frame["weekday"] = frame.get("weekday", frame["date"].dt.day_name()).fillna(frame["date"].dt.day_name()).astype(str)
    frame["month"] = pd.to_numeric(frame.get("month", frame["date"].dt.month), errors="coerce").fillna(frame["date"].dt.month).astype(int)
    frame["year"] = pd.to_numeric(frame.get("year", frame["date"].dt.year), errors="coerce").fillna(frame["date"].dt.year).astype(int)
    frame["is_holiday"] = pd.to_numeric(frame.get("is_holiday", 0), errors="coerce").fillna(0).astype(int)
    frame["is_promotional"] = pd.to_numeric(frame.get("is_promotional", 0), errors="coerce").fillna(0).astype(int)

    price_col = "sell_price" if "sell_price" in frame.columns else "price" if "price" in frame.columns else None
    if price_col:
        frame["price"] = pd.to_numeric(frame[price_col], errors="coerce")
    else:
        frame["price"] = np.nan
    frame["series_id"] = frame["store_id"].astype(str) + "::" + frame["product_id"].astype(str)
    return frame.sort_values(SERIES_KEYS + ["date"], kind="mergesort").reset_index(drop=True)


def _round_float(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(numeric):
        return None
    return round(numeric, digits)


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _records(frame: pd.DataFrame, *, limit: int | None = None) -> list[dict[str, Any]]:
    if limit is not None:
        frame = frame.head(limit)
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _demand_classification(adi: float | None, cv2: float | None, nonzero_days: int) -> str:
    """Syntetos-Boylan style intermittent demand classification."""
    if nonzero_days <= 0 or adi is None or cv2 is None:
        return "no_sales_observed"
    if adi <= 1.32 and cv2 <= 0.49:
        return "smooth"
    if adi <= 1.32 and cv2 > 0.49:
        return "erratic"
    if adi > 1.32 and cv2 <= 0.49:
        return "intermittent"
    return "lumpy"


def _series_lifecycle_frame(frame: pd.DataFrame) -> pd.DataFrame:
    dataset_start = pd.to_datetime(frame["date"]).min()
    dataset_end = pd.to_datetime(frame["date"]).max()
    rows: list[dict[str, Any]] = []

    for (store_id, product_id), group in frame.groupby(SERIES_KEYS, sort=False):
        group = group.sort_values("date", kind="mergesort")
        qty = pd.to_numeric(group["quantity"], errors="coerce").fillna(0.0)
        dates = pd.to_datetime(group["date"])
        positive = group[qty > 0]
        nonzero_qty = pd.to_numeric(positive["quantity"], errors="coerce").fillna(0.0)
        nonzero_days = int(len(nonzero_qty))

        if positive.empty:
            first_sale_date = None
            last_sale_date = None
            first_sale_offset_days = None
            last_sale_tail_days = None
            pre_first_sale_zero_days = int((qty == 0).sum())
            post_last_sale_zero_days = 0
            active_window_days = 0
            active_window_zero_rate = None
            intersale_gap_median_days = None
            intersale_gap_p90_days = None
        else:
            positive_dates = pd.to_datetime(positive["date"])
            first_sale = positive_dates.min()
            last_sale = positive_dates.max()
            active_mask = (dates >= first_sale) & (dates <= last_sale)
            active_qty = qty[active_mask]
            sale_gaps = positive_dates.sort_values().diff().dt.days.dropna()
            first_sale_date = first_sale.date().isoformat()
            last_sale_date = last_sale.date().isoformat()
            first_sale_offset_days = int((first_sale - dataset_start).days)
            last_sale_tail_days = int((dataset_end - last_sale).days)
            pre_first_sale_zero_days = int(((dates < first_sale) & (qty == 0)).sum())
            post_last_sale_zero_days = int(((dates > last_sale) & (qty == 0)).sum())
            active_window_days = int(active_mask.sum())
            active_window_zero_rate = float((active_qty == 0).mean()) if active_window_days else None
            intersale_gap_median_days = float(sale_gaps.median()) if len(sale_gaps) else None
            intersale_gap_p90_days = float(sale_gaps.quantile(0.90)) if len(sale_gaps) else None

        avg_nonzero_qty = float(nonzero_qty.mean()) if nonzero_days else None
        cv2 = (
            float((nonzero_qty.std(ddof=0) / nonzero_qty.mean()) ** 2)
            if nonzero_days > 1 and float(nonzero_qty.mean()) > 0
            else 0.0 if nonzero_days == 1 else None
        )
        adi = float(len(group) / nonzero_days) if nonzero_days else None
        rows.append(
            {
                "store_id": store_id,
                "product_id": product_id,
                "series_id": f"{store_id}::{product_id}",
                "first_sale_date": first_sale_date,
                "last_sale_date": last_sale_date,
                "first_sale_offset_days": first_sale_offset_days,
                "last_sale_tail_days": last_sale_tail_days,
                "pre_first_sale_zero_days": pre_first_sale_zero_days,
                "post_last_sale_zero_days": post_last_sale_zero_days,
                "active_window_days": active_window_days,
                "active_window_zero_rate": active_window_zero_rate,
                "intersale_gap_median_days": intersale_gap_median_days,
                "intersale_gap_p90_days": intersale_gap_p90_days,
                "avg_nonzero_qty": avg_nonzero_qty,
                "adi": adi,
                "cv2": cv2,
                "demand_classification": _demand_classification(adi, cv2, nonzero_days),
            }
        )

    return pd.DataFrame(rows)


def _series_summary(frame: pd.DataFrame) -> pd.DataFrame:
    summary = (
        frame.groupby(SERIES_KEYS, dropna=False)
        .agg(
            category=("category", "first"),
            dept_id=("dept_id", "first"),
            state_id=("state_id", "first"),
            rows=("quantity", "size"),
            total_units=("quantity", "sum"),
            avg_daily_units=("quantity", "mean"),
            median_daily_units=("quantity", "median"),
            nonzero_days=("quantity", lambda s: int((s > 0).sum())),
            max_daily_units=("quantity", "max"),
            price_coverage=("price", lambda s: float(s.notna().mean())),
            median_price=("price", "median"),
            price_unique_count=("price", lambda s: int(s.dropna().nunique())),
        )
        .reset_index()
    )
    summary["series_id"] = summary["store_id"].astype(str) + "::" + summary["product_id"].astype(str)
    summary["nonzero_rate"] = summary["nonzero_days"] / summary["rows"].replace(0, np.nan)
    active = summary[summary["nonzero_rate"] >= 0.20]
    q33 = float(active["avg_daily_units"].quantile(0.33)) if len(active) else 0.0
    q66 = float(active["avg_daily_units"].quantile(0.66)) if len(active) else 0.0
    conditions = [
        summary["nonzero_rate"] < 0.20,
        (summary["avg_daily_units"] < q33) & (summary["nonzero_rate"] >= 0.20),
        (summary["avg_daily_units"] >= q33) & (summary["avg_daily_units"] < q66) & (summary["nonzero_rate"] >= 0.35),
        (summary["avg_daily_units"] >= q66) & (summary["nonzero_rate"] >= 0.60),
    ]
    choices = ["intermittent", "slow", "medium", "fast"]
    summary["velocity_segment"] = np.select(conditions, choices, default="medium")
    q75_total = float(summary["total_units"].quantile(0.75)) if len(summary) else 0.0
    summary["is_high_volume"] = summary["total_units"] >= q75_total
    lifecycle = _series_lifecycle_frame(frame)
    summary = summary.merge(lifecycle, on=SERIES_KEYS + ["series_id"], how="left")
    return summary


def _overall_summary(frame: pd.DataFrame, series: pd.DataFrame, data_dir: Path) -> dict[str, Any]:
    total_units = float(frame["quantity"].sum())
    total_rows = int(len(frame))
    nonzero_rows = int((frame["quantity"] > 0).sum())
    price_coverage = float(frame["price"].notna().mean()) if total_rows else 0.0
    top_decile_count = max(1, int(np.ceil(len(series) * 0.10)))
    top_decile_units = float(series.sort_values("total_units", ascending=False).head(top_decile_count)["total_units"].sum())

    event_cols = [col for col in ("event_name_1", "event_name_2") if col in frame.columns]
    event_mask = pd.Series(False, index=frame.index)
    for col in event_cols:
        event_mask = event_mask | frame[col].notna()

    snap_cols = [col for col in ("snap_CA", "snap_TX", "snap_WI") if col in frame.columns]
    snap_mask = pd.Series(False, index=frame.index)
    for col in snap_cols:
        snap_mask = snap_mask | (pd.to_numeric(frame[col], errors="coerce").fillna(0).astype(float) > 0)

    return {
        "dataset_id": "m5_walmart",
        "data_dir": str(data_dir),
        "provenance": "benchmark",
        "claim_boundary": "M5/Walmart benchmark EDA only. No measured merchant outcomes or live inventory claims.",
        "rows": total_rows,
        "stores": int(frame["store_id"].nunique()),
        "products": int(frame["product_id"].nunique()),
        "series": int(frame["series_id"].nunique()),
        "categories": sorted(frame["category"].dropna().unique().tolist()),
        "departments": int(frame["dept_id"].nunique()),
        "states": sorted(frame["state_id"].dropna().unique().tolist()),
        "date_min": frame["date"].min().date().isoformat(),
        "date_max": frame["date"].max().date().isoformat(),
        "days": int(frame["date"].nunique()),
        "total_units": _round_float(total_units, 3),
        "nonzero_rows": nonzero_rows,
        "zero_sales_rate": _round_float(1.0 - (nonzero_rows / total_rows), 6) if total_rows else None,
        "avg_units_per_row": _round_float(frame["quantity"].mean()),
        "avg_units_when_nonzero": _round_float(frame.loc[frame["quantity"] > 0, "quantity"].mean()),
        "price_coverage": _round_float(price_coverage),
        "median_price": _round_float(frame["price"].median()),
        "event_day_row_rate": _round_float(float(event_mask.mean())),
        "holiday_row_rate": _round_float(float(frame["is_holiday"].mean())),
        "snap_row_rate": _round_float(float(snap_mask.mean())),
        "explicit_promo_row_rate": _round_float(float(frame["is_promotional"].mean())),
        "top_10pct_series_unit_share": _round_float(_safe_div(top_decile_units, total_units)),
        "rows_per_series_min": int(series["rows"].min()),
        "rows_per_series_max": int(series["rows"].max()),
    }


def _data_quality_summary(frame: pd.DataFrame, series: pd.DataFrame) -> dict[str, Any]:
    expected_grid_rows = int(frame["date"].nunique() * frame["series_id"].nunique())
    duplicate_keys = int(frame.duplicated(subset=["date", *SERIES_KEYS]).sum())
    important_columns = [
        "date",
        "store_id",
        "product_id",
        "quantity",
        "category",
        "dept_id",
        "state_id",
        "price",
        "sell_price",
        "event_name_1",
        "event_type_1",
        "snap_CA",
        "snap_TX",
        "snap_WI",
    ]
    column_rows = []
    for column in [col for col in important_columns if col in frame.columns]:
        values = frame[column]
        column_rows.append(
            {
                "column": column,
                "non_null_rate": _round_float(float(values.notna().mean())),
                "distinct_values": int(values.dropna().nunique()),
            }
        )

    price_by_year = (
        frame.groupby("year", dropna=False)
        .agg(rows=("quantity", "size"), price_coverage=("price", lambda s: float(s.notna().mean())))
        .reset_index()
        .sort_values("year")
    )
    lifecycle = _lifecycle_summary(series)
    return {
        "expected_dense_grid_rows": expected_grid_rows,
        "actual_rows": int(len(frame)),
        "dense_grid_coverage": _round_float(_safe_div(float(len(frame)), float(expected_grid_rows))),
        "duplicate_series_date_rows": duplicate_keys,
        "negative_quantity_rows_after_canonicalization": int((frame["quantity"] < 0).sum()),
        "column_profile": column_rows,
        "price_coverage_by_year": _records(price_by_year),
        "lifecycle_summary": lifecycle,
        "retail_data_cautions": [
            "M5 has daily unit sales but not true on-hand inventory, purchase orders, supplier lead times, shelf capacity, or cycle-count outcomes.",
            "A zero-sales row can mean no demand, no shelf availability, no customer traffic for that SKU, or item lifecycle/ranging behavior; it is not a confirmed no-demand observation.",
            "Sell-price changes are observable, but explicit promo flags are not populated in this canonical subset.",
        ],
    }


def _late_launch_deep_dive(frame: pd.DataFrame, series: pd.DataFrame) -> dict[str, Any]:
    """Investigate whether late first sales look seasonal or lifecycle/ranging-driven."""
    dataset_start = pd.to_datetime(frame["date"]).min()
    dataset_end = pd.to_datetime(frame["date"]).max()
    late = series[pd.to_numeric(series["first_sale_offset_days"], errors="coerce").fillna(0) > 90]
    late_ids = set(late["series_id"])
    rows: list[dict[str, Any]] = []

    if not late_ids:
        return {
            "method": "Late launch means first observed sale more than 90 days after dataset start.",
            "thresholds": {},
            "classification_summary": [],
            "by_category": [],
            "high_volume_examples": [],
            "most_delayed_examples": [],
            "nonstandard_examples": [],
            "read": "No late-launch series found.",
        }

    for series_id, group in frame[frame["series_id"].isin(late_ids)].groupby("series_id", sort=False):
        group = group.sort_values("date", kind="mergesort")
        qty = pd.to_numeric(group["quantity"], errors="coerce").fillna(0.0)
        positive = group[qty > 0].copy()
        if positive.empty:
            continue

        positive["year"] = positive["date"].dt.year
        positive["month"] = positive["date"].dt.month
        first_sale = pd.to_datetime(positive["date"]).min()
        last_sale = pd.to_datetime(positive["date"]).max()
        first_sale_offset_days = int((first_sale - dataset_start).days)
        last_sale_tail_days = int((dataset_end - last_sale).days)
        active_span_days = int((last_sale - first_sale).days) + 1
        active_mask = (group["date"] >= first_sale) & (group["date"] <= last_sale)
        active_zero_rate = float((qty[active_mask] == 0).mean()) if active_mask.any() else None

        priced = group[group["price"].notna()]
        first_price = pd.to_datetime(priced["date"]).min() if len(priced) else pd.NaT
        first_price_minus_first_sale_days = (
            int((first_price - first_sale).days) if pd.notna(first_price) else None
        )
        price_aligned_to_first_sale = (
            first_price_minus_first_sale_days is not None
            and abs(first_price_minus_first_sale_days) <= 14
        )

        month_units = positive.groupby("month", dropna=False)["quantity"].sum().sort_values(ascending=False)
        top_3_month_unit_share = (
            float(month_units.head(3).sum() / month_units.sum()) if float(month_units.sum()) else None
        )
        top_month = int(month_units.index[0]) if len(month_units) else None
        year_month = positive.groupby(["year", "month"], dropna=False)["quantity"].sum().reset_index()
        positive_years = int(positive["year"].nunique())
        positive_months = int(positive["month"].nunique())
        top_month_years = int(year_month.loc[year_month["month"] == top_month, "year"].nunique()) if top_month else 0
        top_month_recurrence_rate = _safe_div(float(top_month_years), float(positive_years))
        total_units = float(positive["quantity"].sum())
        nonzero_days = int(len(positive))

        possible_seasonal = (
            positive_years >= 3
            and positive_months <= 5
            and (top_3_month_unit_share or 0) >= 0.65
            and (top_month_recurrence_rate or 0) >= 0.60
        )
        likely_late_ranged = (
            price_aligned_to_first_sale
            and last_sale_tail_days <= 90
            and active_span_days >= 365
            and (positive_months >= 8 or (top_3_month_unit_share or 0) < 0.65)
        )
        too_sparse = nonzero_days < 30 or total_units < 100

        if possible_seasonal:
            classification = "possible_seasonal"
        elif likely_late_ranged:
            classification = "likely_late_ranged_or_introduced"
        elif too_sparse:
            classification = "too_sparse_to_classify"
        elif last_sale_tail_days > 90 or active_span_days < 365:
            classification = "possible_lifecycle_or_delist"
        else:
            classification = "late_start_no_seasonal_concentration"

        rows.append(
            {
                "store_id": str(group["store_id"].iloc[0]),
                "product_id": str(group["product_id"].iloc[0]),
                "series_id": series_id,
                "category": str(group["category"].iloc[0]),
                "dept_id": str(group["dept_id"].iloc[0]),
                "first_sale_date": first_sale.date().isoformat(),
                "last_sale_date": last_sale.date().isoformat(),
                "first_sale_offset_days": first_sale_offset_days,
                "last_sale_tail_days": last_sale_tail_days,
                "first_price_date": None if pd.isna(first_price) else first_price.date().isoformat(),
                "first_price_minus_first_sale_days": first_price_minus_first_sale_days,
                "price_aligned_to_first_sale": bool(price_aligned_to_first_sale),
                "active_span_days": active_span_days,
                "active_zero_rate": _round_float(active_zero_rate),
                "total_units": _round_float(total_units, 3),
                "nonzero_days": nonzero_days,
                "nonzero_rate": _round_float(nonzero_days / len(group)),
                "positive_years": positive_years,
                "positive_months": positive_months,
                "top_months_by_units": ",".join(str(int(month)) for month in month_units.head(4).index.tolist()),
                "top_3_month_unit_share": _round_float(top_3_month_unit_share),
                "top_month_recurrence_rate": _round_float(top_month_recurrence_rate),
                "classification": classification,
            }
        )

    detail = pd.DataFrame(rows)
    if detail.empty:
        return {
            "method": "Late launch means first observed sale more than 90 days after dataset start.",
            "thresholds": {},
            "classification_summary": [],
            "by_category": [],
            "high_volume_examples": [],
            "most_delayed_examples": [],
            "nonstandard_examples": [],
            "read": "Late-launch rows were present, but no positive-sale SKU examples were available.",
        }

    summary = (
        detail.groupby("classification", dropna=False)
        .agg(
            series=("series_id", "size"),
            products=("product_id", "nunique"),
            total_units=("total_units", "sum"),
            avg_first_sale_offset_days=("first_sale_offset_days", "mean"),
            avg_active_span_days=("active_span_days", "mean"),
            avg_positive_months=("positive_months", "mean"),
            avg_top_3_month_unit_share=("top_3_month_unit_share", "mean"),
            price_aligned_rate=("price_aligned_to_first_sale", "mean"),
        )
        .reset_index()
        .sort_values("series", ascending=False)
    )
    summary["unit_share_within_late_launch"] = summary["total_units"] / summary["total_units"].sum()

    by_category = (
        detail.groupby(["category", "classification"], dropna=False)
        .agg(series=("series_id", "size"), total_units=("total_units", "sum"))
        .reset_index()
        .sort_values(["category", "series"], ascending=[True, False])
    )

    likely = detail[detail["classification"] == "likely_late_ranged_or_introduced"]
    seasonal = detail[detail["classification"] == "possible_seasonal"]
    nonstandard = detail[detail["classification"] != "likely_late_ranged_or_introduced"]
    likely_rate = _safe_div(float(len(likely)), float(len(detail)))
    seasonal_rate = _safe_div(float(len(seasonal)), float(len(detail)))

    return {
        "method": (
            "Late launch means first observed sale more than 90 days after dataset start. "
            "The drilldown compares first sale to first available sell price, active span, "
            "month concentration, and recurrence across years."
        ),
        "thresholds": {
            "late_launch_first_sale_offset_days": 90,
            "price_alignment_window_days": 14,
            "seasonal_min_positive_years": 3,
            "seasonal_max_positive_months": 5,
            "seasonal_min_top_3_month_unit_share": 0.65,
            "seasonal_min_top_month_recurrence_rate": 0.60,
            "too_sparse_nonzero_days": 30,
            "too_sparse_total_units": 100,
        },
        "late_launch_series": int(len(detail)),
        "likely_late_ranged_or_introduced_rate": _round_float(likely_rate),
        "possible_seasonal_rate": _round_float(seasonal_rate),
        "price_aligned_late_launch_rate": _round_float(float(detail["price_aligned_to_first_sale"].mean())),
        "classification_summary": _records(summary),
        "by_category": _records(by_category),
        "high_volume_examples": _records(detail.sort_values("total_units", ascending=False), limit=12),
        "most_delayed_examples": _records(
            detail.sort_values(["first_sale_offset_days", "total_units"], ascending=[False, False]),
            limit=12,
        ),
        "nonstandard_examples": _records(
            nonstandard.sort_values(["first_sale_offset_days", "total_units"], ascending=[False, False]),
            limit=12,
        ),
        "read": (
            "Late first sale is not strong evidence of classic seasonality in this subset. "
            "Most late-start series have sell price becoming available within about two weeks "
            "of first sale, continue selling near the dataset end, and sell across many months. "
            "That looks more like item/store ranging or introduction timing than a recurring "
            "seasonal-only demand pattern."
        ),
    }


def _lifecycle_summary(series: pd.DataFrame) -> dict[str, Any]:
    total_rows = float(series["rows"].sum()) if len(series) else 0.0
    pre_first = float(series["pre_first_sale_zero_days"].fillna(0).sum()) if "pre_first_sale_zero_days" in series else 0.0
    post_last = float(series["post_last_sale_zero_days"].fillna(0).sum()) if "post_last_sale_zero_days" in series else 0.0
    late_launch = series["first_sale_offset_days"].fillna(0) > 90
    dormant_tail = series["last_sale_tail_days"].fillna(0) > 90
    no_sales = series["nonzero_days"].fillna(0) == 0

    by_category = (
        series.groupby("category", dropna=False)
        .agg(
            series=("series_id", "size"),
            late_launch_rate=("first_sale_offset_days", lambda s: float((s.fillna(0) > 90).mean())),
            dormant_tail_rate=("last_sale_tail_days", lambda s: float((s.fillna(0) > 90).mean())),
            median_first_sale_offset_days=("first_sale_offset_days", "median"),
            median_last_sale_tail_days=("last_sale_tail_days", "median"),
            avg_active_window_zero_rate=("active_window_zero_rate", "mean"),
        )
        .reset_index()
        .sort_values("late_launch_rate", ascending=False)
    )
    return {
        "series_with_no_sales_rate": _round_float(float(no_sales.mean())),
        "late_launch_series_rate": _round_float(float(late_launch.mean())),
        "dormant_tail_series_rate": _round_float(float(dormant_tail.mean())),
        "pre_first_sale_zero_row_share": _round_float(_safe_div(pre_first, total_rows)),
        "post_last_sale_zero_row_share": _round_float(_safe_div(post_last, total_rows)),
        "median_first_sale_offset_days": _round_float(series["first_sale_offset_days"].median()),
        "median_last_sale_tail_days": _round_float(series["last_sale_tail_days"].median()),
        "avg_active_window_zero_rate": _round_float(series["active_window_zero_rate"].mean()),
        "by_category": _records(by_category),
    }


def _category_summary(frame: pd.DataFrame, series: pd.DataFrame) -> list[dict[str, Any]]:
    category = (
        frame.groupby("category", dropna=False)
        .agg(
            rows=("quantity", "size"),
            stores=("store_id", "nunique"),
            products=("product_id", "nunique"),
            total_units=("quantity", "sum"),
            avg_units_per_row=("quantity", "mean"),
            zero_sales_rate=("quantity", lambda s: float((s == 0).mean())),
            median_price=("price", "median"),
            event_row_rate=("is_holiday", "mean"),
        )
        .reset_index()
    )
    series_category = (
        series.groupby("category", dropna=False)
        .agg(
            series=("series_id", "size"),
            avg_series_daily_units=("avg_daily_units", "mean"),
            avg_series_nonzero_rate=("nonzero_rate", "mean"),
            price_change_series_rate=("price_unique_count", lambda s: float((s > 1).mean())),
        )
        .reset_index()
    )
    category = category.merge(series_category, on="category", how="left")
    category["unit_share"] = category["total_units"] / category["total_units"].sum()
    return _records(category.sort_values("total_units", ascending=False))


def _intermittent_demand_summary(series: pd.DataFrame) -> dict[str, Any]:
    taxonomy = (
        series.groupby("demand_classification", dropna=False)
        .agg(
            series=("series_id", "size"),
            products=("product_id", "nunique"),
            total_units=("total_units", "sum"),
            avg_daily_units=("avg_daily_units", "mean"),
            avg_nonzero_rate=("nonzero_rate", "mean"),
            median_adi=("adi", "median"),
            median_cv2=("cv2", "median"),
            median_intersale_gap_days=("intersale_gap_median_days", "median"),
            p90_intersale_gap_days=("intersale_gap_p90_days", "median"),
        )
        .reset_index()
    )
    taxonomy["unit_share"] = taxonomy["total_units"] / taxonomy["total_units"].sum()
    order = {"smooth": 0, "erratic": 1, "intermittent": 2, "lumpy": 3, "no_sales_observed": 4}
    taxonomy["_order"] = taxonomy["demand_classification"].map(order).fillna(99)

    by_category = (
        series.groupby(["category", "demand_classification"], dropna=False)
        .agg(series=("series_id", "size"), total_units=("total_units", "sum"))
        .reset_index()
        .sort_values(["category", "series"], ascending=[True, False])
    )
    by_category["unit_share_within_category"] = by_category["total_units"] / by_category.groupby("category")[
        "total_units"
    ].transform("sum")

    return {
        "taxonomy": _records(taxonomy.sort_values("_order").drop(columns=["_order"])),
        "by_category": _records(by_category),
        "method": "Syntetos-Boylan demand taxonomy using ADI and squared coefficient of variation on nonzero demand.",
        "thresholds": {"adi": 1.32, "cv2": 0.49},
    }


def _velocity_summary(series: pd.DataFrame) -> list[dict[str, Any]]:
    velocity = (
        series.groupby("velocity_segment", dropna=False)
        .agg(
            series=("series_id", "size"),
            products=("product_id", "nunique"),
            total_units=("total_units", "sum"),
            avg_daily_units=("avg_daily_units", "mean"),
            median_daily_units=("median_daily_units", "median"),
            avg_nonzero_rate=("nonzero_rate", "mean"),
            avg_price_coverage=("price_coverage", "mean"),
            price_change_series_rate=("price_unique_count", lambda s: float((s > 1).mean())),
        )
        .reset_index()
    )
    velocity["unit_share"] = velocity["total_units"] / velocity["total_units"].sum()
    order = {"intermittent": 0, "slow": 1, "medium": 2, "fast": 3}
    velocity["_order"] = velocity["velocity_segment"].map(order).fillna(99)
    return _records(velocity.sort_values("_order").drop(columns=["_order"]))


def _store_state_summary(frame: pd.DataFrame) -> list[dict[str, Any]]:
    store_state = (
        frame.groupby(["state_id", "store_id"], dropna=False)
        .agg(
            rows=("quantity", "size"),
            products=("product_id", "nunique"),
            total_units=("quantity", "sum"),
            avg_units_per_row=("quantity", "mean"),
            zero_sales_rate=("quantity", lambda s: float((s == 0).mean())),
        )
        .reset_index()
        .sort_values(["state_id", "total_units"], ascending=[True, False])
    )
    store_state["unit_share"] = store_state["total_units"] / store_state["total_units"].sum()
    return _records(store_state)


def _regionality_summary(frame: pd.DataFrame, series: pd.DataFrame) -> dict[str, Any]:
    state = (
        frame.groupby("state_id", dropna=False)
        .agg(
            rows=("quantity", "size"),
            stores=("store_id", "nunique"),
            products=("product_id", "nunique"),
            total_units=("quantity", "sum"),
            avg_units_per_row=("quantity", "mean"),
            zero_sales_rate=("quantity", lambda s: float((s == 0).mean())),
            price_coverage=("price", lambda s: float(s.notna().mean())),
        )
        .reset_index()
        .sort_values("total_units", ascending=False)
    )
    state["unit_share"] = state["total_units"] / state["total_units"].sum()

    store = (
        frame.groupby(["state_id", "store_id"], dropna=False)
        .agg(
            rows=("quantity", "size"),
            total_units=("quantity", "sum"),
            avg_units_per_row=("quantity", "mean"),
            zero_sales_rate=("quantity", lambda s: float((s == 0).mean())),
            price_coverage=("price", lambda s: float(s.notna().mean())),
        )
        .reset_index()
        .sort_values("total_units", ascending=False)
    )
    store["unit_share"] = store["total_units"] / store["total_units"].sum()

    category_state = (
        frame.groupby(["category", "state_id"], dropna=False)
        .agg(
            rows=("quantity", "size"),
            products=("product_id", "nunique"),
            total_units=("quantity", "sum"),
            avg_units_per_row=("quantity", "mean"),
            zero_sales_rate=("quantity", lambda s: float((s == 0).mean())),
        )
        .reset_index()
        .sort_values(["category", "total_units"], ascending=[True, False])
    )
    category_state["unit_share_within_category"] = category_state["total_units"] / category_state.groupby(
        "category"
    )["total_units"].transform("sum")
    category_state["index_vs_category_avg"] = (
        category_state["avg_units_per_row"]
        / category_state.groupby("category")["avg_units_per_row"].transform("mean")
        - 1.0
    )

    weekend_work = frame.copy()
    weekend_work["is_weekend"] = weekend_work["date"].dt.dayofweek >= 5
    weekend_rows: list[dict[str, Any]] = []
    for (state_id, category), group in weekend_work.groupby(["state_id", "category"], dropna=False):
        weekend = group.loc[group["is_weekend"], "quantity"]
        weekday = group.loc[~group["is_weekend"], "quantity"]
        weekend_rows.append(
            {
                "state_id": state_id,
                "category": category,
                "weekday_avg_units": _round_float(float(weekday.mean())),
                "weekend_avg_units": _round_float(float(weekend.mean())),
                "weekend_uplift": _round_float(
                    _safe_div(float(weekend.mean()), float(weekday.mean())) - 1.0
                    if len(weekday) and float(weekday.mean())
                    else None
                ),
            }
        )

    series_work = series.copy()
    series_work["is_late_launch"] = pd.to_numeric(
        series_work["first_sale_offset_days"], errors="coerce"
    ).fillna(0) > 90
    series_work["late_units"] = np.where(series_work["is_late_launch"], series_work["total_units"], 0.0)
    late_by_state = (
        series_work.groupby("state_id", dropna=False)
        .agg(
            series=("series_id", "size"),
            late_series=("is_late_launch", "sum"),
            total_units=("total_units", "sum"),
            late_units=("late_units", "sum"),
        )
        .reset_index()
    )
    late_by_state["late_rate"] = late_by_state["late_series"] / late_by_state["series"]
    late_by_state["late_unit_share"] = late_by_state["late_units"] / late_by_state["total_units"]

    late_by_category_state = (
        series_work.groupby(["category", "state_id"], dropna=False)
        .agg(
            series=("series_id", "size"),
            late_series=("is_late_launch", "sum"),
            total_units=("total_units", "sum"),
            late_units=("late_units", "sum"),
        )
        .reset_index()
        .sort_values(["category", "late_rate" if "late_rate" in series_work.columns else "state_id"])
    )
    late_by_category_state["late_rate"] = late_by_category_state["late_series"] / late_by_category_state["series"]
    late_by_category_state["late_unit_share"] = (
        late_by_category_state["late_units"] / late_by_category_state["total_units"]
    )
    late_by_category_state = late_by_category_state.sort_values(
        ["category", "late_rate"], ascending=[True, False]
    )

    taxonomy_state = (
        series.groupby(["state_id", "demand_classification"], dropna=False)
        .agg(series=("series_id", "size"), total_units=("total_units", "sum"))
        .reset_index()
    )
    taxonomy_state["unit_share_within_state"] = taxonomy_state["total_units"] / taxonomy_state.groupby(
        "state_id"
    )["total_units"].transform("sum")

    state_avg_ratio = _safe_div(float(state["avg_units_per_row"].max()), float(state["avg_units_per_row"].min()))
    store_avg_ratio = _safe_div(float(store["avg_units_per_row"].max()), float(store["avg_units_per_row"].min()))
    top_food_snap = None
    if "snap_WI" in frame.columns:
        wi_food = frame[(frame["state_id"] == "WI") & (frame["category"] == "FOODS")]
        wi_snap = pd.to_numeric(wi_food["snap_WI"], errors="coerce").fillna(0) > 0
        if len(wi_food) and wi_snap.any() and (~wi_snap).any():
            top_food_snap = _round_float(
                _safe_div(float(wi_food.loc[wi_snap, "quantity"].mean()), float(wi_food.loc[~wi_snap, "quantity"].mean()))
                - 1.0
            )

    return {
        "state_summary": _records(state),
        "store_summary": _records(store),
        "category_state_summary": _records(category_state),
        "weekend_by_category_state": _records(
            pd.DataFrame(weekend_rows).sort_values("weekend_uplift", ascending=False)
        ),
        "late_launch_by_state": _records(late_by_state.sort_values("late_rate", ascending=False)),
        "late_launch_by_category_state": _records(late_by_category_state),
        "taxonomy_by_state": _records(
            taxonomy_state.sort_values(["state_id", "unit_share_within_state"], ascending=[True, False])
        ),
        "reads": {
            "state_avg_units_max_min_ratio": _round_float(state_avg_ratio),
            "store_avg_units_max_min_ratio": _round_float(store_avg_ratio),
            "wi_food_snap_uplift": top_food_snap,
            "interpretation": (
                "Regionality is not only volume scale. State, store, category, SNAP, and weekend effects "
                "move differently enough to justify interaction features and segment diagnostics."
            ),
        },
    }


def _calendar_summary(frame: pd.DataFrame) -> dict[str, Any]:
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_weekday = (
        frame.groupby("weekday", dropna=False)
        .agg(rows=("quantity", "size"), total_units=("quantity", "sum"), avg_units_per_row=("quantity", "mean"))
        .reset_index()
    )
    by_weekday["_order"] = by_weekday["weekday"].map({day: idx for idx, day in enumerate(weekday_order)}).fillna(99)
    by_weekday["uplift_vs_avg"] = by_weekday["avg_units_per_row"] / frame["quantity"].mean() - 1.0

    by_month = (
        frame.groupby("month", dropna=False)
        .agg(rows=("quantity", "size"), total_units=("quantity", "sum"), avg_units_per_row=("quantity", "mean"))
        .reset_index()
        .sort_values("month")
    )
    by_month["uplift_vs_avg"] = by_month["avg_units_per_row"] / frame["quantity"].mean() - 1.0

    event_mask = pd.Series(False, index=frame.index)
    for col in ("event_name_1", "event_name_2"):
        if col in frame.columns:
            event_mask = event_mask | frame[col].notna()
    non_event_avg = float(frame.loc[~event_mask, "quantity"].mean()) if (~event_mask).any() else 0.0
    event_rows = []
    for label, mask in (
        ("event_rows", event_mask),
        ("holiday_rows", frame["is_holiday"] > 0),
    ):
        group = frame.loc[mask]
        rest = frame.loc[~mask]
        event_rows.append(
            {
                "segment": label,
                "rows": int(mask.sum()),
                "row_rate": _round_float(float(mask.mean())),
                "avg_units": _round_float(group["quantity"].mean()),
                "non_event_avg_units": _round_float(rest["quantity"].mean()),
                "uplift_vs_non_event": _round_float(_safe_div(float(group["quantity"].mean()), float(rest["quantity"].mean())) - 1.0 if len(group) and len(rest) and rest["quantity"].mean() else None),
            }
        )

    snap_rows = []
    snap_category_rows = []
    for state, snap_col in (("CA", "snap_CA"), ("TX", "snap_TX"), ("WI", "snap_WI")):
        if snap_col not in frame.columns:
            continue
        state_frame = frame[frame["state_id"] == state]
        if state_frame.empty:
            continue
        mask = pd.to_numeric(state_frame[snap_col], errors="coerce").fillna(0).astype(float) > 0
        snap = state_frame.loc[mask]
        no_snap = state_frame.loc[~mask]
        snap_rows.append(
            {
                "state_id": state,
                "snap_row_rate": _round_float(float(mask.mean())),
                "snap_avg_units": _round_float(snap["quantity"].mean()),
                "non_snap_avg_units": _round_float(no_snap["quantity"].mean()),
                "uplift_vs_non_snap": _round_float(_safe_div(float(snap["quantity"].mean()), float(no_snap["quantity"].mean())) - 1.0 if len(snap) and len(no_snap) and no_snap["quantity"].mean() else None),
            }
        )
        for category, category_frame in state_frame.groupby("category", dropna=False):
            category_mask = pd.to_numeric(category_frame[snap_col], errors="coerce").fillna(0).astype(float) > 0
            category_snap = category_frame.loc[category_mask]
            category_no_snap = category_frame.loc[~category_mask]
            snap_category_rows.append(
                {
                    "state_id": state,
                    "category": category,
                    "snap_row_rate": _round_float(float(category_mask.mean())),
                    "snap_avg_units": _round_float(category_snap["quantity"].mean()),
                    "non_snap_avg_units": _round_float(category_no_snap["quantity"].mean()),
                    "uplift_vs_non_snap": _round_float(
                        _safe_div(float(category_snap["quantity"].mean()), float(category_no_snap["quantity"].mean())) - 1.0
                        if len(category_snap) and len(category_no_snap) and category_no_snap["quantity"].mean()
                        else None
                    ),
                }
            )

    event_type_rows: list[dict[str, Any]] = []
    event_name_rows: list[dict[str, Any]] = []
    for name_col, type_col in (("event_name_1", "event_type_1"), ("event_name_2", "event_type_2")):
        if name_col not in frame.columns:
            continue
        event_frame = frame[frame[name_col].notna()].copy()
        if event_frame.empty:
            continue
        event_frame[name_col] = event_frame[name_col].astype(str)
        if type_col in event_frame.columns:
            event_frame[type_col] = event_frame[type_col].fillna("UNKNOWN").astype(str)
            by_type = (
                event_frame.groupby(type_col, dropna=False)
                .agg(rows=("quantity", "size"), avg_units=("quantity", "mean"), total_units=("quantity", "sum"))
                .reset_index()
                .rename(columns={type_col: "event_type"})
            )
            by_type["uplift_vs_non_event"] = by_type["avg_units"] / non_event_avg - 1.0 if non_event_avg else np.nan
            event_type_rows.extend(_records(by_type))
        by_name = (
            event_frame.groupby(name_col, dropna=False)
            .agg(rows=("quantity", "size"), avg_units=("quantity", "mean"), total_units=("quantity", "sum"))
            .reset_index()
            .rename(columns={name_col: "event_name"})
        )
        by_name["uplift_vs_non_event"] = by_name["avg_units"] / non_event_avg - 1.0 if non_event_avg else np.nan
        event_name_rows.extend(_records(by_name.sort_values("rows", ascending=False), limit=12))

    return {
        "weekday": _records(by_weekday.sort_values("_order").drop(columns=["_order"])),
        "month": _records(by_month),
        "event_holiday": event_rows,
        "event_type_effects": event_type_rows,
        "event_name_effects": event_name_rows,
        "snap": snap_rows,
        "snap_by_category": snap_category_rows,
    }


def _price_summary(frame: pd.DataFrame, series: pd.DataFrame) -> dict[str, Any]:
    work = frame.copy()
    work["price_filled"] = work.groupby("series_id")["price"].transform(lambda s: s.ffill().bfill())
    work["price_pct_change"] = work.groupby("series_id")["price_filled"].pct_change()
    work["price_change_abs"] = work["price_pct_change"].abs()
    work["price_drop"] = work["price_pct_change"] <= -0.01
    work["price_increase"] = work["price_pct_change"] >= 0.01

    changed = work["price_change_abs"] >= 0.01
    price_change_by_category = (
        work.groupby("category", dropna=False)
        .agg(
            rows=("quantity", "size"),
            price_change_row_rate=("price_change_abs", lambda s: float((s >= 0.01).mean())),
            price_drop_row_rate=("price_pct_change", lambda s: float((s <= -0.01).mean())),
            price_increase_row_rate=("price_pct_change", lambda s: float((s >= 0.01).mean())),
            avg_units=("quantity", "mean"),
            price_drop_avg_units=("quantity", lambda s: float(s[work.loc[s.index, "price_drop"]].mean()) if work.loc[s.index, "price_drop"].any() else np.nan),
            no_change_avg_units=("quantity", lambda s: float(s[~changed.loc[s.index]].mean()) if (~changed.loc[s.index]).any() else np.nan),
        )
        .reset_index()
    )
    price_change_by_category["price_drop_uplift_vs_no_change"] = (
        price_change_by_category["price_drop_avg_units"] / price_change_by_category["no_change_avg_units"] - 1.0
    )

    correlations: list[float] = []
    correlations_by_category: dict[str, list[float]] = {}
    for _, group in work.dropna(subset=["price_filled"]).groupby("series_id", sort=False):
        if group["price_filled"].nunique() < 3 or group["quantity"].nunique() < 2:
            continue
        corr = group["price_filled"].corr(group["quantity"])
        if pd.notna(corr) and np.isfinite(corr):
            correlations.append(float(corr))
            category = str(group["category"].iloc[0])
            correlations_by_category.setdefault(category, []).append(float(corr))

    category_correlations = [
        {
            "category": category,
            "series_with_signal": len(values),
            "median_price_quantity_correlation": _round_float(float(np.median(values))),
            "negative_correlation_rate": _round_float(float(np.mean([value < 0 for value in values]))),
        }
        for category, values in sorted(correlations_by_category.items())
    ]

    price_coverage = (
        work.groupby(["category", "state_id"], dropna=False)
        .agg(
            rows=("quantity", "size"),
            price_coverage=("price", lambda s: float(s.notna().mean())),
            median_price=("price", "median"),
            price_change_row_rate=("price_change_abs", lambda s: float((s >= 0.01).mean())),
        )
        .reset_index()
        .sort_values(["category", "state_id"])
    )

    top_price_movers = series.sort_values("price_unique_count", ascending=False)[
        ["store_id", "product_id", "category", "total_units", "price_unique_count", "median_price", "nonzero_rate"]
    ].head(12)

    return {
        "price_coverage": _round_float(float(work["price"].notna().mean())),
        "series_with_price_changes_rate": _round_float(float((series["price_unique_count"] > 1).mean())),
        "rows_with_price_change_rate": _round_float(float(changed.fillna(False).mean())),
        "rows_with_price_drop_rate": _round_float(float(work["price_drop"].fillna(False).mean())),
        "price_change_rows": int(changed.fillna(False).sum()),
        "price_drop_rows": int(work["price_drop"].fillna(False).sum()),
        "median_series_price_quantity_correlation": _round_float(float(np.median(correlations)) if correlations else np.nan),
        "category_price_effects": _records(price_change_by_category.sort_values("price_change_row_rate", ascending=False)),
        "category_price_correlations": category_correlations,
        "price_coverage_by_category_state": _records(price_coverage),
        "top_price_mover_series": _records(top_price_movers),
    }


def _build_hypotheses(
    summary: dict[str, Any],
    quality: dict[str, Any],
    late_launch: dict[str, Any],
    regionality: dict[str, Any],
    velocity: list[dict[str, Any]],
    intermittent_report: dict[str, Any],
    price: dict[str, Any],
    calendar: dict[str, Any],
) -> list[dict[str, Any]]:
    velocity_by_name = {row["velocity_segment"]: row for row in velocity}
    slow = velocity_by_name.get("slow", {})
    intermittent_velocity = velocity_by_name.get("intermittent", {})
    price_change_rate = price.get("series_with_price_changes_rate") or 0.0
    lifecycle = quality.get("lifecycle_summary") or {}
    demand_taxonomy = intermittent_report.get("taxonomy") or []
    lumpy = next((row for row in demand_taxonomy if row.get("demand_classification") == "lumpy"), {})
    intermittent_taxonomy = next((row for row in demand_taxonomy if row.get("demand_classification") == "intermittent"), {})
    regional_reads = regionality.get("reads") or {}
    snap_by_category = calendar.get("snap_by_category") or []
    food_snap = [row for row in snap_by_category if row.get("category") == "FOODS"]
    weekend_rows = regionality.get("weekend_by_category_state") or []

    return [
        {
            "rank": 1,
            "title": "Activation-aware training window for pre-sellable SKU-store rows",
            "experiment_type": "dataset_spec",
            "rationale": (
                "Many late-start SKU-store rows look like pre-activation/ranging periods, not true no-demand. "
                "Training on those zeros as ordinary demand can teach the model fake zero demand before an item "
                "was commercially active."
            ),
            "evidence": {
                "pre_first_sale_zero_row_share": lifecycle.get("pre_first_sale_zero_row_share"),
                "late_launch_series_rate": lifecycle.get("late_launch_series_rate"),
                "late_launch_series_inspected": late_launch.get("late_launch_series"),
                "price_aligned_late_launch_rate": late_launch.get("price_aligned_late_launch_rate"),
                "likely_late_ranged_or_introduced_rate": late_launch.get(
                    "likely_late_ranged_or_introduced_rate"
                ),
                "possible_seasonal_rate": late_launch.get("possible_seasonal_rate"),
            },
            "expected_metric_movement": {
                "bias_pct_late_launch": "closer_to_zero",
                "wape_late_launch": "down",
                "mase_active_window": "down",
                "stockout_opportunity_cost": "down_if_underforecasting_newly_active_skus_exists",
            },
        },
        {
            "rank": 2,
            "title": "State/category calendar interactions for SNAP and weekend demand",
            "experiment_type": "feature_set",
            "rationale": (
                "Demand timing is not globally uniform. SNAP uplift is concentrated in FOODS and varies by state, "
                "while weekend effects differ by state/category. A global calendar flag can dilute signal."
            ),
            "evidence": {
                "state_avg_units_max_min_ratio": regional_reads.get("state_avg_units_max_min_ratio"),
                "store_avg_units_max_min_ratio": regional_reads.get("store_avg_units_max_min_ratio"),
                "wi_food_snap_uplift": regional_reads.get("wi_food_snap_uplift"),
                "food_snap_effects": food_snap,
                "top_weekend_effects": weekend_rows[:3],
            },
            "expected_metric_movement": {
                "wape_food_snap_windows": "down",
                "bias_weekend_windows": "closer_to_zero",
                "coverage": "up_or_flat",
                "non_food_noise": "watch",
            },
        },
        {
            "rank": 3,
            "title": "Slow/intermittent objective or conservative order policy",
            "experiment_type": "objective_function",
            "rationale": (
                "Sparse item-store demand makes WAPE unstable and can turn small forecast shifts into excess inventory. "
                "A slower-moving segment may need a different objective or decision policy."
            ),
            "evidence": {
                "intermittent_series": intermittent_velocity.get("series"),
                "intermittent_unit_share": intermittent_velocity.get("unit_share"),
                "taxonomy_intermittent_series": intermittent_taxonomy.get("series"),
                "taxonomy_intermittent_unit_share": intermittent_taxonomy.get("unit_share"),
                "lumpy_series": lumpy.get("series"),
                "lumpy_unit_share": lumpy.get("unit_share"),
                "zero_sales_rate": summary.get("zero_sales_rate"),
            },
            "expected_metric_movement": {
                "overstock_dollars": "down",
                "overstock_rate": "down",
                "mase": "flat_or_down_on_slow_segments",
            },
        },
        {
            "rank": 4,
            "title": "Velocity-aware calibration instead of global upward adjustment",
            "experiment_type": "segmentation",
            "rationale": (
                "M5 demand is sparse and velocity-segmented. Slow/intermittent series need different treatment "
                "than fast or high-volume series, so one broad calibration layer can create overbuying."
            ),
            "evidence": {
                "zero_sales_rate": summary.get("zero_sales_rate"),
                "slow_series": slow.get("series"),
                "slow_avg_nonzero_rate": slow.get("avg_nonzero_rate"),
                "intermittent_series": intermittent_velocity.get("series"),
                "late_launch_series_rate": lifecycle.get("late_launch_series_rate"),
                "dormant_tail_series_rate": lifecycle.get("dormant_tail_series_rate"),
                "lumpy_series": lumpy.get("series"),
            },
            "expected_metric_movement": {
                "bias_pct": "down",
                "overstock_dollars": "down",
                "wape": "flat_or_down",
                "stockout_opportunity_cost": "not_materially_worse",
            },
        },
        {
            "rank": 5,
            "title": "Price-change and price-drop features with bounded promo interaction",
            "experiment_type": "feature_set",
            "rationale": (
                "A meaningful share of SKU-store series has sell-price movement. Price drops can proxy promotions "
                "in M5 even when explicit promotion labels are sparse."
            ),
            "evidence": {
                "series_with_price_changes_rate": price_change_rate,
                "rows_with_price_drop_rate": price.get("rows_with_price_drop_rate"),
                "price_drop_rows": price.get("price_drop_rows"),
                "median_price_quantity_correlation": price.get("median_series_price_quantity_correlation"),
            },
            "expected_metric_movement": {
                "wape": "down_on_price_sensitive_segments",
                "bias_pct": "closer_to_zero",
                "overstock_risk": "watch",
            },
        },
        {
            "rank": 6,
            "title": "Category-store hierarchical fallback for sparse series",
            "experiment_type": "segmentation",
            "rationale": (
                "The benchmark has only a few broad categories, but store/category volume differs. Sparse series can "
                "borrow strength from category-store patterns without forcing one global correction."
            ),
            "evidence": {
                "stores": summary.get("stores"),
                "categories": summary.get("categories"),
                "top_10pct_series_unit_share": summary.get("top_10pct_series_unit_share"),
            },
            "expected_metric_movement": {
                "mase": "down",
                "bias_pct": "down_in_sparse_segments",
                "coverage": "up_or_flat",
            },
        },
    ]


def _build_hypothesis_register(report: dict[str, Any]) -> list[dict[str, Any]]:
    lifecycle = report["data_quality_summary"]["lifecycle_summary"]
    late_launch = report["late_launch_deep_dive"]
    regionality = report["regionality_summary"]
    intermittent = report["intermittent_demand_summary"]
    velocity = {row["velocity_segment"]: row for row in report["velocity_summary"]}
    price = report["price_summary"]
    taxonomy = {row["demand_classification"]: row for row in intermittent["taxonomy"]}
    lumpy = taxonomy.get("lumpy", {})
    intermittent_taxonomy = taxonomy.get("intermittent", {})
    fast = velocity.get("fast", {})
    slow = velocity.get("slow", {})
    intermittent_velocity = velocity.get("intermittent", {})

    return [
        {
            "rank": 1,
            "finding": "Pre-activation zeros are common in late-start SKU-store series.",
            "evidence": (
                f"Pre-first-sale zero share {lifecycle['pre_first_sale_zero_row_share']}; "
                f"late-launch series rate {lifecycle['late_launch_series_rate']}; "
                f"price-aligned late launches {late_launch['price_aligned_late_launch_rate']}; "
                f"likely late-ranged/introduced {late_launch['likely_late_ranged_or_introduced_rate']}; "
                f"possible seasonal {late_launch['possible_seasonal_rate']}."
            ),
            "domain_interpretation": (
                "Rows before first available sell price are likely not active sellable demand periods. "
                "They should not be treated like ordinary zero-demand days."
            ),
            "hypothesis": "Activation-aware training window for pre-sellable SKU-store rows.",
            "experiment_change": (
                "Create a versioned M5 activation-aware dataset spec. Keep raw canonical M5 unchanged; "
                "exclude, flag, or downweight rows before first available sell price per SKU-store."
            ),
            "primary_metrics": "Late-launch active-window WAPE, MASE, bias; simulated stockout cost.",
            "risk": "Could remove useful cold-start context or shift comparability. Avoid first-sale leakage by using first price.",
            "confidence": "high",
        },
        {
            "rank": 2,
            "finding": "Demand timing varies by state/category and calendar window.",
            "evidence": (
                f"State avg-units max/min ratio {regionality['reads']['state_avg_units_max_min_ratio']}; "
                f"store avg-units max/min ratio {regionality['reads']['store_avg_units_max_min_ratio']}; "
                f"WI FOODS SNAP uplift {regionality['reads']['wi_food_snap_uplift']}."
            ),
            "domain_interpretation": (
                "Calendar demand is not one global holiday effect. SNAP is mostly a FOODS/state signal, "
                "and weekend demand differs by category and state."
            ),
            "hypothesis": "State/category calendar interactions for SNAP and weekend demand.",
            "experiment_change": "Add SNAP x state x category and weekend x state x category features.",
            "primary_metrics": "WAPE and bias on FOODS/SNAP windows and weekend windows; interval coverage by state/category.",
            "risk": "Interactions can add noise to non-food categories or small segments.",
            "confidence": "medium_high",
        },
        {
            "rank": 3,
            "finding": "Intermittent and lumpy demand are a large part of the benchmark.",
            "evidence": (
                f"Intermittent taxonomy unit share {intermittent_taxonomy.get('unit_share')}; "
                f"lumpy unit share {lumpy.get('unit_share')}; zero-sales row rate {report['summary']['zero_sales_rate']}."
            ),
            "domain_interpretation": (
                "Sparse demand may need a different objective or order policy. Forecast accuracy alone can "
                "hide overstock risk on slow movers."
            ),
            "hypothesis": "Slow/intermittent objective or conservative order policy.",
            "experiment_change": (
                "Evaluate segment-specific loss weighting, conservative order rules, or separate slow-mover policy."
            ),
            "primary_metrics": "Overstock dollars/rate, MASE on intermittent/lumpy segments, service-level miss proxy.",
            "risk": "May reduce stockout protection for items that are sparse but important when they move.",
            "confidence": "medium_high",
        },
        {
            "rank": 4,
            "finding": "Volume is concentrated while many SKU-store series are sparse.",
            "evidence": (
                f"Fast segment unit share {fast.get('unit_share')}; slow series {slow.get('series')}; "
                f"intermittent velocity series {intermittent_velocity.get('series')}; "
                f"top 10% series unit share {report['summary']['top_10pct_series_unit_share']}."
            ),
            "domain_interpretation": (
                "A global calibration can look better by serving high-volume items while overbuying sparse items."
            ),
            "hypothesis": "Velocity-aware calibration instead of global upward adjustment.",
            "experiment_change": "Calibrate forecast bias and safety-stock/order policy by velocity segment.",
            "primary_metrics": "Bias, WAPE, overstock dollars, and stockout cost by velocity segment.",
            "risk": "Segment thresholds can become arbitrary if not validated on holdout slices.",
            "confidence": "medium",
        },
        {
            "rank": 5,
            "finding": "Sell-price movement exists, but explicit promotion labels are unavailable.",
            "evidence": (
                f"Series with price changes {price['series_with_price_changes_rate']}; "
                f"price-drop rows {price['price_drop_rows']}; explicit promo row rate "
                f"{report['summary']['explicit_promo_row_rate']}."
            ),
            "domain_interpretation": (
                "Price drops can be tested as a promotion proxy, but M5 cannot prove true ad/promo response."
            ),
            "hypothesis": "Price-change and price-drop features with bounded promo interaction.",
            "experiment_change": "Add price-change, price-drop, and lagged price features with category guardrails.",
            "primary_metrics": "WAPE/bias on price-change windows and price-sensitive segments.",
            "risk": "Sparse price-change rows and no explicit promo labels can create noisy or misleading features.",
            "confidence": "exploratory",
        },
        {
            "rank": 6,
            "finding": "Store/category heterogeneity exists beyond state-level averages.",
            "evidence": (
                f"Store avg-units max/min ratio {regionality['reads']['store_avg_units_max_min_ratio']}; "
                f"top 10% series unit share {report['summary']['top_10pct_series_unit_share']}."
            ),
            "domain_interpretation": (
                "Sparse SKU-store series may benefit from borrowing signal from store/category hierarchy."
            ),
            "hypothesis": "Category-store hierarchical fallback for sparse series.",
            "experiment_change": "Add category-store fallback features or blended forecasts for sparse SKU-store series.",
            "primary_metrics": "MASE and bias on sparse SKU-store series; no degradation on fast movers.",
            "risk": "Can wash out item-specific signal if fallback is too aggressive.",
            "confidence": "medium",
        },
    ]


def _build_evaluation_plan(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "rank": 1,
            "hypothesis": "Activation-aware training window",
            "experiment_artifact": "m5_activation_aware_v1 dataset spec",
            "primary_slice": "late-launch SKU-store active-window periods",
            "primary_success_metric": "WAPE and MASE improve on late-launch active windows",
            "secondary_metrics": "bias_pct, simulated stockout cost, global WAPE",
            "guardrail": "Non-late SKU-store WAPE does not degrade materially; raw canonical M5 remains unchanged",
            "pass_condition": "Target slice improves and global/non-late metrics are flat or better within a small materiality band",
        },
        {
            "rank": 2,
            "hypothesis": "State/category calendar interactions",
            "experiment_artifact": "calendar_interactions_v1 feature spec",
            "primary_slice": "FOODS SNAP windows and weekend windows by state/category",
            "primary_success_metric": "WAPE and bias improve on targeted calendar windows",
            "secondary_metrics": "coverage, interval width, non-food category WAPE",
            "guardrail": "No added noise in HOBBIES/HOUSEHOLD or non-SNAP windows",
            "pass_condition": "Target calendar slices improve without broad non-food degradation",
        },
        {
            "rank": 3,
            "hypothesis": "Slow/intermittent objective or conservative order policy",
            "experiment_artifact": "intermittent_policy_v1 objective/policy spec",
            "primary_slice": "intermittent and lumpy demand-classification segments",
            "primary_success_metric": "Simulated overstock dollars/rate decrease",
            "secondary_metrics": "MASE, bias_pct, stockout opportunity cost, service-level miss proxy",
            "guardrail": "Stockout opportunity cost does not materially worsen",
            "pass_condition": "Inventory-risk metrics improve with acceptable service-level tradeoff",
        },
        {
            "rank": 4,
            "hypothesis": "Velocity-aware calibration",
            "experiment_artifact": "velocity_calibration_v1 policy spec",
            "primary_slice": "fast, medium, slow, and intermittent velocity segments",
            "primary_success_metric": "Segment bias moves closer to zero",
            "secondary_metrics": "WAPE, overstock dollars, stockout cost by velocity",
            "guardrail": "No segment wins by shifting risk into another segment",
            "pass_condition": "Bias/decision metrics improve across priority segments or reveal a clear segment-specific policy",
        },
        {
            "rank": 5,
            "hypothesis": "Price-change and price-drop features",
            "experiment_artifact": "price_proxy_features_v1 feature spec",
            "primary_slice": "SKU-store windows around sell-price changes",
            "primary_success_metric": "WAPE and bias improve on price-change windows",
            "secondary_metrics": "category-level response, global WAPE, feature importance stability",
            "guardrail": "Do not claim promotion lift; explicit promo labels are unavailable",
            "pass_condition": "Price-window metrics improve enough to justify a later promo-aware dataset",
        },
        {
            "rank": 6,
            "hypothesis": "Category-store hierarchical fallback",
            "experiment_artifact": "hierarchical_fallback_v1 feature/model spec",
            "primary_slice": "sparse SKU-store series",
            "primary_success_metric": "MASE improves on sparse series",
            "secondary_metrics": "bias_pct, WAPE, fast-mover degradation, interval coverage",
            "guardrail": "Do not wash out item-level signal on higher-volume SKUs",
            "pass_condition": "Sparse-series error improves without damaging high-volume SKU-store forecasts",
        },
    ]


def _write_charts(report: dict[str, Any], paths: EDAPaths) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []

    paths.charts_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    def save_bar(rows: list[dict[str, Any]], x: str, y: str, title: str, filename: str) -> None:
        if not rows:
            return
        frame = pd.DataFrame(rows)
        if x not in frame or y not in frame:
            return
        fig, ax = plt.subplots(figsize=(9, 4.8))
        ax.bar(frame[x].astype(str), pd.to_numeric(frame[y], errors="coerce").fillna(0.0))
        ax.set_title(title)
        ax.set_xlabel(x.replace("_", " ").title())
        ax.set_ylabel(y.replace("_", " ").title())
        ax.tick_params(axis="x", rotation=35)
        fig.tight_layout()
        output = paths.charts_dir / filename
        fig.savefig(output, dpi=160)
        plt.close(fig)
        try:
            written.append(str(output.resolve().relative_to(Path.cwd().resolve())))
        except ValueError:
            written.append(str(output))

    save_bar(
        report["category_summary"],
        "category",
        "zero_sales_rate",
        "Zero-sales rate by category",
        "zero_sales_rate_by_category.png",
    )
    save_bar(
        report["velocity_summary"],
        "velocity_segment",
        "unit_share",
        "Unit share by velocity segment",
        "unit_share_by_velocity_segment.png",
    )
    save_bar(
        report["intermittent_demand_summary"]["taxonomy"],
        "demand_classification",
        "unit_share",
        "Unit share by intermittent-demand taxonomy",
        "unit_share_by_demand_taxonomy.png",
    )
    lifecycle_rows = report["data_quality_summary"].get("lifecycle_summary", {}).get("by_category") or []
    save_bar(
        lifecycle_rows,
        "category",
        "late_launch_rate",
        "Late-launch series rate by category",
        "late_launch_rate_by_category.png",
    )
    save_bar(
        report["late_launch_deep_dive"].get("classification_summary") or [],
        "classification",
        "series",
        "Late-launch investigation classification",
        "late_launch_classification.png",
    )
    save_bar(
        report["regionality_summary"].get("state_summary") or [],
        "state_id",
        "unit_share",
        "Unit share by state",
        "unit_share_by_state.png",
    )
    save_bar(
        report["calendar_summary"]["weekday"],
        "weekday",
        "uplift_vs_avg",
        "Weekday unit uplift vs average",
        "weekday_uplift.png",
    )
    price_rows = report["price_summary"].get("category_price_effects") or []
    save_bar(
        price_rows,
        "category",
        "price_change_row_rate",
        "Price-change row rate by category",
        "price_change_rate_by_category.png",
    )
    return written


def _markdown_table(rows: list[dict[str, Any]], columns: list[str], *, limit: int | None = None) -> str:
    rows = rows[:limit] if limit else rows
    if not rows:
        return "_No rows._"
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    return "\n".join([header, sep, *body])


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    quality = report["data_quality_summary"]
    lifecycle = quality["lifecycle_summary"]
    late_launch = report["late_launch_deep_dive"]
    regionality = report["regionality_summary"]
    intermittent = report["intermittent_demand_summary"]
    price = report["price_summary"]
    calendar = report["calendar_summary"]
    hypotheses = report["candidate_hypotheses"]
    chart_lines = "\n".join(f"- `{path}`" for path in report.get("charts", [])) or "- unavailable"
    hypothesis_lines = "\n".join(
        (
            f"### {item['rank']}. {item['title']}\n"
            f"- Type: `{item['experiment_type']}`\n"
            f"- Rationale: {item['rationale']}\n"
            f"- Evidence: `{json.dumps(item['evidence'], sort_keys=True)}`\n"
            f"- Expected movement: `{json.dumps(item['expected_metric_movement'], sort_keys=True)}`"
        )
        for item in hypotheses
    )
    caution_lines = "\n".join(f"- {item}" for item in quality["retail_data_cautions"])

    return f"""# M5 Global EDA Notes

- Dataset: `{summary['dataset_id']}`
- Provenance: `{summary['provenance']}`
- Claim boundary: {summary['claim_boundary']}
- Source: `{summary['data_dir']}`
- Coverage: `{summary['date_min']}` to `{summary['date_max']}` across `{summary['days']}` days
- Rows: `{summary['rows']:,}`
- Stores: `{summary['stores']}`
- Products: `{summary['products']}`
- Store-product series: `{summary['series']}`
- Categories: `{", ".join(summary['categories'])}`

## What I Am Trying To Learn

I am using this notebook to decide what is actually worth testing, not just to summarize
the M5 subset. The main thing I care about is whether the model would be learning true
demand behavior, or whether the dataset has retail artifacts that need to be handled first:
item activation/ranging, sparse demand, calendar timing, store/state differences, and price
movement.

The working question for this pass: what failure mode is big enough, and clean enough, to
become the first logged ShelfOps experiment?

## Data Contract Notes

{caution_lines}

- Expected dense store-product-day rows: `{quality['expected_dense_grid_rows']:,}`
- Actual rows: `{quality['actual_rows']:,}`
- Dense grid coverage: `{quality['dense_grid_coverage']}`
- Duplicate date/store/product rows: `{quality['duplicate_series_date_rows']}`
- Negative quantity rows after canonicalization: `{quality['negative_quantity_rows_after_canonicalization']}`

### Column Profile

{_markdown_table(quality['column_profile'], ['column', 'non_null_rate', 'distinct_values'])}

### Price Coverage By Year

{_markdown_table(quality['price_coverage_by_year'], ['year', 'rows', 'price_coverage'])}

## Demand Shape

- Total units: `{summary['total_units']:,}`
- Zero-sales row rate: `{summary['zero_sales_rate']}`
- Average units per row: `{summary['avg_units_per_row']}`
- Average units when nonzero: `{summary['avg_units_when_nonzero']}`
- Top 10% series unit share: `{summary['top_10pct_series_unit_share']}`
- Price coverage: `{summary['price_coverage']}`
- Explicit promo row rate: `{summary['explicit_promo_row_rate']}`
- Event row rate: `{summary['event_day_row_rate']}`
- SNAP row rate: `{summary['snap_row_rate']}`

My note: the high zero-sales rate is not automatically a data-quality issue. Daily
store-SKU demand is naturally sparse. The problem is that different zeros can mean very
different things: low demand, no shelf availability, not-yet-ranged item, discontinued item,
or just a slow mover. I should not treat every zero as the same training signal.

## Category Summary

{_markdown_table(report['category_summary'], ['category', 'products', 'series', 'total_units', 'unit_share', 'zero_sales_rate', 'avg_series_nonzero_rate', 'price_change_series_rate'])}

## Velocity Summary

{_markdown_table(report['velocity_summary'], ['velocity_segment', 'series', 'products', 'total_units', 'unit_share', 'avg_daily_units', 'avg_nonzero_rate', 'price_change_series_rate'])}

## Lifecycle / Ranging Risk

- Series with no observed sales: `{lifecycle['series_with_no_sales_rate']}`
- Late-launch series rate, first sale more than 90 days after benchmark start: `{lifecycle['late_launch_series_rate']}`
- Dormant-tail series rate, last sale more than 90 days before benchmark end: `{lifecycle['dormant_tail_series_rate']}`
- Pre-first-sale zero row share: `{lifecycle['pre_first_sale_zero_row_share']}`
- Post-last-sale zero row share: `{lifecycle['post_last_sale_zero_row_share']}`
- Average active-window zero rate: `{lifecycle['avg_active_window_zero_rate']}`

My note: pre-first-sale and post-last-sale zeros look like they can include assortment or
ranging behavior, not just weak demand. If those rows are left in as normal observations,
the model can learn "this item does not sell" before the item was really active in the
store.

{_markdown_table(lifecycle['by_category'], ['category', 'series', 'late_launch_rate', 'dormant_tail_rate', 'median_first_sale_offset_days', 'median_last_sale_tail_days', 'avg_active_window_zero_rate'])}

### Late-Launch SKU Drilldown: Seasonal Or Ranging?

I needed to check whether the late first-sale SKUs were simply seasonal. If a SKU sells only
in the same narrow window every year, then the zeros are useful seasonal signal. If price
appears right before first sale and the item then sells across many months, then this looks
more like store/item activation.

How I checked it: {late_launch['method']}

My note: {late_launch['read']}

- Late-launch series inspected: `{late_launch['late_launch_series']}`
- Price-aligned late-launch rate: `{late_launch['price_aligned_late_launch_rate']}`
- Likely late-ranged/introduced rate: `{late_launch['likely_late_ranged_or_introduced_rate']}`
- Possible seasonal rate: `{late_launch['possible_seasonal_rate']}`

#### Late-Launch Classification Summary

{_markdown_table(late_launch['classification_summary'], ['classification', 'series', 'products', 'total_units', 'unit_share_within_late_launch', 'avg_first_sale_offset_days', 'avg_active_span_days', 'avg_positive_months', 'avg_top_3_month_unit_share', 'price_aligned_rate'])}

#### Late-Launch Classification By Category

{_markdown_table(late_launch['by_category'], ['category', 'classification', 'series', 'total_units'], limit=18)}

#### High-Volume Late-Launch SKU Examples

{_markdown_table(late_launch['high_volume_examples'], ['store_id', 'product_id', 'category', 'first_sale_date', 'first_price_date', 'first_price_minus_first_sale_days', 'last_sale_date', 'total_units', 'positive_months', 'top_months_by_units', 'top_3_month_unit_share', 'classification'], limit=10)}

#### Most Delayed Late-Launch SKU Examples

{_markdown_table(late_launch['most_delayed_examples'], ['store_id', 'product_id', 'category', 'first_sale_date', 'first_price_date', 'last_sale_date', 'total_units', 'nonzero_days', 'positive_months', 'top_3_month_unit_share', 'classification'], limit=10)}

#### Nonstandard Late-Launch SKU Examples

{_markdown_table(late_launch['nonstandard_examples'], ['store_id', 'product_id', 'category', 'first_sale_date', 'first_price_date', 'last_sale_date', 'total_units', 'nonzero_days', 'positive_months', 'top_3_month_unit_share', 'classification'], limit=10)}

My takeaway: these late-start rows do not look like classic seasonality. Some of the very
late examples are too sparse to classify confidently, but the high-volume examples look
like activation/ranging. I should use first available sell price as the cleaner marker, not
first sale, because first sale is outcome-based and can leak demand timing.

## Intermittent Demand Taxonomy

Method: {intermittent['method']}
Thresholds: ADI `{intermittent['thresholds']['adi']}`, CV2 `{intermittent['thresholds']['cv2']}`.

{_markdown_table(intermittent['taxonomy'], ['demand_classification', 'series', 'products', 'total_units', 'unit_share', 'avg_nonzero_rate', 'median_adi', 'median_cv2', 'median_intersale_gap_days', 'p90_intersale_gap_days'])}

### Taxonomy By Category

{_markdown_table(intermittent['by_category'], ['category', 'demand_classification', 'series', 'total_units', 'unit_share_within_category'], limit=18)}

My note: this is bigger than feature engineering. Smooth or fast demand can probably use a
direct forecast-to-order flow. Lumpy/intermittent demand may need a separate objective or
conservative order policy because a small forecast shift can become real overstock.

## Store / State Summary

{_markdown_table(report['store_state_summary'], ['state_id', 'store_id', 'products', 'total_units', 'unit_share', 'zero_sales_rate'], limit=12)}

## Regionality / Store Heterogeneity Drilldown

My note: {regionality['reads']['interpretation']}

- State avg-units max/min ratio: `{regionality['reads']['state_avg_units_max_min_ratio']}`
- Store avg-units max/min ratio: `{regionality['reads']['store_avg_units_max_min_ratio']}`
- WI FOODS SNAP uplift: `{regionality['reads']['wi_food_snap_uplift']}`

### State Summary

{_markdown_table(regionality['state_summary'], ['state_id', 'stores', 'products', 'total_units', 'unit_share', 'avg_units_per_row', 'zero_sales_rate', 'price_coverage'])}

### Store Summary

{_markdown_table(regionality['store_summary'], ['state_id', 'store_id', 'total_units', 'unit_share', 'avg_units_per_row', 'zero_sales_rate', 'price_coverage'])}

### Category By State

{_markdown_table(regionality['category_state_summary'], ['category', 'state_id', 'products', 'total_units', 'unit_share_within_category', 'avg_units_per_row', 'zero_sales_rate', 'index_vs_category_avg'])}

### Weekend Uplift By State And Category

{_markdown_table(regionality['weekend_by_category_state'], ['state_id', 'category', 'weekday_avg_units', 'weekend_avg_units', 'weekend_uplift'])}

### Late Activation By State And Category

{_markdown_table(regionality['late_launch_by_state'], ['state_id', 'series', 'late_series', 'late_rate', 'total_units', 'late_units', 'late_unit_share'])}

{_markdown_table(regionality['late_launch_by_category_state'], ['category', 'state_id', 'series', 'late_series', 'late_rate', 'total_units', 'late_units', 'late_unit_share'], limit=12)}

### Demand Taxonomy By State

{_markdown_table(regionality['taxonomy_by_state'], ['state_id', 'demand_classification', 'series', 'total_units', 'unit_share_within_state'], limit=16)}

My takeaway: I would not just add a generic state feature and move on. The useful version is
more specific: state/category calendar interactions, plus segment metrics so I can see
whether I helped FOODS/SNAP windows without adding noise elsewhere.

## Calendar / SNAP / Event Findings

### Weekday

{_markdown_table(calendar['weekday'], ['weekday', 'total_units', 'avg_units_per_row', 'uplift_vs_avg'])}

### SNAP

{_markdown_table(calendar['snap'], ['state_id', 'snap_row_rate', 'snap_avg_units', 'non_snap_avg_units', 'uplift_vs_non_snap'])}

### SNAP By State And Category

{_markdown_table(calendar['snap_by_category'], ['state_id', 'category', 'snap_row_rate', 'snap_avg_units', 'non_snap_avg_units', 'uplift_vs_non_snap'])}

### Event Type Effects

{_markdown_table(calendar['event_type_effects'], ['event_type', 'rows', 'avg_units', 'total_units', 'uplift_vs_non_event'])}

### Frequent Event Name Effects

{_markdown_table(calendar['event_name_effects'], ['event_name', 'rows', 'avg_units', 'total_units', 'uplift_vs_non_event'], limit=12)}

My note: I should not throw in global holiday flags and call it retail domain knowledge.
SNAP seems much more relevant for FOODS, and the effect changes by state. Weekend demand is
also not uniform. This should be tested after the activation-aware dataset change so the
first experiment stays clean.

## Price Findings

- Price coverage: `{price['price_coverage']}`
- Series with price changes: `{price['series_with_price_changes_rate']}`
- Rows with price changes: `{price['rows_with_price_change_rate']}`
- Price-change rows: `{price['price_change_rows']}`
- Rows with price drops: `{price['rows_with_price_drop_rate']}`
- Price-drop rows: `{price['price_drop_rows']}`
- Median series price/quantity correlation: `{price['median_series_price_quantity_correlation']}`

{_markdown_table(price['category_price_effects'], ['category', 'price_change_row_rate', 'price_drop_row_rate', 'price_drop_uplift_vs_no_change'])}

### Price Correlations By Category

{_markdown_table(price['category_price_correlations'], ['category', 'series_with_signal', 'median_price_quantity_correlation', 'negative_correlation_rate'])}

### Price Coverage By Category And State

{_markdown_table(price['price_coverage_by_category_state'], ['category', 'state_id', 'rows', 'price_coverage', 'median_price', 'price_change_row_rate'], limit=12)}

### Highest Price-Movement Series

{_markdown_table(price['top_price_mover_series'], ['store_id', 'product_id', 'category', 'total_units', 'price_unique_count', 'median_price', 'nonzero_rate'])}

My note: M5 has sell-price movement, but this subset does not carry explicit promotion
labels. Price movement could still be useful, but I need to be careful with claims. A price
drop is a proxy hypothesis, not proof of ad or promo response. I should keep any claim at
the forecast/simulated-decision level unless I have real promotion and margin data.

## Modeling Notes I Would Carry Forward

1. I should not start by chasing a larger model. First I need to test whether the dataset
   spec is teaching from pre-sellable zero rows.
2. I need time-based holdouts and segment metrics. Global WAPE can hide worse sparse-SKU
   behavior, and replenishment turns forecast errors into inventory dollars.
3. Lifecycle zeros need to be handled explicitly. Late launch and dormant tail rows should
   not be treated exactly like steady-state no-demand.
4. Price and calendar features should be interaction-aware. The natural splits here are
   state, category, store, velocity, and lifecycle status.
5. Any business metric from M5 stays provisional/simulated. M5 cannot prove actual stockout,
   spoilage, supplier, or buyer outcome claims.

## Hypothesis Register

These are hypotheses, not results. I am writing the chain out explicitly so the next step is
auditable: finding -> retail interpretation -> experiment change -> metric plan. Confidence
means how directly this dataset supports the hypothesis, not whether it will definitely beat
the baseline.

{_markdown_table(report['hypothesis_register'], ['rank', 'finding', 'evidence', 'domain_interpretation', 'hypothesis', 'experiment_change', 'primary_metrics', 'risk', 'confidence'])}

## Evaluation Plan Before Experiments

I want each experiment to change one layer at a time. The first pass should use time-based
holdouts and report both model metrics and simulated decision metrics with benchmark
provenance.

{_markdown_table(report['evaluation_plan'], ['rank', 'hypothesis', 'experiment_artifact', 'primary_slice', 'primary_success_metric', 'secondary_metrics', 'guardrail', 'pass_condition'])}

## Candidate Manual DS Hypotheses

{hypothesis_lines}

## Charts

{chart_lines}
"""


def build_report(data_dir: Path, output_dir: Path) -> dict[str, Any]:
    frame = _load_frame(data_dir)
    series = _series_summary(frame)
    paths = EDAPaths(
        output_dir=output_dir,
        json_path=output_dir / "m5_global_eda.json",
        markdown_path=output_dir / "m5_global_eda.md",
        charts_dir=output_dir / "charts",
    )
    report: dict[str, Any] = {
        "summary": _overall_summary(frame, series, data_dir),
        "data_quality_summary": _data_quality_summary(frame, series),
        "late_launch_deep_dive": _late_launch_deep_dive(frame, series),
        "category_summary": _category_summary(frame, series),
        "intermittent_demand_summary": _intermittent_demand_summary(series),
        "velocity_summary": _velocity_summary(series),
        "store_state_summary": _store_state_summary(frame),
        "regionality_summary": _regionality_summary(frame, series),
        "calendar_summary": _calendar_summary(frame),
        "price_summary": _price_summary(frame, series),
    }
    report["candidate_hypotheses"] = _build_hypotheses(
        report["summary"],
        report["data_quality_summary"],
        report["late_launch_deep_dive"],
        report["regionality_summary"],
        report["velocity_summary"],
        report["intermittent_demand_summary"],
        report["price_summary"],
        report["calendar_summary"],
    )
    report["hypothesis_register"] = _build_hypothesis_register(report)
    report["evaluation_plan"] = _build_evaluation_plan(report)
    report["charts"] = _write_charts(report, paths)
    return report


def write_report(report: dict[str, Any], output_dir: Path) -> EDAPaths:
    paths = EDAPaths(
        output_dir=output_dir,
        json_path=output_dir / "m5_global_eda.json",
        markdown_path=output_dir / "m5_global_eda.md",
        charts_dir=output_dir / "charts",
    )
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths.markdown_path.write_text(_render_markdown(report) + "\n", encoding="utf-8")
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate global M5/Walmart EDA artifacts for manual DS work.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.data_dir, args.output_dir)
    paths = write_report(report, args.output_dir)
    summary = report["summary"]
    print(f"Wrote {paths.json_path}")
    print(f"Wrote {paths.markdown_path}")
    print(
        "M5 EDA:",
        f"rows={summary['rows']}",
        f"series={summary['series']}",
        f"zero_sales_rate={summary['zero_sales_rate']}",
        f"top_hypothesis={report['candidate_hypotheses'][0]['title']}",
    )


if __name__ == "__main__":
    main()
