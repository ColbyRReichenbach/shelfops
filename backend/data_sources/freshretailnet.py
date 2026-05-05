from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ACTIVE_HOURS_START = 6
ACTIVE_HOURS_END = 22
ACTIVE_HOURS_COUNT = ACTIVE_HOURS_END - ACTIVE_HOURS_START + 1


def _to_json_sequence(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return json.dumps(value)
    if isinstance(value, tuple):
        return json.dumps(list(value))
    return "[]"


def canonicalize_freshretailnet(frame: pd.DataFrame, *, split_name: str) -> pd.DataFrame:
    work = frame.copy()
    work["date"] = pd.to_datetime(work["dt"], errors="coerce")
    work = work.dropna(subset=["date"]).copy()

    work["quantity"] = pd.to_numeric(work["sale_amount"], errors="coerce").fillna(0.0)
    work["store_id"] = work["store_id"].astype(str)
    work["product_id"] = work["product_id"].astype(str)
    work["category"] = work["third_category_id"].astype(str)
    work["is_promotional"] = (
        (pd.to_numeric(work.get("discount", 1.0), errors="coerce").fillna(1.0) < 0.999)
        | (pd.to_numeric(work.get("activity_flag", 0), errors="coerce").fillna(0).astype(int) > 0)
    ).astype(int)
    work["is_holiday"] = pd.to_numeric(work.get("holiday_flag", 0), errors="coerce").fillna(0).astype(int)
    work["dataset_id"] = "freshretailnet_50k"
    work["country_code"] = "CN"
    work["frequency"] = "daily"
    work["product_grain"] = "sku_level"
    work["returns_adjustment"] = 0.0
    work["is_return_week"] = 0
    work["split"] = split_name
    stockout_hours = pd.to_numeric(work.get("stock_hour6_22_cnt", 0), errors="coerce").fillna(0).astype(int)
    if "stock_hour6_22_cnt" in work.columns:
        work["is_stockout"] = (stockout_hours > 0).astype(int)
    else:
        status_json = work["hours_stock_status"].apply(_to_json_sequence)
        work["is_stockout"] = status_json.str.contains("1").astype(int)
    work["stockout_window"] = work["is_stockout"].astype(int)
    work["stockout_hours_6_22"] = stockout_hours
    work["stockout_fraction_6_22"] = work["stockout_hours_6_22"] / ACTIVE_HOURS_COUNT
    work["active_hours_6_22"] = ACTIVE_HOURS_COUNT - work["stockout_hours_6_22"]
    work["discount"] = pd.to_numeric(work.get("discount", 1.0), errors="coerce").fillna(1.0)
    work["holiday_flag"] = pd.to_numeric(work.get("holiday_flag", 0), errors="coerce").fillna(0).astype(int)
    work["activity_flag"] = pd.to_numeric(work.get("activity_flag", 0), errors="coerce").fillna(0).astype(int)
    work["precpt"] = pd.to_numeric(work.get("precpt", 0.0), errors="coerce").fillna(0.0)
    work["avg_temperature"] = pd.to_numeric(work.get("avg_temperature", 0.0), errors="coerce").fillna(0.0)
    work["avg_humidity"] = pd.to_numeric(work.get("avg_humidity", 0.0), errors="coerce").fillna(0.0)
    work["avg_wind_level"] = pd.to_numeric(work.get("avg_wind_level", 0.0), errors="coerce").fillna(0.0)
    work["city_id"] = work["city_id"].astype(str)
    work["management_group_id"] = work["management_group_id"].astype(str)
    work["first_category_id"] = work["first_category_id"].astype(str)
    work["second_category_id"] = work["second_category_id"].astype(str)
    work["third_category_id"] = work["third_category_id"].astype(str)
    work["hourly_sales_json"] = work["hours_sale"].apply(_to_json_sequence)
    work["hourly_stock_status_json"] = work["hours_stock_status"].apply(_to_json_sequence)
    work["is_perishable"] = 1

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
        "split",
        "is_stockout",
        "stockout_window",
        "stockout_hours_6_22",
        "stockout_fraction_6_22",
        "active_hours_6_22",
        "discount",
        "holiday_flag",
        "activity_flag",
        "precpt",
        "avg_temperature",
        "avg_humidity",
        "avg_wind_level",
        "is_perishable",
        "city_id",
        "management_group_id",
        "first_category_id",
        "second_category_id",
        "third_category_id",
        "hourly_sales_json",
        "hourly_stock_status_json",
    ]
    cols = [col for col in preferred if col in work.columns] + [col for col in work.columns if col not in preferred]
    return work[cols].reset_index(drop=True)


def load_freshretailnet_directory(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    path = Path(data_dir)
    train_path = path / "train.parquet"
    eval_path = path / "eval.parquet"
    if not train_path.exists() or not eval_path.exists():
        raise FileNotFoundError("FreshRetailNet directory must contain train.parquet and eval.parquet")

    train_df = pd.read_parquet(train_path)
    eval_df = pd.read_parquet(eval_path)
    return {
        "train": canonicalize_freshretailnet(train_df, split_name="train"),
        "eval": canonicalize_freshretailnet(eval_df, split_name="eval"),
    }
