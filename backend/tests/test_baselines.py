import pandas as pd

from ml.baselines import (
    category_store_average_forecast,
    intermittent_demand_forecast,
    moving_average_forecast,
    naive_forecast,
    prepare_series_frame,
    seasonal_naive_forecast,
)


def _sample_series() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.DataFrame(
        [
            {"date": "2026-01-01", "store_id": "S1", "product_id": "P1", "quantity": 1, "category": "A"},
            {"date": "2026-01-02", "store_id": "S1", "product_id": "P1", "quantity": 2, "category": "A"},
            {"date": "2026-01-03", "store_id": "S1", "product_id": "P1", "quantity": 0, "category": "A"},
            {"date": "2026-01-04", "store_id": "S1", "product_id": "P1", "quantity": 3, "category": "A"},
            {"date": "2026-01-05", "store_id": "S1", "product_id": "P1", "quantity": 4, "category": "A"},
            {"date": "2026-01-06", "store_id": "S1", "product_id": "P1", "quantity": 0, "category": "A"},
            {"date": "2026-01-07", "store_id": "S1", "product_id": "P1", "quantity": 5, "category": "A"},
            {"date": "2026-01-08", "store_id": "S1", "product_id": "P1", "quantity": 6, "category": "A"},
        ]
    )
    raw = prepare_series_frame(raw)
    return raw.iloc[:5].copy(), raw.iloc[5:].copy()


def test_baselines_emit_non_negative_predictions():
    train_df, test_df = _sample_series()
    preds = [
        naive_forecast(train_df, test_df),
        seasonal_naive_forecast(train_df, test_df),
        moving_average_forecast(train_df, test_df),
        category_store_average_forecast(train_df, test_df),
        intermittent_demand_forecast(train_df, test_df),
    ]
    for pred in preds:
        assert len(pred) == len(test_df)
        assert pred.notna().all()
        assert (pred >= 0).all()
