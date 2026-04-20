#!/usr/bin/env python3
"""
Benchmark in-domain forecasting baselines across canonical datasets.

Usage:
  PYTHONPATH=backend python3 backend/scripts/benchmark_datasets.py
  PYTHONPATH=backend python3 backend/scripts/benchmark_datasets.py --max-rows 150000
  PYTHONPATH=backend python3 backend/scripts/benchmark_datasets.py --dataset-id m5_walmart --data-dir data/benchmarks/m5_walmart
  # Legacy reference path:
  PYTHONPATH=backend python3 backend/scripts/benchmark_datasets.py --dataset-id favorita --data-dir /path/to/legacy/favorita
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.metrics_contract import compute_forecast_metrics
from ml.baselines import (
    category_store_average_forecast,
    intermittent_demand_forecast,
    moving_average_forecast,
    naive_forecast,
    prepare_series_frame,
    seasonal_naive_forecast,
)

DATASET_DIRS = {
    "m5_walmart": "data/benchmarks/m5_walmart",
}


BUSINESS_METRIC_NOT_AVAILABLE = {
    "stockout_miss_rate": "not_available",
    "overstock_rate": "not_available",
    "overstock_dollars": "not_available",
    "overstock_dollars_confidence": "not_available",
    "lost_sales_qty": "not_available",
    "opportunity_cost_stockout": "not_available",
    "opportunity_cost_stockout_confidence": "not_available",
    "opportunity_cost_overstock": "not_available",
    "opportunity_cost_overstock_confidence": "not_available",
}


def _load_canonical_transactions(data_dir: str) -> pd.DataFrame:
    from ml.data_contracts import load_canonical_transactions

    return load_canonical_transactions(data_dir)


def _time_split(raw: pd.DataFrame, test_fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    unique_dates = sorted(pd.to_datetime(raw["date"]).dropna().unique().tolist())
    if len(unique_dates) < 3:
        raise ValueError("Need at least 3 distinct dates for benchmark split")
    split_idx = max(1, int(len(unique_dates) * (1 - test_fraction)))
    split_idx = min(split_idx, len(unique_dates) - 1)
    cutoff = unique_dates[split_idx]
    train_df = raw[raw["date"] < cutoff].copy()
    test_df = raw[raw["date"] >= cutoff].copy()
    if train_df.empty or test_df.empty:
        raise ValueError("Time split produced empty train or test frame")
    return train_df.reset_index(drop=True), test_df.reset_index(drop=True)


def _build_lgb_features(raw: pd.DataFrame) -> pd.DataFrame:
    frame = prepare_series_frame(raw)
    grouped = frame.groupby(["store_id", "product_id"])["quantity"]
    frame["lag_1"] = grouped.shift(1)
    frame["lag_7"] = grouped.shift(7)
    frame["lag_28"] = grouped.shift(28)
    frame["rolling_mean_7"] = grouped.transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    frame["rolling_mean_28"] = grouped.transform(lambda s: s.shift(1).rolling(28, min_periods=1).mean())
    frame["day_of_week"] = frame["date"].dt.dayofweek
    frame["month"] = frame["date"].dt.month
    frame["week_of_year"] = frame["date"].dt.isocalendar().week.astype(int)
    frame["store_code"] = pd.factorize(frame["store_id"])[0]
    frame["product_code"] = pd.factorize(frame["product_id"])[0]
    frame["category_code"] = pd.factorize(frame["category"].astype(str))[0]
    return frame


def _run_lightgbm(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    try:
        import lightgbm as lgb
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ModuleNotFoundError("lightgbm is required for benchmark_datasets.py") from exc

    feat = _build_lgb_features(pd.concat([train_df, test_df], ignore_index=True))
    train_feat = feat.iloc[: len(train_df)].copy()
    test_feat = feat.iloc[len(train_df) :].copy()
    feature_cols = [
        "lag_1",
        "lag_7",
        "lag_28",
        "rolling_mean_7",
        "rolling_mean_28",
        "day_of_week",
        "month",
        "week_of_year",
        "store_code",
        "product_code",
        "category_code",
        "is_promotional",
        "is_holiday",
    ]
    X_train = train_feat[feature_cols].fillna(0.0)
    y_train = train_feat["quantity"].astype(float)
    X_test = test_feat[feature_cols].fillna(0.0)
    model = lgb.LGBMRegressor(
        objective="poisson",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=63,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    return pd.Series(np.maximum(preds, 0.0), index=test_df.index)


def _safe_metrics(dataset_id: str, y_true: pd.Series, preds: pd.Series) -> dict:
    metrics = compute_forecast_metrics(y_true, preds)
    if dataset_id == "m5_walmart":
        metrics.update(BUSINESS_METRIC_NOT_AVAILABLE)
    metrics["interval_method"] = "not_available"
    metrics["interval_coverage"] = "not_available"
    metrics["pinball_loss"] = "not_available"
    return metrics


def _segment_coverage(raw: pd.DataFrame) -> dict[str, int]:
    return {
        "stores": int(raw["store_id"].nunique()),
        "products": int(raw["product_id"].nunique()),
        "categories": int(raw["category"].astype(str).nunique()),
    }


def _result_row(model_name: str, dataset_id: str, raw: pd.DataFrame, train_df: pd.DataFrame, test_df: pd.DataFrame, preds: pd.Series) -> dict:
    metrics = _safe_metrics(dataset_id, test_df["quantity"].astype(float), preds.astype(float))
    return {
        "model_name": model_name,
        "dataset_id": dataset_id,
        "rows_used": int(len(raw)),
        "rows_train": int(len(train_df)),
        "rows_test": int(len(test_df)),
        "date_min": str(pd.to_datetime(raw["date"]).min().date()),
        "date_max": str(pd.to_datetime(raw["date"]).max().date()),
        "train_end_date": str(pd.to_datetime(train_df["date"]).max().date()),
        "test_start_date": str(pd.to_datetime(test_df["date"]).min().date()),
        "frequency": str(raw["frequency"].iloc[0]) if len(raw) else "unknown",
        "segment_coverage": _segment_coverage(raw),
        **metrics,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Dataset Benchmark Report",
        "",
        f"- dataset_id: `{report['dataset_id']}`",
        f"- rows_used: `{report['rows_used']}`",
        f"- date_range: `{report['date_min']} -> {report['date_max']}`",
        "",
        "| model | mae | wape | mase | bias_pct | interval_method | stockout_miss_rate | overstock_rate | rows_test |",
        "|---|---:|---:|---:|---:|---|---|---|---:|",
    ]
    for row in report["results"]:
        lines.append(
            f"| {row['model_name']} | {row['mae']:.4f} | {row['wape']:.4f} | {row['mase']:.4f} | "
            f"{row['bias_pct']:.4f} | {row['interval_method']} | {row['stockout_miss_rate']} | "
            f"{row['overstock_rate']} | {row['rows_test']} |"
        )
    return "\n".join(lines) + "\n"


def benchmark_dataset(dataset_id: str, data_dir: str, max_rows: int) -> dict:
    raw = _load_canonical_transactions(data_dir)
    raw = prepare_series_frame(raw)
    if len(raw) > max_rows:
        raw = raw.tail(max_rows).reset_index(drop=True)
    train_df, test_df = _time_split(raw)

    results = [
        _result_row("naive", dataset_id, raw, train_df, test_df, naive_forecast(train_df, test_df)),
        _result_row("seasonal_naive", dataset_id, raw, train_df, test_df, seasonal_naive_forecast(train_df, test_df)),
        _result_row("moving_average_7", dataset_id, raw, train_df, test_df, moving_average_forecast(train_df, test_df)),
        _result_row("category_store_average", dataset_id, raw, train_df, test_df, category_store_average_forecast(train_df, test_df)),
        _result_row("intermittent_demand", dataset_id, raw, train_df, test_df, intermittent_demand_forecast(train_df, test_df)),
        _result_row("lightgbm", dataset_id, raw, train_df, test_df, _run_lightgbm(train_df, test_df)),
    ]
    return {
        "dataset_id": dataset_id,
        "rows_used": int(len(raw)),
        "date_min": str(pd.to_datetime(raw["date"]).min().date()),
        "date_max": str(pd.to_datetime(raw["date"]).max().date()),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark datasets with a fixed baseline model")
    parser.add_argument("--max-rows", type=int, default=200000, help="Max rows per dataset (tail sample)")
    parser.add_argument("--dataset-id", type=str, default=None, help="Optional single dataset ID to benchmark")
    parser.add_argument("--data-dir", type=str, default=None, help="Optional explicit dataset directory")
    parser.add_argument(
        "--output-json",
        type=str,
        default="backend/reports/dataset_benchmark_baseline.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--output-md",
        type=str,
        default="backend/reports/dataset_benchmark_baseline.md",
        help="Output Markdown path",
    )
    args = parser.parse_args()

    results = []
    dataset_map = DATASET_DIRS.copy()
    if args.dataset_id and args.data_dir:
        dataset_map = {args.dataset_id: args.data_dir}
    elif args.dataset_id:
        if args.dataset_id not in dataset_map:
            raise SystemExit(f"Unknown dataset_id '{args.dataset_id}'. Pass --data-dir to benchmark a custom path.")
        dataset_map = {args.dataset_id: dataset_map[args.dataset_id]}

    for dataset_id, data_dir in dataset_map.items():
        if not Path(data_dir).exists():
            print(f"Skipping {dataset_id}: missing directory {data_dir}")
            continue
        result = benchmark_dataset(dataset_id, data_dir, args.max_rows)
        results.append(result)

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(render_markdown(report) for report in results), encoding="utf-8")

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
