#!/usr/bin/env python3
"""Canonicalize an M5/Walmart dataset directory for ShelfOps."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sources.m5 import (
    canonicalize_m5,
    filter_m5_sell_prices,
    load_m5_directory,
    load_m5_tables,
    subset_m5_series,
)
from ml.dataset_snapshots import create_dataset_snapshot, persist_dataset_snapshot


def _write_subset_manifest(
    *,
    manifest_path: Path,
    sales_subset: pd.DataFrame,
    sales_filename: str,
    series_per_store_category: int,
    random_seed: int,
) -> None:
    counts = (
        sales_subset.groupby(["store_id", "cat_id"])
        .size()
        .rename("series_count")
        .reset_index()
        .sort_values(["store_id", "cat_id"], kind="mergesort")
    )
    manifest = {
        "source_dataset_id": "m5_walmart",
        "subset_strategy": "balanced_store_category_series_sample",
        "series_per_store_category": int(series_per_store_category),
        "random_seed": int(random_seed),
        "sales_file": sales_filename,
        "selected_series": int(len(sales_subset)),
        "stores": int(sales_subset["store_id"].nunique()),
        "categories": int(sales_subset["cat_id"].nunique()),
        "departments": int(sales_subset["dept_id"].nunique()) if "dept_id" in sales_subset.columns else 0,
        "series_counts": counts.to_dict(orient="records"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare canonical M5/Walmart records for ShelfOps")
    parser.add_argument("--input-dir", required=True, help="Path to M5 dataset directory")
    parser.add_argument(
        "--output-csv",
        default="data/benchmarks/m5_walmart/canonical_transactions.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--series-per-store-category",
        type=int,
        default=0,
        help="Optional balanced sample size per store/category group. Uses the full dataset when omitted.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for deterministic M5 series sampling.",
    )
    parser.add_argument(
        "--subset-dir",
        default=None,
        help="Optional directory to write the sampled raw M5 subset and manifest.",
    )
    args = parser.parse_args()

    if args.series_per_store_category > 0:
        calendar_df, sell_prices_df, sales_df, sales_filename = load_m5_tables(args.input_dir)
        sales_subset = subset_m5_series(
            sales_df,
            series_per_store_category=args.series_per_store_category,
            random_state=args.random_seed,
        )
        sell_prices_subset = filter_m5_sell_prices(sell_prices_df, sales_subset)
        canonical = canonicalize_m5(
            calendar_df=calendar_df,
            sell_prices_df=sell_prices_subset,
            sales_df=sales_subset,
        )

        subset_dir = Path(args.subset_dir) if args.subset_dir else Path(args.output_csv).parent / "raw_subset"
        subset_dir.mkdir(parents=True, exist_ok=True)
        calendar_df.to_csv(subset_dir / "calendar.csv", index=False)
        sell_prices_subset.to_csv(subset_dir / "sell_prices.csv", index=False)
        sales_subset.to_csv(subset_dir / sales_filename, index=False)
        _write_subset_manifest(
            manifest_path=subset_dir / "subset_manifest.json",
            sales_subset=sales_subset,
            sales_filename=sales_filename,
            series_per_store_category=args.series_per_store_category,
            random_seed=args.random_seed,
        )
    else:
        canonical = load_m5_directory(args.input_dir)

    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(output_path, index=False)

    snapshot = create_dataset_snapshot(canonical, dataset_id="m5_walmart", source_type="benchmark")
    snapshot_path = persist_dataset_snapshot(snapshot)

    print(f"Wrote canonical M5 data: {output_path}")
    print(f"Dataset snapshot: {snapshot['snapshot_id']}")
    print(f"Snapshot file: {snapshot_path}")
    if args.series_per_store_category > 0:
        print(f"Subset series/store/category: {args.series_per_store_category}")
        print(f"Random seed: {args.random_seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
