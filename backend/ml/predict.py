"""
ML Prediction — Ensemble inference with business rules.

Supports both cold_start (27-feature) and production (45-feature)
models, reading the tier from saved model metadata.

Agent: ml-engineer
Skill: ml-forecasting
Workflow: train-forecast-model.md
"""

import os
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.features import FEATURE_COLS, get_feature_cols
from ml.train import MODEL_DIR, TARGET_COL

# Default ensemble weights
ENSEMBLE_WEIGHTS = {"xgboost": 0.65, "lstm": 0.35}

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

            result["lstm"] = tf.keras.models.load_model(lstm_path, compile=False)
        except ImportError:
            result["lstm"] = None
    else:
        result["lstm"] = None

    poisson_path = os.path.join(version_dir, "poisson.joblib")
    if os.path.exists(poisson_path):
        result["poisson"] = joblib.load(poisson_path)
    else:
        result["poisson"] = None

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
    
    # Segment SKUs loaded from training metadata (or default all to B)
    segments = models.get("metadata", {}).get("segments", {})
    if not segments:
        segments = {"A": [], "B": features_df["product_id"].unique().tolist(), "C": []}
    
    # Pre-allocate
    forecasted = np.zeros(len(features_df))
    lower_bound = np.zeros(len(features_df))
    upper_bound = np.zeros(len(features_df))
    z = Z_SCORES.get(confidence_level, 1.645)

    # 1. XGBoost prediction
    xgb_preds = models["xgboost"].predict(X)
    if xgb_preds.ndim == 2 and xgb_preds.shape[1] == 3:
        xgb_lower, xgb_mid, xgb_upper = np.maximum(xgb_preds[:, 0], 0), np.maximum(xgb_preds[:, 1], 0), np.maximum(xgb_preds[:, 2], 0)
    else:
        xgb_mid = np.maximum(xgb_preds, 0)
        residual_std = np.std(xgb_mid) * 0.2
        xgb_lower = np.maximum(xgb_mid - z * residual_std, 0)
        xgb_upper = xgb_mid + z * residual_std

    # 2. LSTM prediction
    lstm_valid = False
    if models.get("lstm") is not None:
        lstm_model = models["lstm"]
        X_norm = (X.values - lstm_model._norm_mean) / lstm_model._norm_std
        seq_len = models["metadata"].get("lstm_metrics", {}).get("sequence_length", 30)
        if len(X_norm) >= seq_len:
            lstm_valid = True
            X_seq = np.array([X_norm[-seq_len:]])
            lstm_pred = lstm_model.predict(X_seq, verbose=0)
            if lstm_pred.ndim == 2 and lstm_pred.shape[1] == 3:
                lstm_lower = np.full(len(xgb_mid), np.maximum(lstm_pred[0, 0], 0))
                lstm_mid = np.full(len(xgb_mid), np.maximum(lstm_pred[0, 1], 0))
                lstm_upper = np.full(len(xgb_mid), np.maximum(lstm_pred[0, 2], 0))
            else:
                lstm_pred = lstm_pred.flatten()
                lstm_mid = np.full(len(xgb_mid), np.maximum(lstm_pred[-1], 0))
                lstm_lower = np.maximum(lstm_mid - z * np.std(xgb_mid - lstm_mid), 0)
                lstm_upper = lstm_mid + z * np.std(xgb_mid - lstm_mid)

    # 3. Poisson prediction
    poisson_valid = False
    if models.get("poisson") is not None:
        poisson_preds = models["poisson"].predict(X)
        poisson_mid = np.maximum(poisson_preds, 0)
        poisson_lower = np.maximum(poisson_mid - z * np.sqrt(poisson_mid), 0)
        poisson_upper = poisson_mid + z * np.sqrt(poisson_mid)
        poisson_valid = True

    # Build Segment masks
    a_mask = features_df["product_id"].isin(segments.get("A", []))
    b_mask = features_df["product_id"].isin(segments.get("B", []))
    c_mask = features_df["product_id"].isin(segments.get("C", []))
    default_mask = ~(a_mask | b_mask | c_mask)

    # Apply Router Logic
    
    # C-Items -> Poisson (fallback to XGBoost)
    if poisson_valid:
        forecasted = np.where(c_mask, poisson_mid, forecasted)
        lower_bound = np.where(c_mask, poisson_lower, lower_bound)
        upper_bound = np.where(c_mask, poisson_upper, upper_bound)
    else:
        forecasted = np.where(c_mask, xgb_mid, forecasted)
        lower_bound = np.where(c_mask, xgb_lower, lower_bound)
        upper_bound = np.where(c_mask, xgb_upper, upper_bound)

    # B-Items & defaults -> XGBoost
    forecasted = np.where(b_mask | default_mask, xgb_mid, forecasted)
    lower_bound = np.where(b_mask | default_mask, xgb_lower, lower_bound)
    upper_bound = np.where(b_mask | default_mask, xgb_upper, upper_bound)

    # A-Items -> LSTM ensemble (fallback to XGBoost)
    if lstm_valid:
        weights = models.get("metadata", {}).get("weights", ENSEMBLE_WEIGHTS)
        w_xgb = weights.get("xgboost", 0.65)
        w_lstm = weights.get("lstm", 0.35)
        
        forecasted = np.where(a_mask, w_xgb * xgb_mid + w_lstm * lstm_mid, forecasted)
        lower_bound = np.where(a_mask, w_xgb * xgb_lower + w_lstm * lstm_lower, lower_bound)
        upper_bound = np.where(a_mask, w_xgb * xgb_upper + w_lstm * lstm_upper, upper_bound)
    else:
        forecasted = np.where(a_mask, xgb_mid, forecasted)
        lower_bound = np.where(a_mask, xgb_lower, lower_bound)
        upper_bound = np.where(a_mask, xgb_upper, upper_bound)

    result = features_df[["store_id", "product_id", "date"]].copy()
    result["forecasted_demand"] = np.round(forecasted, 1)
    result["lower_bound"] = np.round(lower_bound, 1)
    result["upper_bound"] = np.round(upper_bound, 1)
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
    prod_info = products_df[["product_id", "is_seasonal", "is_perishable", "shelf_life_days", "category"]]
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
        active_promos = promotions_df[promotions_df["status"] == "active"][["product_id", "store_id", "expected_lift"]]
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
        seasonal_mask = df["is_seasonal"].astype(bool) & month.isin(peak_months)
        df.loc[seasonal_mask, "forecasted_demand"] *= 1.2
        df.loc[seasonal_mask, "upper_bound"] *= 1.2

    # Rule 4: Perishable cap
    perishable_mask = df["is_perishable"].astype(bool) & df["shelf_life_days"].notna()
    if perishable_mask.any():
        max_demand = df.loc[perishable_mask, "shelf_life_days"] * 0.8  # 80% of shelf life
        df.loc[perishable_mask, "forecasted_demand"] = df.loc[perishable_mask, "forecasted_demand"].clip(
            upper=max_demand
        )

    # Clean up
    df = df.drop(columns=["is_seasonal", "is_perishable", "shelf_life_days", "category"], errors="ignore")

    return df
