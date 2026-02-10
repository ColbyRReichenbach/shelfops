"""
ML Prediction — Ensemble inference with business rules.

Supports both cold_start (27-feature) and production (45-feature)
models, reading the tier from saved model metadata.

Agent: ml-engineer
Skill: ml-forecasting
Workflow: train-forecast-model.md
"""

import numpy as np
import pandas as pd
import joblib
import os
from typing import Any

from ml.train import TARGET_COL, MODEL_DIR, ENSEMBLE_WEIGHTS
from ml.features import FEATURE_COLS, get_feature_cols

# Confidence interval z-scores
Z_SCORES = {0.80: 1.28, 0.85: 1.44, 0.90: 1.645, 0.95: 1.96}


def load_models(version: str) -> dict[str, Any]:
    """Load trained models and tier metadata from disk."""
    version_dir = os.path.join(MODEL_DIR, version)

    metadata = joblib.load(os.path.join(version_dir, "metadata.joblib"))

    result = {
        "xgboost": joblib.load(os.path.join(version_dir, "xgboost.joblib")),
        "metadata": metadata,
        # Read tier info; fall back to production for legacy models
        "feature_tier": metadata.get("feature_tier", "production"),
        "feature_cols": metadata.get("feature_cols", FEATURE_COLS),
    }

    lstm_path = os.path.join(version_dir, "lstm.keras")
    if os.path.exists(lstm_path):
        try:
            import tensorflow as tf
            result["lstm"] = tf.keras.models.load_model(lstm_path)
        except ImportError:
            result["lstm"] = None
    else:
        result["lstm"] = None

    return result


def predict_demand(
    features_df: pd.DataFrame,
    models: dict[str, Any],
    confidence_level: float = 0.90,
) -> pd.DataFrame:
    """
    Generate demand forecast using LSTM + XGBoost ensemble.

    Args:
        features_df: Pre-processed features from create_features()
        models: Dict from load_models()
        confidence_level: For prediction intervals (default 90%)

    Returns:
        DataFrame with columns:
          store_id, product_id, date,
          forecasted_demand, lower_bound, upper_bound, confidence
    """
    # Use the feature set the model was trained on
    feature_cols = models.get("feature_cols", FEATURE_COLS)
    X = features_df[[c for c in feature_cols if c in features_df.columns]].fillna(0)

    # XGBoost prediction
    xgb_preds = models["xgboost"].predict(X)
    xgb_preds = np.maximum(xgb_preds, 0)

    # LSTM prediction (if available)
    if models.get("lstm") is not None:
        lstm_model = models["lstm"]
        X_norm = (X.values - lstm_model._norm_mean) / lstm_model._norm_std
        # For single-step prediction, use last sequence_length rows
        seq_len = models["metadata"].get("lstm_metrics", {}).get("sequence_length", 30)
        if len(X_norm) >= seq_len:
            X_seq = np.array([X_norm[-seq_len:]])
            lstm_pred = lstm_model.predict(X_seq, verbose=0).flatten()
            lstm_pred = np.maximum(lstm_pred, 0)
            # Broadcast last prediction
            lstm_preds = np.full(len(xgb_preds), lstm_pred[-1])
        else:
            lstm_preds = xgb_preds  # Fallback
    else:
        lstm_preds = xgb_preds  # XGBoost-only fallback

    # Weighted ensemble
    weights = models.get("metadata", {}).get("weights", ENSEMBLE_WEIGHTS)
    ensemble_preds = (
        weights.get("xgboost", 0.65) * xgb_preds
        + weights.get("lstm", 0.35) * lstm_preds
    )
    ensemble_preds = np.maximum(ensemble_preds, 0)

    # Prediction intervals using residual-based approach
    residual_std = np.std(xgb_preds - lstm_preds) if models.get("lstm") else np.std(xgb_preds) * 0.2
    z = Z_SCORES.get(confidence_level, 1.645)
    lower = np.maximum(ensemble_preds - z * residual_std, 0)
    upper = ensemble_preds + z * residual_std

    result = features_df[["store_id", "product_id", "date"]].copy()
    result["forecasted_demand"] = np.round(ensemble_preds, 1)
    result["lower_bound"] = np.round(lower, 1)
    result["upper_bound"] = np.round(upper, 1)
    result["confidence"] = confidence_level

    return result


def apply_business_rules(
    forecast_df: pd.DataFrame,
    products_df: pd.DataFrame,
    promotions_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Apply business rules to adjust ML forecasts.

    Rules (from workflow spec):
    1. New items (< 30 days history): Use category average
    2. Active promotions: Apply expected_lift multiplier
    3. Seasonal items: Apply seasonal factor
    4. Perishable items: Cap at shelf_life_days supply
    """
    df = forecast_df.copy()

    # Merge product info
    prod_info = products_df[
        ["product_id", "is_seasonal", "is_perishable", "shelf_life_days", "category"]
    ]
    df = df.merge(prod_info, on="product_id", how="left")

    # Rule 1: New items — boost confidence interval
    # (detected by very low forecast values where we don't have enough history)
    low_data_mask = df["forecasted_demand"] < 0.5
    if "category" in df.columns:
        cat_avg = df.groupby("category")["forecasted_demand"].transform("mean")
        df.loc[low_data_mask, "forecasted_demand"] = cat_avg[low_data_mask]
        df.loc[low_data_mask, "confidence"] = 0.5  # Lower confidence for new items

    # Rule 2: Active promotion lift
    if promotions_df is not None and not promotions_df.empty:
        active_promos = promotions_df[promotions_df["status"] == "active"][
            ["product_id", "store_id", "expected_lift"]
        ]
        if not active_promos.empty:
            df = df.merge(active_promos, on=["product_id", "store_id"], how="left")
            lift_mask = df["expected_lift"].notna()
            df.loc[lift_mask, "forecasted_demand"] *= df.loc[lift_mask, "expected_lift"]
            df.loc[lift_mask, "upper_bound"] *= df.loc[lift_mask, "expected_lift"]
            df = df.drop(columns=["expected_lift"])

    # Rule 3: Seasonal adjustment (simple: +20% for seasonal items in peak months)
    peak_months = {11, 12, 6, 7}  # Nov, Dec, Jun, Jul
    if "date" in df.columns:
        month = pd.to_datetime(df["date"]).dt.month
        seasonal_mask = (df["is_seasonal"] == True) & (month.isin(peak_months))
        df.loc[seasonal_mask, "forecasted_demand"] *= 1.2
        df.loc[seasonal_mask, "upper_bound"] *= 1.2

    # Rule 4: Perishable cap
    perishable_mask = (df["is_perishable"] == True) & (df["shelf_life_days"].notna())
    if perishable_mask.any():
        max_demand = df.loc[perishable_mask, "shelf_life_days"] * 0.8  # 80% of shelf life
        df.loc[perishable_mask, "forecasted_demand"] = df.loc[
            perishable_mask, "forecasted_demand"
        ].clip(upper=max_demand)

    # Clean up
    df = df.drop(columns=["is_seasonal", "is_perishable", "shelf_life_days", "category"], errors="ignore")

    return df
