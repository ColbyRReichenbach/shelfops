import json

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


def test_save_models_writes_dataset_snapshot_metadata(monkeypatch, tmp_path):
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
    snapshot = {
        "snapshot_id": "dsnap_1234567890abcd",
        "dataset_id": "m5_walmart",
        "source_type": "benchmark",
        "row_count": 100,
        "store_count": 2,
        "product_count": 3,
        "date_min": "2026-01-01",
        "date_max": "2026-01-31",
        "content_hash": "a" * 64,
        "schema_version": "v1",
        "frequency": "daily",
        "forecast_grain": "store_product_daily",
        "geography": "US",
        "implementation_status": "benchmark_active",
        "claim_boundaries_ref": "data_registry/datasets.yaml",
    }

    save_models(
        ensemble_result=ensemble_result,
        version="vtest_snapshot",
        dataset_name="m5_walmart",
        rows_trained=100,
        dataset_snapshot=snapshot,
    )

    metadata = json.loads((tmp_path / "vtest_snapshot" / "metadata.json").read_text())
    assert metadata["dataset_snapshot_id"] == snapshot["snapshot_id"]
    assert metadata["dataset_snapshot"]["dataset_id"] == "m5_walmart"
    assert captured["metrics"]["dataset_snapshot_id"] == snapshot["snapshot_id"]


def test_save_models_writes_interval_metadata(monkeypatch, tmp_path):
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
            "interval_method": "split_conformal",
            "calibration_status": "calibrated",
            "interval_coverage": 0.91,
            "conformal_residual_quantile": 2.25,
        },
    }

    save_models(
        ensemble_result=ensemble_result,
        version="vtest_interval",
        dataset_name="m5_walmart",
        rows_trained=100,
    )

    metadata = json.loads((tmp_path / "vtest_interval" / "metadata.json").read_text())
    assert metadata["interval_method"] == "split_conformal"
    assert metadata["calibration_status"] == "calibrated"
    assert metadata["interval_coverage"] == 0.91
    assert metadata["conformal_residual_quantile"] == 2.25
    assert captured["metrics"]["interval_method"] == "split_conformal"
