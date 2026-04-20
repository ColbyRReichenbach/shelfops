import numpy as np
import pandas as pd

from ml.features import COLD_START_FEATURE_COLS
from ml.predict import predict_demand


def _feature_frame(n: int = 4) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "store_id": ["S1"] * n,
            "product_id": ["P1"] * n,
            "date": pd.date_range("2026-01-01", periods=n),
        }
    )
    for col in COLD_START_FEATURE_COLS:
        df[col] = np.random.rand(n)
    return df


def test_predict_demand_returns_interval_metadata_for_heuristic_path():
    class MockModel:
        def predict(self, x):
            return np.full(len(x), 10.0)

    models = {
        "xgboost": MockModel(),
        "lstm": None,
        "metadata": {"weights": {"xgboost": 1.0, "lstm": 0.0}},
        "feature_cols": COLD_START_FEATURE_COLS,
    }
    result = predict_demand(_feature_frame(), models)
    assert "interval_method" in result.columns
    assert "calibration_status" in result.columns
    assert (result["interval_method"] == "heuristic_band").all()
    assert (result["calibration_status"] == "uncalibrated").all()


def test_predict_demand_uses_conformal_metadata_when_present():
    class MockModel:
        def predict(self, x):
            return np.full(len(x), 10.0)

    models = {
        "xgboost": MockModel(),
        "lstm": None,
        "metadata": {
            "weights": {"xgboost": 1.0, "lstm": 0.0},
            "interval_method": "split_conformal",
            "calibration_status": "calibrated",
            "interval_coverage": 0.9,
            "conformal_residual_quantile": 2.5,
        },
        "feature_cols": COLD_START_FEATURE_COLS,
    }
    result = predict_demand(_feature_frame(), models)
    assert (result["interval_method"] == "split_conformal").all()
    assert (result["calibration_status"] == "calibrated").all()
    assert (result["interval_coverage"] == 0.9).all()
