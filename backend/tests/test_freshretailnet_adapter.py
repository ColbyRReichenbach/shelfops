from pathlib import Path

import pandas as pd

from data_sources.freshretailnet import canonicalize_freshretailnet, load_freshretailnet_directory
from ml.latent_demand import add_conservative_latent_demand


def _fixture_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "city_id": 1,
                "store_id": 101,
                "management_group_id": 10,
                "first_category_id": 100,
                "second_category_id": 110,
                "third_category_id": 111,
                "product_id": 999,
                "dt": "2024-03-30",
                "sale_amount": 12.0,
                "hours_sale": [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    1.0,
                    1.0,
                    1.2,
                    1.1,
                    1.0,
                    0.9,
                    0.8,
                    1.0,
                    1.1,
                    1.2,
                    1.0,
                    0.7,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
                "stock_hour6_22_cnt": 4,
                "hours_stock_status": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                "discount": 0.9,
                "holiday_flag": 1,
                "activity_flag": 1,
                "precpt": 3.2,
                "avg_temperature": 15.4,
                "avg_humidity": 78.0,
                "avg_wind_level": 2.1,
            },
            {
                "city_id": 1,
                "store_id": 101,
                "management_group_id": 10,
                "first_category_id": 100,
                "second_category_id": 110,
                "third_category_id": 111,
                "product_id": 999,
                "dt": "2024-03-31",
                "sale_amount": 18.0,
                "hours_sale": [0] * 24,
                "stock_hour6_22_cnt": 0,
                "hours_stock_status": [0] * 24,
                "discount": 1.0,
                "holiday_flag": 0,
                "activity_flag": 0,
                "precpt": 0.0,
                "avg_temperature": 16.0,
                "avg_humidity": 76.0,
                "avg_wind_level": 1.5,
            },
        ]
    )


def test_canonicalize_freshretailnet_preserves_stockout_and_weather_fields():
    out = canonicalize_freshretailnet(_fixture_frame(), split_name="train")
    assert out.loc[0, "dataset_id"] == "freshretailnet_50k"
    assert out.loc[0, "quantity"] == 12.0
    assert out.loc[0, "is_promotional"] == 1
    assert out.loc[0, "is_stockout"] == 1
    assert out.loc[0, "stockout_hours_6_22"] == 4
    assert out.loc[0, "precpt"] == 3.2
    assert out.loc[0, "split"] == "train"
    assert out.loc[0, "country_code"] == "CN"


def test_load_freshretailnet_directory_reads_train_and_eval_parquet(tmp_path: Path):
    train = _fixture_frame().iloc[:1].copy()
    eval_df = _fixture_frame().iloc[1:].copy()
    train.to_parquet(tmp_path / "train.parquet", index=False)
    eval_df.to_parquet(tmp_path / "eval.parquet", index=False)

    loaded = load_freshretailnet_directory(tmp_path)
    assert set(loaded.keys()) == {"train", "eval"}
    assert loaded["train"]["split"].iloc[0] == "train"
    assert loaded["eval"]["split"].iloc[0] == "eval"


def test_latent_demand_adds_conservative_recovery_only_for_stockout_rows():
    canonical = canonicalize_freshretailnet(_fixture_frame(), split_name="train")
    out = add_conservative_latent_demand(canonical)
    assert "latent_demand_quantity" in out.columns
    assert out.loc[0, "latent_demand_quantity"] >= out.loc[0, "quantity"]
    assert out.loc[1, "latent_demand_quantity"] == out.loc[1, "quantity"]
