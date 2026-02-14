"""
Alert Outcomes Tracking — Measure alert effectiveness and false positive rates.

Purpose:
  - Track what happened after alerts were actioned
  - Measure false positive rate (alert fired but no issue)
  - Feedback loop for anomaly detection tuning
  - ROI calculation (alerts prevented $X in losses)

Workflow:
  1. Alert fires (stockout risk, ghost stock, etc.)
  2. Ops team investigates → action taken or dismissed
  3. Outcome recorded (true_positive, false_positive, prevented_stockout, etc.)
  4. Metrics aggregated for model tuning
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Alert, Anomaly

logger = structlog.get_logger()


# ── Outcome Recording ───────────────────────────────────────────────────────


async def record_alert_outcome(
    db: AsyncSession,
    customer_id: uuid.UUID,
    alert_id: uuid.UUID,
    outcome: str,
    outcome_notes: str | None = None,
    prevented_loss: float | None = None,
) -> dict[str, Any]:
    """
    Record the outcome of an alert after investigation.

    Args:
        db: Database session
        customer_id: Customer UUID
        alert_id: Alert UUID
        outcome: One of: true_positive, false_positive, prevented_stockout, prevented_overstock, ghost_stock_confirmed
        outcome_notes: Free-text notes from ops team
        prevented_loss: $ value of prevented loss (if applicable)

    Returns:
        {
            "status": "success",
            "alert_id": "...",
            "outcome": "true_positive",
            "prevented_loss": 5000.0
        }
    """
    # Get the alert
    result = await db.execute(
        select(Alert).where(
            Alert.alert_id == alert_id,
            Alert.customer_id == customer_id,
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        return {
            "status": "error",
            "message": "Alert not found",
        }

    # Update alert with outcome
    alert.status = "resolved" if outcome in ("true_positive", "prevented_stockout", "prevented_overstock", "ghost_stock_confirmed") else "dismissed"
    alert.resolved_at = datetime.utcnow()

    # Store outcome in metadata (we'll add an outcome field in a future migration)
    # For now, store in existing columns
    if outcome == "false_positive":
        alert.status = "dismissed"

    await db.commit()

    logger.info(
        "alert_outcome.recorded",
        customer_id=str(customer_id),
        alert_id=str(alert_id),
        outcome=outcome,
        prevented_loss=prevented_loss,
    )

    return {
        "status": "success",
        "alert_id": str(alert_id),
        "outcome": outcome,
        "prevented_loss": prevented_loss,
        "recorded_at": datetime.utcnow().isoformat(),
    }


async def record_anomaly_outcome(
    db: AsyncSession,
    customer_id: uuid.UUID,
    anomaly_id: uuid.UUID,
    outcome: str,
    outcome_notes: str | None = None,
    action_taken: str | None = None,
) -> dict[str, Any]:
    """
    Record the outcome of an anomaly after investigation.

    Args:
        db: Database session
        customer_id: Customer UUID
        anomaly_id: Anomaly UUID
        outcome: One of: true_positive, false_positive, resolved, investigating
        outcome_notes: Free-text notes
        action_taken: Action taken (cycle_count, price_adjustment, restock, etc.)

    Returns:
        {
            "status": "success",
            "anomaly_id": "...",
            "outcome": "true_positive"
        }
    """
    # Get the anomaly
    result = await db.execute(
        select(Anomaly).where(
            Anomaly.anomaly_id == anomaly_id,
            Anomaly.customer_id == customer_id,
        )
    )
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        return {
            "status": "error",
            "message": "Anomaly not found",
        }

    # Update anomaly status
    anomaly.status = outcome

    await db.commit()

    logger.info(
        "anomaly_outcome.recorded",
        customer_id=str(customer_id),
        anomaly_id=str(anomaly_id),
        outcome=outcome,
        action_taken=action_taken,
    )

    return {
        "status": "success",
        "anomaly_id": str(anomaly_id),
        "outcome": outcome,
        "action_taken": action_taken,
        "recorded_at": datetime.utcnow().isoformat(),
    }


# ── Effectiveness Metrics ───────────────────────────────────────────────────


async def calculate_alert_effectiveness(
    db: AsyncSession,
    customer_id: uuid.UUID,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """
    Calculate alert effectiveness metrics over the last N days.

    Metrics:
      - False positive rate (dismissed / total)
      - True positive rate (resolved / total)
      - Response time (time from alert to resolution)
      - Total prevented losses

    Returns:
        {
          "total_alerts": 150,
          "resolved": 120,
          "dismissed": 30,
          "false_positive_rate": 0.20,
          "avg_response_time_hours": 4.2,
          "total_prevented_loss": 47000.0
        }
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    # Count alerts by status
    status_result = await db.execute(
        select(
            Alert.status,
            func.count(Alert.alert_id).label("count"),
        )
        .where(
            Alert.customer_id == customer_id,
            Alert.created_at >= cutoff,
        )
        .group_by(Alert.status)
    )
    status_counts = {row.status: row.count for row in status_result.all()}

    total_alerts = sum(status_counts.values())
    resolved = status_counts.get("resolved", 0)
    dismissed = status_counts.get("dismissed", 0)

    false_positive_rate = dismissed / total_alerts if total_alerts > 0 else 0.0

    # Calculate average response time
    response_time_result = await db.execute(
        select(Alert).where(
            Alert.customer_id == customer_id,
            Alert.created_at >= cutoff,
            Alert.resolved_at.isnot(None),
        )
    )
    alerts_with_resolution = response_time_result.scalars().all()

    if alerts_with_resolution:
        response_times = [
            (alert.resolved_at - alert.created_at).total_seconds() / 3600
            for alert in alerts_with_resolution
        ]
        avg_response_time_hours = sum(response_times) / len(response_times)
    else:
        avg_response_time_hours = 0.0

    return {
        "total_alerts": total_alerts,
        "resolved": resolved,
        "dismissed": dismissed,
        "pending": status_counts.get("pending", 0),
        "acknowledged": status_counts.get("acknowledged", 0),
        "false_positive_rate": round(false_positive_rate, 3),
        "avg_response_time_hours": round(avg_response_time_hours, 1),
        "period_days": lookback_days,
    }


async def calculate_anomaly_effectiveness(
    db: AsyncSession,
    customer_id: uuid.UUID,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """
    Calculate anomaly detection effectiveness metrics.

    Returns:
        {
          "total_anomalies": 100,
          "true_positives": 75,
          "false_positives": 15,
          "investigating": 10,
          "precision": 0.83,
          "by_type": {
            "ml_detected": {"tp": 18, "fp": 2, "precision": 0.90},
            "inventory_discrepancy": {"tp": 57, "fp": 13, "precision": 0.81}
          }
        }
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    # Count anomalies by status
    status_result = await db.execute(
        select(
            Anomaly.status,
            func.count(Anomaly.anomaly_id).label("count"),
        )
        .where(
            Anomaly.customer_id == customer_id,
            Anomaly.detected_at >= cutoff,
        )
        .group_by(Anomaly.status)
    )
    status_counts = {row.status: row.count for row in status_result.all()}

    total_anomalies = sum(status_counts.values())
    true_positives = status_counts.get("resolved", 0)
    false_positives = status_counts.get("false_positive", 0)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0

    # Breakdown by anomaly type
    type_result = await db.execute(
        select(
            Anomaly.anomaly_type,
            Anomaly.status,
            func.count(Anomaly.anomaly_id).label("count"),
        )
        .where(
            Anomaly.customer_id == customer_id,
            Anomaly.detected_at >= cutoff,
        )
        .group_by(Anomaly.anomaly_type, Anomaly.status)
    )

    by_type = {}
    for row in type_result.all():
        if row.anomaly_type not in by_type:
            by_type[row.anomaly_type] = {"tp": 0, "fp": 0}

        if row.status == "resolved":
            by_type[row.anomaly_type]["tp"] = row.count
        elif row.status == "false_positive":
            by_type[row.anomaly_type]["fp"] = row.count

    # Calculate precision per type
    for anomaly_type, counts in by_type.items():
        tp = counts["tp"]
        fp = counts["fp"]
        counts["precision"] = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0

    return {
        "total_anomalies": total_anomalies,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "investigating": status_counts.get("investigating", 0),
        "precision": round(precision, 3),
        "by_type": by_type,
        "period_days": lookback_days,
    }


# ── ROI Calculation ─────────────────────────────────────────────────────────


async def calculate_alert_roi(
    db: AsyncSession,
    customer_id: uuid.UUID,
    lookback_days: int = 90,
) -> dict[str, Any]:
    """
    Calculate ROI of the alert system.

    Measures:
      - Prevented stockouts (forecast vs actual)
      - Prevented overstock (holding cost savings)
      - Ghost stock recovered (cycle count value)

    Returns:
        {
          "prevented_stockouts": 23,
          "prevented_stockout_value": 87000.0,
          "prevented_overstock_value": 12000.0,
          "ghost_stock_recovered_value": 98682.0,
          "total_value_created": 197682.0,
          "roi_multiple": 19.8  # $19.80 value per $1 system cost
        }
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    # This is a simplified calculation
    # In production, would track:
    # - Alerts that led to restocks before stockout
    # - Prevented overstock by adjusting orders
    # - Ghost stock confirmed and recovered

    # For now, use anomaly metadata to estimate value
    anomaly_result = await db.execute(
        select(Anomaly).where(
            Anomaly.customer_id == customer_id,
            Anomaly.detected_at >= cutoff,
            Anomaly.status == "resolved",
        )
    )
    resolved_anomalies = anomaly_result.scalars().all()

    ghost_stock_value = 0.0
    for anomaly in resolved_anomalies:
        if anomaly.anomaly_type == "inventory_discrepancy" and anomaly.anomaly_metadata:
            ghost_stock_value += anomaly.anomaly_metadata.get("ghost_value", 0.0)

    return {
        "prevented_stockouts": 0,  # Would need alert outcome tracking
        "prevented_stockout_value": 0.0,
        "prevented_overstock_value": 0.0,
        "ghost_stock_recovered_value": round(ghost_stock_value, 2),
        "total_value_created": round(ghost_stock_value, 2),
        "period_days": lookback_days,
        "note": "ROI calculation requires alert outcome tracking in production",
    }
