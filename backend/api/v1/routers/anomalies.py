"""
Anomalies API — ML-detected and rule-based anomalies.

Endpoints:
  GET /anomalies — List anomalies (filter by type, severity)
  GET /anomalies/stats — Anomaly statistics
  GET /anomalies/ghost-stock — Ghost stock recommendations
  POST /anomalies/detect — Trigger anomaly detection manually
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import Anomaly

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/ml/anomalies", tags=["anomalies"])


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("")
async def list_anomalies(
    anomaly_type: str | None = None,
    severity: str | None = None,
    days: int = 7,
    limit: int = 100,
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """
    List detected anomalies.

    Query params:
      - anomaly_type: 'ml_detected', 'inventory_discrepancy', 'data_quality', etc.
      - severity: 'critical', 'warning', 'info'
      - days: Lookback period (default 7)
      - limit: Max results (default 100)
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    # Build query
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = select(Anomaly).where(
        Anomaly.customer_id == customer_id,
        Anomaly.detected_at >= cutoff,
    )

    if anomaly_type:
        query = query.where(Anomaly.anomaly_type == anomaly_type)
    if severity:
        query = query.where(Anomaly.severity == severity)

    query = query.order_by(Anomaly.detected_at.desc()).limit(limit)

    anomalies_result = await db.execute(query)
    anomalies = anomalies_result.scalars().all()

    # Get product names
    from db.models import Product

    return [
        {
            "anomaly_id": str(anom.anomaly_id),
            "store_id": str(anom.store_id),
            "product_id": str(anom.product_id),
            "anomaly_type": anom.anomaly_type,
            "severity": anom.severity,
            "description": anom.description,
            "anomaly_metadata": anom.anomaly_metadata,
            "detected_at": anom.detected_at.isoformat(),
        }
        for anom in anomalies
    ]


@router.get("/stats")
async def get_anomaly_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Get anomaly statistics.

    Returns:
        {
          "total_anomalies": 24,
          "critical": 5,
          "warning": 15,
          "info": 4,
          "by_type": {
            "ml_detected": 18,
            "inventory_discrepancy": 6
          },
          "trend": "increasing"  # vs previous period
        }
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    cutoff = datetime.utcnow() - timedelta(days=days)
    prev_cutoff = cutoff - timedelta(days=days)

    # Count current period by severity
    severity_result = await db.execute(
        select(
            Anomaly.severity,
            func.count(Anomaly.anomaly_id).label("count"),
        )
        .where(
            Anomaly.customer_id == customer_id,
            Anomaly.detected_at >= cutoff,
        )
        .group_by(Anomaly.severity)
    )
    severity_counts = {row.severity: row.count for row in severity_result.all()}

    # Count by type
    type_result = await db.execute(
        select(
            Anomaly.anomaly_type,
            func.count(Anomaly.anomaly_id).label("count"),
        )
        .where(
            Anomaly.customer_id == customer_id,
            Anomaly.detected_at >= cutoff,
        )
        .group_by(Anomaly.anomaly_type)
    )
    type_counts = {row.anomaly_type: row.count for row in type_result.all()}

    # Calculate trend
    current_total = sum(severity_counts.values())

    prev_result = await db.execute(
        select(func.count(Anomaly.anomaly_id)).where(
            Anomaly.customer_id == customer_id,
            Anomaly.detected_at >= prev_cutoff,
            Anomaly.detected_at < cutoff,
        )
    )
    prev_total = prev_result.scalar() or 0

    if prev_total > 0:
        trend_pct = ((current_total - prev_total) / prev_total) * 100
        if trend_pct > 20:
            trend = "increasing"
        elif trend_pct < -20:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable" if current_total == 0 else "increasing"

    return {
        "total_anomalies": current_total,
        "critical": severity_counts.get("critical", 0),
        "warning": severity_counts.get("warning", 0),
        "info": severity_counts.get("info", 0),
        "by_type": type_counts,
        "trend": trend,
        "period_days": days,
    }


@router.get("/ghost-stock")
async def get_ghost_stock_recommendations(
    limit: int = 20,
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """
    Get ghost stock (phantom inventory) recommendations for cycle counts.

    Returns products prioritized by:
      - Ghost stock probability
      - Value ($)
      - Shrinkage risk
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    # Use ghost stock recommendation function
    from ml.ghost_stock import recommend_cycle_counts

    recommendations = await recommend_cycle_counts(
        db=db,
        customer_id=customer_id,
        max_recommendations=limit,
    )

    return recommendations


@router.post("/detect")
async def trigger_anomaly_detection(
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Manually trigger anomaly detection (ML + ghost stock).

    Normally runs automatically every 6 hours + daily.
    Use this for on-demand analysis.
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    # Run ML anomaly detection
    from ml.anomaly import detect_anomalies_ml

    anomaly_result = await detect_anomalies_ml(
        db=db,
        customer_id=customer_id,
        contamination=0.05,
    )

    # Run ghost stock detection
    from ml.ghost_stock import detect_ghost_stock

    ghost_result = await detect_ghost_stock(
        db=db,
        customer_id=customer_id,
        lookback_days=7,
    )

    logger.info(
        "anomaly.manual_detect",
        customer_id=str(customer_id),
        ml_anomalies=anomaly_result["anomalies_detected"],
        ghost_stock=ghost_result["ghost_stock_detected"],
    )

    return {
        "status": "success",
        "message": "Anomaly detection completed",
        "ml_anomalies": {
            "detected": anomaly_result["anomalies_detected"],
            "critical": anomaly_result["critical_count"],
            "warning": anomaly_result["warning_count"],
        },
        "ghost_stock": {
            "detected": ghost_result["ghost_stock_detected"],
            "total_value": ghost_result["total_value"],
        },
        "detected_at": datetime.utcnow().isoformat(),
    }
