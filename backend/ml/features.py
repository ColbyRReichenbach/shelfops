"""
Feature Engineering — Two-Phase Demand Forecasting Features.

Phase 1 "Cold Start" (27 features):
  Trained on Kaggle public data (Favorita, Walmart, Rossmann).
  Uses only features that real public datasets actually provide.

Phase 2 "Production" (45 features):
  Activated after 90+ days of real retailer data flows in via
  EDI/SFTP/Kafka adapters. Weekly retraining auto-upgrades.

Feature Groups:
  1. Temporal (10)           — both phases
  2. Sales History (12)      — both phases
  3. Product (8)             — production only (except category_encoded)
  4. Store (5)               — production only
  5. Inventory (5)           — production only
  6. Promotions (3)          — partial cold-start, full production
  7. External (2-5)          — varies by dataset

Agent: ml-engineer
Skill: ml-forecasting
Workflow: train-forecast-model.md
"""

import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Literal


# ══════════════════════════════════════════════════════════════════════════
# Feature Tier Definitions
# ══════════════════════════════════════════════════════════════════════════

FeatureTier = Literal["cold_start", "production"]

# Phase 1 — Cold Start (Kaggle-trainable)
# These features can be derived from ANY public retail dataset that has
# (date, store_id, product_id/category, quantity_sold).
COLD_START_FEATURE_COLS = [
    # Temporal (10) — derived from date column
    "day_of_week", "month", "quarter", "is_weekend", "is_holiday",
    "week_of_year", "day_of_month", "is_month_start", "is_month_end",
    "days_since_last_sale",
    # Sales History (12) — computed from quantity
    "sales_7d", "sales_14d", "sales_30d", "sales_90d",
    "avg_daily_sales_7d", "avg_daily_sales_30d",
    "sales_trend_7d", "sales_trend_30d",
    "sales_volatility_7d", "sales_volatility_30d",
    "max_daily_sales_30d", "min_daily_sales_30d",
    # Category (1) — label-encoded from category/family/dept
    "category_encoded",
    # Promotions (1) — Favorita has onpromotion, Walmart has IsHoliday
    "is_promotion_active",
    # External (3) — Walmart: temperature, fuel; Favorita: oil price
    "temperature", "precipitation", "oil_price",
]  # 27 total

# Phase 2 — Production (full 45 features)
# Requires real retailer data flowing through adapters.
PRODUCTION_FEATURE_COLS = COLD_START_FEATURE_COLS + [
    # Product (7) — from product catalog via EDI/ERP
    "unit_cost", "unit_price", "margin_pct", "weight",
    "shelf_life_days", "is_seasonal", "is_perishable",
    # Store (5) — computed from real store performance data
    "store_avg_daily_sales", "store_product_count",
    "store_inventory_turnover", "lat", "lon",
    # Inventory (5) — from real inventory snapshots/WMS
    "current_stock", "days_of_supply", "stock_velocity",
    "quantity_on_order", "stockout_count_30d",
    # Promotions extended (2) — from real promo calendar
    "promotion_discount_pct", "promotion_days_remaining",
]  # 45 total

# Legacy alias (backward compat with existing saved models)
FEATURE_COLS = PRODUCTION_FEATURE_COLS


def detect_feature_tier(df: pd.DataFrame) -> FeatureTier:
    """
    Auto-detect which feature tier a dataset supports.

    Checks for production-only columns (inventory, product pricing).
    If they're missing or all-zero, falls back to cold_start.
    """
    production_signals = [
        "current_stock", "unit_cost", "unit_price",
        "store_inventory_turnover", "days_of_supply",
    ]
    has_production = all(
        col in df.columns and df[col].notna().any() and (df[col] != 0).any()
        for col in production_signals
    )
    return "production" if has_production else "cold_start"


def get_feature_cols(tier: FeatureTier) -> list[str]:
    """Return the feature column list for a given tier."""
    if tier == "cold_start":
        return COLD_START_FEATURE_COLS.copy()
    return PRODUCTION_FEATURE_COLS.copy()


# ──────────────────────────────────────────────────────────────────────────
# 1. Temporal Features (10)
# ──────────────────────────────────────────────────────────────────────────

def _temporal_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Extract 10 temporal features from a date column."""
    dt = pd.to_datetime(df[date_col], errors="coerce")
    
    # Fill NaT with a default (e.g. first date) to prevent crash, though upstream should filter
    if dt.isna().any():
        dt = dt.fillna(dt.min())

    return df.assign(
        day_of_week=dt.dt.dayofweek.fillna(0).astype(int),
        month=dt.dt.month.fillna(1).astype(int),
        quarter=dt.dt.quarter.fillna(1).astype(int),
        is_weekend=(dt.dt.dayofweek >= 5).astype(int),
        is_holiday=0,  # Placeholder — plug in holidays calendar
        week_of_year=dt.dt.isocalendar().week.astype(int),
        day_of_month=dt.dt.day.fillna(1).astype(int),
        is_month_start=dt.dt.is_month_start.astype(int),
        is_month_end=dt.dt.is_month_end.astype(int),
        days_since_last_sale=0,  # Filled per store-product in pipeline
    )


# ──────────────────────────────────────────────────────────────────────────
# 2. Sales History Features (12)
# ──────────────────────────────────────────────────────────────────────────

def _sales_history_features(
    txn_df: pd.DataFrame,
    store_col: str = "store_id",
    product_col: str = "product_id",
    date_col: str = "date",
    qty_col: str = "quantity",
) -> pd.DataFrame:
    """
    Compute rolling sales statistics per store-product pair.
    Expects daily aggregated quantities.
    """
    group = [store_col, product_col]
    txn_df = txn_df.sort_values(group + [date_col])

    grp = txn_df.groupby(group)[qty_col]

    txn_df["sales_7d"] = grp.transform(lambda x: x.rolling(7, min_periods=1).sum())
    txn_df["sales_14d"] = grp.transform(lambda x: x.rolling(14, min_periods=1).sum())
    txn_df["sales_30d"] = grp.transform(lambda x: x.rolling(30, min_periods=1).sum())
    txn_df["sales_90d"] = grp.transform(lambda x: x.rolling(90, min_periods=1).sum())

    txn_df["avg_daily_sales_7d"] = grp.transform(lambda x: x.rolling(7, min_periods=1).mean())
    txn_df["avg_daily_sales_30d"] = grp.transform(lambda x: x.rolling(30, min_periods=1).mean())

    # Trend: slope proxy via diff of rolling means
    txn_df["sales_trend_7d"] = grp.transform(
        lambda x: x.rolling(7, min_periods=2).mean().diff()
    )
    txn_df["sales_trend_30d"] = grp.transform(
        lambda x: x.rolling(30, min_periods=2).mean().diff()
    )

    txn_df["sales_volatility_7d"] = grp.transform(lambda x: x.rolling(7, min_periods=2).std())
    txn_df["sales_volatility_30d"] = grp.transform(lambda x: x.rolling(30, min_periods=2).std())

    txn_df["max_daily_sales_30d"] = grp.transform(lambda x: x.rolling(30, min_periods=1).max())
    txn_df["min_daily_sales_30d"] = grp.transform(lambda x: x.rolling(30, min_periods=1).min())

    return txn_df


# ──────────────────────────────────────────────────────────────────────────
# 3. Product Features (8)
# ──────────────────────────────────────────────────────────────────────────

def _product_features(products_df: pd.DataFrame) -> pd.DataFrame:
    """Add 8 product-level features. category_encoded via label encoding."""
    df = products_df.copy()
    df["margin_pct"] = np.where(
        df["unit_price"] > 0,
        (df["unit_price"] - df["unit_cost"]) / df["unit_price"],
        0.0,
    )
    # Label-encode category
    df["category_encoded"] = df["category"].astype("category").cat.codes
    # Ensure boolean cols are int
    df["is_seasonal"] = df["is_seasonal"].astype(int)
    df["is_perishable"] = df["is_perishable"].astype(int)

    return df[
        [
            "product_id", "unit_cost", "unit_price", "margin_pct",
            "weight", "shelf_life_days", "is_seasonal", "is_perishable",
            "category_encoded",
        ]
    ]


# ──────────────────────────────────────────────────────────────────────────
# 4. Store Features (5)
# ──────────────────────────────────────────────────────────────────────────

def _store_features(
    stores_df: pd.DataFrame,
    txn_agg_df: pd.DataFrame,
    inv_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute 5 store-level features:
      store_avg_daily_sales, store_product_count,
      store_inventory_turnover, lat, lon
    """
    store_sales = (
        txn_agg_df.groupby("store_id")["quantity"]
        .mean()
        .rename("store_avg_daily_sales")
    )
    store_product_count = (
        txn_agg_df.groupby("store_id")["product_id"]
        .nunique()
        .rename("store_product_count")
    )

    # Inventory turnover = sales / avg inventory
    inv_avg = inv_df.groupby("store_id")["quantity_on_hand"].mean().rename("avg_inv")
    store_turnover = (store_sales / inv_avg.clip(lower=1)).rename("store_inventory_turnover")

    result = stores_df[["store_id", "lat", "lon"]].copy()
    result = result.merge(store_sales, on="store_id", how="left")
    result = result.merge(store_product_count, on="store_id", how="left")
    result = result.merge(store_turnover, on="store_id", how="left")
    return result.fillna(0)


# ──────────────────────────────────────────────────────────────────────────
# 5. Inventory Features (5)
# ──────────────────────────────────────────────────────────────────────────

def _inventory_features(
    inv_df: pd.DataFrame,
    txn_agg_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute 5 inventory features per store-product:
      current_stock, days_of_supply, stock_velocity,
      quantity_on_order, stockout_count_30d
    """
    # Latest inventory per store-product
    latest = (
        inv_df.sort_values("timestamp")
        .groupby(["store_id", "product_id"])
        .last()
        .reset_index()
    )

    # Average daily sales for days_of_supply
    avg_sales = (
        txn_agg_df.groupby(["store_id", "product_id"])["quantity"]
        .mean()
        .rename("avg_daily")
        .reset_index()
    )

    result = latest[["store_id", "product_id", "quantity_on_hand", "quantity_on_order"]].copy()
    result = result.rename(columns={"quantity_on_hand": "current_stock"})
    result = result.merge(avg_sales, on=["store_id", "product_id"], how="left")
    result["avg_daily"] = result["avg_daily"].clip(lower=0.01)
    result["days_of_supply"] = (result["current_stock"] / result["avg_daily"]).round(1)

    # Velocity: 7-day trend
    result["stock_velocity"] = 0.0  # Simplified — full calc uses time-series

    # Stockout count in last 30 days
    thirty_days_ago = inv_df["timestamp"].max() - timedelta(days=30)
    stockouts = (
        inv_df[inv_df["timestamp"] >= thirty_days_ago]
        .groupby(["store_id", "product_id"])
        .apply(lambda g: (g["quantity_on_hand"] == 0).sum())
        .rename("stockout_count_30d")
        .reset_index()
    )
    result = result.merge(stockouts, on=["store_id", "product_id"], how="left")
    result["stockout_count_30d"] = result["stockout_count_30d"].fillna(0).astype(int)

    return result.drop(columns=["avg_daily"])


# ──────────────────────────────────────────────────────────────────────────
# 6. Promotion Features (3)
# ──────────────────────────────────────────────────────────────────────────

def _promotion_features(
    promotions_df: pd.DataFrame | None,
    target_date: str,
) -> pd.DataFrame:
    """
    Compute 3 promotion features:
      is_promotion_active, promotion_discount_pct, promotion_days_remaining
    """
    if promotions_df is None or promotions_df.empty:
        return pd.DataFrame(columns=[
            "store_id", "product_id",
            "is_promotion_active", "promotion_discount_pct", "promotion_days_remaining",
        ])

    dt = pd.Timestamp(target_date)
    active = promotions_df[
        (promotions_df["start_date"] <= dt) & (promotions_df["end_date"] >= dt)
    ].copy()

    active["is_promotion_active"] = 1
    active["promotion_discount_pct"] = active["discount_pct"]
    active["promotion_days_remaining"] = (
        pd.to_datetime(active["end_date"]) - dt
    ).dt.days

    return active[
        ["store_id", "product_id", "is_promotion_active",
         "promotion_discount_pct", "promotion_days_remaining"]
    ]


# ──────────────────────────────────────────────────────────────────────────
# Master Pipeline
# ──────────────────────────────────────────────────────────────────────────

def create_features(
    transactions_df: pd.DataFrame,
    inventory_df: pd.DataFrame | None = None,
    products_df: pd.DataFrame | None = None,
    stores_df: pd.DataFrame | None = None,
    promotions_df: pd.DataFrame | None = None,
    weather_df: pd.DataFrame | None = None,
    macro_df: pd.DataFrame | None = None,
    target_date: str | None = None,
    force_tier: FeatureTier | None = None,
) -> pd.DataFrame:
    """
    Create features for demand forecasting.

    Auto-detects feature tier based on available data:
      - cold_start (27 features): Only needs transactions + optional weather/macro
      - production (45 features): Needs inventory, products, stores too

    Args:
        transactions_df: Daily-aggregated transactions (store_id, product_id, date, quantity)
        inventory_df: Inventory snapshots (production tier)
        products_df: Product catalog (production tier)
        stores_df: Store information (production tier)
        promotions_df: Active promotions (optional)
        weather_df: Weather data (optional) — temperature, precipitation
        macro_df: Macro data (optional) — oil_price (e.g., from Favorita)
        target_date: Reference date for promo features
        force_tier: Override auto-detection ("cold_start" or "production")

    Returns:
        DataFrame with engineered features + _feature_tier attribute
    """
    if target_date is None:
        target_date = transactions_df["date"].max()

    # ── Phase-independent features (both tiers) ─────────────────────

    # 1. Temporal (10)
    features = _temporal_features(transactions_df, "date")

    # 2. Sales History (12)
    features = _sales_history_features(features)

    # Category encoding (cold-start compatible)
    if "category" in features.columns:
        features["category_encoded"] = features["category"].astype("category").cat.codes
    elif products_df is not None and "category" in products_df.columns:
        cat_map = products_df[["product_id", "category"]].drop_duplicates()
        features = features.merge(cat_map, on="product_id", how="left")
        features["category_encoded"] = features["category"].astype("category").cat.codes
    else:
        features["category_encoded"] = 0

    # Basic promotion flag (cold-start: binary only)
    if "is_promotional" in transactions_df.columns:
        features["is_promotion_active"] = transactions_df["is_promotional"].astype(int)
    elif promotions_df is not None and not promotions_df.empty:
        promo_feats = _promotion_features(promotions_df, str(target_date))
        if not promo_feats.empty:
            features = features.merge(
                promo_feats[["store_id", "product_id", "is_promotion_active"]],
                on=["store_id", "product_id"], how="left",
            )
        features["is_promotion_active"] = features.get("is_promotion_active", 0).fillna(0).astype(int)
    else:
        features["is_promotion_active"] = 0

    # External — weather
    if weather_df is not None and not weather_df.empty:
        weather_cols = ["date", "store_id"]
        if "temperature" in weather_df.columns:
            weather_cols.append("temperature")
        if "precipitation" in weather_df.columns:
            weather_cols.append("precipitation")
        features = features.merge(
            weather_df[weather_cols], on=["date", "store_id"], how="left",
        )
    if "temperature" not in features.columns:
        features["temperature"] = np.nan
    if "precipitation" not in features.columns:
        features["precipitation"] = np.nan

    # External — macro (oil price from Favorita, etc.)
    if macro_df is not None and not macro_df.empty and "oil_price" in macro_df.columns:
        features = features.merge(
            macro_df[["date", "oil_price"]], on="date", how="left",
        )
    if "oil_price" not in features.columns:
        features["oil_price"] = np.nan

    # ── Determine tier ──────────────────────────────────────────────

    has_production_data = (
        inventory_df is not None and not inventory_df.empty
        and products_df is not None and not products_df.empty
        and stores_df is not None and not stores_df.empty
    )
    tier = force_tier or ("production" if has_production_data else "cold_start")

    # ── Production-only features (Phase 2) ──────────────────────────

    if tier == "production" and has_production_data:
        # 3. Product (7 additional)
        prod_feats = _product_features(products_df)
        features = features.merge(prod_feats, on="product_id", how="left")

        # 4. Store (5)
        store_feats = _store_features(stores_df, transactions_df, inventory_df)
        features = features.merge(store_feats, on="store_id", how="left")

        # 5. Inventory (5)
        inv_feats = _inventory_features(inventory_df, transactions_df)
        features = features.merge(inv_feats, on=["store_id", "product_id"], how="left")

        # 6. Extended promotions (2 more)
        if promotions_df is not None and not promotions_df.empty:
            promo_feats = _promotion_features(promotions_df, str(target_date))
            if not promo_feats.empty:
                features = features.merge(
                    promo_feats[["store_id", "product_id",
                                 "promotion_discount_pct", "promotion_days_remaining"]],
                    on=["store_id", "product_id"], how="left",
                )
        if "promotion_discount_pct" not in features.columns:
            features["promotion_discount_pct"] = 0.0
        if "promotion_days_remaining" not in features.columns:
            features["promotion_days_remaining"] = 0

    # ── Fill NaN and tag ────────────────────────────────────────────

    feature_cols = get_feature_cols(tier)
    # Ensure all expected columns exist (fill missing with 0)
    for col in feature_cols:
        if col not in features.columns:
            features[col] = 0

    features = features.fillna(0)
    features.attrs["feature_tier"] = tier

    return features
