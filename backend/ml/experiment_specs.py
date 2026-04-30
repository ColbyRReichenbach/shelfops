from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

SCHEMA_VERSION = "shelfops.experiment_spec.v1"
SPEC_VERSION = "2026-04-29"

_DEFAULT_DECISION_CONFIG = {
    "lead_time_days": 5,
    "safety_stock_days": 2.0,
    "order_up_to_days": 7.0,
    "initial_inventory_days": 14.0,
    "order_cost": 24.0,
    "holding_cost_rate_annual": 0.25,
}

_DEFAULT_GATES = {
    "wape_regression_max_pct": 0.02,
    "mase_regression_max_pct": 0.02,
    "combined_cost_proxy_regression_max_pct": 0.02,
    "service_level_drop_max": 0.005,
    "measured_pilot_outcome_required_for_promotion": True,
}

_BASE_HYPERPARAMETERS = {
    "n_estimators": 180,
    "learning_rate": 0.05,
    "num_leaves": 47,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "min_child_samples": 20,
    "random_state": 42,
}


def _template(
    *,
    template_id: str,
    spec_name: str,
    experiment_type: str,
    feature_set_id: str,
    feature_config: dict[str, Any],
    model_config: dict[str, Any] | None = None,
    calibration_config: dict[str, Any] | None = None,
    segmentation_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "template_id": template_id,
        "spec_name": spec_name,
        "spec_version": SPEC_VERSION,
        "model_name": "demand_forecast",
        "dataset_id": "m5_walmart",
        "forecast_grain": "store_id x product_id x date",
        "experiment_type": experiment_type,
        "feature_set_id": feature_set_id,
        "feature_config": feature_config,
        "model_config": model_config
        or {
            "architecture": "lightgbm",
            "objective": "poisson",
            "hyperparameters": dict(_BASE_HYPERPARAMETERS),
        },
        "calibration_config": calibration_config
        or {
            "strategy": "category_velocity_bias",
            "clip_range": [0.75, 1.25],
        },
        "segmentation_config": segmentation_config
        or {
            "strategy": "store_product_velocity_and_category_bias_calibration",
            "velocity_quantiles": [0.33, 0.66],
        },
        "decision_config": dict(_DEFAULT_DECISION_CONFIG),
        "promotion_gates": dict(_DEFAULT_GATES),
        "provenance": "benchmark",
        "claim_boundary": "M5/Walmart benchmark execution only. No measured merchant ROI.",
    }


EXPERIMENT_SPEC_TEMPLATES: dict[str, dict[str, Any]] = {
    "m5_lag_price_calendar_v1": _template(
        template_id="m5_lag_price_calendar_v1",
        spec_name="M5 lag, price, calendar baseline",
        experiment_type="feature_set",
        feature_set_id="m5_lag_price_calendar_v1",
        feature_config={
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
        },
    ),
    "m5_price_promo_lag_v1": _template(
        template_id="m5_price_promo_lag_v1",
        spec_name="M5 price and promotion lag challenger",
        experiment_type="feature_set",
        feature_set_id="m5_price_promo_lag_v1",
        feature_config={
            "lag_days": [1, 7, 14, 28, 56],
            "rolling_windows": [7, 28, 56],
            "rolling_nonzero_windows": [28],
            "include_calendar": True,
            "include_product_codes": True,
            "include_price": True,
            "include_price_momentum": True,
            "include_promotion": True,
            "include_promo_price_interaction": True,
            "include_holiday": True,
            "include_intermittency": False,
        },
    ),
    "m5_velocity_segmented_bias_v1": _template(
        template_id="m5_velocity_segmented_bias_v1",
        spec_name="M5 velocity-segmented bias calibration",
        experiment_type="segmentation",
        feature_set_id="m5_velocity_segmented_bias_v1",
        feature_config={
            "lag_days": [1, 7, 14, 28],
            "rolling_windows": [7, 14, 28],
            "rolling_nonzero_windows": [14, 28],
            "include_calendar": True,
            "include_product_codes": True,
            "include_price": True,
            "include_price_momentum": False,
            "include_promotion": True,
            "include_promo_price_interaction": False,
            "include_holiday": True,
            "include_intermittency": True,
        },
        model_config={
            "architecture": "lightgbm",
            "objective": "poisson",
            "hyperparameters": {
                **_BASE_HYPERPARAMETERS,
                "num_leaves": 63,
                "min_child_samples": 12,
            },
        },
        calibration_config={
            "strategy": "category_velocity_bias",
            "clip_range": [0.7, 1.3],
        },
    ),
    "m5_slow_mover_conservative_v1": _template(
        template_id="m5_slow_mover_conservative_v1",
        spec_name="M5 conservative slow-mover challenger",
        experiment_type="hyperparameter_tuning",
        feature_set_id="m5_slow_mover_conservative_v1",
        feature_config={
            "lag_days": [1, 7, 14, 28, 56],
            "rolling_windows": [14, 28, 56],
            "rolling_nonzero_windows": [14, 28, 56],
            "include_calendar": True,
            "include_product_codes": True,
            "include_price": True,
            "include_price_momentum": False,
            "include_promotion": True,
            "include_promo_price_interaction": False,
            "include_holiday": True,
            "include_intermittency": True,
        },
        model_config={
            "architecture": "lightgbm",
            "objective": "tweedie",
            "hyperparameters": {
                **_BASE_HYPERPARAMETERS,
                "n_estimators": 220,
                "num_leaves": 31,
                "min_child_samples": 30,
            },
        },
        calibration_config={
            "strategy": "global_bias",
            "clip_range": [0.85, 1.15],
        },
        segmentation_config={
            "strategy": "slow_mover_conservative_global_bias",
            "velocity_quantiles": [0.33, 0.66],
        },
    ),
    "freshretailnet_stockout_precision_v1": {
        "schema_version": SCHEMA_VERSION,
        "template_id": "freshretailnet_stockout_precision_v1",
        "spec_name": "FreshRetailNet precision-first stockout sentinel",
        "spec_version": SPEC_VERSION,
        "model_name": "anomaly_detector",
        "dataset_id": "freshretailnet_50k",
        "forecast_grain": "store_id x product_id x date stockout context",
        "experiment_type": "post_processing",
        "feature_set_id": "freshretailnet_stockout_context_v1",
        "target_label": "stock_hour6_22_cnt > 0",
        "feature_config": {
            "lookback_days": 7,
            "include_sales_gap": True,
            "include_zero_sales": True,
            "include_promo": True,
            "include_holiday": True,
            "include_weather": True,
            "include_category_segments": True,
        },
        "model_config": {
            "architecture": "deterministic_stockout_risk_score",
            "objective": "precision_first_stockout_detection",
            "threshold": 0.55,
            "weights": {
                "sales_gap": 0.64,
                "zero_sales": 0.20,
                "promo": 0.08,
                "holiday": 0.04,
                "weather_stress": 0.04,
            },
        },
        "promotion_gates": {
            "precision_min": 0.55,
            "recall_min": 0.05,
            "false_positive_rate_max": 0.20,
            "review_rate_max": 0.25,
            "measured_feedback_required_for_promotion": True,
        },
        "provenance": "benchmark",
        "claim_boundary": "FreshRetailNet benchmark anomaly evidence only. Buyer outcomes require real cycle-count feedback.",
    },
    "freshretailnet_balanced_context_v1": {
        "schema_version": SCHEMA_VERSION,
        "template_id": "freshretailnet_balanced_context_v1",
        "spec_name": "FreshRetailNet balanced context challenger",
        "spec_version": SPEC_VERSION,
        "model_name": "anomaly_detector",
        "dataset_id": "freshretailnet_50k",
        "forecast_grain": "store_id x product_id x date stockout context",
        "experiment_type": "post_processing",
        "feature_set_id": "freshretailnet_balanced_context_v1",
        "target_label": "stock_hour6_22_cnt > 0",
        "feature_config": {
            "lookback_days": 7,
            "include_sales_gap": True,
            "include_zero_sales": True,
            "include_promo": True,
            "include_holiday": True,
            "include_weather": True,
            "include_category_segments": True,
        },
        "model_config": {
            "architecture": "deterministic_stockout_risk_score",
            "objective": "balanced_stockout_detection",
            "threshold": 0.35,
            "weights": {
                "sales_gap": 0.58,
                "zero_sales": 0.18,
                "promo": 0.11,
                "holiday": 0.04,
                "weather_stress": 0.09,
            },
        },
        "promotion_gates": {
            "precision_min": 0.40,
            "recall_min": 0.15,
            "false_positive_rate_max": 0.35,
            "review_rate_max": 0.40,
            "measured_feedback_required_for_promotion": True,
        },
        "provenance": "benchmark",
        "claim_boundary": "FreshRetailNet benchmark anomaly evidence only. Buyer outcomes require real cycle-count feedback.",
    },
    "freshretailnet_high_recall_review_cap_v1": {
        "schema_version": SCHEMA_VERSION,
        "template_id": "freshretailnet_high_recall_review_cap_v1",
        "spec_name": "FreshRetailNet high-recall review-cap challenger",
        "spec_version": SPEC_VERSION,
        "model_name": "anomaly_detector",
        "dataset_id": "freshretailnet_50k",
        "forecast_grain": "store_id x product_id x date stockout context",
        "experiment_type": "post_processing",
        "feature_set_id": "freshretailnet_high_recall_review_cap_v1",
        "target_label": "stock_hour6_22_cnt > 0",
        "feature_config": {
            "lookback_days": 7,
            "include_sales_gap": True,
            "include_zero_sales": True,
            "include_promo": True,
            "include_holiday": True,
            "include_weather": True,
            "include_category_segments": True,
        },
        "model_config": {
            "architecture": "deterministic_stockout_risk_score",
            "objective": "high_recall_stockout_detection",
            "threshold": 0.25,
            "weights": {
                "sales_gap": 0.54,
                "zero_sales": 0.22,
                "promo": 0.12,
                "holiday": 0.04,
                "weather_stress": 0.08,
            },
        },
        "promotion_gates": {
            "precision_min": 0.30,
            "recall_min": 0.25,
            "false_positive_rate_max": 0.45,
            "review_rate_max": 0.50,
            "measured_feedback_required_for_promotion": True,
        },
        "provenance": "benchmark",
        "claim_boundary": "FreshRetailNet benchmark anomaly evidence only. Buyer outcomes require real cycle-count feedback.",
    },
}

_ALLOWED_HYPERPARAMETERS = {
    "n_estimators",
    "learning_rate",
    "num_leaves",
    "subsample",
    "colsample_bytree",
    "min_child_samples",
    "random_state",
}

_ALLOWED_ANOMALY_WEIGHTS = {
    "sales_gap",
    "zero_sales",
    "promo",
    "holiday",
    "weather_stress",
}

_ALLOWED_OVERRIDE_PATHS = {
    ("spec_name",),
    ("feature_set_id",),
    ("feature_config", "lag_days"),
    ("feature_config", "rolling_windows"),
    ("feature_config", "rolling_nonzero_windows"),
    ("feature_config", "include_calendar"),
    ("feature_config", "include_product_codes"),
    ("feature_config", "include_price"),
    ("feature_config", "include_price_momentum"),
    ("feature_config", "include_promotion"),
    ("feature_config", "include_promo_price_interaction"),
    ("feature_config", "include_holiday"),
    ("feature_config", "include_intermittency"),
    ("feature_config", "include_sales_gap"),
    ("feature_config", "include_zero_sales"),
    ("feature_config", "include_promo"),
    ("feature_config", "include_weather"),
    ("feature_config", "include_category_segments"),
    ("feature_config", "lookback_days"),
    ("model_config", "objective"),
    ("model_config", "threshold"),
    ("calibration_config", "strategy"),
    ("calibration_config", "clip_range"),
    ("decision_config", "lead_time_days"),
    ("decision_config", "safety_stock_days"),
    ("decision_config", "order_up_to_days"),
    ("decision_config", "initial_inventory_days"),
    ("decision_config", "order_cost"),
    ("decision_config", "holding_cost_rate_annual"),
}


def _stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def hash_experiment_spec(spec: dict[str, Any]) -> str:
    """Return a stable hash for the executable spec body."""
    return hashlib.sha256(_stable_json(spec).encode("utf-8")).hexdigest()


def _merge_allowed(base: dict[str, Any], overrides: dict[str, Any], path: tuple[str, ...] = ()) -> None:
    for key, value in overrides.items():
        next_path = (*path, str(key))
        if next_path[:2] == ("model_config", "hyperparameters") and len(next_path) == 3:
            if next_path[2] not in _ALLOWED_HYPERPARAMETERS:
                raise ValueError(f"Unsupported experiment spec hyperparameter override: {'.'.join(next_path)}")
            base[next_path[2]] = value
            continue
        if next_path[:2] == ("model_config", "weights") and len(next_path) == 3:
            if next_path[2] not in _ALLOWED_ANOMALY_WEIGHTS:
                raise ValueError(f"Unsupported experiment spec anomaly weight override: {'.'.join(next_path)}")
            base[next_path[2]] = value
            continue
        if isinstance(value, dict):
            if key not in base or not isinstance(base[key], dict):
                raise ValueError(f"Unsupported experiment spec override path: {'.'.join(next_path)}")
            _merge_allowed(base[key], value, next_path)
            continue
        if next_path not in _ALLOWED_OVERRIDE_PATHS:
            raise ValueError(f"Unsupported experiment spec override path: {'.'.join(next_path)}")
        base[key] = value


def _bounded_int_list(values: Any, *, field_name: str, minimum: int = 1, maximum: int = 120) -> list[int]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{field_name} must be a non-empty list")
    normalized = sorted({int(value) for value in values})
    if any(value < minimum or value > maximum for value in normalized):
        raise ValueError(f"{field_name} values must be between {minimum} and {maximum}")
    return normalized


def _bounded_float(value: Any, *, field_name: str, minimum: float, maximum: float) -> float:
    number = float(value)
    if number < minimum or number > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return number


def validate_experiment_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a ShelfOps executable experiment spec."""
    normalized = copy.deepcopy(spec)
    required = [
        "schema_version",
        "template_id",
        "spec_name",
        "model_name",
        "dataset_id",
        "experiment_type",
        "feature_set_id",
        "feature_config",
        "model_config",
        "provenance",
    ]
    missing = [field for field in required if field not in normalized]
    if missing:
        raise ValueError(f"Experiment spec missing required fields: {missing}")
    if normalized["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"Unsupported experiment spec schema_version: {normalized['schema_version']}")
    if normalized["model_name"] not in {"demand_forecast", "anomaly_detector"}:
        raise ValueError("Only demand_forecast and anomaly_detector experiment specs are executable")
    if normalized["model_name"] == "demand_forecast" and normalized["dataset_id"] != "m5_walmart":
        raise ValueError("Demand forecast experiment specs must use m5_walmart")
    if normalized["model_name"] == "anomaly_detector" and normalized["dataset_id"] != "freshretailnet_50k":
        raise ValueError("Anomaly detector experiment specs must use freshretailnet_50k")
    if normalized["provenance"] != "benchmark":
        raise ValueError("Experiment specs must label benchmark provenance until pilot outcomes are measured")

    feature_config = normalized["feature_config"]
    model_config = normalized["model_config"]
    if normalized["model_name"] == "demand_forecast":
        if "calibration_config" not in normalized or "decision_config" not in normalized:
            raise ValueError("Demand forecast specs require calibration_config and decision_config")
        feature_config["lag_days"] = _bounded_int_list(
            feature_config.get("lag_days"), field_name="feature_config.lag_days"
        )
        feature_config["rolling_windows"] = _bounded_int_list(
            feature_config.get("rolling_windows"), field_name="feature_config.rolling_windows"
        )
        feature_config["rolling_nonzero_windows"] = _bounded_int_list(
            feature_config.get("rolling_nonzero_windows", []), field_name="feature_config.rolling_nonzero_windows"
        )
        for flag in (
            "include_calendar",
            "include_product_codes",
            "include_price",
            "include_price_momentum",
            "include_promotion",
            "include_promo_price_interaction",
            "include_holiday",
            "include_intermittency",
        ):
            feature_config[flag] = bool(feature_config.get(flag, False))

        objective = str(model_config.get("objective", "poisson")).strip().lower()
        if objective not in {"poisson", "tweedie", "regression"}:
            raise ValueError("model_config.objective must be one of: poisson, tweedie, regression")
        model_config["objective"] = objective
        model_config["architecture"] = "lightgbm"
        hyperparameters = dict(model_config.get("hyperparameters") or {})
        for key in list(hyperparameters):
            if key not in _ALLOWED_HYPERPARAMETERS:
                raise ValueError(f"Unsupported LightGBM hyperparameter in experiment spec: {key}")
        hyperparameters["n_estimators"] = int(
            hyperparameters.get("n_estimators", _BASE_HYPERPARAMETERS["n_estimators"])
        )
        hyperparameters["num_leaves"] = int(hyperparameters.get("num_leaves", _BASE_HYPERPARAMETERS["num_leaves"]))
        hyperparameters["min_child_samples"] = int(
            hyperparameters.get("min_child_samples", _BASE_HYPERPARAMETERS["min_child_samples"])
        )
        hyperparameters["random_state"] = int(
            hyperparameters.get("random_state", _BASE_HYPERPARAMETERS["random_state"])
        )
        hyperparameters["learning_rate"] = _bounded_float(
            hyperparameters.get("learning_rate", _BASE_HYPERPARAMETERS["learning_rate"]),
            field_name="model_config.hyperparameters.learning_rate",
            minimum=0.001,
            maximum=0.5,
        )
        hyperparameters["subsample"] = _bounded_float(
            hyperparameters.get("subsample", _BASE_HYPERPARAMETERS["subsample"]),
            field_name="model_config.hyperparameters.subsample",
            minimum=0.4,
            maximum=1.0,
        )
        hyperparameters["colsample_bytree"] = _bounded_float(
            hyperparameters.get("colsample_bytree", _BASE_HYPERPARAMETERS["colsample_bytree"]),
            field_name="model_config.hyperparameters.colsample_bytree",
            minimum=0.4,
            maximum=1.0,
        )
        if hyperparameters["n_estimators"] < 20 or hyperparameters["n_estimators"] > 800:
            raise ValueError("model_config.hyperparameters.n_estimators must be between 20 and 800")
        if hyperparameters["num_leaves"] < 8 or hyperparameters["num_leaves"] > 255:
            raise ValueError("model_config.hyperparameters.num_leaves must be between 8 and 255")
        if hyperparameters["min_child_samples"] < 1 or hyperparameters["min_child_samples"] > 500:
            raise ValueError("model_config.hyperparameters.min_child_samples must be between 1 and 500")
        model_config["hyperparameters"] = hyperparameters

        calibration_config = normalized["calibration_config"]
        strategy = str(calibration_config.get("strategy", "category_velocity_bias")).strip().lower()
        if strategy not in {"none", "global_bias", "category_velocity_bias"}:
            raise ValueError("calibration_config.strategy must be one of: none, global_bias, category_velocity_bias")
        calibration_config["strategy"] = strategy
        clip_range = calibration_config.get("clip_range", [0.75, 1.25])
        if not isinstance(clip_range, list) or len(clip_range) != 2:
            raise ValueError("calibration_config.clip_range must be [min, max]")
        low, high = float(clip_range[0]), float(clip_range[1])
        if low <= 0 or high < low or high > 2.0:
            raise ValueError("calibration_config.clip_range must be positive and ordered")
        calibration_config["clip_range"] = [low, high]

        decision_config = normalized["decision_config"]
        decision_config["lead_time_days"] = int(decision_config.get("lead_time_days", 5))
        for key in ("safety_stock_days", "order_up_to_days", "initial_inventory_days", "order_cost"):
            decision_config[key] = float(decision_config.get(key, _DEFAULT_DECISION_CONFIG[key]))
            if decision_config[key] < 0:
                raise ValueError(f"decision_config.{key} must be non-negative")
        decision_config["holding_cost_rate_annual"] = _bounded_float(
            decision_config.get("holding_cost_rate_annual", _DEFAULT_DECISION_CONFIG["holding_cost_rate_annual"]),
            field_name="decision_config.holding_cost_rate_annual",
            minimum=0.0,
            maximum=2.0,
        )
    else:
        feature_config["lookback_days"] = int(feature_config.get("lookback_days", 7))
        if feature_config["lookback_days"] < 2 or feature_config["lookback_days"] > 60:
            raise ValueError("feature_config.lookback_days must be between 2 and 60")
        for flag in (
            "include_sales_gap",
            "include_zero_sales",
            "include_promo",
            "include_holiday",
            "include_weather",
            "include_category_segments",
        ):
            feature_config[flag] = bool(feature_config.get(flag, False))
        model_config["architecture"] = "deterministic_stockout_risk_score"
        model_config["objective"] = str(model_config.get("objective") or "stockout_detection")
        model_config["threshold"] = _bounded_float(
            model_config.get("threshold", 0.55),
            field_name="model_config.threshold",
            minimum=0.01,
            maximum=0.99,
        )
        weights = dict(model_config.get("weights") or {})
        for key in weights:
            if key not in _ALLOWED_ANOMALY_WEIGHTS:
                raise ValueError(f"Unsupported anomaly score weight in experiment spec: {key}")
        for key in _ALLOWED_ANOMALY_WEIGHTS:
            weights[key] = float(weights.get(key, 0.0))
            if weights[key] < 0:
                raise ValueError(f"model_config.weights.{key} must be non-negative")
        weight_sum = sum(weights.values())
        if weight_sum <= 0:
            raise ValueError("model_config.weights must contain at least one positive weight")
        model_config["weights"] = {key: round(value / weight_sum, 6) for key, value in weights.items()}
        gates = dict(normalized.get("promotion_gates") or {})
        gates["precision_min"] = _bounded_float(
            gates.get("precision_min", 0.0), field_name="promotion_gates.precision_min", minimum=0.0, maximum=1.0
        )
        gates["recall_min"] = _bounded_float(
            gates.get("recall_min", 0.0), field_name="promotion_gates.recall_min", minimum=0.0, maximum=1.0
        )
        gates["false_positive_rate_max"] = _bounded_float(
            gates.get("false_positive_rate_max", 1.0),
            field_name="promotion_gates.false_positive_rate_max",
            minimum=0.0,
            maximum=1.0,
        )
        gates["review_rate_max"] = _bounded_float(
            gates.get("review_rate_max", 1.0), field_name="promotion_gates.review_rate_max", minimum=0.0, maximum=1.0
        )
        gates["measured_feedback_required_for_promotion"] = bool(
            gates.get("measured_feedback_required_for_promotion", True)
        )
        normalized["promotion_gates"] = gates

    normalized["spec_version"] = str(normalized.get("spec_version") or SPEC_VERSION)
    normalized["forecast_grain"] = str(
        normalized.get("forecast_grain")
        or (
            "store_id x product_id x date"
            if normalized["model_name"] == "demand_forecast"
            else "store_id x product_id x date stockout context"
        )
    )
    normalized["claim_boundary"] = str(
        normalized.get("claim_boundary")
        or (
            "M5/Walmart benchmark execution only. No measured merchant ROI."
            if normalized["model_name"] == "demand_forecast"
            else "FreshRetailNet benchmark anomaly evidence only. Buyer outcomes require real cycle-count feedback."
        )
    )
    return normalized


def materialize_experiment_spec(
    *,
    template_id: str,
    spec_name: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if template_id not in EXPERIMENT_SPEC_TEMPLATES:
        raise ValueError(f"Unsupported experiment spec template_id: {template_id}")
    spec = copy.deepcopy(EXPERIMENT_SPEC_TEMPLATES[template_id])
    if spec_name:
        spec["spec_name"] = spec_name
    if overrides:
        _merge_allowed(spec, overrides)
    return validate_experiment_spec(spec)


def list_experiment_spec_templates(model_name: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template_id, template in EXPERIMENT_SPEC_TEMPLATES.items():
        spec = validate_experiment_spec(template)
        if model_name and spec["model_name"] != model_name:
            continue
        rows.append(
            {
                "template_id": template_id,
                "spec_name": spec["spec_name"],
                "model_name": spec["model_name"],
                "dataset_id": spec["dataset_id"],
                "experiment_type": spec["experiment_type"],
                "feature_set_id": spec["feature_set_id"],
                "objective": spec["model_config"]["objective"],
                "calibration_strategy": (spec.get("calibration_config") or {}).get("strategy")
                or f"threshold_{spec['model_config'].get('threshold')}",
                "provenance": spec["provenance"],
                "claim_boundary": spec["claim_boundary"],
                "spec": spec,
                "spec_hash": hash_experiment_spec(spec),
            }
        )
    return rows


def default_template_for_experiment_type(experiment_type: str | None, model_name: str = "demand_forecast") -> str:
    if model_name == "anomaly_detector":
        return "freshretailnet_balanced_context_v1"
    normalized = str(experiment_type or "").strip().lower()
    if normalized == "segmentation":
        return "m5_velocity_segmented_bias_v1"
    if normalized == "hyperparameter_tuning":
        return "m5_slow_mover_conservative_v1"
    return "m5_lag_price_calendar_v1"


def decision_config_kwargs_from_spec(
    spec: dict[str, Any],
    *,
    experiment_spec_id: str | None = None,
    experiment_spec_hash: str | None = None,
) -> dict[str, Any]:
    normalized = validate_experiment_spec(spec)
    if normalized["model_name"] != "demand_forecast":
        raise ValueError("decision_config_kwargs_from_spec only accepts demand_forecast specs")
    decision_config = dict(normalized["decision_config"])
    return {
        "dataset_id": normalized["dataset_id"],
        "experiment_spec_id": experiment_spec_id,
        "experiment_spec_hash": experiment_spec_hash or hash_experiment_spec(normalized),
        "spec_template_id": normalized["template_id"],
        "spec_name": normalized["spec_name"],
        "feature_set_id": normalized["feature_set_id"],
        "feature_config": normalized["feature_config"],
        "model_config": normalized["model_config"],
        "calibration_config": normalized["calibration_config"],
        "segmentation_config": normalized.get("segmentation_config") or {},
        "lead_time_days": decision_config["lead_time_days"],
        "safety_stock_days": decision_config["safety_stock_days"],
        "order_up_to_days": decision_config["order_up_to_days"],
        "initial_inventory_days": decision_config["initial_inventory_days"],
        "order_cost": decision_config["order_cost"],
        "holding_cost_rate_annual": decision_config["holding_cost_rate_annual"],
        "random_state": int(normalized["model_config"]["hyperparameters"].get("random_state", 42)),
    }


def anomaly_config_kwargs_from_spec(
    spec: dict[str, Any],
    *,
    experiment_spec_id: str | None = None,
    experiment_spec_hash: str | None = None,
) -> dict[str, Any]:
    normalized = validate_experiment_spec(spec)
    if normalized["model_name"] != "anomaly_detector":
        raise ValueError("anomaly_config_kwargs_from_spec only accepts anomaly_detector specs")
    return {
        "dataset_id": normalized["dataset_id"],
        "experiment_spec_id": experiment_spec_id,
        "experiment_spec_hash": experiment_spec_hash or hash_experiment_spec(normalized),
        "spec_template_id": normalized["template_id"],
        "spec_name": normalized["spec_name"],
        "feature_set_id": normalized["feature_set_id"],
        "feature_config": normalized["feature_config"],
        "model_config": normalized["model_config"],
        "promotion_gates": normalized.get("promotion_gates") or {},
    }
