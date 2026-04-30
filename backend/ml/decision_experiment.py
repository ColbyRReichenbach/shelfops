from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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
    model_config: dict[str, Any] = field(default_factory=dict)
    calibration_config: dict[str, Any] = field(default_factory=dict)
    segmentation_config: dict[str, Any] = field(default_factory=dict)
    holdout_days: int = 28
    calibration_days: int = 28
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


def prepare_decision_frame(raw: pd.DataFrame, *, config: DecisionExperimentConfig) -> pd.DataFrame:
    frame = prepare_series_frame(raw)
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0.0).clip(lower=0.0)
    frame["category"] = frame.get("category", frame["product_id"]).astype(str)
    frame["is_promotional"] = pd.to_numeric(frame.get("is_promotional", 0), errors="coerce").fillna(0).astype(int)
    frame["is_holiday"] = pd.to_numeric(frame.get("is_holiday", 0), errors="coerce").fillna(0).astype(int)
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
    frame: pd.DataFrame, *, config: DecisionExperimentConfig
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    unique_dates = sorted(pd.to_datetime(frame["date"]).dropna().unique().tolist())
    required_days = config.holdout_days + config.calibration_days + 28
    if len(unique_dates) < required_days:
        raise ValueError(
            f"Need at least {required_days} distinct dates for train/calibration/holdout; found {len(unique_dates)}"
        )

    holdout_start = unique_dates[-config.holdout_days]
    calibration_start = unique_dates[-(config.holdout_days + config.calibration_days)]

    train = frame[frame["date"] < calibration_start].copy()
    calibration = frame[(frame["date"] >= calibration_start) & (frame["date"] < holdout_start)].copy()
    holdout = frame[frame["date"] >= holdout_start].copy()
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


def _fit_champion_predictions(
    frame: pd.DataFrame,
    *,
    train_end: pd.Timestamp,
    predict_start: pd.Timestamp,
    config: DecisionExperimentConfig,
) -> pd.DataFrame:
    try:
        import lightgbm as lgb
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ModuleNotFoundError("lightgbm is required for decision-aware experiments") from exc

    features = _build_feature_frame(frame, config=config)
    feature_cols = [col for col in _feature_columns_for_config(config) if col in features.columns]
    train_mask = features["date"] < train_end
    required_lags = [col for col in [f"lag_{day}" for day in _active_feature_config(config)["lag_days"]] if col in feature_cols]
    drop_subset = required_lags[-2:] if len(required_lags) >= 2 else required_lags
    train_df = features.loc[train_mask].dropna(subset=drop_subset).copy() if drop_subset else features.loc[train_mask].copy()
    if train_df.empty:
        train_df = features.loc[train_mask].copy()
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
    out["forecast_champion"] = np.maximum(preds, 0.0)
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
) -> dict[str, Any]:
    work = calibration.copy()
    work["forecast_champion"] = pd.to_numeric(work["forecast_champion"], errors="coerce").fillna(0.0)
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
        predicted = float(group["forecast_champion"].sum())
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


def _apply_bias_adjustments(frame: pd.DataFrame, adjustments: dict[str, Any]) -> pd.Series:
    global_adjustment = float(adjustments.get("global") or 1.0)
    by_category_velocity = dict(adjustments.get("by_category_velocity") or {})
    by_category = dict(adjustments.get("by_category") or {})

    factors = []
    for row in frame.itertuples(index=False):
        category = str(getattr(row, "category"))
        velocity = str(getattr(row, "velocity_segment"))
        factors.append(by_category_velocity.get(f"{category}::{velocity}", by_category.get(category, global_adjustment)))
    factor_series = pd.Series(factors, index=frame.index, dtype="float64")
    return (pd.to_numeric(frame["forecast_champion"], errors="coerce").fillna(0.0) * factor_series).clip(lower=0.0)


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
    metrics = compute_forecast_metrics(
        frame["quantity"],
        frame[pred_col],
        unit_cost=frame["unit_cost"],
        unit_price=frame["price"],
        holding_cost_per_unit_per_day=frame["holding_cost_per_unit_per_day"],
        category=frame["category"],
    )
    metrics["mape"] = metrics.get("mape_nonzero")
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

    train, calibration, holdout = _time_split(frame, config=active_config)
    combined = pd.concat([train, calibration, holdout], ignore_index=True)
    train_end = pd.to_datetime(calibration["date"].min())
    predict_start = train_end
    prediction_frame = _fit_champion_predictions(
        combined,
        train_end=train_end,
        predict_start=predict_start,
        config=active_config,
    )

    velocity_lookup = _velocity_lookup(train)
    prediction_frame["velocity_segment"] = prediction_frame["series_id"].map(velocity_lookup).fillna("unknown")

    calibration_pred = prediction_frame[prediction_frame["date"].isin(calibration["date"].unique())].copy()
    holdout_pred = prediction_frame[prediction_frame["date"].isin(holdout["date"].unique())].copy()
    calibration_config = _active_calibration_config(active_config)
    adjustments = _fit_bias_adjustments(
        calibration_pred,
        strategy=str(calibration_config["strategy"]),
        clip_range=calibration_config["clip_range"],
    )
    calibration_pred["forecast_challenger"] = _apply_bias_adjustments(calibration_pred, adjustments)
    holdout_pred["forecast_challenger"] = _apply_bias_adjustments(holdout_pred, adjustments)

    moving_average_history = pd.concat([train, calibration], ignore_index=True)
    holdout_pred["forecast_moving_average"] = moving_average_forecast(moving_average_history, holdout_pred).to_numpy()

    champion_interval = _interval_metrics(calibration_pred, holdout_pred, pred_col="forecast_champion")
    challenger_interval = _interval_metrics(calibration_pred, holdout_pred, pred_col="forecast_challenger")

    moving_average_metrics = _forecast_metrics(holdout_pred, pred_col="forecast_moving_average")
    champion_metrics = _forecast_metrics(holdout_pred, pred_col="forecast_champion", interval=champion_interval)
    challenger_metrics = _forecast_metrics(holdout_pred, pred_col="forecast_challenger", interval=challenger_interval)

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
        "architecture": "lightgbm_plus_calibrated_post_processing",
        "objective": f"{model_config['objective']}_demand_forecast",
        "feature_columns": feature_columns,
        "feature_config": feature_config,
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
        "provenance": "benchmark",
        "claim_boundary": "Benchmark evidence only. No measured merchant ROI.",
    }

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_dir),
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
        "lineage_metadata": lineage_metadata,
        "experiment_spec": {
            "experiment_spec_id": active_config.experiment_spec_id,
            "spec_hash": active_config.experiment_spec_hash,
            "template_id": active_config.spec_template_id,
            "spec_name": active_config.spec_name,
            "feature_set_id": active_config.feature_set_id,
            "feature_columns": feature_columns,
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
            "segment_metrics": _segment_metrics(holdout_pred, pred_col="forecast_champion"),
            "lineage_metadata": lineage_metadata,
        },
        "challenger": {
            "version": active_config.challenger_version,
            "holdout_metrics": challenger_metrics,
            "segment_metrics": _segment_metrics(holdout_pred, pred_col="forecast_challenger"),
            "calibration_adjustments": _json_safe(adjustments),
            "lineage_metadata": {
                **lineage_metadata,
                "post_processing": "category_velocity_bias_calibration",
                "calibration_window_days": active_config.calibration_days,
            },
        },
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
