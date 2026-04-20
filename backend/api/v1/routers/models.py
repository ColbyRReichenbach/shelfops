"""
Model Health & MLOps API — Champion/Challenger status, backtesting, promotion.

Endpoints:
  GET /models/health — Champion/challenger status, recent performance
  GET /models/backtest/{version} — 90-day backtest time series
  POST /models/{version}/promote — Manual promotion (admin only)
  GET /models/history — Model version history
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_tenant_db
from db.models import ModelVersion
from ml.lineage import append_lifecycle_event

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/ml/models", tags=["models"])
MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
ROOT_DIR = Path(__file__).resolve().parents[4]


class PromoteModelRequest(BaseModel):
    promotion_reason: str = Field(min_length=8, max_length=500)


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _extract_model_card_bullets(section_name: str) -> list[str]:
    model_card_path = ROOT_DIR / "MODEL_CARD.md"
    if not model_card_path.exists():
        return []

    lines = model_card_path.read_text().splitlines()
    bullets: list[str] = []
    current_section: str | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue
        if current_section == section_name and line.startswith("- "):
            bullets.append(line[2:].strip())
        elif current_section == section_name and line and not line.startswith("- "):
            if bullets:
                break
    return bullets


def _build_benchmark_rows(
    *,
    benchmark_report: list[dict[str, Any]] | None,
    holdout_eval: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if holdout_eval:
        rows.append(
            {
                "label": "Active model holdout",
                "source": "Promotion holdout",
                "wape": holdout_eval.get("holdout_wape"),
                "mase": holdout_eval.get("holdout_mase"),
                "note": "Holdout result used when the active model was selected.",
            }
        )
        baseline = holdout_eval.get("baseline_to_beat") or {}
        if baseline:
            rows.append(
                {
                    "label": f"{str(baseline.get('model_name', 'baseline')).replace('_', ' ')} baseline",
                    "source": "Public benchmark",
                    "wape": baseline.get("wape"),
                    "mase": baseline.get("mase"),
                    "note": "Strongest simple public baseline on the same subset.",
                }
            )

    benchmark_entry = benchmark_report[0] if benchmark_report else None
    benchmark_results = benchmark_entry.get("results", []) if isinstance(benchmark_entry, dict) else []
    lightgbm_row = next(
        (row for row in benchmark_results if row.get("model_name") == "lightgbm"),
        None,
    )
    if lightgbm_row:
        rows.append(
            {
                "label": "Simple LightGBM benchmark",
                "source": "Public benchmark",
                "wape": lightgbm_row.get("wape"),
                "mase": lightgbm_row.get("mase"),
                "note": "Reference benchmark with a lighter feature set.",
            }
        )

    return [row for row in rows if row.get("wape") is not None and row.get("mase") is not None]


def _active_model_evidence_payload() -> dict[str, Any]:
    champion = _load_json(MODELS_DIR / "champion.json")
    if not isinstance(champion, dict):
        raise HTTPException(status_code=404, detail="Active champion artifact not found")

    version = champion.get("version")
    if not version:
        raise HTTPException(status_code=404, detail="Champion version missing from artifact")

    metadata = _load_json(MODELS_DIR / str(version) / "metadata.json")
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=404, detail=f"Metadata for champion {version} not found")

    benchmark_report = _load_json(ROOT_DIR / str(metadata.get("benchmark_report_path", "")))
    holdout_eval = _load_json(ROOT_DIR / str(metadata.get("holdout_evaluation_path", "")))
    dataset_snapshot = metadata.get("dataset_snapshot") or {}
    subset_provenance = metadata.get("subset_provenance") or {}
    lightgbm_metrics = metadata.get("lightgbm_metrics") or {}
    holdout_metrics = metadata.get("holdout_metrics") or {}
    benchmark_entry = benchmark_report[0] if isinstance(benchmark_report, list) and benchmark_report else {}
    segment_coverage = benchmark_entry.get("results", [{}])[0].get("segment_coverage", {}) if benchmark_entry else {}

    claim_boundary_bullets = _extract_model_card_bullets("Claim Boundaries")
    claim_boundary = (
        claim_boundary_bullets[0] if claim_boundary_bullets else "This is benchmark evidence, not pilot evidence."
    )
    limitations = claim_boundary_bullets[1:] or [
        "Live business results also depend on inventory position, vendor lead times, and operating policy.",
        "Use the Impact page to review live outcomes and scenario comparisons alongside model quality.",
    ]

    return {
        "version": version,
        "model_name": metadata.get("model_name"),
        "architecture": metadata.get("architecture"),
        "objective": metadata.get("objective"),
        "promoted_at": champion.get("promoted_at") or metadata.get("promoted_at"),
        "promotion_reason": metadata.get("promotion_reason"),
        "dataset_id": metadata.get("dataset_id") or metadata.get("dataset"),
        "dataset_snapshot_id": metadata.get("dataset_snapshot_id"),
        "rows_trained": dataset_snapshot.get("row_count"),
        "stores": dataset_snapshot.get("store_count"),
        "products": dataset_snapshot.get("product_count"),
        "categories": segment_coverage.get("categories"),
        "series_selected": subset_provenance.get("selected_series"),
        "subset_strategy": str(subset_provenance.get("subset_strategy", "")).replace("_", " "),
        "coverage_start": dataset_snapshot.get("date_min"),
        "coverage_end": dataset_snapshot.get("date_max"),
        "feature_tier": metadata.get("feature_tier") or lightgbm_metrics.get("feature_tier"),
        "feature_count": len(metadata.get("feature_cols") or []),
        "interval_method": metadata.get("interval_method"),
        "calibration_status": metadata.get("calibration_status"),
        "interval_coverage": metadata.get("interval_coverage"),
        "cv": {
            "mae": lightgbm_metrics.get("mae"),
            "wape": lightgbm_metrics.get("wape"),
            "mase": lightgbm_metrics.get("mase"),
            "bias_pct": lightgbm_metrics.get("bias_pct"),
        },
        "holdout": {
            "cutoff": holdout_metrics.get("cutoff") or (holdout_eval or {}).get("cutoff"),
            "mae": holdout_metrics.get("mae") or (holdout_eval or {}).get("holdout_mae"),
            "wape": holdout_metrics.get("wape") or (holdout_eval or {}).get("holdout_wape"),
            "mase": holdout_metrics.get("mase") or (holdout_eval or {}).get("holdout_mase"),
            "bias_pct": holdout_metrics.get("bias_pct") or (holdout_eval or {}).get("holdout_bias_pct"),
        },
        "benchmark_rows": _build_benchmark_rows(
            benchmark_report=benchmark_report if isinstance(benchmark_report, list) else None,
            holdout_eval=holdout_eval if isinstance(holdout_eval, dict) else None,
        ),
        "limitations": limitations,
        "claim_boundary": claim_boundary,
    }


def _resolve_customer_id(user: dict) -> uuid.UUID:
    raw = user.get("customer_id")
    if not raw:
        raise HTTPException(status_code=401, detail="No customer context set")
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid customer context") from exc


def _is_admin_user(user: dict) -> bool:
    role_values: list[str] = []
    for key in ("role", "roles", "permissions", "scopes", "scope"):
        value = user.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            role_values.extend(value.replace(",", " ").split())
        elif isinstance(value, (list, tuple, set)):
            role_values.extend([str(v) for v in value])
    roles = {r.strip().lower() for r in role_values if str(r).strip()}
    admin_markers = {"admin", "tenant_admin", "ml_admin", "owner", "platform_admin"}
    return bool(roles & admin_markers)


# ── Model Health Dashboard ──────────────────────────────────────────────────


@router.get("/evidence/active")
async def get_active_model_evidence(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    del user, db
    return _active_model_evidence_payload()


@router.get("/health")
async def get_model_health(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Get champion/challenger status and recent performance metrics.

    Returns:
        {
          "champion": {
            "version": "v12",
            "status": "healthy",
            "mae_7d": 11.2,
            "mae_30d": 11.8,
            "trend": "improving",
            "last_retrain": "2026-02-10T02:00:00Z",
            "next_retrain": "2026-02-17T02:00:00Z"
          },
          "challenger": {
            "version": "v13",
            "status": "shadow_testing",
            "shadow_mae_7d": 10.9,
            "promotion_eligible": true,
            "confidence": 0.92
          },
          "retraining_triggers": {
            "drift_detected": false,
            "new_data_available": true,
            "last_trigger": "scheduled"
          }
        }
    """
    from ml.arena import get_challenger_model, get_champion_model

    customer_id = _resolve_customer_id(user)

    # Get champion model
    champion = await get_champion_model(db, customer_id, "demand_forecast")
    champion_data = None
    if champion:
        # Get recent backtest results for champion
        from ml.backtest import get_backtest_trend

        backtest_7d = await get_backtest_trend(db, customer_id, champion["model_id"], days=7)
        backtest_30d = await get_backtest_trend(db, customer_id, champion["model_id"], days=30)

        mae_7d = sum(r["mae"] for r in backtest_7d if r["mae"]) / len(backtest_7d) if backtest_7d else None
        mae_30d = sum(r["mae"] for r in backtest_30d if r["mae"]) / len(backtest_30d) if backtest_30d else None

        # Determine trend
        trend = "stable"
        if mae_7d and mae_30d:
            if mae_7d < mae_30d * 0.95:
                trend = "improving"
            elif mae_7d > mae_30d * 1.05:
                trend = "degrading"

        # Determine health status
        status = "healthy"
        if trend == "degrading":
            status = "warning"

        champion_data = {
            "version": champion["version"],
            "status": status,
            "mae_7d": round(mae_7d, 2) if mae_7d else None,
            "mae_30d": round(mae_30d, 2) if mae_30d else None,
            "trend": trend,
            "promoted_at": champion["promoted_at"].isoformat() if champion.get("promoted_at") else None,
            "next_retrain": (
                datetime.now(timezone.utc) + timedelta(days=7 - datetime.now(timezone.utc).weekday())
            ).isoformat(),
        }

    # Get challenger model
    challenger = await get_challenger_model(db, customer_id, "demand_forecast")
    challenger_data = None
    if challenger:
        # Get challenger backtest results
        from ml.backtest import get_backtest_trend

        backtest_7d = await get_backtest_trend(db, customer_id, challenger["model_id"], days=7)
        mae_7d = sum(r["mae"] for r in backtest_7d if r["mae"]) / len(backtest_7d) if backtest_7d else None

        # Check promotion eligibility
        promotion_eligible = False
        confidence = 0.0
        if champion and mae_7d and champion_data and champion_data.get("mae_7d"):
            improvement = 1 - (mae_7d / champion_data["mae_7d"])
            promotion_eligible = improvement >= -0.02  # 2% non-regression tolerance
            confidence = min(0.99, max(0.5, improvement))

        challenger_data = {
            "version": challenger["version"],
            "status": "shadow_testing" if challenger.get("routing_weight", 0) == 0 else "canary",
            "mae_7d": round(mae_7d, 2) if mae_7d else None,
            "routing_weight": challenger.get("routing_weight", 0.0),
            "promotion_eligible": promotion_eligible,
            "confidence": round(confidence, 2) if confidence else None,
        }

    # Get recent retraining events
    from db.models import MLAlert, ModelRetrainingLog, Transaction

    retraining_result = await db.execute(
        select(
            ModelRetrainingLog.trigger_type,
            ModelRetrainingLog.started_at,
            ModelRetrainingLog.status,
            ModelRetrainingLog.version_produced,
            ModelRetrainingLog.trigger_metadata,
        )
        .where(
            ModelRetrainingLog.customer_id == customer_id,
            ModelRetrainingLog.model_name == "demand_forecast",
        )
        .order_by(ModelRetrainingLog.started_at.desc())
        .limit(1)
    )
    last_retrain = retraining_result.one_or_none()

    drift_cutoff = datetime.utcnow() - timedelta(days=7)
    drift_result = await db.execute(
        select(func.count(MLAlert.ml_alert_id))
        .where(
            MLAlert.customer_id == customer_id,
            MLAlert.alert_type == "drift_detected",
            MLAlert.created_at >= drift_cutoff,
            MLAlert.status.in_(["unread", "read", "actioned"]),
        )
        .limit(1)
    )
    recent_drift_alerts = int(drift_result.scalar() or 0)

    if last_retrain and last_retrain.started_at:
        # Strip tzinfo for comparison with naive timestamp columns
        ts = last_retrain.started_at
        tx_cutoff = ts.replace(tzinfo=None) if ts.tzinfo else ts
    else:
        tx_cutoff = datetime.utcnow() - timedelta(hours=24)
    new_data_result = await db.execute(
        select(func.count(Transaction.transaction_id)).where(
            Transaction.customer_id == customer_id,
            Transaction.timestamp > tx_cutoff,
            Transaction.transaction_type.in_(["sale", "return"]),
        )
    )
    new_data_row_count = int(new_data_result.scalar() or 0)

    retraining_triggers = {
        "drift_detected": recent_drift_alerts > 0,
        "new_data_available": new_data_row_count > 0,
        "new_data_rows_since_last_retrain": new_data_row_count,
        "last_trigger": last_retrain.trigger_type if last_retrain else None,
        "last_retrain_at": last_retrain.started_at.isoformat() if last_retrain else None,
    }

    recent_retraining_events_result = await db.execute(
        select(ModelRetrainingLog)
        .where(
            ModelRetrainingLog.customer_id == customer_id,
            ModelRetrainingLog.model_name == "demand_forecast",
        )
        .order_by(ModelRetrainingLog.started_at.desc())
        .limit(5)
    )
    recent_retraining_events = [
        {
            "trigger_type": row.trigger_type,
            "status": row.status,
            "version_produced": row.version_produced,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "trigger_metadata": row.trigger_metadata,
        }
        for row in recent_retraining_events_result.scalars().all()
    ]

    return {
        "champion": champion_data,
        "challenger": challenger_data,
        "retraining_triggers": retraining_triggers,
        "recent_retraining_events": recent_retraining_events,
        "models_count": (1 if champion else 0) + (1 if challenger else 0),
    }


# ── Backtest Time Series ────────────────────────────────────────────────────


@router.get("/backtest/{version}")
async def get_backtest_time_series(
    version: str,
    days: int = 90,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """
    Get 90-day backtest time series for a model version.

    Returns:
        [
          {
            "forecast_date": "2026-01-15",
            "mae": 11.2,
            "mape": 18.5,
            "stockout_miss_rate": 0.05,
            "overstock_rate": 0.12
          },
          ...
        ]
    """
    customer_id = _resolve_customer_id(user)

    # Get model ID for version
    model_result = await db.execute(
        select(ModelVersion.model_id)
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == "demand_forecast",
            ModelVersion.version == version,
        )
        .limit(1)
    )
    model_row = model_result.one_or_none()
    if not model_row:
        raise HTTPException(status_code=404, detail=f"Model version {version} not found")

    model_id = model_row.model_id

    # Get backtest trend
    from ml.backtest import get_backtest_trend

    trend = await get_backtest_trend(db, customer_id, model_id, days=days)
    return trend


# ── Manual Promotion ────────────────────────────────────────────────────────


@router.post("/{version}/promote")
async def promote_model(
    version: str,
    payload: PromoteModelRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Manually promote a model version to champion (admin only).

    This bypasses auto-promotion threshold checks.
    Use with caution — should only be done after manual review.
    """
    customer_id = _resolve_customer_id(user)
    if not _is_admin_user(user):
        raise HTTPException(status_code=403, detail="Manual promotion requires admin role")

    actor = str(user.get("email") or user.get("sub") or "unknown")
    reason = payload.promotion_reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="promotion_reason is required")

    # Check model exists
    model_result = await db.execute(
        select(ModelVersion)
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == "demand_forecast",
            ModelVersion.version == version,
        )
        .limit(1)
    )
    model = model_result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail=f"Model version {version} not found")

    # Check not already champion
    if model.status == "champion":
        raise HTTPException(status_code=400, detail=f"Model {version} is already champion")

    model_metrics = dict(model.metrics or {})
    original_status = model.status
    history = list(model_metrics.get("manual_promotion_history", []))
    entry = {
        "version": version,
        "reason": reason,
        "actor": actor,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    history.append(entry)
    model_metrics["last_manual_promotion"] = entry
    model_metrics["manual_promotion_history"] = history
    model_metrics = append_lifecycle_event(
        model_metrics,
        event_type="manual_promotion_requested",
        from_status=original_status,
        to_status="champion",
        reason=reason,
        actor=actor,
        related_version=version,
        metadata={"rollback": original_status == "archived"},
    )
    model.metrics = model_metrics
    await db.flush()

    # Promote
    from ml.arena import promote_to_champion

    await promote_to_champion(db, customer_id, "demand_forecast", version)

    from db.models import ModelExperiment

    db.add(
        ModelExperiment(
            customer_id=customer_id,
            experiment_name=f"manual_promotion_demand_forecast_{version}",
            hypothesis="Manual promotion approved by admin reviewer",
            experiment_type="rollback" if original_status == "archived" else "promotion_decision",
            model_name="demand_forecast",
            baseline_version=None,
            experimental_version=version,
            status="completed",
            proposed_by=actor,
            approved_by=actor,
            results={"reason": reason, "actor": actor, "manual": True, "rollback": original_status == "archived"},
            decision_rationale=reason,
            completed_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    try:
        from ml.experiment import sync_registry_with_runtime_state

        sync_registry_with_runtime_state(
            version=version,
            model_name="demand_forecast",
            candidate_status="champion",
            active_champion_version=version,
            promotion_reason="manual_promotion",
        )
    except Exception as exc:
        logger.warning(
            "models.manual_promotion_registry_sync_failed",
            customer_id=str(customer_id),
            version=version,
            error=str(exc),
            exc_info=True,
        )

    logger.info(
        "models.manual_promotion",
        customer_id=str(customer_id),
        version=version,
        promoted_by=actor,
        promotion_reason=reason,
    )

    return {
        "status": "success",
        "message": f"Model {version} promoted to champion",
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "promoted_by": actor,
        "promotion_reason": reason,
    }


# ── Model Version History ───────────────────────────────────────────────────


@router.get("/history")
async def get_model_history(
    limit: int = 10,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """
    Get model version history (last N versions).

    Returns:
        [
          {
            "version": "v12",
            "status": "champion",
            "mae": 11.2,
            "mape": 18.5,
            "created_at": "2026-02-10T02:00:00Z",
            "promoted_at": "2026-02-10T02:30:00Z"
          },
          ...
        ]
    """
    customer_id = _resolve_customer_id(user)

    # Get model versions
    versions_result = await db.execute(
        select(ModelVersion)
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == "demand_forecast",
        )
        .order_by(ModelVersion.created_at.desc())
        .limit(limit)
    )
    versions = versions_result.scalars().all()

    return [
        {
            "version": v.version,
            "status": v.status,
            "mae": v.metrics.get("mae") if v.metrics else None,
            "mape": v.metrics.get("mape") if v.metrics else None,
            "wape": v.metrics.get("wape") if v.metrics else None,
            "mase": v.metrics.get("mase") if v.metrics else None,
            "bias_pct": v.metrics.get("bias_pct") if v.metrics else None,
            "tier": v.metrics.get("tier") if v.metrics else None,
            "dataset_id": v.metrics.get("dataset_id") if v.metrics else None,
            "forecast_grain": v.metrics.get("forecast_grain") if v.metrics else None,
            "feature_set_id": v.metrics.get("feature_set_id") if v.metrics else None,
            "architecture": v.metrics.get("architecture") if v.metrics else None,
            "objective": v.metrics.get("objective") if v.metrics else None,
            "segment_strategy": v.metrics.get("segment_strategy") if v.metrics else None,
            "tuning_profile": v.metrics.get("tuning_profile") if v.metrics else None,
            "trigger_source": v.metrics.get("trigger_source") if v.metrics else None,
            "lineage_label": v.metrics.get("lineage_label") if v.metrics else None,
            "promotion_block_reason": v.metrics.get("promotion_block_reason") if v.metrics else None,
            "promotion_decision": v.metrics.get("promotion_decision") if v.metrics else None,
            "lifecycle_events": v.metrics.get("lifecycle_events", []) if v.metrics else [],
            "created_at": v.created_at.isoformat(),
            "promoted_at": v.promoted_at.isoformat() if v.promoted_at else None,
            "archived_at": v.archived_at.isoformat() if v.archived_at else None,
            "smoke_test_passed": v.smoke_test_passed,
        }
        for v in versions
    ]
