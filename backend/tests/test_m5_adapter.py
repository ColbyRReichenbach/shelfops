from pathlib import Path

import pandas as pd

from data_sources.m5 import canonicalize_m5, filter_m5_sell_prices, subset_m5_series
from ml.data_contracts import load_canonical_transactions


def test_canonicalize_m5_emits_calendar_and_price_fields():
    calendar = pd.DataFrame(
        [
            {
                "date": "2011-01-29",
                "wm_yr_wk": 11101,
                "d": "d_1",
                "event_name_1": "SuperBowl",
                "event_type_1": "Sporting",
                "event_name_2": None,
                "event_type_2": None,
                "snap_CA": 0,
                "snap_TX": 1,
                "snap_WI": 0,
            }
        ]
    )
    sell_prices = pd.DataFrame([{"store_id": "CA_1", "item_id": "ITEM_1", "wm_yr_wk": 11101, "sell_price": 3.49}])
    sales = pd.DataFrame(
        [
            {
                "id": "ITEM_1_CA_1_validation",
                "item_id": "ITEM_1",
                "dept_id": "FOODS_1",
                "cat_id": "FOODS",
                "store_id": "CA_1",
                "state_id": "CA",
                "d_1": 8,
            }
        ]
    )

    out = canonicalize_m5(calendar, sell_prices, sales)
    assert out.loc[0, "store_id"] == "CA_1"
    assert out.loc[0, "product_id"] == "ITEM_1"
    assert out.loc[0, "quantity"] == 8
    assert out.loc[0, "price"] == 3.49
    assert out.loc[0, "dept_id"] == "FOODS_1"
    assert out.loc[0, "cat_id"] == "FOODS"
    assert out.loc[0, "state_id"] == "CA"
    assert out.loc[0, "event_name_1"] == "SuperBowl"
    assert out.loc[0, "dataset_id"] == "m5_walmart"


def test_load_canonical_transactions_supports_m5_directory(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "date": "2011-01-29",
                "wm_yr_wk": 11101,
                "d": "d_1",
                "event_name_1": "SuperBowl",
                "event_type_1": "Sporting",
                "event_name_2": None,
                "event_type_2": None,
                "snap_CA": 0,
                "snap_TX": 1,
                "snap_WI": 0,
            }
        ]
    ).to_csv(tmp_path / "calendar.csv", index=False)
    pd.DataFrame([{"store_id": "CA_1", "item_id": "ITEM_1", "wm_yr_wk": 11101, "sell_price": 3.49}]).to_csv(
        tmp_path / "sell_prices.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "id": "ITEM_1_CA_1_validation",
                "item_id": "ITEM_1",
                "dept_id": "FOODS_1",
                "cat_id": "FOODS",
                "store_id": "CA_1",
                "state_id": "CA",
                "d_1": 8,
            }
        ]
    ).to_csv(tmp_path / "sales_train_validation.csv", index=False)

    out = load_canonical_transactions(str(tmp_path))
    assert out["dataset_id"].iloc[0] == "m5_walmart"
    assert out["frequency"].iloc[0] == "daily"
    assert "price" in out.columns
    assert "event_name_1" in out.columns


def test_subset_m5_series_balances_store_category_groups():
    sales = pd.DataFrame(
        [
            {"id": "A1", "item_id": "ITEM_A1", "dept_id": "D1", "cat_id": "FOODS", "store_id": "CA_1", "state_id": "CA", "d_1": 1},
            {"id": "A2", "item_id": "ITEM_A2", "dept_id": "D1", "cat_id": "FOODS", "store_id": "CA_1", "state_id": "CA", "d_1": 2},
            {"id": "A3", "item_id": "ITEM_A3", "dept_id": "D1", "cat_id": "FOODS", "store_id": "CA_1", "state_id": "CA", "d_1": 3},
            {"id": "B1", "item_id": "ITEM_B1", "dept_id": "D2", "cat_id": "HOBBIES", "store_id": "CA_1", "state_id": "CA", "d_1": 4},
            {"id": "B2", "item_id": "ITEM_B2", "dept_id": "D2", "cat_id": "HOBBIES", "store_id": "CA_1", "state_id": "CA", "d_1": 5},
            {"id": "C1", "item_id": "ITEM_C1", "dept_id": "D1", "cat_id": "FOODS", "store_id": "TX_1", "state_id": "TX", "d_1": 6},
            {"id": "C2", "item_id": "ITEM_C2", "dept_id": "D1", "cat_id": "FOODS", "store_id": "TX_1", "state_id": "TX", "d_1": 7},
        ]
    )

    subset = subset_m5_series(sales, series_per_store_category=2, random_state=7)
    counts = (
        subset.groupby(["store_id", "cat_id"]).size().to_dict()
    )

    assert counts[("CA_1", "FOODS")] == 2
    assert counts[("CA_1", "HOBBIES")] == 2
    assert counts[("TX_1", "FOODS")] == 2
    assert len(subset) == 6


def test_filter_m5_sell_prices_matches_subset_series_keys():
    sales_subset = pd.DataFrame(
        [
            {"store_id": "CA_1", "item_id": "ITEM_1"},
            {"store_id": "TX_1", "item_id": "ITEM_9"},
        ]
    )
    sell_prices = pd.DataFrame(
        [
            {"store_id": "CA_1", "item_id": "ITEM_1", "wm_yr_wk": 11101, "sell_price": 3.49},
            {"store_id": "CA_1", "item_id": "ITEM_2", "wm_yr_wk": 11101, "sell_price": 1.25},
            {"store_id": "TX_1", "item_id": "ITEM_9", "wm_yr_wk": 11101, "sell_price": 9.99},
        ]
    )

    filtered = filter_m5_sell_prices(sell_prices, sales_subset)
    assert filtered[["store_id", "item_id"]].drop_duplicates().to_dict(orient="records") == [
        {"store_id": "CA_1", "item_id": "ITEM_1"},
        {"store_id": "TX_1", "item_id": "ITEM_9"},
    ]
