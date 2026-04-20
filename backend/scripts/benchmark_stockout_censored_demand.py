#!/usr/bin/env python3
"""
Benchmark FreshRetailNet stockout-aware and censored-demand baselines.

Usage:
  PYTHONPATH=backend python3 backend/scripts/benchmark_stockout_censored_demand.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from data_sources.freshretailnet import load_freshretailnet_directory
from ml.baselines import intermittent_demand_forecast, moving_average_forecast, naive_forecast, prepare_series_frame
from ml.dataset_snapshots import create_dataset_snapshot, persist_dataset_snapshot
from ml.latent_demand import add_conservative_latent_demand
from ml.metrics_contract import compute_forecast_metrics
from ml.stockout_metrics import evaluate_stockout_windows


DEFAULT_DATA_DIR = "data/benchmarks/freshretailnet_50k/raw"


def _build_result_row(name: str, test_df, preds, *, estimated_recovered_target) -> dict:
    metrics = compute_forecast_metrics(test_df["quantity"], preds)
    stockout_metrics = evaluate_stockout_windows(
        y_true=test_df["quantity"],
        y_pred=preds,
        stockout_window=test_df["stockout_window"],
        estimated_recovered_target=estimated_recovered_target,
    )
    return {
        "model_name": name,
        "rows_test": int(len(test_df)),
        "date_min": str(test_df["date"].min().date()),
        "date_max": str(test_df["date"].max().date()),
        "frequency": str(test_df["frequency"].iloc[0]) if len(test_df) else "unknown",
        **metrics,
        **stockout_metrics,
    }


def _sample_series(splits: dict[str, pd.DataFrame], *, max_series: int | None, random_seed: int) -> dict[str, pd.DataFrame]:
    if not max_series or max_series <= 0:
        return splits

    train = splits["train"].copy()
    series_cols = ["store_id", "product_id"]
    stratify_col = "first_category_id" if "first_category_id" in train.columns else None
    unique_series = train[series_cols + ([stratify_col] if stratify_col else [])].drop_duplicates().reset_index(drop=True)

    if len(unique_series) <= max_series:
        return splits

    if stratify_col:
        sampled_parts = []
        total = len(unique_series)
        for idx, (_, group) in enumerate(unique_series.groupby(stratify_col, dropna=False, sort=True)):
            share = max(1, round(max_series * len(group) / total))
            take = min(len(group), share)
            sampled_parts.append(group.sample(n=take, random_state=random_seed + idx))
        sampled = pd.concat(sampled_parts, ignore_index=True).drop_duplicates(subset=series_cols)
        if len(sampled) > max_series:
            sampled = sampled.sample(n=max_series, random_state=random_seed).reset_index(drop=True)
        elif len(sampled) < max_series:
            remainder = unique_series.merge(sampled[series_cols], on=series_cols, how="left", indicator=True)
            remainder = remainder[remainder["_merge"] == "left_only"].drop(columns="_merge")
            extra = remainder.sample(n=min(len(remainder), max_series - len(sampled)), random_state=random_seed)
            sampled = pd.concat([sampled, extra], ignore_index=True)
    else:
        sampled = unique_series.sample(n=max_series, random_state=random_seed).reset_index(drop=True)

    sampled_keys = sampled[series_cols].drop_duplicates()
    out: dict[str, pd.DataFrame] = {}
    for split_name, frame in splits.items():
        out[split_name] = frame.merge(sampled_keys, on=series_cols, how="inner").reset_index(drop=True)
    return out


def render_markdown(report: dict) -> str:
    lines = [
        "# FreshRetailNet Stockout/Censored-Demand Benchmark",
        "",
        f"- dataset_id: `{report['dataset_id']}`",
        f"- source_note: `{report['source_note']}`",
        f"- rows_train: `{report['rows_train']}`",
        f"- rows_eval: `{report['rows_eval']}`",
        f"- series_sampled: `{report['series_sampled']}`",
        f"- dataset_snapshot_id: `{report['dataset_snapshot_id']}`",
        "",
        "This benchmark is not U.S.-based and does not prove merchant ROI or end-to-end replenishment performance.",
        "",
        "| model | wape | mase | stockout_window_bias | underforecast_rate_during_stockouts | non_stockout_wape | estimated_recovered_demand_gap |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["results"]:
        lines.append(
            f"| {row['model_name']} | {row['wape']:.4f} | {row['mase']:.4f} | "
            f"{row['stockout_window_bias']:.4f} | {row['underforecast_rate_during_stockouts']:.4f} | "
            f"{(row['non_stockout_wape'] if row['non_stockout_wape'] is not None else 0.0):.4f} | "
            f"{(row['estimated_recovered_demand_gap'] if row['estimated_recovered_demand_gap'] is not None else 0.0):.4f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark FreshRetailNet stockout-aware baselines")
    parser.add_argument("--data-dir", type=str, default=DEFAULT_DATA_DIR, help="Directory with train.parquet and eval.parquet")
    parser.add_argument(
        "--output-json",
        type=str,
        default="backend/reports/freshretailnet_stockout_benchmark.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--output-md",
        type=str,
        default="backend/reports/freshretailnet_stockout_benchmark.md",
        help="Output Markdown path",
    )
    parser.add_argument("--max-series", type=int, default=5000, help="Optional deterministic series cap for reproducible benchmarking")
    parser.add_argument("--random-seed", type=int, default=42, help="Random seed for series sampling")
    args = parser.parse_args()

    splits = load_freshretailnet_directory(args.data_dir)
    splits = _sample_series(splits, max_series=args.max_series, random_seed=args.random_seed)
    combined = prepare_series_frame(pd.concat([splits["train"], splits["eval"]], ignore_index=True))
    combined = add_conservative_latent_demand(combined, split_col="split")
    train_df = combined[combined["split"] == "train"].copy().reset_index(drop=True)
    eval_df = combined[combined["split"] == "eval"].copy().reset_index(drop=True)

    snapshot = create_dataset_snapshot(
        train_df,
        dataset_id="freshretailnet_50k",
        source_type="benchmark",
    )
    persist_dataset_snapshot(snapshot)

    observed_moving_average = moving_average_forecast(train_df, eval_df)
    observed_intermittent = intermittent_demand_forecast(train_df, eval_df)
    observed_naive = naive_forecast(train_df, eval_df)

    latent_train = train_df.copy()
    latent_train["quantity"] = latent_train["latent_demand_quantity"]
    latent_adjusted_moving_average = moving_average_forecast(latent_train, eval_df)

    estimated_recovered_target = eval_df["latent_demand_quantity"]
    results = [
        _build_result_row("naive_observed", eval_df, observed_naive, estimated_recovered_target=estimated_recovered_target),
        _build_result_row(
            "moving_average_7_observed",
            eval_df,
            observed_moving_average,
            estimated_recovered_target=estimated_recovered_target,
        ),
        _build_result_row(
            "intermittent_observed",
            eval_df,
            observed_intermittent,
            estimated_recovered_target=estimated_recovered_target,
        ),
        _build_result_row(
            "moving_average_7_latent_adjusted",
            eval_df,
            latent_adjusted_moving_average,
            estimated_recovered_target=estimated_recovered_target,
        ),
    ]

    report = {
        "dataset_id": "freshretailnet_50k",
        "source_note": "Secondary stockout-aware benchmark. Not U.S.-based. No merchant ROI claims.",
        "rows_train": int(len(train_df)),
        "rows_eval": int(len(eval_df)),
        "series_sampled": int(train_df[["store_id", "product_id"]].drop_duplicates().shape[0]),
        "max_series": int(args.max_series) if args.max_series else None,
        "dataset_snapshot_id": snapshot["snapshot_id"],
        "results": results,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
