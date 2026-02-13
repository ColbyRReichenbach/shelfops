"""
ML Alerts API — In-app notifications for model events requiring human attention.

Endpoints:
  GET /ml-alerts — List alerts (filter by status, severity)
  GET /ml-alerts/{id} — Get alert details
  PATCH /ml-alerts/{id}/read — Mark as read
  PATCH /ml-alerts/{id}/action — Take action (approve/dismiss)
  GET /ml-alerts/stats — Alert statistics (unread count by severity)
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import MLAlert

logger = structlog.get_logger()

router = APIRouter(prefix="/ml-alerts", tags=["ml-alerts"])


# ── Request/Response Models ─────────────────────────────────────────────────


class AlertActionRequest(BaseModel):
    action: Literal["approve", "dismiss"]
    notes: str | None = None


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("")
async def list_ml_alerts(
    status: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """
    List ML alerts with optional filters.

    Query params:
      - status: 'unread', 'read', 'actioned', 'dismissed'
      - severity: 'info', 'warning', 'critical'
      - alert_type: 'drift_detected', 'promotion_pending', etc.
      - limit: Max alerts to return (default 50)
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    # Build query
    query = select(MLAlert).where(MLAlert.customer_id == customer_id)

    if status:
        query = query.where(MLAlert.status == status)
    if severity:
        query = query.where(MLAlert.severity == severity)
    if alert_type:
        query = query.where(MLAlert.alert_type == alert_type)

    query = query.order_by(MLAlert.created_at.desc()).limit(limit)

    alerts_result = await db.execute(query)
    alerts = alerts_result.scalars().all()

    return [
        {
            "ml_alert_id": str(alert.ml_alert_id),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "alert_metadata": alert.alert_metadata,
            "status": alert.status,
            "action_url": alert.action_url,
            "created_at": alert.created_at.isoformat(),
            "read_at": alert.read_at.isoformat() if alert.read_at else None,
            "actioned_at": alert.actioned_at.isoformat() if alert.actioned_at else None,
        }
        for alert in alerts
    ]


@router.get("/stats")
async def get_alert_stats(
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Get alert statistics (unread count by severity).

    Returns:
        {
          "total_unread": 5,
          "critical_unread": 2,
          "warning_unread": 3,
          "info_unread": 0
        }
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    # Count unread by severity
    from sqlalchemy import func

    result = await db.execute(
        select(
            MLAlert.severity,
            func.count(MLAlert.ml_alert_id).label("count"),
        )
        .where(
            MLAlert.customer_id == customer_id,
            MLAlert.status == "unread",
        )
        .group_by(MLAlert.severity)
    )

    counts = {row.severity: row.count for row in result.all()}

    return {
        "total_unread": sum(counts.values()),
        "critical_unread": counts.get("critical", 0),
        "warning_unread": counts.get("warning", 0),
        "info_unread": counts.get("info", 0),
    }


@router.get("/{alert_id}")
async def get_alert_details(
    alert_id: str,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Get full details for a specific alert."""
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    # Get alert
    alert_result = await db.execute(
        select(MLAlert).where(
            MLAlert.ml_alert_id == uuid.UUID(alert_id),
            MLAlert.customer_id == customer_id,
        )
    )
    alert = alert_result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {
        "ml_alert_id": str(alert.ml_alert_id),
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "alert_metadata": alert.alert_metadata,
        "status": alert.status,
        "action_url": alert.action_url,
        "created_at": alert.created_at.isoformat(),
        "read_at": alert.read_at.isoformat() if alert.read_at else None,
        "actioned_at": alert.actioned_at.isoformat() if alert.actioned_at else None,
    }


@router.patch("/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Mark an alert as read."""
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    # Get alert
    alert_result = await db.execute(
        select(MLAlert).where(
            MLAlert.ml_alert_id == uuid.UUID(alert_id),
            MLAlert.customer_id == customer_id,
        )
    )
    alert = alert_result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Update status
    alert.status = "read"
    alert.read_at = datetime.utcnow()
    await db.commit()

    logger.info(
        "ml_alert.marked_read",
        alert_id=alert_id,
        alert_type=alert.alert_type,
    )

    return {
        "status": "success",
        "message": "Alert marked as read",
        "read_at": alert.read_at.isoformat(),
    }


@router.patch("/{alert_id}/action")
async def action_alert(
    alert_id: str,
    action_request: AlertActionRequest,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Take action on an alert (approve or dismiss).

    For 'approve' actions on drift_detected alerts:
      - Triggers model promotion workflow
      - Updates alert status to 'actioned'

    For 'dismiss' actions:
      - Updates alert status to 'dismissed'
      - No further action taken
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    # Get alert
    alert_result = await db.execute(
        select(MLAlert).where(
            MLAlert.ml_alert_id == uuid.UUID(alert_id),
            MLAlert.customer_id == customer_id,
        )
    )
    alert = alert_result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if action_request.action == "approve":
        # Handle approval based on alert type
        if alert.alert_type == "drift_detected":
            # Promote challenger to champion
            new_version = alert.alert_metadata.get("new_version") if alert.alert_metadata else None

            if new_version:
                from ml.arena import promote_to_champion

                await promote_to_champion(
                    db=db,
                    customer_id=customer_id,
                    model_name="demand_forecast",
                    version=new_version,
                )

                logger.info(
                    "ml_alert.drift_approved",
                    alert_id=alert_id,
                    new_version=new_version,
                    notes=action_request.notes,
                )

        alert.status = "actioned"
        alert.actioned_at = datetime.utcnow()
        message = "Alert approved and action taken"

    elif action_request.action == "dismiss":
        alert.status = "dismissed"
        message = "Alert dismissed"

        logger.info(
            "ml_alert.dismissed",
            alert_id=alert_id,
            alert_type=alert.alert_type,
            notes=action_request.notes,
        )

    await db.commit()

    return {
        "status": "success",
        "action": action_request.action,
        "message": message,
        "actioned_at": alert.actioned_at.isoformat() if alert.actioned_at else None,
    }
