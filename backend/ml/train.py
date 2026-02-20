"""
ML Training Pipeline — XGBoost Baseline + LSTM + Ensemble.

Agent: ml-engineer
Skill: ml-forecasting
Workflow: train-forecast-model.md

Performance Targets (from workflow):
  - MAE < 15 units
  - MAPE < 20%
  - Coverage (90% PI) >= 85%

Standards Integration:
  - MLflow experiment tracking (ml/experiment.py)
  - SHAP explainability (ml/explain.py)
  - Pandera validation (ml/validate.py)
  - Plotly charts (ml/charts.py)
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

import joblib
import numpy as np
import pandas as pd
import structlog
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
from sklearn.model_selection import TimeSeriesSplit

from ml.experiment import ExperimentTracker, register_model
from ml.features import (
    COLD_START_FEATURE_COLS,
    FEATURE_COLS,  # legacy alias = PRODUCTION_FEATURE_COLS
    PRODUCTION_FEATURE_COLS,
    FeatureTier,
    detect_feature_tier,
    get_feature_cols,
)
from ml.validate import validate_features

logger = structlog.get_logger()

TARGET_COL = "quantity"
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


# ──────────────────────────────────────────────────────────────────────────
# Utilities & Wrappers
# ──────────────────────────────────────────────────────────────────────────

class QuantileXGBoost:
    """Wrapper for multi-quantile XGBoost predictions (P10, P50, P90)."""
    def __init__(self, p10_model, p50_model, p90_model):
        self.p10 = p10_model
        self.p50 = p50_model
        self.p90 = p90_model

    def predict(self, X):
        return np.column_stack([
            np.maximum(self.p10.predict(X), 0),
            np.maximum(self.p50.predict(X), 0),
            np.maximum(self.p90.predict(X), 0)
        ])

def segment_skus(features_df: pd.DataFrame, target_col: str = TARGET_COL) -> dict[str, list[str]]:
    """Segment SKUs into A (Fast), B (Steady), C (Slow) based on cumulative sales volume."""
    if "product_id" not in features_df.columns:
        return {"A": [], "B": [], "C": []}
    
    sku_sales = features_df.groupby("product_id")[target_col].sum().sort_values(ascending=False)
    if sku_sales.empty or sku_sales.sum() == 0:
        return {"A": list(sku_sales.index), "B": [], "C": []}
        
    cum_sales = sku_sales.cumsum() / sku_sales.sum()
    
    a_items = cum_sales[cum_sales <= 0.7].index.tolist()
    b_items = cum_sales[(cum_sales > 0.7) & (cum_sales <= 0.9)].index.tolist()
    c_items = cum_sales[cum_sales > 0.9].index.tolist()
    
    return {"A": a_items, "B": b_items, "C": c_items}


# ──────────────────────────────────────────────────────────────────────────
# XGBoost
# ──────────────────────────────────────────────────────────────────────────


def train_xgboost(
    features_df: pd.DataFrame,
    target_col: str = TARGET_COL,
    params: dict[str, Any] | None = None,
    feature_cols: list[str] | None = None,
) -> tuple[xgb.XGBRegressor, dict[str, Any], dict[str, Any]]:
    """
    Train XGBoost baseline model with time-series cross-validation.

    Args:
        feature_cols: Override feature list. If None, auto-detects tier.

    Returns:
        (model, metrics_dict, params_dict)
    """
    if feature_cols is None:
        tier = detect_feature_tier(features_df)
        feature_cols = get_feature_cols(tier)
    else:
        tier = "production" if len(feature_cols) > 30 else "cold_start"
    default_params = {
        "n_estimators": 500,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "min_child_weight": 5,
        "early_stopping_rounds": 30,
        "random_state": 42,
    }
    if params:
        default_params.update(params)

    X = features_df[[c for c in feature_cols if c in features_df.columns]].fillna(0)
    y = features_df[target_col]

    # Time-series split: 5 folds
    tscv = TimeSeriesSplit(n_splits=5)
    maes, mapes, coverages = [], [], []

    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model = xgb.XGBRegressor(**default_params)
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        preds = model.predict(X_val)
        preds = np.maximum(preds, 0)  # Demand can't be negative

        maes.append(mean_absolute_error(y_val, preds))
        # Guard against zero actuals
        nonzero_mask = y_val > 0
        if nonzero_mask.sum() > 0:
            mapes.append(mean_absolute_percentage_error(y_val[nonzero_mask], preds[nonzero_mask]))

        # Approximate 90% interval coverage from fold residual dispersion.
        residual_std = float(np.std(y_val - preds))
        z_90 = 1.645
        lower = np.maximum(preds - z_90 * residual_std, 0)
        upper = preds + z_90 * residual_std
        coverages.append(float(np.mean((y_val >= lower) & (y_val <= upper))))

    # Train quantiles on all data
    models = {}
    for alpha, name in zip([0.1, 0.5, 0.9], ["p10", "p50", "p90"]):
        params_q = {k: v for k, v in default_params.items() if k != "early_stopping_rounds"}
        params_q["objective"] = "reg:quantileerror"
        params_q["quantile_alpha"] = alpha
        m = xgb.XGBRegressor(**params_q)
        try:
            # Silence internal warnings during fallback checks if version is old
            m.fit(X, y, verbose=False)
        except Exception:
            m = xgb.XGBRegressor(**{k: v for k, v in default_params.items() if k != "early_stopping_rounds"})
            m.fit(X, y, verbose=False)
        models[name] = m

    final_model = QuantileXGBoost(models["p10"], models["p50"], models["p90"])

    metrics = {
        "mae": np.mean(maes),
        "mape": np.mean(mapes) if mapes else 0.0,
        "coverage_90": np.mean(coverages) if coverages else 0.0,
        "cv_folds": 5,
        "model_type": "xgboost",
        "feature_tier": tier,
        "n_features": X.shape[1],
        "feature_cols": list(X.columns),
    }

    return final_model, metrics, default_params.copy()


def train_poisson(
    features_df: pd.DataFrame,
    target_col: str = TARGET_COL,
    feature_cols: list[str] | None = None,
) -> tuple[xgb.XGBRegressor, dict[str, Any], dict[str, Any]]:
    """Train a Poisson regression model for slow-moving C-items."""
    if feature_cols is None:
        tier = detect_feature_tier(features_df)
        feature_cols = get_feature_cols(tier)
    else:
        tier = "production" if len(feature_cols) > 30 else "cold_start"

    X = features_df[[c for c in feature_cols if c in features_df.columns]].fillna(0)
    y = features_df[target_col]

    model = xgb.XGBRegressor(objective="count:poisson", n_estimators=100, learning_rate=0.05, max_depth=4)
    model.fit(X, y)
    
    metrics = {
        "model_type": "poisson_xgboost",
        "feature_tier": tier,
        "n_features": X.shape[1],
        "feature_cols": list(X.columns),
    }
    return model, metrics, {}


# ──────────────────────────────────────────────────────────────────────────
# LSTM (simplified Keras implementation)
# ──────────────────────────────────────────────────────────────────────────


def train_lstm(
    features_df: pd.DataFrame,
    target_col: str = TARGET_COL,
    sequence_length: int = 30,
    epochs: int = 20,
    batch_size: int = 64,
    feature_cols: list[str] | None = None,
    max_samples: int = 50_000,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """
    Train LSTM model on time-series sequences.

    Expects features_df sorted by (store_id, product_id, date).
    Returns (model, metrics_dict, config_dict).
    """
    try:
        import tensorflow as tf
        from tensorflow.keras import callbacks, layers, models
    except ImportError:
        raise ImportError("TensorFlow required for LSTM. Install: pip install tensorflow")

    def multi_quantile_loss(y_true, y_pred):
        q = tf.constant([0.1, 0.5, 0.9], dtype=tf.float32)
        y_true = tf.reshape(y_true, [-1, 1])
        e = y_true - y_pred
        return tf.reduce_mean(tf.maximum(q * e, (q - 1.0) * e))

    if feature_cols is None:
        tier = detect_feature_tier(features_df)
        feature_cols = get_feature_cols(tier)
    else:
        tier = "production" if len(feature_cols) > 30 else "cold_start"

    cols = [c for c in feature_cols if c in features_df.columns]

    X_all = features_df[cols].fillna(0).values
    y_all = features_df[target_col].values

    num_sequences = len(X_all) - sequence_length
    split = int(num_sequences * 0.8)

    # Compute normalization parameters only on the training portion to prevent data leakage.
    train_end_idx = split + sequence_length - 1
    mean = X_all[:train_end_idx].mean(axis=0)
    std = X_all[:train_end_idx].std(axis=0) + 1e-8
    X_norm = (X_all - mean) / std

    # Use timeseries_dataset_from_array for efficient streaming and low memory usage (removes arbitrary capping)
    train_dataset = tf.keras.utils.timeseries_dataset_from_array(
        data=X_norm[:-1],
        targets=y_all[sequence_length:],
        sequence_length=sequence_length,
        batch_size=batch_size,
        end_index=split
    )
    
    val_dataset = tf.keras.utils.timeseries_dataset_from_array(
        data=X_norm[:-1],
        targets=y_all[sequence_length:],
        sequence_length=sequence_length,
        batch_size=batch_size,
        start_index=split
    )

    y_val = y_all[sequence_length + split :]

    # Build LSTM model
    n_features = len(cols)
    model = models.Sequential(
        [
            layers.LSTM(64, return_sequences=True, input_shape=(sequence_length, n_features)),
            layers.Dropout(0.2),
            layers.LSTM(32),
            layers.Dropout(0.2),
            layers.Dense(16, activation="relu"),
            layers.Dense(3),  # P10, P50, P90
        ]
    )
    model.compile(optimizer="adam", loss=multi_quantile_loss)

    early_stop = callbacks.EarlyStopping(patience=5, restore_best_weights=True)

    model.fit(
        train_dataset,
        validation_data=val_dataset,
        epochs=epochs,
        callbacks=[early_stop],
        verbose=0,
    )

    # Evaluate
    preds = model.predict(val_dataset, verbose=0)
    # Extract P50 for validation metrics
    p50_preds = np.maximum(preds[:, 1], 0)

    mae = mean_absolute_error(y_val, p50_preds)
    nonzero = y_val > 0
    mape = mean_absolute_percentage_error(y_val[nonzero], p50_preds[nonzero]) if nonzero.sum() > 0 else 0.0

    # Store normalization params on model for inference
    model._norm_mean = mean
    model._norm_std = std

    metrics = {
        "mae": float(mae),
        "mape": float(mape),
        "sequence_length": sequence_length,
        "model_type": "lstm",
        "feature_tier": tier,
        "n_features": n_features,
        "feature_cols": cols,
    }

    config = {
        "sequence_length": sequence_length,
        "epochs": epochs,
        "batch_size": batch_size,
        "max_samples": max_samples,
    }
    return model, metrics, config


# ──────────────────────────────────────────────────────────────────────────
# Ensemble
# ──────────────────────────────────────────────────────────────────────────

ENSEMBLE_WEIGHTS = {"xgboost": 0.65, "lstm": 0.35}


def train_ensemble(
    features_df: pd.DataFrame,
    target_col: str = TARGET_COL,
    dataset_name: str = "unknown",
    version: str | None = None,
    xgb_params: dict[str, Any] | None = None,
    xgb_only: bool = True,
) -> dict[str, Any]:
    """
    Train forecasting model with XGBoost-default and optional LSTM ensemble.

    Auto-detects feature tier from the data. Both models use the
    same tier so their feature sets are aligned.

    Ensemble weights: 35% LSTM, 65% XGBoost (per workflow spec).
    If xgb_only=True (default), skips LSTM and uses 100% XGBoost.

    Integrations:
      - MLflow experiment tracking (params, metrics, artifacts)
      - Pandera validation before training
      - SHAP explanations after training
      - Plotly charts for analysis artifacts

    Returns dict with models, metrics, weights, and tier.
    """
    # Auto-detect once, pass to both models
    tier = features_df.attrs.get("feature_tier") or detect_feature_tier(features_df)
    feature_cols = get_feature_cols(tier)

    # ── Validation gate ────────────────────────────────────────────
    features_df = validate_features(features_df, tier=tier, raise_on_error=False)
    logger.info("train.validated", tier=tier, rows=len(features_df))

    effective_weights = {"xgboost": 1.0, "lstm": 0.0} if xgb_only else ENSEMBLE_WEIGHTS

    # ── Experiment tracking ────────────────────────────────────────
    with ExperimentTracker() as tracker:
        tracker.log_params(
            {
                "feature_tier": tier,
                "n_features": len(feature_cols),
                "dataset": dataset_name,
                "n_rows": len(features_df),
                "ensemble_weight_xgb": effective_weights["xgboost"],
                "ensemble_weight_lstm": effective_weights["lstm"],
                "xgb_only": xgb_only,
            }
        )
        tracker.log_tags(
            {
                "tier": tier,
                "dataset": dataset_name,
            }
        )

        # ── Train XGBoost ──────────────────────────────────────────
        xgb_model, xgb_metrics, xgb_params = train_xgboost(
            features_df,
            target_col,
            params=xgb_params,
            feature_cols=feature_cols,
        )
        tracker.log_params({f"xgb_{k}": v for k, v in xgb_params.items()})
        tracker.log_metrics({f"xgb_{k}": v for k, v in xgb_metrics.items() if isinstance(v, (int, float))})
        tracker.log_model(xgb_model, "xgboost")
        tracker.log_feature_importance(xgb_model, feature_cols)

        # ── Train LSTM ─────────────────────────────────────────────
        if xgb_only:
            lstm_model, lstm_metrics = (
                None,
                {
                    "mae": None,
                    "mape": None,
                    "model_type": "lstm",
                    "feature_tier": tier,
                    "skipped": True,
                },
            )
            lstm_config = {
                "sequence_length": 30,
                "epochs": 20,
                "batch_size": 64,
                "max_samples": 50_000,
            }
            lstm_available = False
            logger.info("train.lstm_skipped_xgb_only")
        else:
            try:
                lstm_model, lstm_metrics, lstm_config = train_lstm(
                    features_df,
                    target_col,
                    feature_cols=feature_cols,
                )
                tracker.log_params({f"lstm_{k}": v for k, v in lstm_config.items()})
                lstm_available = True
                tracker.log_metrics({f"lstm_{k}": v for k, v in lstm_metrics.items() if isinstance(v, (int, float))})
            except ImportError:
                lstm_model, lstm_metrics = (
                    None,
                    {
                        "mae": float("inf"),
                        "mape": float("inf"),
                        "model_type": "lstm",
                        "feature_tier": tier,
                    },
                )
                lstm_config = {
                    "sequence_length": 30,
                    "epochs": 20,
                    "batch_size": 64,
                    "max_samples": 50_000,
                }
                lstm_available = False
                logger.warning("train.lstm_unavailable")

        # ── Ensemble metrics ───────────────────────────────────────
        if lstm_available:
            ensemble_mae = (
                effective_weights["xgboost"] * xgb_metrics["mae"] + effective_weights["lstm"] * lstm_metrics["mae"]
            )
        else:
            ensemble_mae = xgb_metrics["mae"]

        tracker.log_metrics(
            {
                "ensemble_mae": ensemble_mae,
                "ensemble_mape": xgb_metrics.get("mape", 0),
                "ensemble_coverage_90": xgb_metrics.get("coverage_90", 0),
            }
        )

        # ── SHAP explanations ──────────────────────────────────────
        try:
            from ml.explain import generate_explanations

            X_test = (
                features_df[[c for c in feature_cols if c in features_df.columns]].fillna(0).values[-1000:]
            )  # Last 1000 rows as test

            ver = version or datetime.now(timezone.utc).strftime("v%Y%m%d")
            shap_artifacts = generate_explanations(
                xgb_model,
                X_test,
                feature_cols,
                version=ver,
            )
            for path in shap_artifacts.values():
                if isinstance(path, list):
                    for p in path:
                        tracker.log_artifact(p)
                else:
                    tracker.log_artifact(path)
        except Exception as e:
            logger.warning("train.shap_failed", error=str(e))

        # ── Analysis charts ────────────────────────────────────────
        try:
            from ml.charts import (
                plot_error_distribution,
                plot_tier_comparison,
                plot_training_summary,
            )

            # Error distribution
            X_full = features_df[[c for c in feature_cols if c in features_df.columns]].fillna(0)
            preds = xgb_model.predict(X_full)
            residuals = (features_df[target_col].values - preds).tolist()
            plot_error_distribution(residuals)

            # Training summary table
            plot_training_summary(
                params={"tier": tier, "n_features": len(feature_cols)},
                metrics={"mae": xgb_metrics["mae"], "mape": xgb_metrics.get("mape", 0)},
                data_stats={"rows": len(features_df), "dataset": dataset_name},
            )
        except Exception as e:
            logger.warning("train.charts_failed", error=str(e))

    return {
        "xgboost": {
            "model": xgb_model,
            "metrics": xgb_metrics,
            "params": xgb_params,
        },
        "lstm": {
            "model": lstm_model,
            "metrics": lstm_metrics,
            "available": lstm_available,
            "config": lstm_config,
        },
        "ensemble": {
            "weights": effective_weights,
            "estimated_mae": ensemble_mae,
            "estimated_mape": xgb_metrics.get("mape", 0),
            "estimated_coverage_90": xgb_metrics.get("coverage_90", 0),
            "feature_tier": tier,
            "feature_cols": feature_cols,
            "xgb_only": xgb_only,
        },
    }


def save_models(
    ensemble_result: dict,
    version: str,
    dataset_name: str = "unknown",
    promote: bool = False,
    rows_trained: int | None = None,
) -> str:
    """
    Save trained models, metadata (JSON), and register in model registry.

    Args:
        ensemble_result: Output of train_ensemble().
        version: Version string (e.g., "v1").
        dataset_name: Name of training dataset.
        promote: If True, promote this version to champion.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    version_dir = os.path.join(MODEL_DIR, version)
    os.makedirs(version_dir, exist_ok=True)

    # XGBoost
    joblib.dump(
        ensemble_result["xgboost"]["model"],
        os.path.join(version_dir, "xgboost.joblib"),
    )

    # LSTM
    if ensemble_result["lstm"]["available"]:
        ensemble_result["lstm"]["model"].save(os.path.join(version_dir, "lstm.keras"))

    # ── Human-readable JSON metadata (was .joblib) ─────────────────
    tier = ensemble_result["ensemble"].get("feature_tier", "production")
    feature_cols = ensemble_result["ensemble"].get("feature_cols", FEATURE_COLS)
    rows_trained_value = rows_trained if rows_trained is not None else len(feature_cols)

    meta = {
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset_name,
        "rows_trained": rows_trained_value,
        "xgb_only": ensemble_result["ensemble"].get("xgb_only", False),
        "weights": ensemble_result["ensemble"]["weights"],
        "xgboost_params": ensemble_result["xgboost"].get("params", {}),
        "xgboost_metrics": ensemble_result["xgboost"]["metrics"],
        "lstm_config": ensemble_result["lstm"].get("config", {}),
        "lstm_metrics": ensemble_result["lstm"]["metrics"],
        "ensemble_mae": ensemble_result["ensemble"]["estimated_mae"],
        "ensemble_mape": ensemble_result["ensemble"].get("estimated_mape"),
        "ensemble_coverage_90": ensemble_result["ensemble"].get("estimated_coverage_90"),
        "feature_tier": tier,
        "feature_cols": feature_cols,
    }

    # Save as JSON (human-readable) + joblib (backward compat)
    with open(os.path.join(version_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2, default=str)
    joblib.dump(meta, os.path.join(version_dir, "metadata.joblib"))

    # ── Register in model registry ─────────────────────────────────
    try:
        register_model(
            version=version,
            feature_tier=tier,
            dataset=dataset_name,
            rows_trained=rows_trained_value,
            metrics={
                "mae": ensemble_result["xgboost"]["metrics"].get("mae", 0),
                "mape": ensemble_result["xgboost"]["metrics"].get("mape", 0),
            },
            promote=promote,
        )
    except Exception as e:
        logger.warning("train.registry_failed", error=str(e))

    logger.info(
        "model.saved",
        version=version,
        tier=tier,
        mae=meta["ensemble_mae"],
        promoted=promote,
    )

    return version_dir
