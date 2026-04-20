from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

EXPERIMENT_TYPE_ALIASES = {
    "feature_engineering": "feature_set",
    "model_architecture": "architecture",
    "data_source": "data_contract",
}

EXPERIMENT_TYPE_CHOICES = {
    "architecture",
    "feature_set",
    "hyperparameter_tuning",
    "data_contract",
    "data_window",
    "segmentation",
    "objective_function",
    "post_processing",
    "promotion_decision",
    "rollback",
    "baseline_refresh",
}


def normalize_experiment_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = EXPERIMENT_TYPE_ALIASES.get(normalized, normalized)
    if normalized not in EXPERIMENT_TYPE_CHOICES:
        raise ValueError(f"Unsupported experiment_type '{value}'. Expected one of: {sorted(EXPERIMENT_TYPE_CHOICES)}")
    return normalized


def build_lineage_label(
    *,
    model_name: str,
    architecture: str,
    objective: str,
    segment_strategy: str,
    feature_set_id: str,
) -> str:
    return "__".join(
        [
            str(model_name).strip() or "model",
            str(architecture).strip() or "unknown_arch",
            str(objective).strip() or "unknown_obj",
            str(segment_strategy).strip() or "unknown_segment",
            str(feature_set_id).strip() or "unknown_features",
        ]
    )


def standard_model_metadata(
    *,
    model_name: str,
    dataset_id: str,
    dataset_snapshot_id: str | None = None,
    forecast_grain: str,
    feature_tier: str,
    trigger_source: str | None = None,
    change_category: str | None = None,
    segment_strategy: str = "global",
    rule_overlay_enabled: bool = False,
    evaluation_window_days: int = 30,
    architecture: str = "lightgbm",
    objective: str = "poisson",
    feature_set_id: str | None = None,
    tuning_profile: str = "baseline",
    lineage_label: str | None = None,
    baseline_version: str | None = None,
    candidate_version: str | None = None,
    interval_method: str | None = None,
    calibration_status: str | None = None,
    interval_coverage: float | None = None,
    conformal_residual_quantile: float | None = None,
) -> dict[str, Any]:
    feature_set = feature_set_id or f"{feature_tier}_v1"
    return {
        "model_name": model_name,
        "dataset_id": dataset_id,
        "dataset_snapshot_id": dataset_snapshot_id,
        "forecast_grain": forecast_grain,
        "feature_tier": feature_tier,
        "feature_set_id": feature_set,
        "segment_strategy": segment_strategy,
        "rule_overlay_enabled": rule_overlay_enabled,
        "evaluation_window_days": evaluation_window_days,
        "architecture": architecture,
        "objective": objective,
        "tuning_profile": tuning_profile,
        "trigger_source": trigger_source,
        "change_category": change_category,
        "baseline_version": baseline_version,
        "candidate_version": candidate_version,
        "interval_method": interval_method,
        "calibration_status": calibration_status,
        "interval_coverage": interval_coverage,
        "conformal_residual_quantile": conformal_residual_quantile,
        "lineage_label": lineage_label
        or build_lineage_label(
            model_name=model_name,
            architecture=architecture,
            objective=objective,
            segment_strategy=segment_strategy,
            feature_set_id=feature_set,
        ),
    }


def append_lifecycle_event(
    metrics: dict[str, Any] | None,
    *,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    reason: str | None = None,
    actor: str | None = None,
    related_version: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(metrics or {})
    events = list(payload.get("lifecycle_events", []))
    event = {
        "event_type": event_type,
        "at": datetime.now(timezone.utc).isoformat(),
        "from_status": from_status,
        "to_status": to_status,
        "reason": reason,
        "actor": actor,
        "related_version": related_version,
        "metadata": metadata or {},
    }
    events.append(event)
    payload["lifecycle_events"] = events[-50:]
    payload["last_lifecycle_event"] = event
    return payload
