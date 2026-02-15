#!/usr/bin/env python3
"""
Assign Store Clusters — Run K-Means clustering on stores.

Usage:
  python scripts/assign_store_clusters.py
  python scripts/assign_store_clusters.py --data-dir data/seed --clusters 3
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="Assign store clusters via K-Means")
    parser.add_argument("--data-dir", type=str, default=None, help="Training data directory")
    parser.add_argument("--clusters", type=int, default=3, help="Number of clusters")
    args = parser.parse_args()

    from retail.store_clustering import (
        CLUSTER_LABELS,
        CLUSTER_SAFETY_MULTIPLIERS,
        cluster_stores,
        get_cluster_summary,
    )
    from workers.retrain import _load_csv_data

    # Resolve data dir
    data_dir = args.data_dir
    if data_dir is None:
        for d in ["data/seed", "data/kaggle", "../data/seed"]:
            if os.path.isdir(d):
                data_dir = os.path.abspath(d)
                break
        if data_dir is None:
            print("No training data found. Run seed_enterprise_data.py first.")
            sys.exit(1)

    print("=" * 60)
    print("  ShelfOps Store Clustering")
    print("=" * 60)
    print(f"  Data:     {data_dir}")
    print(f"  Clusters: {args.clusters}")
    print()

    # Load data
    transactions_df = _load_csv_data(data_dir)
    print(f"  Loaded {len(transactions_df):,} rows")
    print(f"  Stores: {transactions_df['store_id'].nunique()}")

    # Run clustering
    clusters = cluster_stores(transactions_df, n_clusters=args.clusters)

    # Print results
    summaries = get_cluster_summary(clusters, transactions_df)

    print(f"\n  {'Cluster':<20} {'Stores':<8} {'Avg Volume':<12} {'Volatility':<12} {'Safety Mult':<12}")
    print(f"  {'-' * 20} {'-' * 8} {'-' * 12} {'-' * 12} {'-' * 12}")

    for s in summaries:
        print(
            f"  {s['label']:<20} {s['n_stores']:<8} "
            f"{s['avg_daily_volume']:<12.1f} {s['avg_volatility']:<12.3f} "
            f"{s['safety_multiplier']:<12.2f}"
        )

    print("\n  Store Assignments:")
    for store_id, cluster_id in sorted(clusters.items(), key=lambda x: x[1]):
        label = CLUSTER_LABELS.get(cluster_id, f"cluster_{cluster_id}")
        print(f"    {store_id}: {label} (tier {cluster_id})")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
