"""
Store Clustering — K-Means clustering for store segmentation.

Groups stores into tiers based on sales patterns for differentiated
safety stock calculation and model routing.

Features used for clustering:
  - avg_daily_volume: Average daily sales quantity
  - sales_volatility: Coefficient of variation (std/mean)
  - promo_sensitivity: Ratio of promo-day sales to regular sales

Cluster interpretation:
  - Cluster 0 (High-volume): Urban flagships, high traffic, stable demand
  - Cluster 1 (Mid-volume): Suburban stores, moderate traffic
  - Cluster 2 (Low-volume): Rural/smaller stores, lower traffic, higher volatility

Usage:
    from retail.store_clustering import cluster_stores, CLUSTER_SAFETY_MULTIPLIERS

    clusters = cluster_stores(transactions_df, n_clusters=3)
    # → {store_id: 0, store_id: 1, ...}

    multiplier = CLUSTER_SAFETY_MULTIPLIERS[clusters[store_id]]
    # → 1.15 for high-volume, 1.00 for mid, 0.85 for low
"""

from typing import Any

import numpy as np
import pandas as pd
import structlog
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger()

# Safety stock multipliers by cluster tier
# High-volume stores need slightly more safety stock (more customers affected by stockouts)
# Low-volume stores can run leaner (fewer customers, lower stockout cost)
CLUSTER_SAFETY_MULTIPLIERS = {
    0: 1.15,  # High-volume
    1: 1.00,  # Mid-volume (baseline)
    2: 0.85,  # Low-volume
}

CLUSTER_LABELS = {
    0: "high_volume",
    1: "mid_volume",
    2: "low_volume",
}


def cluster_stores(
    transactions_df: pd.DataFrame,
    n_clusters: int = 3,
    store_col: str = "store_id",
    qty_col: str = "quantity",
    date_col: str = "date",
    promo_col: str = "is_promotion_active",
) -> dict[str, int]:
    """
    Cluster stores by sales behavior using K-Means.

    Args:
        transactions_df: Daily transaction data with store_id, quantity, date columns
        n_clusters: Number of clusters (default 3: high/mid/low volume)
        store_col: Column name for store identifier
        qty_col: Column name for quantity sold
        date_col: Column name for date
        promo_col: Column name for promotion flag (optional)

    Returns:
        Dict mapping store_id → cluster_tier (0=high, 1=mid, 2=low)
    """
    # Aggregate metrics per store
    store_metrics = _compute_store_metrics(transactions_df, store_col, qty_col, date_col, promo_col)

    if len(store_metrics) < n_clusters:
        logger.warning(
            "clustering.insufficient_stores",
            n_stores=len(store_metrics),
            n_clusters=n_clusters,
        )
        # Assign all to mid-volume if not enough stores
        return {sid: 1 for sid in store_metrics.index}

    # Normalize features
    feature_cols = ["avg_daily_volume", "sales_volatility", "promo_sensitivity"]
    X = store_metrics[feature_cols].fillna(0).values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # K-Means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # Reorder clusters so 0 = highest volume
    cluster_volumes = {}
    for i in range(n_clusters):
        mask = labels == i
        cluster_volumes[i] = store_metrics.iloc[mask]["avg_daily_volume"].mean()

    # Sort by volume descending → map original label to sorted label
    sorted_clusters = sorted(cluster_volumes.items(), key=lambda x: x[1], reverse=True)
    label_map = {old_label: new_label for new_label, (old_label, _) in enumerate(sorted_clusters)}

    # Build result mapping
    result = {}
    for idx, store_id in enumerate(store_metrics.index):
        result[store_id] = label_map[labels[idx]]

    logger.info(
        "clustering.completed",
        n_stores=len(result),
        n_clusters=n_clusters,
        cluster_sizes={CLUSTER_LABELS[i]: sum(1 for v in result.values() if v == i) for i in range(n_clusters)},
    )

    return result


def _compute_store_metrics(
    transactions_df: pd.DataFrame,
    store_col: str,
    qty_col: str,
    date_col: str,
    promo_col: str,
) -> pd.DataFrame:
    """Compute clustering features per store."""
    # Daily sales per store
    daily = transactions_df.groupby([store_col, date_col]).agg({qty_col: "sum"}).reset_index()

    # Average daily volume
    avg_volume = daily.groupby(store_col)[qty_col].mean().rename("avg_daily_volume")

    # Sales volatility (CV = std / mean)
    std_volume = daily.groupby(store_col)[qty_col].std().rename("std_daily_volume")
    cv = (std_volume / avg_volume).rename("sales_volatility")

    # Promo sensitivity
    if promo_col in transactions_df.columns:
        promo_sales = (
            transactions_df[transactions_df[promo_col] == 1].groupby(store_col)[qty_col].mean().rename("promo_avg")
        )
        regular_sales = (
            transactions_df[transactions_df[promo_col] == 0].groupby(store_col)[qty_col].mean().rename("regular_avg")
        )
        promo_sensitivity = (promo_sales / regular_sales.clip(lower=1)).rename("promo_sensitivity")
    else:
        promo_sensitivity = pd.Series(1.0, index=avg_volume.index, name="promo_sensitivity")

    metrics = pd.concat([avg_volume, cv, promo_sensitivity], axis=1).fillna(0)
    return metrics


def get_cluster_summary(
    clusters: dict[str, int],
    transactions_df: pd.DataFrame,
    store_col: str = "store_id",
    qty_col: str = "quantity",
    date_col: str = "date",
) -> list[dict[str, Any]]:
    """
    Get a summary of each cluster for reporting.

    Returns:
        List of dicts with cluster stats for display.
    """
    metrics = _compute_store_metrics(transactions_df, store_col, qty_col, date_col, "is_promotion_active")

    summaries = []
    for cluster_id in sorted(set(clusters.values())):
        store_ids = [sid for sid, cid in clusters.items() if cid == cluster_id]
        cluster_data = metrics.loc[metrics.index.isin(store_ids)]

        summaries.append(
            {
                "cluster_id": cluster_id,
                "label": CLUSTER_LABELS.get(cluster_id, f"cluster_{cluster_id}"),
                "n_stores": len(store_ids),
                "avg_daily_volume": round(float(cluster_data["avg_daily_volume"].mean()), 1),
                "avg_volatility": round(float(cluster_data["sales_volatility"].mean()), 3),
                "safety_multiplier": CLUSTER_SAFETY_MULTIPLIERS.get(cluster_id, 1.0),
                "store_ids": store_ids,
            }
        )

    return summaries
