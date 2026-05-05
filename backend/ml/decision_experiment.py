from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.arena import compare_candidate_vs_champion_metrics
from ml.baselines import moving_average_forecast, prepare_series_frame
from ml.dataset_snapshots import create_dataset_snapshot, persist_dataset_snapshot
from ml.evaluation import evaluate_predictions
from ml.metrics_contract import compute_forecast_metrics
from ml.replenishment_simulation import PolicyResult, SimulationConfig, _simulate_policy

DEFAULT_DATA_DIR = "data/benchmarks/m5_walmart/subset_20spc"
DEFAULT_EXPERIMENT_NAME = "m5_decision_bias_calibration_shadow"
DEFAULT_HYPOTHESIS = (
    "A calibrated post-processing layer can reduce benchmark holdout bias and improve simulated "
    "replenishment cost without increasing stockout risk."
)

SERIES_KEYS = ["store_id", "product_id"]


@dataclass(frozen=True)
class DecisionExperimentConfig:
    dataset_id: str = "m5_walmart"
    baseline_version: str = "v3"
    challenger_version: str = "e_m5_decision_v1"
    model_name: str = "demand_forecast"
    experiment_name: str = DEFAULT_EXPERIMENT_NAME
    hypothesis: str = DEFAULT_HYPOTHESIS
    experiment_type: str = "post_processing"
    experiment_spec_id: str | None = None
    experiment_spec_hash: str | None = None
    spec_template_id: str | None = None
    spec_name: str | None = None
    feature_set_id: str = "m5_lag_price_calendar_v1"
    feature_config: dict[str, Any] = field(default_factory=dict)
    dataset_config: dict[str, Any] = field(default_factory=dict)
    model_config: dict[str, Any] = field(default_factory=dict)
    calibration_config: dict[str, Any] = field(default_factory=dict)
    segmentation_config: dict[str, Any] = field(default_factory=dict)
    holdout_days: int = 28
    calibration_days: int = 28
    validation_mode: str = "quick_screen"
    rolling_window_count: int = 0
    rolling_window_days: int = 28
    rolling_stride_days: int = 28
    max_rows: int = 120_000
    max_series: int = 60
    lead_time_days: int = 5
    safety_stock_days: float = 2.0
    order_up_to_days: float = 7.0
    initial_inventory_days: float = 14.0
    order_cost: float = 24.0
    holding_cost_rate_annual: float = 0.25
    random_state: int = 42


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    return value


def _load_canonical_transactions(data_dir: str | Path) -> pd.DataFrame:
    from ml.data_contracts import load_canonical_transactions

    return load_canonical_transactions(str(data_dir))


def _price_series(frame: pd.DataFrame) -> pd.Series:
    if "price" in frame.columns:
        values = pd.to_numeric(frame["price"], errors="coerce")
    elif "sell_price" in frame.columns:
        values = pd.to_numeric(frame["sell_price"], errors="coerce")
    else:
        values = pd.Series([np.nan] * len(frame), index=frame.index, dtype="float64")
    by_series = values.groupby([frame["store_id"], frame["product_id"]]).transform(lambda s: s.ffill().bfill())
    global_median = float(by_series.dropna().median()) if by_series.notna().any() else 0.0
    return by_series.fillna(global_median).fillna(0.0).clip(lower=0.0)


def _raw_price_values(frame: pd.DataFrame) -> pd.Series:
    if "sell_price" in frame.columns:
        return pd.to_numeric(frame["sell_price"], errors="coerce")
    if "price" in frame.columns:
        return pd.to_numeric(frame["price"], errors="coerce")
    return pd.Series([np.nan] * len(frame), index=frame.index, dtype="float64")


def _attach_activation_flags(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["raw_sell_price"] = _raw_price_values(out)
    out["is_price_available"] = out["raw_sell_price"].notna().astype(int)

    first_price = (
        out.loc[out["is_price_available"] == 1, SERIES_KEYS + ["date"]]
        .groupby(SERIES_KEYS, dropna=False)["date"]
        .min()
        .rename("first_available_sell_price_date")
        .reset_index()
    )
    out = out.merge(first_price, on=SERIES_KEYS, how="left")
    first_date = pd.to_datetime(out["first_available_sell_price_date"], errors="coerce")
    out["has_activation_marker"] = first_date.notna().astype(int)
    out["is_pre_activation"] = ((first_date.notna()) & (out["date"] < first_date)).astype(int)
    out["is_active_sellable"] = ((first_date.notna()) & (out["date"] >= first_date)).astype(int)

    series_start = out.groupby(SERIES_KEYS, dropna=False)["date"].transform("min")
    out["days_to_first_available_price"] = (first_date - series_start).dt.days
    out["days_since_first_available_price"] = (out["date"] - first_date).dt.days
    out.loc[first_date.isna(), ["days_to_first_available_price", "days_since_first_available_price"]] = np.nan
    out["is_late_activation"] = (
        first_date.notna() & (pd.to_numeric(out["days_to_first_available_price"], errors="coerce") >= 28)
    ).astype(int)
    return out


def prepare_decision_frame(raw: pd.DataFrame, *, config: DecisionExperimentConfig) -> pd.DataFrame:
    frame = prepare_series_frame(raw)
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0.0).clip(lower=0.0)
    frame["category"] = frame.get("category", frame["product_id"]).astype(str)
    frame["is_promotional"] = pd.to_numeric(frame.get("is_promotional", 0), errors="coerce").fillna(0).astype(int)
    frame["is_holiday"] = pd.to_numeric(frame.get("is_holiday", 0), errors="coerce").fillna(0).astype(int)
    frame = _attach_activation_flags(frame)
    frame["price"] = _price_series(frame)
    frame["unit_cost"] = (frame["price"] * 0.7).round(6)
    frame["holding_cost_per_unit_per_day"] = frame["unit_cost"] * config.holding_cost_rate_annual / 365.0
    frame["series_id"] = frame["store_id"].astype(str) + "::" + frame["product_id"].astype(str)

    if config.max_series:
        top_series = (
            frame.groupby("series_id")["quantity"].sum().sort_values(ascending=False).head(config.max_series).index
        )
        frame = frame[frame["series_id"].isin(top_series)].copy()

    if config.max_rows and len(frame) > config.max_rows:
        keep_dates: list[pd.Timestamp] = []
        running = 0
        counts = frame.groupby("date").size().sort_index(ascending=False)
        for current_date, count in counts.items():
            if keep_dates and running + int(count) > config.max_rows:
                break
            keep_dates.append(current_date)
            running += int(count)
        frame = frame[frame["date"].isin(set(keep_dates))].copy()

    frame = frame.sort_values(SERIES_KEYS + ["date"], kind="mergesort").reset_index(drop=True)
    if frame.empty:
        raise ValueError("decision experiment frame is empty after filtering")
    return frame


def _time_split(
    frame: pd.DataFrame,
    *,
    config: DecisionExperimentConfig,
    holdout_end: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    unique_dates = sorted(pd.to_datetime(frame["date"]).dropna().unique().tolist())
    if holdout_end is not None:
        holdout_end = pd.to_datetime(holdout_end)
        unique_dates = [current_date for current_date in unique_dates if pd.to_datetime(current_date) <= holdout_end]
    required_days = config.holdout_days + config.calibration_days + 28
    if len(unique_dates) < required_days:
        raise ValueError(
            f"Need at least {required_days} distinct dates for train/calibration/holdout; found {len(unique_dates)}"
        )

    holdout_start = unique_dates[-config.holdout_days]
    calibration_start = unique_dates[-(config.holdout_days + config.calibration_days)]
    holdout_end = unique_dates[-1]

    train = frame[frame["date"] < calibration_start].copy()
    calibration = frame[(frame["date"] >= calibration_start) & (frame["date"] < holdout_start)].copy()
    holdout = frame[(frame["date"] >= holdout_start) & (frame["date"] <= holdout_end)].copy()
    if train.empty or calibration.empty or holdout.empty:
        raise ValueError("time split produced an empty train, calibration, or holdout frame")
    return train.reset_index(drop=True), calibration.reset_index(drop=True), holdout.reset_index(drop=True)


def _active_feature_config(config: DecisionExperimentConfig) -> dict[str, Any]:
    defaults = {
        "lag_days": [1, 7, 14, 28],
        "rolling_windows": [7, 28],
        "rolling_nonzero_windows": [28],
        "include_calendar": True,
        "include_product_codes": True,
        "include_price": True,
        "include_price_momentum": False,
        "include_promotion": True,
        "include_promo_price_interaction": False,
        "include_holiday": True,
        "include_intermittency": False,
    }
    merged = {**defaults, **dict(config.feature_config or {})}
    for key in ("lag_days", "rolling_windows", "rolling_nonzero_windows"):
        merged[key] = sorted({int(value) for value in merged.get(key, []) if int(value) > 0})
    return merged


def _active_dataset_config(config: DecisionExperimentConfig) -> dict[str, Any]:
    dataset_config = {
        "activation_policy": "none",
        "activation_marker": "none",
        "training_policy": "canonical_train_rows",
        "calibration_policy": "canonical_calibration_rows",
        "primary_metric_filter": "all_holdout_rows",
        "guardrail_metric_filter": "canonical_holdout",
        "preserve_canonical_holdout": True,
        **dict(config.dataset_config or {}),
    }
    for key in (
        "activation_policy",
        "activation_marker",
        "training_policy",
        "calibration_policy",
        "primary_metric_filter",
        "guardrail_metric_filter",
    ):
        dataset_config[key] = str(dataset_config.get(key) or "").strip().lower()
    dataset_config["preserve_canonical_holdout"] = bool(dataset_config.get("preserve_canonical_holdout", True))
    return dataset_config


def _is_activation_aware(config: DecisionExperimentConfig) -> bool:
    return _active_dataset_config(config).get("activation_policy") in {
        "exclude_pre_first_price",
        "segment_gated_pre_first_price",
        "segment_routed_pre_first_price",
    }


def _is_segment_gated_activation(config: DecisionExperimentConfig) -> bool:
    return _active_dataset_config(config).get("activation_policy") in {
        "segment_gated_pre_first_price",
        "segment_routed_pre_first_price",
    }


def _is_segment_routed_activation(config: DecisionExperimentConfig) -> bool:
    return _active_dataset_config(config).get("activation_policy") == "segment_routed_pre_first_price"


def _bool_series(frame: pd.DataFrame, column: str, *, default: int = 0) -> pd.Series:
    if column in frame.columns:
        values = pd.to_numeric(frame[column], errors="coerce")
    else:
        values = pd.Series(default, index=frame.index)
    return values.fillna(default).astype(int) == 1


def _activation_gate_lookup(
    train: pd.DataFrame,
    *,
    dataset_config: dict[str, Any],
    velocity_lookup: dict[str, str],
) -> dict[str, dict[str, Any]]:
    eligible_velocity = {
        str(value).strip().lower()
        for value in dataset_config.get("activation_eligible_velocity_segments", [])
        if str(value).strip()
    }
    protected_velocity = {
        str(value).strip().lower()
        for value in dataset_config.get("activation_protected_velocity_segments", [])
        if str(value).strip()
    }
    include_late_activation = bool(dataset_config.get("activation_include_late_activation"))
    include_intermittent = bool(dataset_config.get("activation_include_intermittent"))
    intermittent_threshold = float(dataset_config.get("activation_intermittent_zero_rate_min", 0.8))

    late_series = _bool_series(train, "is_late_activation").groupby(train["series_id"]).max().to_dict()
    zero_rate = (
        (pd.to_numeric(train["quantity"], errors="coerce").fillna(0.0) <= 0)
        .astype(float)
        .groupby(train["series_id"])
        .mean()
        .to_dict()
    )
    lookup: dict[str, dict[str, Any]] = {}
    for series_id in sorted(train["series_id"].astype(str).unique()):
        velocity = str(velocity_lookup.get(series_id, "unknown"))
        protected = velocity in protected_velocity
        reasons: list[str] = []
        if not protected:
            if velocity in eligible_velocity:
                reasons.append(f"velocity_{velocity}")
            if include_late_activation and bool(late_series.get(series_id, False)):
                reasons.append("late_activation")
            if include_intermittent and float(zero_rate.get(series_id, 0.0)) >= intermittent_threshold:
                reasons.append("intermittent_demand")
        lookup[series_id] = {
            "eligible": bool(reasons),
            "protected": protected,
            "velocity_segment": velocity,
            "reason": ",".join(reasons) if reasons else ("protected_velocity" if protected else "not_eligible"),
            "zero_demand_rate": float(zero_rate.get(series_id, 0.0)),
            "late_activation": bool(late_series.get(series_id, False)),
        }
    return lookup


def _attach_activation_gate_columns(
    frame: pd.DataFrame,
    *,
    gate_lookup: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    out = frame.copy()
    if not gate_lookup:
        out["activation_gate_eligible"] = False
        out["activation_gate_protected"] = False
        out["activation_gate_reason"] = "not_applicable"
        return out
    out["activation_gate_eligible"] = out["series_id"].map(
        lambda series_id: bool(gate_lookup.get(str(series_id), {}).get("eligible", False))
    )
    out["activation_gate_protected"] = out["series_id"].map(
        lambda series_id: bool(gate_lookup.get(str(series_id), {}).get("protected", False))
    )
    out["activation_gate_reason"] = out["series_id"].map(
        lambda series_id: str(gate_lookup.get(str(series_id), {}).get("reason", "not_eligible"))
    )
    return out


def _activation_train_mask(combined: pd.DataFrame, *, segment_gated: bool) -> pd.Series:
    if segment_gated:
        return ~(_bool_series(combined, "is_pre_activation") & combined["activation_gate_eligible"].astype(bool))
    return _bool_series(combined, "is_active_sellable", default=1)


def _activation_calibration_mask(calibration: pd.DataFrame, *, segment_gated: bool) -> pd.Series:
    if segment_gated:
        return ~(_bool_series(calibration, "is_pre_activation") & calibration["activation_gate_eligible"].astype(bool))
    return _bool_series(calibration, "is_active_sellable", default=1)


def _activation_gate_summary(gate_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = list(gate_lookup.values())
    by_velocity: dict[str, dict[str, int]] = {}
    for row in rows:
        velocity = str(row.get("velocity_segment", "unknown"))
        current = by_velocity.setdefault(velocity, {"series": 0, "eligible_series": 0, "protected_series": 0})
        current["series"] += 1
        current["eligible_series"] += int(bool(row.get("eligible")))
        current["protected_series"] += int(bool(row.get("protected")))
    return {
        "series": len(rows),
        "eligible_series": sum(1 for row in rows if row.get("eligible")),
        "protected_series": sum(1 for row in rows if row.get("protected")),
        "late_activation_series": sum(1 for row in rows if row.get("late_activation")),
        "by_velocity_segment": by_velocity,
    }


def _active_model_config(config: DecisionExperimentConfig) -> dict[str, Any]:
    model_config = dict(config.model_config or {})
    hyperparameters = {
        "objective": model_config.get("objective", "poisson"),
        "n_estimators": 180,
        "learning_rate": 0.05,
        "num_leaves": 47,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "min_child_samples": 20,
        "random_state": config.random_state,
        **dict(model_config.get("hyperparameters") or {}),
    }
    hyperparameters["objective"] = str(hyperparameters.get("objective") or "poisson")
    return hyperparameters


def _active_calibration_config(config: DecisionExperimentConfig) -> dict[str, Any]:
    calibration = {
        "strategy": "category_velocity_bias",
        "clip_range": [0.75, 1.25],
        **dict(config.calibration_config or {}),
    }
    if calibration["strategy"] not in {"none", "global_bias", "category_velocity_bias"}:
        calibration["strategy"] = "category_velocity_bias"
    clip_range = calibration.get("clip_range") or [0.75, 1.25]
    calibration["clip_range"] = [float(clip_range[0]), float(clip_range[1])]
    return calibration


def _feature_columns_for_config(config: DecisionExperimentConfig) -> list[str]:
    cfg = _active_feature_config(config)
    columns: list[str] = []
    columns.extend(f"lag_{day}" for day in cfg["lag_days"])
    columns.extend(f"rolling_mean_{window}" for window in cfg["rolling_windows"])
    columns.extend(f"rolling_nonzero_{window}" for window in cfg["rolling_nonzero_windows"])
    if cfg["include_calendar"]:
        columns.extend(["day_of_week", "month", "week_of_year"])
    if cfg["include_product_codes"]:
        columns.extend(["store_code", "product_code", "category_code"])
    if cfg["include_price"]:
        columns.append("price")
    if cfg["include_price_momentum"]:
        columns.extend(["price_change_7", "price_index_28"])
    if cfg["include_promotion"]:
        columns.append("is_promotional")
    if cfg["include_promo_price_interaction"]:
        columns.append("promo_price_interaction")
    if cfg["include_holiday"]:
        columns.append("is_holiday")
    if cfg["include_intermittency"]:
        columns.extend(["zero_demand_rate_28", "days_since_nonzero"])
    return columns


def _build_feature_frame(frame: pd.DataFrame, *, config: DecisionExperimentConfig) -> pd.DataFrame:
    work = prepare_series_frame(frame)
    grouped = work.groupby(SERIES_KEYS)["quantity"]
    feature_config = _active_feature_config(config)
    for lag_day in feature_config["lag_days"]:
        work[f"lag_{lag_day}"] = grouped.shift(lag_day)
    for window in feature_config["rolling_windows"]:
        work[f"rolling_mean_{window}"] = grouped.transform(
            lambda s, size=window: s.shift(1).rolling(size, min_periods=1).mean()
        )
    for window in feature_config["rolling_nonzero_windows"]:
        work[f"rolling_nonzero_{window}"] = grouped.transform(
            lambda s, size=window: (s.shift(1) > 0).rolling(size, min_periods=1).mean()
        )
    work["day_of_week"] = work["date"].dt.dayofweek
    work["month"] = work["date"].dt.month
    work["week_of_year"] = work["date"].dt.isocalendar().week.astype(int)
    work["store_code"] = pd.factorize(work["store_id"])[0]
    work["product_code"] = pd.factorize(work["product_id"])[0]
    work["category_code"] = pd.factorize(work["category"].astype(str))[0]
    work["price"] = pd.to_numeric(work.get("price", 0.0), errors="coerce").fillna(0.0)
    price_grouped = work.groupby(SERIES_KEYS)["price"]
    prior_price_7 = price_grouped.shift(7).replace(0, np.nan)
    rolling_price_28 = price_grouped.transform(lambda s: s.shift(1).rolling(28, min_periods=1).mean()).replace(0, np.nan)
    work["price_change_7"] = ((work["price"] - prior_price_7) / prior_price_7).replace([np.inf, -np.inf], 0).fillna(0.0)
    work["price_index_28"] = (work["price"] / rolling_price_28).replace([np.inf, -np.inf], 1.0).fillna(1.0)
    work["is_promotional"] = pd.to_numeric(work.get("is_promotional", 0), errors="coerce").fillna(0).astype(int)
    work["promo_price_interaction"] = work["is_promotional"] * work["price"]
    work["is_holiday"] = pd.to_numeric(work.get("is_holiday", 0), errors="coerce").fillna(0).astype(int)
    work["zero_demand_rate_28"] = grouped.transform(
        lambda s: (s.shift(1) <= 0).rolling(28, min_periods=1).mean()
    )

    def days_since_nonzero(series: pd.Series) -> pd.Series:
        values = []
        last_seen: int | None = None
        for idx, quantity in enumerate(series.shift(1).fillna(0.0).to_numpy()):
            if quantity > 0:
                last_seen = idx
                values.append(0)
            elif last_seen is None:
                values.append(365)
            else:
                values.append(idx - last_seen)
        return pd.Series(values, index=series.index)

    work["days_since_nonzero"] = grouped.transform(days_since_nonzero)
    return work


def _fit_model_predictions(
    frame: pd.DataFrame,
    *,
    train_end: pd.Timestamp,
    predict_start: pd.Timestamp,
    config: DecisionExperimentConfig,
    output_col: str,
    train_row_mask: pd.Series | None = None,
) -> pd.DataFrame:
    try:
        import lightgbm as lgb
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ModuleNotFoundError("lightgbm is required for decision-aware experiments") from exc

    row_id_col = "__experiment_row_id"
    model_frame = frame.copy()
    model_frame[row_id_col] = np.arange(len(model_frame), dtype=np.int64)
    features = _build_feature_frame(model_frame, config=config)
    feature_cols = [col for col in _feature_columns_for_config(config) if col in features.columns]
    train_mask = features["date"] < train_end
    if train_row_mask is not None:
        mask_by_row_id = pd.Series(train_row_mask.astype(bool).to_numpy(), index=model_frame[row_id_col])
        aligned_mask = features[row_id_col].map(mask_by_row_id).fillna(False).astype(bool)
        train_mask = train_mask & aligned_mask
    required_lags = [col for col in [f"lag_{day}" for day in _active_feature_config(config)["lag_days"]] if col in feature_cols]
    drop_subset = required_lags[-2:] if len(required_lags) >= 2 else required_lags
    train_df = features.loc[train_mask].dropna(subset=drop_subset).copy() if drop_subset else features.loc[train_mask].copy()
    if train_df.empty:
        fallback_mask = features["date"] < train_end
        train_df = features.loc[fallback_mask].dropna(subset=drop_subset).copy() if drop_subset else features.loc[fallback_mask].copy()
    predict_df = features.loc[features["date"] >= predict_start].copy()

    model_params = _active_model_config(config)
    model = lgb.LGBMRegressor(
        objective=model_params["objective"],
        n_estimators=int(model_params["n_estimators"]),
        learning_rate=float(model_params["learning_rate"]),
        num_leaves=int(model_params["num_leaves"]),
        min_child_samples=int(model_params["min_child_samples"]),
        subsample=float(model_params["subsample"]),
        colsample_bytree=float(model_params["colsample_bytree"]),
        random_state=int(model_params["random_state"]),
        verbosity=-1,
    )
    model.fit(train_df[feature_cols].fillna(0.0), train_df["quantity"].astype(float))
    preds = model.predict(predict_df[feature_cols].fillna(0.0))
    out = predict_df.copy()
    out[output_col] = np.maximum(preds, 0.0)
    return out


def _velocity_lookup(train: pd.DataFrame) -> dict[str, str]:
    summary = train.groupby("series_id")["quantity"].mean()
    if summary.empty:
        return {}
    q33 = float(summary.quantile(0.33))
    q66 = float(summary.quantile(0.66))

    def label(value: float) -> str:
        if value >= q66:
            return "fast"
        if value >= q33:
            return "medium"
        return "slow"

    return {str(series_id): label(float(avg)) for series_id, avg in summary.items()}


def _fit_bias_adjustments(
    calibration: pd.DataFrame,
    *,
    strategy: str = "category_velocity_bias",
    clip_range: list[float] | tuple[float, float] = (0.75, 1.25),
    pred_col: str = "forecast_champion",
) -> dict[str, Any]:
    work = calibration.copy()
    work[pred_col] = pd.to_numeric(work[pred_col], errors="coerce").fillna(0.0)
    work["quantity"] = pd.to_numeric(work["quantity"], errors="coerce").fillna(0.0)
    low, high = float(clip_range[0]), float(clip_range[1])

    if strategy == "none":
        return {
            "global": 1.0,
            "by_category_velocity": {},
            "by_category": {},
            "clip_range": [1.0, 1.0],
            "method": "no_calibration",
        }

    def ratio(group: pd.DataFrame) -> float:
        predicted = float(group[pred_col].sum())
        actual = float(group["quantity"].sum())
        if predicted <= 0:
            return 1.0
        return float(np.clip(actual / predicted, low, high))

    global_adjustment = ratio(work)
    by_category_velocity: dict[str, float] = {}
    by_category: dict[str, float] = {}
    if strategy == "category_velocity_bias":
        by_category_velocity = {
            f"{category}::{velocity}": ratio(group)
            for (category, velocity), group in work.groupby(["category", "velocity_segment"], dropna=False)
        }
        by_category = {str(category): ratio(group) for category, group in work.groupby("category", dropna=False)}

    return {
        "global": global_adjustment,
        "by_category_velocity": by_category_velocity,
        "by_category": by_category,
        "clip_range": [low, high],
        "method": f"{strategy}_calibration_window_actual_to_predicted_ratio",
    }


def _apply_bias_adjustments(
    frame: pd.DataFrame,
    adjustments: dict[str, Any],
    *,
    pred_col: str = "forecast_champion",
) -> pd.Series:
    global_adjustment = float(adjustments.get("global") or 1.0)
    by_category_velocity = dict(adjustments.get("by_category_velocity") or {})
    by_category = dict(adjustments.get("by_category") or {})

    factors = []
    for row in frame.itertuples(index=False):
        category = str(getattr(row, "category"))
        velocity = str(getattr(row, "velocity_segment"))
        factors.append(by_category_velocity.get(f"{category}::{velocity}", by_category.get(category, global_adjustment)))
    factor_series = pd.Series(factors, index=frame.index, dtype="float64")
    return (pd.to_numeric(frame[pred_col], errors="coerce").fillna(0.0) * factor_series).clip(lower=0.0)


def _interval_metrics(
    calibration: pd.DataFrame,
    holdout: pd.DataFrame,
    *,
    pred_col: str,
    quantile: float = 0.9,
) -> dict[str, float | str]:
    residuals = (calibration["quantity"].astype(float) - calibration[pred_col].astype(float)).abs()
    residual_quantile = float(residuals.quantile(quantile)) if len(residuals) else 0.0
    lower = (holdout[pred_col].astype(float) - residual_quantile).clip(lower=0.0)
    upper = holdout[pred_col].astype(float) + residual_quantile
    actual = holdout["quantity"].astype(float)
    coverage = float(((actual >= lower) & (actual <= upper)).mean()) if len(actual) else 0.0
    width = float((upper - lower).mean()) if len(actual) else 0.0
    return {
        "interval_method": "split_conformal_abs_residual_q90",
        "interval_provenance": "benchmark",
        "coverage": coverage,
        "interval_coverage": coverage,
        "avg_interval_width": width,
        "residual_quantile": residual_quantile,
        "target_coverage": quantile,
    }


def _forecast_metrics(frame: pd.DataFrame, *, pred_col: str, interval: dict[str, Any] | None = None) -> dict[str, Any]:
    if frame.empty:
        return {
            "mae": None,
            "mape_nonzero": None,
            "mape": None,
            "wape": None,
            "mase": None,
            "bias_pct": None,
            "stockout_miss_rate": None,
            "overstock_rate": None,
            "overstock_dollars": None,
            "lost_sales_qty": None,
            "opportunity_cost_stockout": None,
            "opportunity_cost_overstock": None,
            "evaluation_rows": 0,
            "provenance": "benchmark",
            "metric_status": "unavailable_empty_slice",
        }
    metrics = compute_forecast_metrics(
        frame["quantity"],
        frame[pred_col],
        unit_cost=frame["unit_cost"],
        unit_price=frame["price"],
        holding_cost_per_unit_per_day=frame["holding_cost_per_unit_per_day"],
        category=frame["category"],
    )
    metrics["mape"] = metrics.get("mape_nonzero")
    metrics["evaluation_rows"] = int(len(frame))
    if interval:
        metrics.update(interval)
    metrics["provenance"] = "benchmark"
    metrics["cost_basis_provenance"] = "estimated_from_m5_sell_price_and_margin_assumption"
    for key in (
        "overstock_dollars_confidence",
        "opportunity_cost_stockout_confidence",
        "opportunity_cost_overstock_confidence",
    ):
        if metrics.get(key) in {"measured", "estimated"}:
            metrics[key] = "estimated"
    return _json_safe(metrics)


def _segment_metrics(frame: pd.DataFrame, *, pred_col: str) -> dict[str, Any]:
    eval_frame = frame.copy().reset_index(drop=True)
    eval_frame["predicted_qty"] = pd.to_numeric(eval_frame[pred_col], errors="coerce").fillna(0.0)
    raw = evaluate_predictions(eval_frame, predicted_col="predicted_qty").get("segment_metrics", {})
    compact: dict[str, Any] = {}
    for name, payload in raw.items():
        metrics = payload.get("metrics") or {}
        compact[name] = {
            "available": bool(payload.get("available")),
            "sample_rows": int(payload.get("sample_rows") or 0),
            "low_sample": bool(payload.get("low_sample")),
            "metrics": {
                key: metrics.get(key)
                for key in ["mae", "wape", "mase", "bias_pct", "stockout_miss_rate", "overstock_rate"]
                if key in metrics
            }
            if metrics
            else None,
        }
    return _json_safe(compact)


def _policy_results_to_map(results: list[PolicyResult]) -> dict[str, dict[str, Any]]:
    return {row.policy_name: _json_safe(asdict(row)) for row in results}


def _decision_replay(
    history: pd.DataFrame,
    holdout: pd.DataFrame,
    *,
    config: DecisionExperimentConfig,
) -> dict[str, Any]:
    replay = holdout.copy().sort_values(["series_id", "date"]).reset_index(drop=True)
    static = history.groupby("series_id")["quantity"].mean().rename("forecast_static")
    replay = replay.merge(static, on="series_id", how="left")
    replay["forecast_static"] = replay["forecast_static"].fillna(float(history["quantity"].mean()))
    replay["forecast_moving_average"] = replay["forecast_moving_average"].fillna(replay["forecast_static"])

    sim_config = SimulationConfig(
        dataset_id=config.dataset_id,
        model_version=config.baseline_version,
        policy_version="replenishment_v1",
        lead_time_days=config.lead_time_days,
        safety_stock_days=config.safety_stock_days,
        order_up_to_days=config.order_up_to_days,
        initial_inventory_days=config.initial_inventory_days,
        order_cost=config.order_cost,
        holding_cost_rate_annual=config.holding_cost_rate_annual,
        replay_days=config.holdout_days,
        warmup_days=max(28, config.calibration_days),
        max_series=config.max_series,
    )
    results = [
        _simulate_policy(replay, forecast_col="forecast_moving_average", config=sim_config),
        _simulate_policy(replay, forecast_col="forecast_champion", config=sim_config),
        _simulate_policy(replay, forecast_col="forecast_challenger", config=sim_config),
    ]
    return {
        "simulation_scope": "benchmark_replay",
        "impact_confidence": "simulated",
        "inventory_assumptions_confidence": "simulated",
        "po_assumptions_confidence": "simulated",
        "lead_time_assumptions_confidence": "simulated",
        "cost_assumptions_confidence": "simulated",
        "claim_boundary": "Benchmark simulation only. Not measured merchant impact.",
        "policy_version": sim_config.policy_version,
        "config": _json_safe(asdict(sim_config)),
        "results": _policy_results_to_map(results),
    }


def _promotion_comparison(
    *,
    champion_metrics: dict[str, Any],
    challenger_metrics: dict[str, Any],
    decision_replay: dict[str, Any],
) -> dict[str, Any]:
    arena = compare_candidate_vs_champion_metrics(champion_metrics, challenger_metrics)
    decision_results = decision_replay["results"]
    champion_decision = decision_results["champion"]
    challenger_decision = decision_results["challenger"]

    champion_cost = float(champion_decision["combined_cost_proxy"])
    challenger_cost = float(challenger_decision["combined_cost_proxy"])
    champion_service = float(champion_decision["service_level"])
    challenger_service = float(challenger_decision["service_level"])

    decision_cost_gate = challenger_cost <= champion_cost * 1.02 if champion_cost > 0 else challenger_cost <= champion_cost
    service_level_gate = challenger_service >= champion_service - 0.005
    simulated_evidence_gate = False
    gate_checks = {
        **dict(arena.get("gate_checks") or {}),
        "decision_combined_cost_proxy_gate": decision_cost_gate,
        "decision_service_level_gate": service_level_gate,
        "measured_pilot_outcome_gate": simulated_evidence_gate,
    }
    benchmark_gates_passed = all(value for key, value in gate_checks.items() if key != "measured_pilot_outcome_gate")
    failed = [key for key, value in gate_checks.items() if not value]
    if benchmark_gates_passed:
        reason = "benchmark_gates_passed_but_measured_pilot_outcomes_unavailable"
    else:
        reason = "failed_gates:" + ",".join(failed)

    return {
        "promoted": False,
        "benchmark_gates_passed": benchmark_gates_passed,
        "decision": "continue_shadow_review",
        "reason": reason,
        "gate_checks": gate_checks,
        "arena_comparison": arena,
        "claim_boundary": "Promotion is blocked until measured pilot outcomes exist; M5 decision replay is simulated.",
        "champion_decision_metrics": champion_decision,
        "challenger_decision_metrics": challenger_decision,
    }


def _build_decision_experiment_report(
    *,
    frame: pd.DataFrame,
    dataset_snapshot: dict[str, Any],
    active_config: DecisionExperimentConfig,
    holdout_end: pd.Timestamp | None = None,
    window_label: str | None = None,
) -> dict[str, Any]:
    train, calibration, holdout = _time_split(frame, config=active_config, holdout_end=holdout_end)
    combined = pd.concat([train, calibration, holdout], ignore_index=True)
    train_end = pd.to_datetime(calibration["date"].min())
    predict_start = train_end
    dataset_config = _active_dataset_config(active_config)
    activation_aware = _is_activation_aware(active_config)
    segment_gated_activation = _is_segment_gated_activation(active_config)
    segment_routed_activation = _is_segment_routed_activation(active_config)
    velocity_lookup = _velocity_lookup(train)
    combined["velocity_segment"] = combined["series_id"].map(velocity_lookup).fillna("unknown")
    gate_lookup = (
        _activation_gate_lookup(train, dataset_config=dataset_config, velocity_lookup=velocity_lookup)
        if segment_gated_activation
        else {}
    )
    combined = _attach_activation_gate_columns(combined, gate_lookup=gate_lookup)
    challenger_train_mask = (
        _activation_train_mask(combined, segment_gated=segment_gated_activation) if activation_aware else None
    )
    train_region_mask = combined["date"] < train_end
    calibration_region_mask = (combined["date"] >= train_end) & (combined["date"] < pd.to_datetime(holdout["date"].min()))
    excluded_train_mask = (
        train_region_mask & ~challenger_train_mask if activation_aware and challenger_train_mask is not None else None
    )
    calibration_policy = dataset_config.get("calibration_policy")
    excluded_calibration_mask: pd.Series | None = None
    if activation_aware and calibration_policy in {
        "exclude_pre_activation_from_calibration",
        "exclude_pre_activation_for_eligible_segments",
    }:
        excluded_calibration_mask = calibration_region_mask & ~_activation_calibration_mask(
            combined,
            segment_gated=segment_gated_activation,
        )

    prediction_frame = _fit_model_predictions(
        combined,
        train_end=train_end,
        predict_start=predict_start,
        config=active_config,
        output_col="forecast_champion",
    )
    if activation_aware:
        challenger_predictions = _fit_model_predictions(
            combined,
            train_end=train_end,
            predict_start=predict_start,
            config=active_config,
            output_col="forecast_challenger_raw",
            train_row_mask=challenger_train_mask,
        )
        prediction_frame = prediction_frame.merge(
            challenger_predictions[SERIES_KEYS + ["date", "forecast_challenger_raw"]],
            on=SERIES_KEYS + ["date"],
            how="left",
        )
        prediction_frame["forecast_challenger_raw"] = prediction_frame["forecast_challenger_raw"].fillna(
            prediction_frame["forecast_champion"]
        )
        challenger_base_col = "forecast_challenger_raw"
    else:
        prediction_frame["forecast_challenger_raw"] = prediction_frame["forecast_champion"]
        challenger_base_col = "forecast_champion"

    prediction_frame["velocity_segment"] = prediction_frame["series_id"].map(velocity_lookup).fillna("unknown")
    if segment_routed_activation:
        routed_eligible_mask = prediction_frame["activation_gate_eligible"].astype(bool)
        prediction_frame["forecast_challenger_routed_raw"] = np.where(
            routed_eligible_mask,
            prediction_frame["forecast_challenger_raw"],
            prediction_frame["forecast_champion"],
        )
        challenger_base_col = "forecast_challenger_routed_raw"

    calibration_pred = prediction_frame[prediction_frame["date"].isin(calibration["date"].unique())].copy()
    holdout_pred = prediction_frame[prediction_frame["date"].isin(holdout["date"].unique())].copy()
    calibration_config = _active_calibration_config(active_config)
    calibration_for_adjustment = calibration_pred
    if segment_routed_activation and dataset_config.get("calibration_scope") == "eligible_segments_only":
        calibration_for_adjustment = calibration_pred[
            calibration_pred["activation_gate_eligible"].astype(bool)
            & _activation_calibration_mask(calibration_pred, segment_gated=segment_gated_activation)
        ].copy()
        if calibration_for_adjustment.empty:
            calibration_for_adjustment = calibration_pred[
                _activation_calibration_mask(calibration_pred, segment_gated=segment_gated_activation)
            ].copy()
        if calibration_for_adjustment.empty:
            calibration_for_adjustment = calibration_pred
    elif activation_aware and dataset_config.get("calibration_policy") in {
        "exclude_pre_activation_from_calibration",
        "exclude_pre_activation_for_eligible_segments",
    }:
        calibration_for_adjustment = calibration_pred[
            _activation_calibration_mask(calibration_pred, segment_gated=segment_gated_activation)
        ].copy()
        if calibration_for_adjustment.empty:
            calibration_for_adjustment = calibration_pred
    adjustments = _fit_bias_adjustments(
        calibration_for_adjustment,
        strategy=str(calibration_config["strategy"]),
        clip_range=calibration_config["clip_range"],
        pred_col=challenger_base_col,
    )
    calibration_pred["forecast_challenger_calibrated"] = _apply_bias_adjustments(
        calibration_pred,
        adjustments,
        pred_col=challenger_base_col,
    )
    holdout_pred["forecast_challenger_calibrated"] = _apply_bias_adjustments(
        holdout_pred,
        adjustments,
        pred_col=challenger_base_col,
    )
    if segment_routed_activation:
        calibration_route_mask = calibration_pred["activation_gate_eligible"].astype(bool)
        holdout_route_mask = holdout_pred["activation_gate_eligible"].astype(bool)
        calibration_pred["forecast_challenger"] = np.where(
            calibration_route_mask,
            calibration_pred["forecast_challenger_calibrated"],
            calibration_pred["forecast_champion"],
        )
        holdout_pred["forecast_challenger"] = np.where(
            holdout_route_mask,
            holdout_pred["forecast_challenger_calibrated"],
            holdout_pred["forecast_champion"],
        )
    else:
        calibration_pred["forecast_challenger"] = calibration_pred["forecast_challenger_calibrated"]
        holdout_pred["forecast_challenger"] = holdout_pred["forecast_challenger_calibrated"]

    calibration_for_interval = calibration_pred
    if segment_routed_activation:
        calibration_for_interval = calibration_pred
    elif activation_aware and dataset_config.get("calibration_policy") in {
        "exclude_pre_activation_from_calibration",
        "exclude_pre_activation_for_eligible_segments",
    }:
        calibration_for_interval = calibration_pred[
            _activation_calibration_mask(calibration_pred, segment_gated=segment_gated_activation)
        ].copy()
        if calibration_for_interval.empty:
            calibration_for_interval = calibration_pred

    moving_average_history = pd.concat([train, calibration], ignore_index=True)
    holdout_pred["forecast_moving_average"] = moving_average_forecast(moving_average_history, holdout_pred).to_numpy()

    primary_holdout_pred = holdout_pred
    if dataset_config.get("primary_metric_filter") == "active_holdout_rows":
        primary_holdout_pred = holdout_pred[
            pd.to_numeric(holdout_pred.get("is_active_sellable", 1), errors="coerce").fillna(1).astype(int) == 1
        ].copy()
        if primary_holdout_pred.empty:
            primary_holdout_pred = holdout_pred

    champion_interval = _interval_metrics(calibration_pred, primary_holdout_pred, pred_col="forecast_champion")
    challenger_interval = _interval_metrics(
        calibration_for_interval,
        primary_holdout_pred,
        pred_col="forecast_challenger",
    )

    moving_average_metrics = _forecast_metrics(primary_holdout_pred, pred_col="forecast_moving_average")
    champion_metrics = _forecast_metrics(primary_holdout_pred, pred_col="forecast_champion", interval=champion_interval)
    challenger_metrics = _forecast_metrics(
        primary_holdout_pred,
        pred_col="forecast_challenger",
        interval=challenger_interval,
    )
    guardrail_champion_metrics = _forecast_metrics(holdout_pred, pred_col="forecast_champion")
    guardrail_challenger_metrics = _forecast_metrics(holdout_pred, pred_col="forecast_challenger")
    for metrics in (moving_average_metrics, champion_metrics, challenger_metrics):
        metrics["metric_scope"] = "primary_holdout"
        metrics["primary_metric_filter"] = dataset_config.get("primary_metric_filter")
    for metrics in (guardrail_champion_metrics, guardrail_challenger_metrics):
        metrics["metric_scope"] = "canonical_holdout_guardrail"
        metrics["primary_metric_filter"] = "all_holdout_rows"

    active_holdout = holdout_pred[
        pd.to_numeric(holdout_pred.get("is_active_sellable", 1), errors="coerce").fillna(1).astype(int) == 1
    ].copy()
    pre_activation_holdout = holdout_pred[
        pd.to_numeric(holdout_pred.get("is_pre_activation", 0), errors="coerce").fillna(0).astype(int) == 1
    ].copy()
    late_activation_active_holdout = holdout_pred[
        (
            pd.to_numeric(holdout_pred.get("is_late_activation", 0), errors="coerce").fillna(0).astype(int) == 1
        )
        & (
            pd.to_numeric(holdout_pred.get("is_active_sellable", 1), errors="coerce").fillna(1).astype(int) == 1
        )
    ].copy()
    routed_challenger_holdout = holdout_pred[
        holdout_pred.get("activation_gate_eligible", False).astype(bool)
    ].copy()
    routed_champion_holdout = holdout_pred[
        ~holdout_pred.get("activation_gate_eligible", False).astype(bool)
    ].copy()

    def evaluation_slice(slice_frame: pd.DataFrame, *, primary: bool = False) -> dict[str, Any]:
        return {
            "rows": int(len(slice_frame)),
            "primary": bool(primary),
            "baseline": _forecast_metrics(slice_frame, pred_col="forecast_champion"),
            "challenger": _forecast_metrics(slice_frame, pred_col="forecast_challenger"),
        }

    evaluation_slices = {
        "primary_holdout": evaluation_slice(primary_holdout_pred, primary=True),
        "canonical_holdout_guardrail": {
            **evaluation_slice(holdout_pred),
            "guardrail": True,
        },
        "active_holdout": evaluation_slice(active_holdout),
        "late_activation_active_holdout": evaluation_slice(late_activation_active_holdout),
        "routed_challenger_holdout": {
            **evaluation_slice(routed_challenger_holdout),
            "routing_role": "activation_challenger" if segment_routed_activation else "not_applicable",
        },
        "routed_champion_holdout": {
            **evaluation_slice(routed_champion_holdout),
            "routing_role": "champion_passthrough" if segment_routed_activation else "not_applicable",
        },
        "pre_activation_holdout_reported_not_primary": {
            **evaluation_slice(pre_activation_holdout),
            "excluded_from_primary": dataset_config.get("primary_metric_filter") == "active_holdout_rows",
        },
    }

    train_pre_activation_mask = train_region_mask & _bool_series(combined, "is_pre_activation")
    eligible_train_pre_activation_mask = train_pre_activation_mask & combined["activation_gate_eligible"].astype(bool)
    protected_train_pre_activation_mask = train_pre_activation_mask & combined["activation_gate_protected"].astype(bool)
    non_eligible_train_pre_activation_mask = train_pre_activation_mask & ~combined["activation_gate_eligible"].astype(bool)

    training_rows_excluded = int(excluded_train_mask.sum()) if excluded_train_mask is not None else 0
    calibration_rows_excluded = int(excluded_calibration_mask.sum()) if excluded_calibration_mask is not None else 0
    affected_series = (
        int(combined.loc[excluded_train_mask, "series_id"].nunique())
        if excluded_train_mask is not None and training_rows_excluded
        else 0
    )

    training_policy_by_segment: dict[str, dict[str, int]] = {}
    if activation_aware:
        train_policy_frame = combined.loc[train_region_mask, ["velocity_segment", "series_id"]].copy()
        train_policy_frame["pre_activation_rows"] = train_pre_activation_mask.loc[train_region_mask].astype(int).to_numpy()
        train_policy_frame["eligible_pre_activation_rows"] = (
            eligible_train_pre_activation_mask.loc[train_region_mask].astype(int).to_numpy()
        )
        train_policy_frame["protected_pre_activation_rows"] = (
            protected_train_pre_activation_mask.loc[train_region_mask].astype(int).to_numpy()
        )
        train_policy_frame["training_rows_excluded"] = (
            excluded_train_mask.loc[train_region_mask].astype(int).to_numpy()
            if excluded_train_mask is not None
            else 0
        )
        for velocity, group in train_policy_frame.groupby("velocity_segment", dropna=False):
            training_policy_by_segment[str(velocity)] = {
                "series": int(group["series_id"].nunique()),
                "rows": int(len(group)),
                "pre_activation_rows": int(group["pre_activation_rows"].sum()),
                "eligible_pre_activation_rows": int(group["eligible_pre_activation_rows"].sum()),
                "protected_pre_activation_rows": int(group["protected_pre_activation_rows"].sum()),
                "training_rows_excluded": int(group["training_rows_excluded"].sum()),
            }

    routing_policy_by_segment: dict[str, dict[str, int]] = {}
    if segment_routed_activation:
        route_frame = holdout_pred[["velocity_segment", "series_id", "activation_gate_eligible"]].copy()
        route_frame["routed_challenger_rows"] = route_frame["activation_gate_eligible"].astype(int)
        route_frame["routed_champion_rows"] = (~route_frame["activation_gate_eligible"].astype(bool)).astype(int)
        for velocity, group in route_frame.groupby("velocity_segment", dropna=False):
            routing_policy_by_segment[str(velocity)] = {
                "series": int(group["series_id"].nunique()),
                "rows": int(len(group)),
                "routed_challenger_rows": int(group["routed_challenger_rows"].sum()),
                "routed_champion_rows": int(group["routed_champion_rows"].sum()),
            }

    activation_policy = {
        "enabled": bool(activation_aware),
        "dataset_config": dataset_config,
        "policy_type": dataset_config.get("activation_policy"),
        "segment_gated": bool(segment_gated_activation),
        "segment_routed": bool(segment_routed_activation),
        "prediction_routing_policy": dataset_config.get("prediction_routing_policy"),
        "calibration_scope": dataset_config.get("calibration_scope"),
        "activation_marker": dataset_config.get("activation_marker"),
        "training_rows_excluded": training_rows_excluded,
        "calibration_rows_excluded": calibration_rows_excluded,
        "candidate_pre_activation_training_rows": int(train_pre_activation_mask.sum()) if activation_aware else 0,
        "eligible_pre_activation_training_rows": int(eligible_train_pre_activation_mask.sum())
        if activation_aware
        else 0,
        "protected_pre_activation_training_rows": int(protected_train_pre_activation_mask.sum())
        if activation_aware
        else 0,
        "non_eligible_pre_activation_training_rows": int(non_eligible_train_pre_activation_mask.sum())
        if activation_aware
        else 0,
        "training_policy_by_segment": training_policy_by_segment,
        "activation_gate_summary": _activation_gate_summary(gate_lookup) if segment_gated_activation else None,
        "routing_policy_by_segment": routing_policy_by_segment,
        "routed_challenger_holdout_rows": int(len(routed_challenger_holdout)) if segment_routed_activation else 0,
        "routed_champion_holdout_rows": int(len(routed_champion_holdout)) if segment_routed_activation else 0,
        "holdout_rows": int(len(holdout_pred)),
        "holdout_active_rows": int(len(active_holdout)),
        "holdout_pre_activation_rows": int(len(pre_activation_holdout)),
        "late_activation_holdout_active_rows": int(len(late_activation_active_holdout)),
        "affected_series": affected_series,
        "evaluation_policy": {
            "primary_metric_filter": dataset_config.get("primary_metric_filter"),
            "guardrail_metric_filter": dataset_config.get("guardrail_metric_filter"),
            "preserve_canonical_holdout": bool(dataset_config.get("preserve_canonical_holdout", True)),
        },
        "claim_boundary": (
            "Activation-aware evidence uses first available sell price as the sellable marker. "
            "Segment-routed activation uses challenger forecasts only for eligible segments and preserves "
            "champion forecasts for protected segments. Raw M5 rows remain unchanged; canonical holdout is "
            "retained as a guardrail."
            if segment_routed_activation
            else "Activation-aware evidence uses first available sell price as the sellable marker. "
            "Segment-gated activation filters are applied only to the challenger training/calibration "
            "rows declared eligible by the spec. Raw M5 rows remain unchanged; canonical holdout is "
            "retained as a guardrail."
            if segment_gated_activation
            else "Activation-aware evidence uses first available sell price as the sellable marker. "
            "Raw M5 rows remain unchanged; canonical holdout is retained as a guardrail."
        ),
        "provenance": "benchmark",
    }

    decision_replay = _decision_replay(moving_average_history, holdout_pred, config=active_config)
    comparison = _promotion_comparison(
        champion_metrics=champion_metrics,
        challenger_metrics=challenger_metrics,
        decision_replay=decision_replay,
    )

    model_config = _active_model_config(active_config)
    feature_config = _active_feature_config(active_config)
    feature_columns = _feature_columns_for_config(active_config)
    lineage_metadata = {
        "dataset_id": active_config.dataset_id,
        "dataset_snapshot_id": dataset_snapshot["snapshot_id"],
        "experiment_spec_id": active_config.experiment_spec_id,
        "experiment_spec_hash": active_config.experiment_spec_hash,
        "spec_template_id": active_config.spec_template_id,
        "spec_name": active_config.spec_name,
        "feature_set_id": active_config.feature_set_id,
        "segment_strategy": (
            active_config.segmentation_config.get("strategy")
            if active_config.segmentation_config
            else "store_product_velocity_and_category_bias_calibration"
        ),
        "feature_tier": "benchmark",
        "architecture": (
            "lightgbm_plus_segment_routed_activation_policy_plus_calibrated_post_processing"
            if segment_routed_activation
            else (
                "lightgbm_plus_segment_gated_activation_window_plus_calibrated_post_processing"
                if segment_gated_activation
                else (
                    "lightgbm_plus_activation_window_plus_calibrated_post_processing"
                    if activation_aware
                    else "lightgbm_plus_calibrated_post_processing"
                )
            )
        ),
        "objective": f"{model_config['objective']}_demand_forecast",
        "feature_columns": feature_columns,
        "feature_config": feature_config,
        "dataset_config": dataset_config,
        "model_config": {
            "architecture": "lightgbm",
            "objective": model_config["objective"],
            "hyperparameters": {
                key: model_config[key]
                for key in [
                    "n_estimators",
                    "learning_rate",
                    "num_leaves",
                    "min_child_samples",
                    "subsample",
                    "colsample_bytree",
                    "random_state",
                ]
                if key in model_config
            },
        },
        "calibration_config": calibration_config,
        "validation_mode": active_config.validation_mode,
        "provenance": "benchmark",
        "claim_boundary": "Benchmark evidence only. No measured merchant ROI.",
    }

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(DEFAULT_DATA_DIR),
        "experiment": {
            "experiment_name": active_config.experiment_name,
            "hypothesis": active_config.hypothesis,
            "experiment_type": active_config.experiment_type,
            "model_name": active_config.model_name,
            "baseline_version": active_config.baseline_version,
            "experimental_version": active_config.challenger_version,
            "decision": comparison["decision"],
            "decision_rationale": comparison["reason"],
            "lineage_metadata": lineage_metadata,
        },
        "dataset": {
            **dataset_snapshot,
            "dataset_snapshot_id": dataset_snapshot["snapshot_id"],
            "provenance": "benchmark",
            "rows_used": int(len(frame)),
            "series_used": int(frame["series_id"].nunique()),
            "stores_used": int(frame["store_id"].nunique()),
            "products_used": int(frame["product_id"].nunique()),
            "train_start": str(train["date"].min().date()),
            "train_end": str(train["date"].max().date()),
            "calibration_start": str(calibration["date"].min().date()),
            "calibration_end": str(calibration["date"].max().date()),
            "holdout_start": str(holdout["date"].min().date()),
            "holdout_end": str(holdout["date"].max().date()),
        },
        "validation": {
            "mode": active_config.validation_mode,
            "window_label": window_label or "primary",
            "calibration_days": active_config.calibration_days,
            "holdout_days": active_config.holdout_days,
            "rolling_window_count": active_config.rolling_window_count,
            "rolling_window_days": active_config.rolling_window_days,
            "rolling_stride_days": active_config.rolling_stride_days,
            "purpose": _validation_mode_purpose(active_config.validation_mode),
        },
        "lineage_metadata": lineage_metadata,
        "experiment_spec": {
            "experiment_spec_id": active_config.experiment_spec_id,
            "spec_hash": active_config.experiment_spec_hash,
            "template_id": active_config.spec_template_id,
            "spec_name": active_config.spec_name,
            "feature_set_id": active_config.feature_set_id,
            "feature_columns": feature_columns,
            "dataset_config": dataset_config,
            "provenance": "benchmark",
        },
        "baselines": {
            "moving_average_7": {
                "version": "moving_average_7",
                "holdout_metrics": moving_average_metrics,
                "lineage_metadata": {"provenance": "benchmark", "feature_tier": "baseline"},
            }
        },
        "baseline": {
            "version": active_config.baseline_version,
            "holdout_metrics": champion_metrics,
            "guardrail_holdout_metrics": guardrail_champion_metrics,
            "segment_metrics": _segment_metrics(primary_holdout_pred, pred_col="forecast_champion"),
            "lineage_metadata": lineage_metadata,
        },
        "challenger": {
            "version": active_config.challenger_version,
            "holdout_metrics": challenger_metrics,
            "guardrail_holdout_metrics": guardrail_challenger_metrics,
            "segment_metrics": _segment_metrics(primary_holdout_pred, pred_col="forecast_challenger"),
            "calibration_adjustments": _json_safe(adjustments),
            "lineage_metadata": {
                **lineage_metadata,
                "post_processing": "category_velocity_bias_calibration",
                "calibration_window_days": active_config.calibration_days,
            },
        },
        "activation_policy": activation_policy,
        "evaluation_slices": evaluation_slices,
        "decision_replay": decision_replay,
        "promotion_comparison": comparison,
        "comparison": comparison,
        "overall_business_safe": bool(comparison["benchmark_gates_passed"]),
        "claim_boundary": "M5/Walmart benchmark evidence with simulated replenishment replay; not measured merchant impact.",
        "limitations": [
            "M5 has sales and price history but no true inventory position, supplier lead time, purchase orders, or buyer decisions.",
            "Unit cost, order cost, holding cost, stockout cost, and replenishment outcomes are simulated proxy values.",
            "Promotion remains shadow-only until measured pilot outcomes arrive from CSV or Square merchant data.",
        ],
        "config": _json_safe(asdict(active_config)),
    }
    return _json_safe(report)


def _validation_mode_purpose(mode: str) -> str:
    if mode == "extended_backtest":
        return "Multi-window temporal robustness check for promising hypotheses."
    if mode == "promotion_gate":
        return "Stricter multi-window validation before a challenger is promotion-worthy."
    return "Fast single-window hypothesis screen."


def _metric_float(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    try:
        if value is None:
            return None
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def _average(values: list[float | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    return float(np.mean(cleaned)) if cleaned else None


def _max_value(values: list[float | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    return max(cleaned) if cleaned else None


def _min_value(values: list[float | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    return min(cleaned) if cleaned else None


def _extract_policy_metric(report: dict[str, Any], policy: str, metric: str) -> float | None:
    value = (((report.get("decision_replay") or {}).get("results") or {}).get(policy) or {}).get(metric)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rolling_holdout_ends(frame: pd.DataFrame, *, config: DecisionExperimentConfig) -> list[pd.Timestamp]:
    unique_dates = sorted(pd.to_datetime(frame["date"]).dropna().unique().tolist())
    if not unique_dates:
        return []
    latest = pd.to_datetime(unique_dates[-1])
    ends: list[pd.Timestamp] = []
    for idx in range(max(0, int(config.rolling_window_count))):
        target = latest - timedelta(days=idx * int(config.rolling_stride_days))
        eligible = [pd.to_datetime(current_date) for current_date in unique_dates if pd.to_datetime(current_date) <= target]
        if not eligible:
            continue
        candidate = eligible[-1]
        if candidate not in ends:
            ends.append(candidate)
    return ends


def _rolling_validation_summary(
    *,
    frame: pd.DataFrame,
    dataset_snapshot: dict[str, Any],
    active_config: DecisionExperimentConfig,
) -> dict[str, Any] | None:
    if active_config.validation_mode == "quick_screen" and active_config.rolling_window_count <= 0:
        return None

    rolling_config = replace(active_config, holdout_days=active_config.rolling_window_days)
    window_reports: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for idx, holdout_end in enumerate(_rolling_holdout_ends(frame, config=rolling_config), start=1):
        try:
            window_reports.append(
                _build_decision_experiment_report(
                    frame=frame,
                    dataset_snapshot=dataset_snapshot,
                    active_config=rolling_config,
                    holdout_end=holdout_end,
                    window_label=f"rolling_{idx}",
                )
            )
        except ValueError as exc:
            skipped.append({"holdout_end": holdout_end.date().isoformat(), "reason": str(exc)})

    if not window_reports:
        if active_config.validation_mode in {"extended_backtest", "promotion_gate"}:
            raise ValueError("No valid rolling validation windows could be generated for this dataset and config")
        return None

    windows: list[dict[str, Any]] = []
    for idx, report in enumerate(window_reports, start=1):
        baseline_metrics = report["baseline"]["holdout_metrics"]
        challenger_metrics = report["challenger"]["holdout_metrics"]
        windows.append(
            {
                "window": idx,
                "train_start": report["dataset"]["train_start"],
                "train_end": report["dataset"]["train_end"],
                "calibration_start": report["dataset"]["calibration_start"],
                "calibration_end": report["dataset"]["calibration_end"],
                "holdout_start": report["dataset"]["holdout_start"],
                "holdout_end": report["dataset"]["holdout_end"],
                "baseline": {
                    key: baseline_metrics.get(key)
                    for key in ["mae", "wape", "mase", "bias_pct", "coverage", "interval_coverage"]
                    if key in baseline_metrics
                },
                "challenger": {
                    key: challenger_metrics.get(key)
                    for key in ["mae", "wape", "mase", "bias_pct", "coverage", "interval_coverage"]
                    if key in challenger_metrics
                },
                "champion_decision": report["promotion_comparison"]["champion_decision_metrics"],
                "challenger_decision": report["promotion_comparison"]["challenger_decision_metrics"],
                "benchmark_gates_passed": bool(report["promotion_comparison"]["benchmark_gates_passed"]),
                "reason": report["promotion_comparison"]["reason"],
            }
        )

    def series(model: str, metric: str) -> list[float | None]:
        return [_metric_float(report[model]["holdout_metrics"], metric) for report in window_reports]

    baseline_wape_avg = _average(series("baseline", "wape"))
    challenger_wape_avg = _average(series("challenger", "wape"))
    baseline_wape_worst = _max_value(series("baseline", "wape"))
    challenger_wape_worst = _max_value(series("challenger", "wape"))
    baseline_cost_avg = _average([_extract_policy_metric(report, "champion", "combined_cost_proxy") for report in window_reports])
    challenger_cost_avg = _average(
        [_extract_policy_metric(report, "challenger", "combined_cost_proxy") for report in window_reports]
    )
    baseline_service_avg = _average([_extract_policy_metric(report, "champion", "service_level") for report in window_reports])
    challenger_service_avg = _average(
        [_extract_policy_metric(report, "challenger", "service_level") for report in window_reports]
    )
    passed_windows = sum(1 for report in window_reports if report["promotion_comparison"]["benchmark_gates_passed"])
    required_passes = len(window_reports) if active_config.validation_mode == "promotion_gate" else math.ceil(len(window_reports) / 2)

    average_wape_gate = (
        challenger_wape_avg <= baseline_wape_avg * 1.02
        if baseline_wape_avg is not None and challenger_wape_avg is not None
        else False
    )
    worst_wape_gate = (
        challenger_wape_worst <= baseline_wape_worst * 1.05
        if baseline_wape_worst is not None and challenger_wape_worst is not None
        else False
    )
    average_cost_gate = (
        challenger_cost_avg <= baseline_cost_avg * 1.02
        if baseline_cost_avg is not None and challenger_cost_avg is not None
        else False
    )
    service_gate = (
        challenger_service_avg >= baseline_service_avg - 0.005
        if baseline_service_avg is not None and challenger_service_avg is not None
        else False
    )
    window_pass_gate = passed_windows >= required_passes
    temporal_validation_gate = all(
        [
            window_pass_gate,
            average_wape_gate,
            average_cost_gate,
            service_gate,
            worst_wape_gate if active_config.validation_mode == "promotion_gate" else True,
        ]
    )

    return _json_safe(
        {
            "mode": active_config.validation_mode,
            "purpose": _validation_mode_purpose(active_config.validation_mode),
            "requested_windows": int(active_config.rolling_window_count),
            "completed_windows": len(window_reports),
            "rolling_window_days": int(active_config.rolling_window_days),
            "rolling_stride_days": int(active_config.rolling_stride_days),
            "skipped_windows": skipped,
            "summary_metrics": {
                "baseline_avg_wape": baseline_wape_avg,
                "challenger_avg_wape": challenger_wape_avg,
                "baseline_worst_wape": baseline_wape_worst,
                "challenger_worst_wape": challenger_wape_worst,
                "baseline_avg_mase": _average(series("baseline", "mase")),
                "challenger_avg_mase": _average(series("challenger", "mase")),
                "baseline_min_coverage": _min_value(series("baseline", "coverage")),
                "challenger_min_coverage": _min_value(series("challenger", "coverage")),
                "baseline_avg_combined_cost_proxy": baseline_cost_avg,
                "challenger_avg_combined_cost_proxy": challenger_cost_avg,
                "baseline_avg_service_level": baseline_service_avg,
                "challenger_avg_service_level": challenger_service_avg,
            },
            "gate_checks": {
                "rolling_window_pass_count_gate": window_pass_gate,
                "rolling_average_wape_gate": average_wape_gate,
                "rolling_average_decision_cost_gate": average_cost_gate,
                "rolling_average_service_level_gate": service_gate,
                "rolling_worst_window_wape_gate": worst_wape_gate,
                "temporal_validation_gate": temporal_validation_gate,
            },
            "windows": windows,
            "claim_boundary": "Rolling validation is benchmark evidence with simulated decision replay; not measured merchant impact.",
        }
    )


def _apply_validation_summary_to_comparison(
    comparison: dict[str, Any],
    validation_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    if not validation_summary:
        return comparison

    updated = dict(comparison)
    gate_checks = {**dict(updated.get("gate_checks") or {}), **dict(validation_summary.get("gate_checks") or {})}
    updated["gate_checks"] = gate_checks
    updated["temporal_validation"] = validation_summary
    benchmark_gates_passed = all(value for key, value in gate_checks.items() if key != "measured_pilot_outcome_gate")
    updated["benchmark_gates_passed"] = benchmark_gates_passed
    failed = [key for key, value in gate_checks.items() if not value]
    if benchmark_gates_passed:
        updated["reason"] = "benchmark_and_temporal_gates_passed_but_measured_pilot_outcomes_unavailable"
    else:
        updated["reason"] = "failed_gates:" + ",".join(failed)
    updated["decision"] = "continue_shadow_review"
    updated["promoted"] = False
    return updated


def render_decision_experiment_markdown(report: dict[str, Any]) -> str:
    baseline = report["baseline"]
    challenger = report["challenger"]
    moving_average = report["baselines"]["moving_average_7"]
    replay_results = report["decision_replay"]["results"]
    promo = report["promotion_comparison"]

    def metric(model: dict[str, Any], key: str) -> Any:
        value = (model.get("holdout_metrics") or {}).get(key)
        return "" if value is None else value

    lines = [
        "# Decision-Aware Experiment Report",
        "",
        f"- experiment: `{report['experiment']['experiment_name']}`",
        f"- dataset_id: `{report['dataset']['dataset_id']}`",
        f"- dataset_snapshot_id: `{report['dataset'].get('dataset_snapshot_id') or 'unavailable'}`",
        f"- provenance: `{report['dataset']['provenance']}`",
        f"- validation_mode: `{(report.get('validation') or {}).get('mode', 'quick_screen')}`",
        f"- claim_boundary: {report['claim_boundary']}",
        "",
        "## Forecast Holdout",
        "",
        "| model | version | mae | wape | mase | bias_pct | coverage | provenance |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for label, row in [
        ("moving_average_7", moving_average),
        ("champion_proxy", baseline),
        ("challenger", challenger),
    ]:
        lines.append(
            f"| {label} | {row.get('version')} | {metric(row, 'mae')} | {metric(row, 'wape')} | "
            f"{metric(row, 'mase')} | {metric(row, 'bias_pct')} | {metric(row, 'coverage')} | "
            f"{metric(row, 'provenance')} |"
        )

    activation = report.get("activation_policy") or {}
    if activation.get("enabled"):
        policy = activation.get("evaluation_policy") or {}
        lines.extend(
            [
                "",
                "## Activation Window",
                "",
                f"- activation_marker: `{activation.get('activation_marker')}`",
                f"- training_rows_excluded: `{activation.get('training_rows_excluded')}`",
                f"- calibration_rows_excluded: `{activation.get('calibration_rows_excluded')}`",
                f"- holdout_active_rows: `{activation.get('holdout_active_rows')}`",
                f"- holdout_pre_activation_rows: `{activation.get('holdout_pre_activation_rows')}`",
                f"- primary_metric_filter: `{policy.get('primary_metric_filter')}`",
                f"- guardrail_metric_filter: `{policy.get('guardrail_metric_filter')}`",
                "",
                "| slice | rows | baseline_wape | challenger_wape | primary |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for slice_name, payload in (report.get("evaluation_slices") or {}).items():
            baseline_metrics = (payload.get("baseline") or {}) if isinstance(payload, dict) else {}
            challenger_metrics = (payload.get("challenger") or {}) if isinstance(payload, dict) else {}
            lines.append(
                f"| {slice_name} | {payload.get('rows', 0) if isinstance(payload, dict) else 0} | "
                f"{baseline_metrics.get('wape', '')} | {challenger_metrics.get('wape', '')} | "
                f"{payload.get('primary', False) if isinstance(payload, dict) else False} |"
            )

    rolling = report.get("rolling_validation")
    if rolling:
        summary = rolling.get("summary_metrics") or {}
        lines.extend(
            [
                "",
                "## Rolling Validation",
                "",
                f"- completed_windows: `{rolling.get('completed_windows')}`",
                f"- rolling_window_days: `{rolling.get('rolling_window_days')}`",
                f"- rolling_stride_days: `{rolling.get('rolling_stride_days')}`",
                f"- temporal_validation_gate: `{(rolling.get('gate_checks') or {}).get('temporal_validation_gate')}`",
                "",
                "| metric | baseline | challenger |",
                "|---|---:|---:|",
                f"| avg_wape | {summary.get('baseline_avg_wape', '')} | {summary.get('challenger_avg_wape', '')} |",
                f"| worst_wape | {summary.get('baseline_worst_wape', '')} | {summary.get('challenger_worst_wape', '')} |",
                f"| avg_combined_cost_proxy | {summary.get('baseline_avg_combined_cost_proxy', '')} | {summary.get('challenger_avg_combined_cost_proxy', '')} |",
                f"| avg_service_level | {summary.get('baseline_avg_service_level', '')} | {summary.get('challenger_avg_service_level', '')} |",
                "",
                "| window | holdout_start | holdout_end | baseline_wape | challenger_wape | gates_passed |",
                "|---:|---|---|---:|---:|---|",
            ]
        )
        for window in rolling.get("windows") or []:
            lines.append(
                f"| {window.get('window')} | {window.get('holdout_start')} | {window.get('holdout_end')} | "
                f"{(window.get('baseline') or {}).get('wape', '')} | "
                f"{(window.get('challenger') or {}).get('wape', '')} | "
                f"{window.get('benchmark_gates_passed')} |"
            )

    lines.extend(
        [
            "",
            "## Replenishment Replay",
            "",
            "| policy | stockout_days | lost_sales_proxy | overstock_dollars | service_level | po_count | combined_cost_proxy | provenance |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for policy_name in ["moving_average", "champion", "challenger"]:
        row = replay_results[policy_name]
        lines.append(
            f"| {policy_name} | {row['stockout_days']} | {row['lost_sales_proxy']} | "
            f"{row['overstock_dollars']} | {row['service_level']} | {row['po_count']} | "
            f"{row['combined_cost_proxy']} | simulated |"
        )

    lines.extend(
        [
            "",
            "## Segment Highlights",
            "",
            "| segment | champion_wape | challenger_wape | rows | low_sample |",
            "|---|---:|---:|---:|---|",
        ]
    )
    champion_segments = baseline.get("segment_metrics") or {}
    challenger_segments = challenger.get("segment_metrics") or {}
    for segment_name in sorted(challenger_segments):
        c_payload = champion_segments.get(segment_name) or {}
        n_payload = challenger_segments.get(segment_name) or {}
        c_metrics = c_payload.get("metrics") or {}
        n_metrics = n_payload.get("metrics") or {}
        lines.append(
            f"| {segment_name} | {c_metrics.get('wape', '')} | {n_metrics.get('wape', '')} | "
            f"{n_payload.get('sample_rows', 0)} | {n_payload.get('low_sample', False)} |"
        )

    lines.extend(
        [
            "",
            "## Shadow Decision",
            "",
            f"- decision: `{promo['decision']}`",
            f"- benchmark_gates_passed: `{promo['benchmark_gates_passed']}`",
            f"- promoted: `{promo['promoted']}`",
            f"- reason: {promo['reason']}",
            f"- claim_boundary: {promo['claim_boundary']}",
            "",
        ]
    )
    return "\n".join(lines)


def run_decision_aware_experiment(
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    config: DecisionExperimentConfig | None = None,
    output_json: str | Path | None = None,
    output_md: str | Path | None = None,
    persist_snapshot: bool = True,
) -> dict[str, Any]:
    active_config = config or DecisionExperimentConfig()
    raw = _load_canonical_transactions(data_dir)
    frame = prepare_decision_frame(raw, config=active_config)
    dataset_snapshot = create_dataset_snapshot(frame, dataset_id=active_config.dataset_id)
    if persist_snapshot:
        persist_dataset_snapshot(dataset_snapshot)

    report = _build_decision_experiment_report(
        frame=frame,
        dataset_snapshot=dataset_snapshot,
        active_config=active_config,
    )
    report["data_dir"] = str(data_dir)
    rolling_validation = _rolling_validation_summary(
        frame=frame,
        dataset_snapshot=dataset_snapshot,
        active_config=active_config,
    )
    if rolling_validation:
        comparison = _apply_validation_summary_to_comparison(report["promotion_comparison"], rolling_validation)
        report["rolling_validation"] = rolling_validation
        report["promotion_comparison"] = comparison
        report["comparison"] = comparison
        report["overall_business_safe"] = bool(comparison["benchmark_gates_passed"])
        report["experiment"]["decision"] = comparison["decision"]
        report["experiment"]["decision_rationale"] = comparison["reason"]
    report = _json_safe(report)

    if output_json:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if output_md:
        output_md = Path(output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_decision_experiment_markdown(report) + "\n", encoding="utf-8")

    return report
