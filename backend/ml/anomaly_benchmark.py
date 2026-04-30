from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

FRESHRETAILNET_STOCKOUT_COLUMNS = [
    "store_id",
    "product_id",
    "dt",
    "sale_amount",
    "stock_hour6_22_cnt",
    "discount",
    "holiday_flag",
    "activity_flag",
    "precpt",
    "avg_temperature",
    "avg_humidity",
    "avg_wind_level",
    "first_category_id",
    "second_category_id",
    "third_category_id",
]

DEFAULT_ANOMALY_DATA_DIR = "data/benchmarks/freshretailnet_50k/raw"
DEFAULT_ANOMALY_EXPERIMENT_NAME = "freshretailnet_anomaly_spec_shadow"
DEFAULT_ANOMALY_HYPOTHESIS = (
    "A context-aware stockout anomaly detector can increase known-stockout recall while keeping "
    "false-positive cycle-count workload inside the review-rate gate."
)


@dataclass(frozen=True)
class AnomalyExperimentConfig:
    dataset_id: str = "freshretailnet_50k"
    baseline_version: str = "a1"
    challenger_version: str = "e_freshretailnet_anomaly_v1"
    model_name: str = "anomaly_detector"
    experiment_name: str = DEFAULT_ANOMALY_EXPERIMENT_NAME
    hypothesis: str = DEFAULT_ANOMALY_HYPOTHESIS
    experiment_type: str = "post_processing"
    experiment_spec_id: str | None = None
    experiment_spec_hash: str | None = None
    spec_template_id: str | None = None
    spec_name: str | None = None
    feature_set_id: str = "freshretailnet_balanced_context_v1"
    feature_config: dict[str, Any] = field(default_factory=dict)
    model_config: dict[str, Any] = field(default_factory=dict)
    promotion_gates: dict[str, Any] = field(default_factory=dict)
    max_rows: int | None = 250_000


def load_freshretailnet_eval_frame(
    data_dir: str | Path,
    *,
    max_rows: int | None = 250_000,
    lookback_days: int = 7,
) -> pd.DataFrame:
    """Load and prepare the FreshRetailNet eval split for stockout detector evidence."""
    return prepare_stockout_detection_frame(
        load_freshretailnet_raw_frame(data_dir, max_rows=max_rows),
        lookback_days=lookback_days,
    )


def load_freshretailnet_raw_frame(
    data_dir: str | Path,
    *,
    max_rows: int | None = 250_000,
) -> pd.DataFrame:
    """Load the FreshRetailNet eval split columns needed for anomaly benchmark evidence."""
    path = Path(data_dir) / "eval.parquet"
    if not path.exists():
        raise FileNotFoundError(f"FreshRetailNet eval split not found: {path}")

    frame = pd.read_parquet(path, columns=FRESHRETAILNET_STOCKOUT_COLUMNS)
    if max_rows and max_rows > 0:
        frame = frame.head(max_rows)
    return frame


def prepare_stockout_detection_frame(raw_frame: pd.DataFrame, *, lookback_days: int = 7) -> pd.DataFrame:
    """Create leakage-safe stockout-risk features from observed sales context."""
    lookback_days = max(2, min(int(lookback_days), 60))
    frame = raw_frame.copy()
    frame["date"] = pd.to_datetime(frame["dt"], errors="coerce")
    frame = frame.dropna(subset=["date"]).copy()
    frame["store_id"] = frame["store_id"].astype(str)
    frame["product_id"] = frame["product_id"].astype(str)
    frame["quantity"] = pd.to_numeric(frame["sale_amount"], errors="coerce").fillna(0.0)
    frame["stockout_label"] = (
        pd.to_numeric(frame["stock_hour6_22_cnt"], errors="coerce").fillna(0).astype(float) > 0
    ).astype(int)
    frame["discount"] = pd.to_numeric(frame.get("discount", 1.0), errors="coerce").fillna(1.0)
    frame["holiday_flag"] = pd.to_numeric(frame.get("holiday_flag", 0), errors="coerce").fillna(0).astype(int)
    frame["activity_flag"] = pd.to_numeric(frame.get("activity_flag", 0), errors="coerce").fillna(0).astype(int)
    frame["precpt"] = pd.to_numeric(frame.get("precpt", 0.0), errors="coerce").fillna(0.0)
    frame["avg_temperature"] = pd.to_numeric(frame.get("avg_temperature", 0.0), errors="coerce").fillna(0.0)
    frame["avg_humidity"] = pd.to_numeric(frame.get("avg_humidity", 0.0), errors="coerce").fillna(0.0)
    frame["avg_wind_level"] = pd.to_numeric(frame.get("avg_wind_level", 0.0), errors="coerce").fillna(0.0)
    frame["category"] = frame.get("third_category_id", "unknown").astype(str)

    frame = frame.sort_values(["store_id", "product_id", "date"], kind="mergesort").reset_index(drop=True)
    series = frame.groupby(["store_id", "product_id"], sort=False)["quantity"]
    prior_quantity = series.shift(1)
    frame["expected_sales_7d"] = prior_quantity.groupby([frame["store_id"], frame["product_id"]]).transform(
        lambda values: values.rolling(lookback_days, min_periods=2).mean()
    )
    frame["sales_std_7d"] = prior_quantity.groupby([frame["store_id"], frame["product_id"]]).transform(
        lambda values: values.rolling(lookback_days, min_periods=2).std()
    )
    frame["feature_lookback_days"] = lookback_days
    frame["sales_std_7d"] = frame["sales_std_7d"].fillna(0.0)
    frame["sales_gap_ratio"] = (
        (frame["expected_sales_7d"] - frame["quantity"]) / (frame["expected_sales_7d"] + 0.05)
    ).clip(lower=0.0, upper=2.0)
    frame["zero_sales_flag"] = (frame["quantity"] <= 0.001).astype(float)
    frame["promo_flag"] = ((frame["discount"] < 0.999) | (frame["activity_flag"] > 0)).astype(float)
    return frame


def _active_anomaly_feature_config(config: AnomalyExperimentConfig | None = None) -> dict[str, Any]:
    return {
        "include_sales_gap": True,
        "include_zero_sales": True,
        "include_promo": True,
        "include_holiday": True,
        "include_weather": True,
        "include_category_segments": True,
        **dict((config.feature_config if config else {}) or {}),
    }


def _active_anomaly_model_config(config: AnomalyExperimentConfig | None = None) -> dict[str, Any]:
    default_weights = {
        "sales_gap": 0.64,
        "zero_sales": 0.20,
        "promo": 0.08,
        "holiday": 0.04,
        "weather_stress": 0.04,
    }
    model_config = dict((config.model_config if config else {}) or {})
    weights = {**default_weights, **dict(model_config.get("weights") or {})}
    weight_sum = sum(max(0.0, float(value)) for value in weights.values())
    if weight_sum <= 0:
        weights = default_weights
        weight_sum = sum(weights.values())
    return {
        "architecture": "deterministic_stockout_risk_score",
        "objective": model_config.get("objective", "stockout_detection"),
        "threshold": float(model_config.get("threshold", 0.55)),
        "weights": {key: max(0.0, float(value)) / weight_sum for key, value in weights.items()},
    }


def score_stockout_risk(
    frame: pd.DataFrame,
    *,
    config: AnomalyExperimentConfig | None = None,
) -> pd.Series:
    """
    Score likely shelf/inventory integrity anomalies without using stockout labels.

    This intentionally favors precision over recall for the champion profile:
    false cycle-count work is costly for SMB operators, so high-risk items should
    be trusted before they affect a buyer queue.
    """
    feature_config = _active_anomaly_feature_config(config)
    weights = _active_anomaly_model_config(config)["weights"]
    sales_gap = frame["sales_gap_ratio"].fillna(0.0).clip(lower=0.0, upper=1.0)
    zero_sales = frame["zero_sales_flag"].fillna(0.0)
    promo = frame["promo_flag"].fillna(0.0)
    holiday = frame["holiday_flag"].fillna(0.0).astype(float)
    weather_stress = (frame["precpt"].fillna(0.0) > frame["precpt"].fillna(0.0).quantile(0.80)).astype(float) * 0.5 + (
        frame["avg_temperature"].fillna(0.0).abs() > frame["avg_temperature"].fillna(0.0).abs().quantile(0.90)
    ).astype(float) * 0.5

    components = {
        "sales_gap": sales_gap if feature_config["include_sales_gap"] else pd.Series(0.0, index=frame.index),
        "zero_sales": zero_sales if feature_config["include_zero_sales"] else pd.Series(0.0, index=frame.index),
        "promo": promo if feature_config["include_promo"] else pd.Series(0.0, index=frame.index),
        "holiday": holiday if feature_config["include_holiday"] else pd.Series(0.0, index=frame.index),
        "weather_stress": weather_stress if feature_config["include_weather"] else pd.Series(0.0, index=frame.index),
    }
    score = pd.Series(0.0, index=frame.index)
    for name, value in components.items():
        score = score + float(weights.get(name, 0.0)) * value
    return score.clip(
        lower=0.0,
        upper=1.0,
    )


def evaluate_binary_detector(
    y_true: pd.Series | np.ndarray,
    scores: pd.Series | np.ndarray,
    *,
    threshold: float,
) -> dict[str, Any]:
    y = np.asarray(y_true).astype(bool)
    pred = np.asarray(scores, dtype=float) >= threshold

    tp = int(np.logical_and(pred, y).sum())
    fp = int(np.logical_and(pred, ~y).sum())
    fn = int(np.logical_and(~pred, y).sum())
    tn = int(np.logical_and(~pred, ~y).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    false_positive_rate = fp / (fp + tn) if (fp + tn) else 0.0
    review_rate = (tp + fp) / len(y) if len(y) else 0.0

    return {
        "threshold": float(threshold),
        "rows": int(len(y)),
        "positives": int(y.sum()),
        "predicted_positive": int(pred.sum()),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "false_positive_rate": round(float(false_positive_rate), 4),
        "review_rate": round(float(review_rate), 4),
    }


def _segment_metrics(
    frame: pd.DataFrame,
    *,
    score_col: str,
    threshold: float,
    config: AnomalyExperimentConfig | None = None,
) -> dict[str, Any]:
    segments: dict[str, Any] = {}
    feature_config = _active_anomaly_feature_config(config)
    segment_sources = {}
    if feature_config["include_category_segments"]:
        segment_sources["category"] = frame.get("category", pd.Series(["unknown"] * len(frame), index=frame.index)).astype(str)
    segment_sources.update({
        "promo_flag": frame.get("promo_flag", pd.Series([0] * len(frame), index=frame.index)).astype(int).astype(str),
    })
    for source_name, values in segment_sources.items():
        for value in sorted(values.dropna().unique().tolist())[:12]:
            mask = values == value
            if int(mask.sum()) < 10:
                continue
            metrics = evaluate_binary_detector(
                frame.loc[mask, "stockout_label"],
                frame.loc[mask, score_col],
                threshold=threshold,
            )
            segments[f"{source_name}:{value}"] = {
                "available": True,
                "sample_rows": metrics["rows"],
                "low_sample": metrics["rows"] < 100,
                "metrics": {
                    key: metrics[key]
                    for key in ["precision", "recall", "f1", "false_positive_rate", "review_rate"]
                },
            }
    return segments


def _anomaly_lineage(config: AnomalyExperimentConfig, *, rows_eval: int) -> dict[str, Any]:
    model_config = _active_anomaly_model_config(config)
    return {
        "dataset_id": config.dataset_id,
        "experiment_spec_id": config.experiment_spec_id,
        "experiment_spec_hash": config.experiment_spec_hash,
        "spec_template_id": config.spec_template_id,
        "spec_name": config.spec_name,
        "feature_set_id": config.feature_set_id,
        "feature_config": _active_anomaly_feature_config(config),
        "architecture": model_config["architecture"],
        "objective": model_config["objective"],
        "threshold": model_config["threshold"],
        "model_config": model_config,
        "feature_tier": "benchmark",
        "rows_eval": rows_eval,
        "provenance": "benchmark",
        "claim_boundary": "FreshRetailNet benchmark anomaly evidence only. Buyer outcomes require real cycle-count feedback.",
    }


def _promotion_comparison(
    *,
    baseline_metrics: dict[str, Any],
    challenger_metrics: dict[str, Any],
    config: AnomalyExperimentConfig,
) -> dict[str, Any]:
    gates = {
        "precision_min": 0.40,
        "recall_min": 0.10,
        "false_positive_rate_max": 0.35,
        "review_rate_max": 0.40,
        "measured_feedback_required_for_promotion": True,
        **dict(config.promotion_gates or {}),
    }
    gate_checks = {
        "precision_gate": float(challenger_metrics.get("precision") or 0.0) >= float(gates["precision_min"]),
        "recall_gate": float(challenger_metrics.get("recall") or 0.0) >= float(gates["recall_min"]),
        "false_positive_rate_gate": float(challenger_metrics.get("false_positive_rate") or 1.0)
        <= float(gates["false_positive_rate_max"]),
        "review_rate_gate": float(challenger_metrics.get("review_rate") or 1.0) <= float(gates["review_rate_max"]),
        "measured_cycle_count_feedback_gate": False,
    }
    benchmark_gates_passed = all(value for key, value in gate_checks.items() if key != "measured_cycle_count_feedback_gate")
    failed = [key for key, value in gate_checks.items() if not value]
    reason = (
        "benchmark_gates_passed_but_cycle_count_feedback_unavailable"
        if benchmark_gates_passed
        else "failed_gates:" + ",".join(failed)
    )
    return {
        "promoted": False,
        "benchmark_gates_passed": benchmark_gates_passed,
        "decision": "continue_shadow_review",
        "reason": reason,
        "gate_checks": gate_checks,
        "champion_metrics": baseline_metrics,
        "challenger_metrics": challenger_metrics,
        "claim_boundary": "Promotion is blocked until measured cycle-count or buyer-review outcomes exist.",
    }


def render_anomaly_experiment_markdown(report: dict[str, Any]) -> str:
    baseline = report["baseline"]
    challenger = report["challenger"]
    comparison = report["promotion_comparison"]

    def metric(model: dict[str, Any], key: str) -> Any:
        value = (model.get("holdout_metrics") or {}).get(key)
        return "" if value is None else value

    lines = [
        "# Anomaly Detection Experiment Report",
        "",
        f"- experiment: `{report['experiment']['experiment_name']}`",
        f"- dataset_id: `{report['dataset']['dataset_id']}`",
        f"- provenance: `{report['dataset']['provenance']}`",
        f"- claim_boundary: {report['claim_boundary']}",
        "",
        "## Benchmark Metrics",
        "",
        "| model | version | precision | recall | f1 | false_positive_rate | review_rate | threshold | provenance |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label, row in [("champion", baseline), ("challenger", challenger)]:
        lines.append(
            f"| {label} | {row.get('version')} | {metric(row, 'precision')} | {metric(row, 'recall')} | "
            f"{metric(row, 'f1')} | {metric(row, 'false_positive_rate')} | {metric(row, 'review_rate')} | "
            f"{metric(row, 'threshold')} | {metric(row, 'provenance')} |"
        )
    lines.extend(
        [
            "",
            "## Shadow Decision",
            "",
            f"- decision: `{comparison['decision']}`",
            f"- benchmark_gates_passed: `{comparison['benchmark_gates_passed']}`",
            f"- promoted: `{comparison['promoted']}`",
            f"- reason: {comparison['reason']}",
            f"- claim_boundary: {comparison['claim_boundary']}",
            "",
        ]
    )
    return "\n".join(lines)


def run_anomaly_detection_experiment(
    *,
    data_dir: str | Path = DEFAULT_ANOMALY_DATA_DIR,
    config: AnomalyExperimentConfig | None = None,
    output_json: str | Path | None = None,
    output_md: str | Path | None = None,
) -> dict[str, Any]:
    active_config = config or AnomalyExperimentConfig()
    active_feature_config = _active_anomaly_feature_config(active_config)
    raw_frame = load_freshretailnet_raw_frame(data_dir, max_rows=active_config.max_rows)
    baseline_frame = prepare_stockout_detection_frame(raw_frame, lookback_days=7)
    frame = prepare_stockout_detection_frame(
        raw_frame,
        lookback_days=int(active_feature_config.get("lookback_days") or 7),
    )
    frame = frame[frame["expected_sales_7d"].notna()].copy()
    baseline_frame = baseline_frame.loc[frame.index].copy()

    baseline_config = AnomalyExperimentConfig(
        dataset_id=active_config.dataset_id,
        baseline_version=active_config.baseline_version,
        challenger_version=active_config.baseline_version,
        model_name=active_config.model_name,
        experiment_name=active_config.experiment_name,
        hypothesis=active_config.hypothesis,
        feature_set_id="freshretailnet_stockout_context_v1",
        model_config={
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
    )
    frame["risk_score_champion"] = score_stockout_risk(baseline_frame, config=baseline_config)
    frame["risk_score_challenger"] = score_stockout_risk(frame, config=active_config)

    baseline_threshold = _active_anomaly_model_config(baseline_config)["threshold"]
    challenger_threshold = _active_anomaly_model_config(active_config)["threshold"]
    baseline_metrics = evaluate_binary_detector(
        frame["stockout_label"], frame["risk_score_champion"], threshold=baseline_threshold
    )
    challenger_metrics = evaluate_binary_detector(
        frame["stockout_label"], frame["risk_score_challenger"], threshold=challenger_threshold
    )
    for metrics in (baseline_metrics, challenger_metrics):
        metrics.update(
            {
                "provenance": "benchmark",
                "target_label": "stock_hour6_22_cnt > 0",
                "cost_basis_provenance": "unavailable",
            }
        )

    comparison = _promotion_comparison(
        baseline_metrics=baseline_metrics,
        challenger_metrics=challenger_metrics,
        config=active_config,
    )
    lineage_metadata = _anomaly_lineage(active_config, rows_eval=int(len(frame)))
    report = {
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
            "dataset_id": active_config.dataset_id,
            "provenance": "benchmark",
            "rows_eval": int(len(frame)),
            "date_min": str(frame["date"].min().date()) if len(frame) else None,
            "date_max": str(frame["date"].max().date()) if len(frame) else None,
            "positive_rate": round(float(frame["stockout_label"].mean()), 4) if len(frame) else 0.0,
        },
        "lineage_metadata": lineage_metadata,
        "baseline": {
            "version": active_config.baseline_version,
            "holdout_metrics": baseline_metrics,
            "segment_metrics": _segment_metrics(frame, score_col="risk_score_champion", threshold=baseline_threshold),
            "lineage_metadata": {
                **lineage_metadata,
                "feature_set_id": "freshretailnet_stockout_context_v1",
                "threshold": baseline_threshold,
            },
        },
        "challenger": {
            "version": active_config.challenger_version,
            "holdout_metrics": challenger_metrics,
            "segment_metrics": _segment_metrics(
                frame,
                score_col="risk_score_challenger",
                threshold=challenger_threshold,
                config=active_config,
            ),
            "lineage_metadata": lineage_metadata,
        },
        "promotion_comparison": comparison,
        "comparison": comparison,
        "overall_business_safe": bool(comparison["benchmark_gates_passed"]),
        "claim_boundary": "FreshRetailNet benchmark anomaly evidence only. Buyer outcomes require real cycle-count feedback.",
        "limitations": [
            "FreshRetailNet stockout labels are benchmark labels, not measured U.S. SMB cycle-count outcomes.",
            "Promotion remains shadow-only until buyer or cycle-count feedback is recorded.",
            "Detector scores use leakage-safe prior-sales context and observed exogenous context, not current stockout labels.",
        ],
        "config": asdict(active_config),
    }

    if output_json:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if output_md:
        output_md = Path(output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_anomaly_experiment_markdown(report) + "\n", encoding="utf-8")

    return report


def build_stockout_anomaly_report(
    data_dir: str | Path,
    *,
    max_rows: int | None = 250_000,
) -> dict[str, Any]:
    frame = load_freshretailnet_eval_frame(data_dir, max_rows=max_rows)
    frame = frame[frame["expected_sales_7d"].notna()].copy()
    frame["risk_score"] = score_stockout_risk(frame)

    profiles = [
        ("precision_first_stockout_sentinel", 0.55, "champion"),
        ("balanced_shadow_stockout_sentinel", 0.35, "challenger"),
        ("recall_first_stockout_sentinel", 0.25, "candidate"),
    ]
    results = []
    for name, threshold, status in profiles:
        row = evaluate_binary_detector(frame["stockout_label"], frame["risk_score"], threshold=threshold)
        row.update(
            {
                "model_name": name,
                "model_family": "anomaly_detector",
                "status": status,
                "target_label": "stock_hour6_22_cnt > 0",
                "provenance": "benchmark",
            }
        )
        results.append(row)

    return {
        "dataset_id": "freshretailnet_50k",
        "source_note": (
            "FreshRetailNet stockout labels are used for benchmark anomaly evidence. "
            "This is not measured U.S. merchant impact."
        ),
        "model_family": "anomaly_detector",
        "task": "stockout_and_inventory_integrity_anomaly_detection",
        "rows_eval": int(len(frame)),
        "date_min": str(frame["date"].min().date()) if len(frame) else None,
        "date_max": str(frame["date"].max().date()) if len(frame) else None,
        "positive_rate": round(float(frame["stockout_label"].mean()), 4) if len(frame) else 0.0,
        "feature_set_id": "freshretailnet_stockout_context_v1",
        "evaluation_protocol": "time-ordered eval split, prior-7-day sales context, no stockout label leakage",
        "champion_version": "a1",
        "challenger_version": "a2",
        "promotion_decision": {
            "decision": "keep_champion_shadow_challenger",
            "reason": (
                "Champion profile has materially lower false-positive rate for cycle-count workload; "
                "balanced challenger remains in shadow to test whether higher recall is worth extra review volume."
            ),
        },
        "results": results,
        "claim_boundary": "Benchmark anomaly evidence only. Buyer outcomes require real cycle-count feedback.",
    }
