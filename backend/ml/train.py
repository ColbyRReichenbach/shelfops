from __future__ import annotations

"""
ML Training Pipeline — Pure LightGBM (demo mode).

Agent: ml-engineer
Skill: ml-forecasting
Workflow: train-forecast-model.md

Performance Targets (from workflow):
  - MAE < 15 units
  - WAPE < 20%
  - MASE < 1.0 (beats naive forecast)
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

import numpy as np
import pandas as pd
import structlog
from sklearn.model_selection import TimeSeriesSplit

from ml.calibration import calibration_summary, conformal_interval, conformal_residual_quantile
from ml.experiment import ExperimentTracker, register_model
from ml.features import (
    COLD_START_FEATURE_COLS,
    FEATURE_COLS,  # legacy alias = PRODUCTION_FEATURE_COLS
    PRODUCTION_FEATURE_COLS,
    FeatureTier,
    detect_feature_tier,
    get_feature_cols,
)
from ml.lineage import standard_model_metadata
from ml.validate import validate_features

logger = structlog.get_logger()

try:
    import lightgbm as lgb
except ModuleNotFoundError:  # pragma: no cover - exercised in CI dependency validation
    lgb = None

TARGET_COL = "quantity"
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


def _require_lightgbm() -> Any:
    if lgb is None:
        raise ModuleNotFoundError(
            "lightgbm is required for training. Install backend/requirements-ml.txt before running ML workflows."
        )
    return lgb


def _is_lightgbm_booster(model: Any) -> bool:
    return lgb is not None and isinstance(model, lgb.Booster)


def _shap_sample_size(n_rows: int) -> int:
    """Keep SHAP generation bounded for large training runs."""
    if n_rows <= 0:
        return 0
    if n_rows >= 250_000:
        return 50
    if n_rows >= 50_000:
        return 100
    if n_rows >= 10_000:
        return 250
    return min(500, n_rows)


# ──────────────────────────────────────────────────────────────────────────
# LightGBM
# ──────────────────────────────────────────────────────────────────────────


def train_lightgbm(
    features_df: pd.DataFrame,
    target_col: str = TARGET_COL,
    params: dict[str, Any] | None = None,
    feature_cols: list[str] | None = None,
    n_splits: int = 5,
) -> tuple[lgb.Booster, dict[str, float]]:
    """
    Train LightGBM with time-series cross-validation.

    Uses TimeSeriesSplit — never shuffle. Poisson objective for count
    data (demand is non-negative integer-valued).

    Args:
        features_df: Feature DataFrame (output of create_features).
        target_col: Target column name (default 'quantity').
        params: Override default LightGBM params.
        feature_cols: Override feature list. If None, auto-detects tier.
        n_splits: Number of time-series CV folds.

    Returns:
        (booster, metrics_dict)
    """
    lightgbm = _require_lightgbm()

    if feature_cols is None:
        tier = detect_feature_tier(features_df)
        feature_cols = get_feature_cols(tier)
    else:
        tier = "production" if len(feature_cols) > 30 else "cold_start"

    default_params = {
        "objective": "poisson",
        "metric": "mape",
        "num_leaves": 63,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "min_child_samples": 20,
        "verbosity": -1,
        "n_estimators": 500,
        "random_state": 42,
    }
    # XGBoost-compat params that are not valid LightGBM params — strip them
    _XGBOOST_ONLY_PARAMS = {
        "early_stopping_rounds",
        "reg_alpha",
        "reg_lambda",
        "min_child_weight",
        "colsample_bytree",  # LightGBM uses feature_fraction
        "subsample",  # LightGBM uses bagging_fraction
        "max_depth",  # LightGBM uses num_leaves instead
        "n_estimators",  # Handled via num_boost_round
    }
    if params:
        for k, v in params.items():
            if k == "n_estimators":
                default_params["n_estimators"] = v  # Map to num_boost_round
            elif k == "subsample":
                default_params["bagging_fraction"] = v  # Map to LightGBM equivalent
            elif k == "colsample_bytree":
                default_params["feature_fraction"] = v  # Map to LightGBM equivalent
            elif k not in _XGBOOST_ONLY_PARAMS:
                default_params[k] = v

    X = features_df[[c for c in feature_cols if c in features_df.columns]].fillna(0)
    y = features_df[target_col].clip(lower=0)  # Poisson requires non-negative targets

    # Time-series split: never shuffle
    tscv = TimeSeriesSplit(n_splits=n_splits)
    maes, mapes, wapes, mases, biases = [], [], [], [], []
    calibration_coverages, calibration_widths = [], []
    oof_actuals: list[float] = []
    oof_preds: list[float] = []

    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        train_data = lightgbm.Dataset(X_train, label=y_train)
        val_data = lightgbm.Dataset(X_val, label=y_val, reference=train_data)

        # Extract n_estimators for num_boost_round; remove it from params
        n_rounds = default_params.pop("n_estimators", 500)
        random_state = default_params.pop("random_state", 42)
        lgb_params = dict(default_params)
        lgb_params["seed"] = random_state

        booster = lightgbm.train(
            lgb_params,
            train_data,
            num_boost_round=n_rounds,
            valid_sets=[val_data],
            callbacks=[lightgbm.early_stopping(30, verbose=False), lightgbm.log_evaluation(-1)],
        )

        # Restore for next fold
        default_params["n_estimators"] = n_rounds
        default_params["random_state"] = random_state

        preds = np.maximum(booster.predict(X_val), 0)

        from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

        from ml.metrics import bias_pct as compute_bias_pct
        from ml.metrics import mase as compute_mase
        from ml.metrics import wape as compute_wape

        y_val_arr = y_val.values if hasattr(y_val, "values") else np.asarray(y_val)
        maes.append(mean_absolute_error(y_val_arr, preds))
        nonzero_mask = y_val_arr > 0
        if nonzero_mask.sum() > 0:
            mapes.append(mean_absolute_percentage_error(y_val_arr[nonzero_mask], preds[nonzero_mask]))
        wapes.append(compute_wape(y_val_arr, preds))
        mases.append(compute_mase(y_val_arr, preds, seasonality=7))
        biases.append(compute_bias_pct(y_val_arr, preds))
        oof_actuals.extend(y_val_arr.tolist())
        oof_preds.extend(preds.tolist())

    residual_quantile = conformal_residual_quantile(np.asarray(oof_actuals), np.asarray(oof_preds), alpha=0.1)
    if oof_preds:
        lower, upper = conformal_interval(np.asarray(oof_preds), residual_quantile)
        interval_summary = calibration_summary(np.asarray(oof_actuals), lower, upper)
        calibration_coverages.append(interval_summary["coverage"])
        calibration_widths.append(interval_summary["mean_interval_width"])
    else:
        interval_summary = {"coverage": 0.0, "mean_interval_width": 0.0}

    # Train final model on all data
    n_rounds = default_params.pop("n_estimators", 500)
    random_state = default_params.pop("random_state", 42)
    lgb_params = dict(default_params)
    lgb_params["seed"] = random_state
    # Remove metric to allow final training without validation set
    lgb_params.pop("metric", None)

    full_data = lightgbm.Dataset(X, label=y)
    final_booster = lightgbm.train(
        lgb_params,
        full_data,
        num_boost_round=n_rounds,
        # No callbacks for final full-data training (no eval set, no early stopping)
    )

    metrics = {
        "mae": float(np.mean(maes)),
        "mape": float(np.mean(mapes)) if mapes else 0.0,
        "wape": float(np.mean(wapes)),
        "mase": float(np.mean(mases)),
        "bias_pct": float(np.mean(biases)) if biases else 0.0,
        "coverage": float(np.mean(calibration_coverages))
        if calibration_coverages
        else float(interval_summary["coverage"]),
        "interval_method": "split_conformal",
        "calibration_status": "calibrated",
        "interval_coverage": float(np.mean(calibration_coverages))
        if calibration_coverages
        else float(interval_summary["coverage"]),
        "mean_interval_width": float(np.mean(calibration_widths))
        if calibration_widths
        else float(interval_summary["mean_interval_width"]),
        "conformal_residual_quantile": float(residual_quantile),
        "cv_folds": n_splits,
        "model_type": "lightgbm",
        "feature_tier": tier,
        "n_features": X.shape[1],
        "feature_cols": list(X.columns),
    }

    return final_booster, metrics


# ──────────────────────────────────────────────────────────────────────────
# XGBoost backward-compat stub (replaced by LightGBM)
# ──────────────────────────────────────────────────────────────────────────


def train_xgboost(
    features_df: pd.DataFrame,
    target_col: str = TARGET_COL,
    params: dict[str, Any] | None = None,
    feature_cols: list[str] | None = None,
) -> tuple[Any, dict[str, float]]:
    """Backward-compat stub — delegates to train_lightgbm. XGBoost replaced by LightGBM."""
    logger.info("train.xgboost_stub", reason="delegating to LightGBM; XGBoost replaced in P0 demo")
    return train_lightgbm(features_df, target_col, params=params, feature_cols=feature_cols)


# ──────────────────────────────────────────────────────────────────────────
# LSTM stub (disabled — pure LightGBM mode)
# ──────────────────────────────────────────────────────────────────────────


def train_lstm(
    features_df: pd.DataFrame,
    target_col: str = TARGET_COL,
    sequence_length: int = 30,
    epochs: int = 20,
    batch_size: int = 64,
    feature_cols: list[str] | None = None,
    max_samples: int = 50_000,
) -> tuple[Any, dict[str, float]]:
    """LSTM disabled — pure LightGBM mode. Returns empty stub metrics."""
    logger.info("train.lstm_disabled", reason="pure LightGBM mode")

    if feature_cols is None:
        tier = detect_feature_tier(features_df)
    else:
        tier = "production" if len(feature_cols) > 30 else "cold_start"

    return None, {
        "mae": float("inf"),
        "mape": float("inf"),
        "model_type": "lstm_disabled",
        "feature_tier": tier,
    }


# ──────────────────────────────────────────────────────────────────────────
# Ensemble
# ──────────────────────────────────────────────────────────────────────────

ENSEMBLE_WEIGHTS = {"lightgbm": 1.0, "lstm": 0.0}


def train_ensemble(
    features_df: pd.DataFrame,
    target_col: str = TARGET_COL,
    dataset_name: str = "unknown",
    version: str | None = None,
    model_name: str = "demand_forecast",
) -> dict[str, Any]:
    """
    Train the active LightGBM-first forecast path with full MLOps instrumentation.

    Auto-detects feature tier from the data and preserves legacy-compatible
    return keys for older runtime consumers.

    Ensemble weights: 100% LightGBM, 0% LSTM.

    Integrations:
      - MLflow experiment tracking (params, metrics, artifacts)
      - Pandera validation before training
      - SHAP explanations after training
      - Plotly charts for analysis artifacts

    Returns dict with models, metrics, weights, and tier.
    """
    # Auto-detect once
    tier = detect_feature_tier(features_df)
    feature_cols = get_feature_cols(tier)

    # ── Validation gate ────────────────────────────────────────────
    features_df = validate_features(features_df, tier=tier, raise_on_error=False)
    logger.info("train.validated", tier=tier, rows=len(features_df))

    # ── Experiment tracking ────────────────────────────────────────
    with ExperimentTracker(model_name=model_name) as tracker:
        tracker.log_params(
            {
                "feature_tier": tier,
                "n_features": len(feature_cols),
                "dataset": dataset_name,
                "n_rows": len(features_df),
                "ensemble_weight_lightgbm": ENSEMBLE_WEIGHTS["lightgbm"],
                "ensemble_weight_lstm": ENSEMBLE_WEIGHTS["lstm"],
                "model_type": "lightgbm",
            }
        )
        tracker.log_tags(
            {
                "tier": tier,
                "dataset": dataset_name,
                "model_name": model_name,
            }
        )

        # ── Train LightGBM ─────────────────────────────────────────
        lgb_model, lgb_metrics = train_lightgbm(
            features_df,
            target_col,
            feature_cols=feature_cols,
        )
        tracker.log_metrics({f"lgb_{k}": v for k, v in lgb_metrics.items() if isinstance(v, (int, float))})

        # ── Ensemble metrics (single-model) ────────────────────────
        ensemble_mae = lgb_metrics["mae"]

        tracker.log_metrics(
            {
                "ensemble_mae": ensemble_mae,
                "ensemble_mape": lgb_metrics.get("mape", 0),
                "ensemble_wape": lgb_metrics.get("wape", 0),
                "ensemble_mase": lgb_metrics.get("mase", 0),
                "ensemble_bias_pct": lgb_metrics.get("bias_pct", 0),
                "ensemble_coverage": lgb_metrics.get("interval_coverage", 0),
            }
        )

        # ── SHAP explanations ──────────────────────────────────────
        try:
            from ml.explain import generate_explanations

            sample_size = _shap_sample_size(len(features_df))
            X_test = features_df[[c for c in feature_cols if c in features_df.columns]].fillna(0).values[-sample_size:]

            ver = version or datetime.now(timezone.utc).strftime("v%Y%m%d")
            # LightGBM SHAP: use predict with pred_contrib
            shap_artifacts = generate_explanations(
                lgb_model,
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
                plot_training_summary,
            )

            X_full = features_df[[c for c in feature_cols if c in features_df.columns]].fillna(0)
            preds = np.maximum(lgb_model.predict(X_full), 0)
            residuals = (features_df[target_col].values - preds).tolist()
            plot_error_distribution(residuals)

            plot_training_summary(
                params={"tier": tier, "n_features": len(feature_cols)},
                metrics={"mae": lgb_metrics["mae"], "mape": lgb_metrics.get("mape", 0)},
                data_stats={"rows": len(features_df), "dataset": dataset_name},
            )
        except Exception as e:
            logger.warning("train.charts_failed", error=str(e))

    # Return structure keeps backward-compat keys so retrain.py works unchanged.
    # "xgboost" key is aliased to lightgbm for minimal disruption to callers.
    return {
        "lightgbm": {"model": lgb_model, "metrics": lgb_metrics},
        "xgboost": {"model": lgb_model, "metrics": lgb_metrics},  # backward-compat alias
        "lstm": {
            "model": None,
            "metrics": {"mae": float("inf"), "mape": float("inf"), "model_type": "lstm_disabled"},
            "available": False,
        },
        "ensemble": {
            "weights": ENSEMBLE_WEIGHTS,
            "estimated_mae": ensemble_mae,
            "feature_tier": tier,
            "feature_cols": feature_cols,
            "model_name": model_name,
            **standard_model_metadata(
                model_name=model_name,
                dataset_id=dataset_name,
                forecast_grain="store-family-day" if dataset_name == "favorita" else "dataset_specific",
                feature_tier=tier,
                change_category="baseline_refresh",
                segment_strategy="global",
                rule_overlay_enabled=False,
                evaluation_window_days=30,
                architecture="lightgbm",
                objective="poisson",
                tuning_profile="baseline",
                interval_method=lgb_metrics.get("interval_method"),
                calibration_status=lgb_metrics.get("calibration_status"),
                interval_coverage=lgb_metrics.get("interval_coverage"),
                conformal_residual_quantile=lgb_metrics.get("conformal_residual_quantile"),
            ),
        },
    }


def save_models(
    ensemble_result: dict,
    version: str,
    dataset_name: str = "unknown",
    promote: bool = False,
    rows_trained: int | None = None,
    dataset_snapshot: dict | None = None,
) -> str:
    """
    Save trained models, metadata (JSON), and register in model registry.

    Args:
        ensemble_result: Output of train_ensemble().
        version: Version string (e.g., "v1").
        dataset_name: Name of training dataset.
        promote: If True, promote this version to champion.
    """
    import joblib

    os.makedirs(MODEL_DIR, exist_ok=True)
    version_dir = os.path.join(MODEL_DIR, version)
    os.makedirs(version_dir, exist_ok=True)

    # LightGBM — use native save_model (not joblib)
    lgb_model = ensemble_result.get("lightgbm", {}).get("model") or ensemble_result.get("xgboost", {}).get("model")
    if _is_lightgbm_booster(lgb_model):
        lgb_model.save_model(os.path.join(version_dir, "lightgbm.txt"))
    elif lgb_model is not None:
        # Fallback: joblib for any non-Booster object
        joblib.dump(lgb_model, os.path.join(version_dir, "lightgbm.joblib"))

    # ── Human-readable JSON metadata ──────────────────────────────
    tier = ensemble_result["ensemble"].get("feature_tier", "production")
    feature_cols = ensemble_result["ensemble"].get("feature_cols", FEATURE_COLS)
    model_name = ensemble_result["ensemble"].get("model_name", "demand_forecast")

    lgb_metrics = ensemble_result.get("lightgbm", ensemble_result.get("xgboost", {})).get("metrics", {})
    dataset_snapshot = dataset_snapshot or ensemble_result["ensemble"].get("dataset_snapshot")
    dataset_snapshot_id = (
        dataset_snapshot.get("snapshot_id")
        if dataset_snapshot
        else ensemble_result["ensemble"].get("dataset_snapshot_id")
    )

    meta = {
        "version": version,
        "model_name": model_name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset_name,
        "dataset_id": dataset_name,
        "dataset_snapshot_id": dataset_snapshot_id,
        "dataset_snapshot": dataset_snapshot,
        "forecast_grain": ensemble_result["ensemble"].get("forecast_grain", "dataset_specific"),
        "segment_strategy": ensemble_result["ensemble"].get("segment_strategy", "global"),
        "rule_overlay_enabled": ensemble_result["ensemble"].get("rule_overlay_enabled", False),
        "evaluation_window_days": ensemble_result["ensemble"].get("evaluation_window_days", 30),
        "architecture": ensemble_result["ensemble"].get("architecture", "lightgbm"),
        "objective": ensemble_result["ensemble"].get("objective", "poisson"),
        "feature_set_id": ensemble_result["ensemble"].get("feature_set_id"),
        "tuning_profile": ensemble_result["ensemble"].get("tuning_profile", "baseline"),
        "trigger_source": ensemble_result["ensemble"].get("trigger_source"),
        "change_category": ensemble_result["ensemble"].get("change_category"),
        "lineage_label": ensemble_result["ensemble"].get("lineage_label"),
        "interval_method": ensemble_result["ensemble"].get("interval_method"),
        "calibration_status": ensemble_result["ensemble"].get("calibration_status"),
        "interval_coverage": ensemble_result["ensemble"].get("interval_coverage"),
        "conformal_residual_quantile": ensemble_result["ensemble"].get("conformal_residual_quantile"),
        "weights": ensemble_result["ensemble"]["weights"],
        "lightgbm_metrics": lgb_metrics,
        "lstm_metrics": ensemble_result["lstm"]["metrics"],
        "ensemble_mae": ensemble_result["ensemble"]["estimated_mae"],
        "feature_tier": tier,
        "feature_cols": feature_cols,
        "raw_holdout_metrics": ensemble_result["ensemble"].get("raw_holdout_metrics"),
        "rule_overlay_holdout_metrics": ensemble_result["ensemble"].get("rule_overlay_holdout_metrics"),
    }

    with open(os.path.join(version_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2, default=str)
    joblib.dump(meta, os.path.join(version_dir, "metadata.joblib"))

    # ── Register in model registry ─────────────────────────────────
    try:
        register_model(
            version=version,
            feature_tier=tier,
            dataset=dataset_name,
            rows_trained=int(rows_trained if rows_trained is not None else len(feature_cols)),
            metrics={
                "mae": lgb_metrics.get("mae", 0),
                "mape": lgb_metrics.get("mape", 0),
                "wape": lgb_metrics.get("wape", 0),
                "mase": lgb_metrics.get("mase", 0),
                "bias_pct": lgb_metrics.get("bias_pct", 0),
                "dataset_id": dataset_name,
                "dataset_snapshot_id": dataset_snapshot_id,
                "forecast_grain": ensemble_result["ensemble"].get("forecast_grain", "dataset_specific"),
                "segment_strategy": ensemble_result["ensemble"].get("segment_strategy", "global"),
                "rule_overlay_enabled": ensemble_result["ensemble"].get("rule_overlay_enabled", False),
                "evaluation_window_days": ensemble_result["ensemble"].get("evaluation_window_days", 30),
                "architecture": ensemble_result["ensemble"].get("architecture", "lightgbm"),
                "objective": ensemble_result["ensemble"].get("objective", "poisson"),
                "feature_set_id": ensemble_result["ensemble"].get("feature_set_id"),
                "tuning_profile": ensemble_result["ensemble"].get("tuning_profile", "baseline"),
                "trigger_source": ensemble_result["ensemble"].get("trigger_source"),
                "change_category": ensemble_result["ensemble"].get("change_category"),
                "lineage_label": ensemble_result["ensemble"].get("lineage_label"),
                "interval_method": ensemble_result["ensemble"].get("interval_method"),
                "calibration_status": ensemble_result["ensemble"].get("calibration_status"),
                "interval_coverage": ensemble_result["ensemble"].get("interval_coverage"),
                "conformal_residual_quantile": ensemble_result["ensemble"].get("conformal_residual_quantile"),
            },
            promote=promote,
            model_name=model_name,
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
