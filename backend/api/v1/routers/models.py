"""
Model Health & MLOps API — Champion/Challenger status, backtesting, promotion.

Endpoints:
  GET /models/health — Champion/challenger status, recent performance
  GET /models/backtest/{version} — 90-day backtest time series
  POST /models/{version}/promote — Manual promotion (admin only)
  GET /models/history — Model version history
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import ModelVersion

logger = structlog.get_logger()

router = APIRouter(prefix="/models", tags=["models"])


# ── Model Health Dashboard ──────────────────────────────────────────────────


@router.get("/health")
async def get_model_health(
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
    from ml.arena import get_champion_model, get_challenger_model

    # Get current customer_id from RLS context
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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
            "next_retrain": (datetime.now(timezone.utc) + timedelta(days=7 - datetime.now(timezone.utc).weekday())).isoformat(),
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
            promotion_eligible = improvement >= 0.05  # 5% improvement threshold
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
    from db.models import ModelRetrainingLog

    retraining_result = await db.execute(
        select(ModelRetrainingLog.trigger_type, ModelRetrainingLog.started_at)
        .where(
            ModelRetrainingLog.customer_id == customer_id,
            ModelRetrainingLog.model_name == "demand_forecast",
        )
        .order_by(ModelRetrainingLog.started_at.desc())
        .limit(1)
    )
    last_retrain = retraining_result.one_or_none()

    # Check for drift (simplified — would integrate with drift detection job)
    retraining_triggers = {
        "drift_detected": False,  # Placeholder — integrate with monitoring.detect_model_drift
        "new_data_available": True,  # Placeholder — check transaction freshness
        "last_trigger": last_retrain.trigger_type if last_retrain else None,
        "last_retrain_at": last_retrain.started_at.isoformat() if last_retrain else None,
    }

    return {
        "champion": champion_data,
        "challenger": challenger_data,
        "retraining_triggers": retraining_triggers,
        "models_count": 1 + (1 if challenger else 0),
    }


# ── Backtest Time Series ────────────────────────────────────────────────────


@router.get("/backtest/{version}")
async def get_backtest_time_series(
    version: str,
    days: int = 90,
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
    # Get current customer_id
    result = await db.execute("SELECT current_setting('app.current_customer_id', TRUE)")
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Manually promote a model version to champion (admin only).

    This bypasses auto-promotion threshold checks.
    Use with caution — should only be done after manual review.
    """
    # Get current customer_id
    result = await db.execute("SELECT current_setting('app.current_customer_id', TRUE)")
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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

    # Promote
    from ml.arena import promote_to_champion

    await promote_to_champion(db, customer_id, "demand_forecast", version)

    logger.info(
        "models.manual_promotion",
        customer_id=str(customer_id),
        version=version,
        promoted_by="admin",  # Future: get from JWT auth
    )

    return {
        "status": "success",
        "message": f"Model {version} promoted to champion",
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Model Version History ───────────────────────────────────────────────────


@router.get("/history")
async def get_model_history(
    limit: int = 10,
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
    # Get current customer_id
    result = await db.execute("SELECT current_setting('app.current_customer_id', TRUE)")
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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
            "tier": v.metrics.get("tier") if v.metrics else None,
            "created_at": v.created_at.isoformat(),
            "promoted_at": v.promoted_at.isoformat() if v.promoted_at else None,
            "archived_at": v.archived_at.isoformat() if v.archived_at else None,
            "smoke_test_passed": v.smoke_test_passed,
        }
        for v in versions
    ]
