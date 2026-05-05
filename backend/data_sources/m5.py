from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd


def load_m5_tables(data_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    path = Path(data_dir)
    sales_path = None
    for candidate in ("sales_train_validation.csv", "sales_train_evaluation.csv"):
        if (path / candidate).exists():
            sales_path = path / candidate
            break
    if sales_path is None:
        raise FileNotFoundError("M5 sales file not found")

    calendar_df = pd.read_csv(path / "calendar.csv", low_memory=False)
    sell_prices_df = pd.read_csv(path / "sell_prices.csv", low_memory=False)
    sales_df = pd.read_csv(sales_path, low_memory=False)
    return calendar_df, sell_prices_df, sales_df, sales_path.name


def canonicalize_m5(
    calendar_df: pd.DataFrame,
    sell_prices_df: pd.DataFrame,
    sales_df: pd.DataFrame,
) -> pd.DataFrame:
    id_cols = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    day_cols = [col for col in sales_df.columns if col.startswith("d_")]
    if not day_cols:
        raise ValueError("M5 sales dataframe must include d_* demand columns")

    melted = sales_df.melt(
        id_vars=id_cols,
        value_vars=day_cols,
        var_name="d",
        value_name="quantity",
    )
    calendar = calendar_df.copy()
    calendar["date"] = pd.to_datetime(calendar["date"], errors="coerce")

    merged = melted.merge(calendar, on="d", how="left", validate="many_to_one")
    merged = merged.merge(
        sell_prices_df,
        on=["store_id", "item_id", "wm_yr_wk"],
        how="left",
        validate="many_to_one",
    )

    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = merged.dropna(subset=["date"]).copy()
    merged["quantity"] = pd.to_numeric(merged["quantity"], errors="coerce").fillna(0.0)
    merged["sell_price"] = pd.to_numeric(merged["sell_price"], errors="coerce")
    merged["is_holiday"] = (
        merged[["event_name_1", "event_name_2"]].notna().any(axis=1).astype(int)
        if {"event_name_1", "event_name_2"}.intersection(merged.columns)
        else 0
    )
    merged["is_promotional"] = 0
    merged["category"] = merged["cat_id"].astype(str)
    merged["product_id"] = merged["item_id"].astype(str)
    merged["dataset_id"] = "m5_walmart"
    merged["country_code"] = "US"
    merged["frequency"] = "daily"
    merged["product_grain"] = "sku_level"
    merged["returns_adjustment"] = 0.0
    merged["is_return_week"] = 0
    merged["price"] = merged["sell_price"]
    merged["units_sold"] = merged["quantity"]

    preferred = [
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
        "price",
        "units_sold",
        "id",
        "item_id",
        "dept_id",
        "cat_id",
        "state_id",
        "event_name_1",
        "event_type_1",
        "event_name_2",
        "event_type_2",
        "snap_CA",
        "snap_TX",
        "snap_WI",
        "wm_yr_wk",
    ]
    cols = [col for col in preferred if col in merged.columns] + [col for col in merged.columns if col not in preferred]
    return merged[cols].reset_index(drop=True)


def subset_m5_series(
    sales_df: pd.DataFrame,
    *,
    series_per_store_category: int,
    random_state: int = 42,
) -> pd.DataFrame:
    if series_per_store_category <= 0:
        raise ValueError("series_per_store_category must be > 0")

    required = {"store_id", "cat_id"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(f"M5 sales dataframe missing required columns for subsetting: {sorted(missing)}")

    sampled_groups: list[pd.DataFrame] = []
    grouped: Iterable[tuple[tuple[str, str], pd.DataFrame]] = sales_df.groupby(["store_id", "cat_id"], sort=True)
    for index, (_, group) in enumerate(grouped):
        take = min(series_per_store_category, len(group))
        if take >= len(group):
            sampled = group
        else:
            sampled = group.sample(n=take, random_state=random_state + index)
        sampled_groups.append(sampled)

    if not sampled_groups:
        return sales_df.iloc[0:0].copy()

    subset = pd.concat(sampled_groups, ignore_index=True)
    order_cols = [col for col in ["store_id", "cat_id", "dept_id", "item_id", "id"] if col in subset.columns]
    if order_cols:
        subset = subset.sort_values(order_cols, kind="mergesort").reset_index(drop=True)
    return subset


def filter_m5_sell_prices(sell_prices_df: pd.DataFrame, sales_subset_df: pd.DataFrame) -> pd.DataFrame:
    keys = sales_subset_df[["store_id", "item_id"]].drop_duplicates().copy()
    return (
        sell_prices_df.merge(keys, on=["store_id", "item_id"], how="inner", validate="many_to_one")
        .sort_values(["store_id", "item_id", "wm_yr_wk"], kind="mergesort")
        .reset_index(drop=True)
    )


def load_m5_directory(data_dir: str | Path) -> pd.DataFrame:
    calendar_df, sell_prices_df, sales_df, _ = load_m5_tables(data_dir)

    return canonicalize_m5(calendar_df=calendar_df, sell_prices_df=sell_prices_df, sales_df=sales_df)
