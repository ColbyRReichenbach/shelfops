from __future__ import annotations

from datetime import date

import pandas as pd

from ml.replay_partition import build_time_partition


def test_build_time_partition_strict_boundary():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "store_id": ["s1"] * 10,
            "product_id": ["p1"] * 10,
            "quantity": list(range(10)),
        }
    )

    partition = build_time_partition(df, holdout_days=3, dataset_id="test")
    train_df = partition["train_df"]
    holdout_df = partition["holdout_df"]
    meta = partition["metadata"]

    assert not train_df.empty
    assert not holdout_df.empty

    train_end = date.fromisoformat(meta["train_end_date"])
    holdout_start = date.fromisoformat(meta["holdout_start_date"])

    assert pd.to_datetime(train_df["date"]).dt.date.max() <= train_end
    assert pd.to_datetime(holdout_df["date"]).dt.date.min() == holdout_start
    assert holdout_start > train_end


def test_build_time_partition_with_explicit_cutoff():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=6, freq="D"),
            "store_id": ["s1"] * 6,
            "product_id": ["p1"] * 6,
            "quantity": [1, 2, 3, 4, 5, 6],
        }
    )

    partition = build_time_partition(df, holdout_days=0, train_end_date="2024-01-04", dataset_id="test")
    train_df = partition["train_df"]
    holdout_df = partition["holdout_df"]

    assert pd.to_datetime(train_df["date"]).dt.date.max().isoformat() == "2024-01-04"
    assert pd.to_datetime(holdout_df["date"]).dt.date.min().isoformat() == "2024-01-05"
