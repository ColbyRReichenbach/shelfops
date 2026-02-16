#!/usr/bin/env python3
"""
Build a deterministic, representative transaction subset for fast model iteration.

This keeps full time-series rows for sampled (store_id, product_id) pairs while
sampling pairs across demand strata, so experiments run faster without collapsing
the retail mix into only high-volume or only low-volume SKUs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add backend to path so imports work when run from repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workers.retrain import _load_csv_data


def _build_pair_stats(df: pd.DataFrame, strata_bins: int, seed: int) -> pd.DataFrame:
    pair_stats = (
        df.groupby(["store_id", "product_id"], as_index=False)
        .agg(
            rows=("quantity", "size"),
            total_qty=("quantity", "sum"),
            mean_qty=("quantity", "mean"),
            nonzero_rate=("quantity", lambda s: float((s > 0).mean())),
        )
        .sort_values(["store_id", "product_id"])
        .reset_index(drop=True)
    )

    q = max(1, min(int(strata_bins), len(pair_stats)))
    if q > 1:
        # Rank before qcut to avoid duplicate-bin edge cases on tied totals.
        ranked = pair_stats["total_qty"].rank(method="first")
        pair_stats["demand_bin"] = pd.qcut(ranked, q=q, labels=False, duplicates="drop").astype(int)
    else:
        pair_stats["demand_bin"] = 0

    rng = np.random.default_rng(seed)
    pair_stats["rand"] = rng.random(len(pair_stats))

    # Keep one anchor pair per demand bin so every stratum is represented.
    anchor_idx = pair_stats.groupby("demand_bin")["rand"].idxmin()
    pair_stats["is_anchor"] = False
    pair_stats.loc[anchor_idx, "is_anchor"] = True
    return pair_stats


def _estimate_rows(pair_stats: pd.DataFrame, frac: float) -> tuple[int, int, pd.Series]:
    mask = (pair_stats["rand"] <= frac) | pair_stats["is_anchor"]
    rows = int(pair_stats.loc[mask, "rows"].sum())
    pairs = int(mask.sum())
    return rows, pairs, mask


def _choose_fraction(pair_stats: pd.DataFrame, target_rows: int) -> tuple[float, int, int, pd.Series]:
    total_rows = int(pair_stats["rows"].sum())
    if target_rows <= 0 or target_rows >= total_rows:
        rows, pairs, mask = _estimate_rows(pair_stats, 1.0)
        return 1.0, rows, pairs, mask

    low, high = 0.0, 1.0
    best_frac = 0.0
    best_rows = 0
    best_pairs = 0
    best_mask = pair_stats["is_anchor"].copy()

    for _ in range(30):
        mid = (low + high) / 2.0
        rows, pairs, mask = _estimate_rows(pair_stats, mid)

        if rows <= target_rows:
            best_frac, best_rows, best_pairs, best_mask = mid, rows, pairs, mask
            low = mid
        else:
            high = mid

    if best_rows == 0:
        rows, pairs, mask = _estimate_rows(pair_stats, high)
        return high, rows, pairs, mask

    return best_frac, best_rows, best_pairs, best_mask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fast exploration subset for model iteration.")
    parser.add_argument("--input-dir", default="data/seed", help="Input data directory (recursive CSV scan).")
    parser.add_argument("--output-dir", default="data/exploration_subset", help="Output directory for subset files.")
    parser.add_argument("--target-rows", type=int, default=400_000, help="Target row count for subset.")
    parser.add_argument("--strata-bins", type=int, default=8, help="Demand strata count for pair sampling.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic sampling.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists():
        print(f"Input dir not found: {input_dir}", file=sys.stderr)
        return 1

    print("=== Build Exploration Subset ===")
    print(f"input_dir={input_dir}")
    print(f"output_dir={output_dir}")
    print(f"target_rows={args.target_rows}")
    print(f"strata_bins={args.strata_bins}")
    print(f"seed={args.seed}")

    transactions_df = _load_csv_data(str(input_dir))
    total_rows = len(transactions_df)
    total_pairs = transactions_df.groupby(["store_id", "product_id"]).ngroups
    print(f"loaded_rows={total_rows:,} store_product_pairs={total_pairs:,}")

    pair_stats = _build_pair_stats(transactions_df, strata_bins=args.strata_bins, seed=args.seed)
    frac, chosen_rows, chosen_pairs, chosen_mask = _choose_fraction(pair_stats, target_rows=args.target_rows)
    chosen_pairs_df = pair_stats.loc[chosen_mask, ["store_id", "product_id", "demand_bin", "rows", "total_qty"]]

    subset_df = transactions_df.merge(
        chosen_pairs_df[["store_id", "product_id"]],
        on=["store_id", "product_id"],
        how="inner",
    ).sort_values(["store_id", "product_id", "date"])

    subset_csv = output_dir / "transactions_subset.csv"
    subset_df.to_csv(subset_csv, index=False)

    bins_full = pair_stats.groupby("demand_bin", as_index=False)["rows"].sum().rename(columns={"rows": "full_rows"})
    bins_subset = (
        chosen_pairs_df.groupby("demand_bin", as_index=False)["rows"].sum().rename(columns={"rows": "subset_rows"})
    )
    bin_mix = bins_full.merge(bins_subset, on="demand_bin", how="left").fillna({"subset_rows": 0})
    bin_mix["subset_share"] = (bin_mix["subset_rows"] / max(1, int(subset_df.shape[0]))).round(6)
    bin_mix["full_share"] = (bin_mix["full_rows"] / max(1, int(transactions_df.shape[0]))).round(6)

    metadata = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "target_rows": int(args.target_rows),
        "actual_rows": int(subset_df.shape[0]),
        "total_rows": int(total_rows),
        "total_store_product_pairs": int(total_pairs),
        "selected_store_product_pairs": int(chosen_pairs),
        "selection_fraction": float(round(frac, 8)),
        "seed": int(args.seed),
        "strata_bins": int(args.strata_bins),
        "created_at_utc": pd.Timestamp.utcnow().isoformat(),
        "subset_file": str(subset_csv),
        "bin_mix": bin_mix.to_dict(orient="records"),
    }
    metadata_path = output_dir / "subset_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))

    print(f"subset_rows={len(subset_df):,} selected_pairs={chosen_pairs:,} fraction={frac:.6f}")
    print(f"subset_csv={subset_csv}")
    print(f"metadata_json={metadata_path}")
    print("\nUse this subset for fast iteration:")
    print(
        "  backend/scripts/iterate_model.sh "
        f"--data-dir {output_dir} --dataset exploration_subset "
        "--version <version> --baseline <baseline> --skip-tests"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

