"""Experiment governance helpers for manual-vs-agent DS workflows.

The functions in this module build a bounded context package from local model
and benchmark artifacts. The package is intentionally an audit artifact: it
freezes what a human analyst or AI agent was allowed to know before proposing
or running experiments.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ALLOWED_EXPERIMENT_TYPES = [
    "feature_set",
    "segmentation",
    "hyperparameter_tuning",
    "objective_function",
    "post_processing",
    "data_window",
    "data_contract",
    "architecture",
    "baseline_refresh",
]

PROVENANCE_LABELS = ["measured", "estimated", "simulated", "benchmark", "provisional", "unavailable"]

ROOT = Path(__file__).resolve().parents[2]
MODEL_METADATA_PATH = ROOT / "backend/models/v3/metadata.json"
FEATURE_IMPORTANCE_PATH = ROOT / "backend/models/v3/feature_importance.json"
DECISION_REPORT_PATH = ROOT / "backend/reports/experiments/m5_decision_aware_experiment.json"
OUTPUT_DIR = ROOT / "backend/reports/experiment_context"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _artifact_ref(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path.relative_to(ROOT)), "available": False}
    stat = path.stat()
    content = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "available": True,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def _top_features(feature_importance: dict[str, Any] | None, limit: int = 12) -> list[dict[str, Any]]:
    if not feature_importance:
        return []
    pairs = sorted(
        ((name, score) for name, score in feature_importance.items() if isinstance(score, int | float)),
        key=lambda item: item[1],
        reverse=True,
    )
    return [{"feature": name, "importance": round(float(score), 6)} for name, score in pairs[:limit]]


def _metric_subset(metrics: dict[str, Any] | None) -> dict[str, Any]:
    if not metrics:
        return {}
    keys = [
        "mae",
        "wape",
        "mase",
        "bias_pct",
        "coverage",
        "interval_coverage",
        "overstock_dollars",
        "opportunity_cost_stockout",
        "lost_sales_qty",
        "stockout_miss_rate",
        "overstock_rate",
        "provenance",
    ]
    return {key: metrics[key] for key in keys if key in metrics}


def _decision_report_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {"available": False}
    comparison = dict(report.get("promotion_comparison") or report.get("comparison") or {})
    baseline = dict(report.get("baseline") or {})
    challenger = dict(report.get("challenger") or {})
    return {
        "available": True,
        "claim_boundary": report.get("claim_boundary"),
        "overall_business_safe": report.get("overall_business_safe"),
        "decision": comparison.get("decision"),
        "reason": comparison.get("reason"),
        "promoted": comparison.get("promoted"),
        "gate_checks": comparison.get("gate_checks") or {},
        "baseline_metrics": _metric_subset(dict(baseline.get("holdout_metrics") or {})),
        "challenger_metrics": _metric_subset(dict(challenger.get("holdout_metrics") or {})),
        "lineage_metadata": dict(challenger.get("lineage_metadata") or report.get("lineage_metadata") or {}),
    }


def _source_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_context_package_payload(
    *,
    context_package_id: uuid.UUID,
    package_name: str,
    model_name: str,
    baseline_version: str | None,
    dataset_id: str | None,
    actor: str,
    package_type: str = "manual_vs_ai",
    allowed_experiment_types: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    metadata = _read_json(MODEL_METADATA_PATH) or {}
    feature_importance = _read_json(FEATURE_IMPORTANCE_PATH)
    decision_report = _read_json(DECISION_REPORT_PATH)

    resolved_dataset_id = dataset_id or metadata.get("dataset_id") or metadata.get("dataset") or "m5_walmart"
    resolved_baseline = baseline_version or metadata.get("version")
    dataset_snapshot = dict(metadata.get("dataset_snapshot") or {})
    decision_summary = _decision_report_summary(decision_report)
    report_lineage = dict(decision_summary.get("lineage_metadata") or {})
    dataset_snapshot_id = (
        report_lineage.get("dataset_snapshot_id")
        or metadata.get("dataset_snapshot_id")
        or dataset_snapshot.get("snapshot_id")
    )

    payload: dict[str, Any] = {
        "context_package_id": str(context_package_id),
        "package_name": package_name,
        "package_type": package_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": actor,
        "model_name": model_name,
        "baseline_version": resolved_baseline,
        "dataset_id": resolved_dataset_id,
        "dataset_snapshot_id": dataset_snapshot_id,
        "provenance": "benchmark",
        "provenance_labels": PROVENANCE_LABELS,
        "allowed_experiment_types": allowed_experiment_types or DEFAULT_ALLOWED_EXPERIMENT_TYPES,
        "claim_boundary": {
            "forecasting": "M5 benchmark evidence only.",
            "decision_replay": "Simulated replenishment replay, not measured merchant ROI.",
            "promotion": "No automatic promotion from benchmark replay without measured pilot outcomes.",
            "pilot": "Measured claims require CSV or Square pilot outcomes.",
        },
        "controls": {
            "split_protocol": "time_based_holdout",
            "random_train_test_splits_allowed": False,
            "autonomous_ordering_allowed": False,
            "direct_production_promotion_allowed": False,
            "human_review_required": True,
            "required_metric_provenance": PROVENANCE_LABELS,
        },
        "model_context": {
            "architecture": metadata.get("architecture"),
            "objective": metadata.get("objective"),
            "feature_set_id": metadata.get("feature_set_id"),
            "feature_tier": metadata.get("feature_tier"),
            "segment_strategy": metadata.get("segment_strategy"),
            "interval_method": metadata.get("interval_method"),
            "calibration_status": metadata.get("calibration_status"),
            "training_metrics": _metric_subset(dict(metadata.get("lightgbm_metrics") or {})),
            "holdout_metrics": _metric_subset(dict(metadata.get("holdout_metrics") or {})),
            "top_features": _top_features(feature_importance),
        },
        "decision_report_summary": decision_summary,
        "input_artifacts": {
            "model_metadata": _artifact_ref(MODEL_METADATA_PATH),
            "feature_importance": _artifact_ref(FEATURE_IMPORTANCE_PATH),
            "decision_aware_report": _artifact_ref(DECISION_REPORT_PATH),
        },
        "recommended_agent_scope": {
            "may_do": [
                "propose hypotheses",
                "draft experiment plans",
                "compare manual and agent-backed results",
                "surface risks and metric tradeoffs",
            ],
            "must_not_do": [
                "claim measured merchant ROI from benchmark replay",
                "promote a model without human approval",
                "drop provenance labels from metrics",
                "use random train/test splits for time-series evidence",
            ],
        },
        "notes": notes,
    }
    payload["context_hash"] = _source_hash(payload)
    return payload


def render_context_package_markdown(payload: dict[str, Any]) -> str:
    model = dict(payload.get("model_context") or {})
    decision = dict(payload.get("decision_report_summary") or {})
    top_features = model.get("top_features") or []
    feature_lines = "\n".join(
        f"- `{item['feature']}`: `{item['importance']}`" for item in top_features[:8]
    ) or "- unavailable"
    gates = decision.get("gate_checks") or {}
    gate_lines = "\n".join(f"- `{name}`: `{passed}`" for name, passed in gates.items()) or "- unavailable"

    return f"""# Experiment Context Package

- Context package: `{payload.get("context_package_id")}`
- Name: `{payload.get("package_name")}`
- Type: `{payload.get("package_type")}`
- Model: `{payload.get("model_name")}`
- Baseline version: `{payload.get("baseline_version")}`
- Dataset: `{payload.get("dataset_id")}`
- Dataset snapshot: `{payload.get("dataset_snapshot_id")}`
- Provenance: `{payload.get("provenance")}`
- Context hash: `{payload.get("context_hash")}`

## Claim Boundary

- Forecasting evidence is M5 benchmark evidence.
- Decision replay is simulated and cannot be presented as measured merchant ROI.
- Model promotion requires human approval and measured pilot evidence for business-impact claims.

## Controls

- Time-based holdout required.
- Random train/test splits are not allowed for this evidence path.
- Human review is required before execution and before promotion.
- Metrics must keep one of these provenance labels: `{", ".join(PROVENANCE_LABELS)}`.

## Model Context

- Architecture: `{model.get("architecture")}`
- Objective: `{model.get("objective")}`
- Feature set: `{model.get("feature_set_id")}`
- Segment strategy: `{model.get("segment_strategy")}`
- Interval method: `{model.get("interval_method")}`

## Top Driver Features

{feature_lines}

## Latest Decision Report

- Available: `{decision.get("available")}`
- Decision: `{decision.get("decision")}`
- Promoted: `{decision.get("promoted")}`
- Reason: `{decision.get("reason")}`

### Gates

{gate_lines}
"""


def write_context_package_artifacts(context_package_id: uuid.UUID, payload: dict[str, Any]) -> tuple[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / f"{context_package_id}.json"
    md_path = OUTPUT_DIR / f"{context_package_id}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    md_path.write_text(render_context_package_markdown(payload))
    return str(json_path.relative_to(ROOT)), str(md_path.relative_to(ROOT))
