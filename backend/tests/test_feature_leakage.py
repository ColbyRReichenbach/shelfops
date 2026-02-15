import pandas as pd

from ml.features import create_features


def test_sales_history_features_are_lagged_by_one_step():
    transactions = pd.DataFrame(
        [
            {"date": "2026-01-01", "store_id": "S1", "product_id": "P1", "quantity": 10, "category": "A"},
            {"date": "2026-01-02", "store_id": "S1", "product_id": "P1", "quantity": 20, "category": "A"},
            {"date": "2026-01-03", "store_id": "S1", "product_id": "P1", "quantity": 30, "category": "A"},
        ]
    )
    transactions["date"] = pd.to_datetime(transactions["date"])

    features = create_features(transactions, force_tier="cold_start").sort_values("date").reset_index(drop=True)

    assert features.loc[0, "sales_7d"] == 0
    assert features.loc[1, "sales_7d"] == 10
    assert features.loc[2, "sales_7d"] == 30
    assert features.loc[2, "sales_7d"] != 60


def test_sales_history_lag_is_group_local():
    transactions = pd.DataFrame(
        [
            {"date": "2026-01-01", "store_id": "S1", "product_id": "P1", "quantity": 10, "category": "A"},
            {"date": "2026-01-01", "store_id": "S2", "product_id": "P1", "quantity": 7, "category": "A"},
            {"date": "2026-01-02", "store_id": "S1", "product_id": "P1", "quantity": 5, "category": "A"},
            {"date": "2026-01-02", "store_id": "S2", "product_id": "P1", "quantity": 9, "category": "A"},
        ]
    )
    transactions["date"] = pd.to_datetime(transactions["date"])

    features = create_features(transactions, force_tier="cold_start")
    by_key = features.set_index(["store_id", "date"])["sales_7d"]

    assert by_key[("S1", pd.Timestamp("2026-01-01"))] == 0
    assert by_key[("S1", pd.Timestamp("2026-01-02"))] == 10
    assert by_key[("S2", pd.Timestamp("2026-01-01"))] == 0
    assert by_key[("S2", pd.Timestamp("2026-01-02"))] == 7
