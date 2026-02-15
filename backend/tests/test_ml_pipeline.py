"""
Unit Tests — ML pipeline (feature engineering, validation, prediction).
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest


class TestFeatureTierDetection:
    """Test auto-detection of cold_start vs production feature tier."""

    def test_cold_start_detected_when_no_production_cols(self):
        from ml.features import detect_feature_tier

        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=10),
                "store_id": "S1",
                "product_id": "P1",
                "quantity": range(10),
            }
        )
        assert detect_feature_tier(df) == "cold_start"

    def test_production_detected_with_all_signals(self):
        from ml.features import detect_feature_tier

        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=10),
                "store_id": "S1",
                "product_id": "P1",
                "quantity": range(10),
                "current_stock": [50] * 10,
                "unit_cost": [3.0] * 10,
                "unit_price": [5.0] * 10,
                "store_inventory_turnover": [1.5] * 10,
                "days_of_supply": [14] * 10,
            }
        )
        assert detect_feature_tier(df) == "production"

    def test_cold_start_when_production_cols_all_zero(self):
        from ml.features import detect_feature_tier

        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=10),
                "store_id": "S1",
                "product_id": "P1",
                "quantity": range(10),
                "current_stock": [0] * 10,
                "unit_cost": [0] * 10,
                "unit_price": [0] * 10,
                "store_inventory_turnover": [0] * 10,
                "days_of_supply": [0] * 10,
            }
        )
        assert detect_feature_tier(df) == "cold_start"


class TestGetFeatureCols:
    """Test feature column list retrieval."""

    def test_cold_start_has_27_features(self):
        from ml.features import get_feature_cols

        cols = get_feature_cols("cold_start")
        assert len(cols) == 27

    def test_production_has_46_features(self):
        from ml.features import get_feature_cols

        cols = get_feature_cols("production")
        assert len(cols) == 46

    def test_production_superset_of_cold_start(self):
        from ml.features import get_feature_cols

        cold = set(get_feature_cols("cold_start"))
        prod = set(get_feature_cols("production"))
        assert cold.issubset(prod)

    def test_returns_copy_not_reference(self):
        from ml.features import get_feature_cols

        cols1 = get_feature_cols("cold_start")
        cols2 = get_feature_cols("cold_start")
        cols1.append("extra")
        assert "extra" not in cols2


class TestTemporalFeatures:
    """Test temporal feature extraction."""

    def test_temporal_features_basic(self):
        from ml.features import _temporal_features

        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-06-15", periods=7),
                "quantity": [10] * 7,
            }
        )
        result = _temporal_features(df)
        assert "day_of_week" in result.columns
        assert "month" in result.columns
        assert "is_weekend" in result.columns
        assert "is_holiday" in result.columns
        assert "week_of_year" in result.columns
        assert len(result) == 7

    def test_weekend_detection(self):
        from ml.features import _temporal_features

        # 2025-06-14 is Saturday, 2025-06-16 is Monday
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-06-14", "2025-06-15", "2025-06-16"]),
                "quantity": [1, 2, 3],
            }
        )
        result = _temporal_features(df)
        assert result["is_weekend"].tolist() == [1, 1, 0]


class TestSalesHistoryFeatures:
    """Test rolling sales features computation."""

    def test_sales_rolling_features_exist(self):
        from ml.features import _sales_history_features

        dates = pd.date_range("2025-01-01", periods=40)
        df = pd.DataFrame(
            {
                "store_id": ["S1"] * 40,
                "product_id": ["P1"] * 40,
                "date": dates,
                "quantity": np.random.randint(5, 20, 40).astype(float),
            }
        )
        result = _sales_history_features(df)
        expected_cols = ["sales_7d", "sales_14d", "sales_30d", "avg_daily_sales_7d"]
        for col in expected_cols:
            assert col in result.columns


class TestValidation:
    """Test Pandera validation schemas."""

    def test_valid_training_data_passes(self):
        from ml.validate import validate_training_data

        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=5),
                "store_id": ["S1"] * 5,
                "product_id": ["P1"] * 5,
                "quantity": [10.0, 15.0, 12.0, 18.0, 20.0],
            }
        )
        result = validate_training_data(df)
        assert len(result) == 5

    def test_negative_quantity_fails(self):
        import pandera

        from ml.validate import validate_training_data

        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=3),
                "store_id": ["S1"] * 3,
                "product_id": ["P1"] * 3,
                "quantity": [10.0, -5.0, 12.0],
            }
        )
        with pytest.raises(pandera.errors.SchemaErrors):
            validate_training_data(df)

    def test_missing_required_column_fails(self):
        import pandera

        from ml.validate import validate_training_data

        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=3),
                "store_id": ["S1"] * 3,
                # missing product_id and quantity
            }
        )
        with pytest.raises(pandera.errors.SchemaErrors):
            validate_training_data(df)

    def test_prediction_input_validation(self):
        from ml.validate import validate_prediction_input

        df = pd.DataFrame(
            {
                "store_id": ["S1", "S2"],
                "product_id": ["P1", "P2"],
                "date": pd.date_range("2025-01-01", periods=2),
            }
        )
        result = validate_prediction_input(df)
        assert len(result) == 2

    def test_features_validation_cold_start(self):
        from ml.features import COLD_START_FEATURE_COLS
        from ml.validate import validate_features

        data = {col: [1.0, 2.0, 3.0] for col in COLD_START_FEATURE_COLS}
        data["quantity"] = [10.0, 15.0, 20.0]
        df = pd.DataFrame(data)
        result = validate_features(df, tier="cold_start")
        assert len(result) == 3


class TestPredictDemand:
    """Test prediction function with mock models."""

    def test_predict_demand_xgb_only(self):
        from ml.features import COLD_START_FEATURE_COLS
        from ml.predict import predict_demand

        n = 10
        features_df = pd.DataFrame(
            {
                "store_id": ["S1"] * n,
                "product_id": ["P1"] * n,
                "date": pd.date_range("2025-01-01", periods=n),
            }
        )
        for col in COLD_START_FEATURE_COLS:
            features_df[col] = np.random.rand(n)

        # Mock XGBoost model
        class MockXGB:
            def predict(self, X):
                return np.full(len(X), 15.0)

        models = {
            "xgboost": MockXGB(),
            "lstm": None,
            "metadata": {"feature_tier": "cold_start", "weights": {"xgboost": 1.0, "lstm": 0.0}},
            "feature_cols": COLD_START_FEATURE_COLS,
        }

        result = predict_demand(features_df, models, confidence_level=0.90)
        assert "forecasted_demand" in result.columns
        assert "lower_bound" in result.columns
        assert "upper_bound" in result.columns
        assert len(result) == n
        assert (result["forecasted_demand"] >= 0).all()
        assert (result["lower_bound"] <= result["forecasted_demand"]).all()
        assert (result["upper_bound"] >= result["forecasted_demand"]).all()

    def test_predict_demand_non_negative(self):
        from ml.features import COLD_START_FEATURE_COLS
        from ml.predict import predict_demand

        n = 5
        features_df = pd.DataFrame(
            {
                "store_id": ["S1"] * n,
                "product_id": ["P1"] * n,
                "date": pd.date_range("2025-01-01", periods=n),
            }
        )
        for col in COLD_START_FEATURE_COLS:
            features_df[col] = np.random.rand(n)

        class MockXGB:
            def predict(self, X):
                return np.array([-5.0, 0.0, 3.0, -1.0, 10.0])

        models = {
            "xgboost": MockXGB(),
            "lstm": None,
            "metadata": {"weights": {"xgboost": 1.0, "lstm": 0.0}},
            "feature_cols": COLD_START_FEATURE_COLS,
        }

        result = predict_demand(features_df, models)
        assert (result["forecasted_demand"] >= 0).all()
        assert (result["lower_bound"] >= 0).all()

    def test_predict_demand_lstm_missing_norm_stats_falls_back(self):
        from ml.features import COLD_START_FEATURE_COLS
        from ml.predict import predict_demand

        n = 4
        features_df = pd.DataFrame(
            {
                "store_id": ["S1"] * n,
                "product_id": ["P1"] * n,
                "date": pd.date_range("2025-01-01", periods=n),
            }
        )
        for col in COLD_START_FEATURE_COLS:
            features_df[col] = np.random.rand(n)

        class MockXGB:
            def predict(self, X):
                return np.array([4.0, 5.0, 6.0, 7.0])

        class MockLSTM:
            # Intentionally missing _norm_mean/_norm_std to force fallback path.
            def predict(self, X, verbose=0):
                return np.array([999.0])

        models = {
            "xgboost": MockXGB(),
            "lstm": MockLSTM(),
            "metadata": {
                "weights": {"xgboost": 0.65, "lstm": 0.35},
                "lstm_metrics": {"sequence_length": 2},
            },
            "feature_cols": COLD_START_FEATURE_COLS,
        }

        result = predict_demand(features_df, models)
        assert result["forecasted_demand"].tolist() == [4.0, 5.0, 6.0, 7.0]


class TestApplyBusinessRules:
    """Test post-prediction business rule adjustments."""

    def test_perishable_cap(self):
        from ml.predict import apply_business_rules

        forecast_df = pd.DataFrame(
            {
                "product_id": ["P1"],
                "store_id": ["S1"],
                "date": ["2025-01-15"],
                "forecasted_demand": [100.0],
                "lower_bound": [80.0],
                "upper_bound": [120.0],
                "confidence": [0.9],
            }
        )
        products_df = pd.DataFrame(
            {
                "product_id": ["P1"],
                "is_seasonal": [False],
                "is_perishable": [True],
                "shelf_life_days": [5],
                "category": ["Dairy"],
            }
        )
        result = apply_business_rules(forecast_df, products_df)
        # 5 days * 0.8 = 4.0 cap
        assert result["forecasted_demand"].iloc[0] <= 4.0
