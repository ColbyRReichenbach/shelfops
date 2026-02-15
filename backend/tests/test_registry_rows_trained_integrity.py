import numpy as np
import pandas as pd
import xgboost as xgb

from ml.train import save_models


def test_save_models_registers_true_rows_trained(monkeypatch, tmp_path):
    captured = {}

    def fake_register_model(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("ml.train.register_model", fake_register_model)
    monkeypatch.setattr("ml.train.MODEL_DIR", str(tmp_path))

    X = np.array([[0.0], [1.0], [2.0], [3.0]], dtype=float)
    y = np.array([0.0, 1.0, 2.0, 3.0], dtype=float)
    model = xgb.XGBRegressor(n_estimators=5, max_depth=2, random_state=42)
    model.fit(X, y, verbose=False)

    ensemble_result = {
        "xgboost": {"model": model, "metrics": {"mae": 1.0, "mape": 0.1}},
        "lstm": {"available": False, "metrics": {"mae": float("inf"), "mape": float("inf")}, "model": None},
        "ensemble": {
            "weights": {"xgboost": 1.0, "lstm": 0.0},
            "estimated_mae": 1.0,
            "feature_tier": "cold_start",
            "feature_cols": ["sales_7d"],
            "model_name": "demand_forecast",
        },
    }

    save_models(
        ensemble_result=ensemble_result,
        version="vtest",
        dataset_name="unit-test",
        rows_trained=123,
    )

    assert captured["rows_trained"] == 123
