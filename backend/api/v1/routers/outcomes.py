"""
Alert Outcomes API — Track alert effectiveness and ROI.

Endpoints:
  POST /outcomes/alert/{alert_id} — Record alert outcome
  POST /outcomes/anomaly/{anomaly_id} — Record anomaly outcome
  GET /outcomes/alerts/effectiveness — Alert effectiveness metrics
  GET /outcomes/anomalies/effectiveness — Anomaly detection effectiveness
  GET /outcomes/roi — System ROI calculation
"""

import uuid
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db

logger = structlog.get_logger()

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


# ── Request/Response Models ─────────────────────────────────────────────────


class AlertOutcomeRequest(BaseModel):
    outcome: Literal[
        "true_positive",
        "false_positive",
        "prevented_stockout",
        "prevented_overstock",
        "ghost_stock_confirmed",
    ]
    outcome_notes: str | None = None
    prevented_loss: float | None = None


class AnomalyOutcomeRequest(BaseModel):
    outcome: Literal["true_positive", "false_positive", "resolved", "investigating"]
    outcome_notes: str | None = None
    action_taken: str | None = None  # cycle_count, price_adjustment, restock, etc.


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/alert/{alert_id}")
async def record_alert_outcome(
    alert_id: str,
    request: AlertOutcomeRequest,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Record the outcome of an alert after investigation.

    Valid outcomes:
      - true_positive: Alert was correct, action needed
      - false_positive: Alert was incorrect, no action needed
      - prevented_stockout: Alert led to restock, prevented stockout
      - prevented_overstock: Alert led to reduced order
      - ghost_stock_confirmed: Ghost stock was verified
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    from ml.alert_outcomes import record_alert_outcome as record_func

    result = await record_func(
        db=db,
        customer_id=customer_id,
        alert_id=uuid.UUID(alert_id),
        outcome=request.outcome,
        outcome_notes=request.outcome_notes,
        prevented_loss=request.prevented_loss,
    )

    if result["status"] == "error":
        status_code = 404 if result["message"] == "Alert not found" else 400
        raise HTTPException(status_code=status_code, detail=result["message"])

    return result


@router.post("/anomaly/{anomaly_id}")
async def record_anomaly_outcome(
    anomaly_id: str,
    request: AnomalyOutcomeRequest,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Record the outcome of an anomaly after investigation.

    Valid outcomes:
      - true_positive: Anomaly was real
      - false_positive: Anomaly was incorrect
      - resolved: Issue resolved
      - investigating: Still investigating
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    from ml.alert_outcomes import record_anomaly_outcome as record_func

    result = await record_func(
        db=db,
        customer_id=customer_id,
        anomaly_id=uuid.UUID(anomaly_id),
        outcome=request.outcome,
        outcome_notes=request.outcome_notes,
        action_taken=request.action_taken,
    )

    if result["status"] == "error":
        status_code = 404 if result["message"] == "Anomaly not found" else 400
        raise HTTPException(status_code=status_code, detail=result["message"])

    return result


@router.get("/alerts/effectiveness")
async def get_alert_effectiveness(
    days: int = 30,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Get alert effectiveness metrics.

    Returns false positive rate, response times, resolution stats.
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    from ml.alert_outcomes import calculate_alert_effectiveness

    effectiveness = await calculate_alert_effectiveness(
        db=db,
        customer_id=customer_id,
        lookback_days=days,
    )

    return effectiveness


@router.get("/anomalies/effectiveness")
async def get_anomaly_effectiveness(
    days: int = 30,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Get anomaly detection effectiveness metrics.

    Returns precision (TP / (TP + FP)), breakdown by type.
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    from ml.alert_outcomes import calculate_anomaly_effectiveness

    effectiveness = await calculate_anomaly_effectiveness(
        db=db,
        customer_id=customer_id,
        lookback_days=days,
    )

    return effectiveness


@router.get("/roi")
async def get_alert_roi(
    days: int = 90,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Calculate system ROI.

    Estimates value created from prevented stockouts, ghost stock recovery, etc.
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    from ml.alert_outcomes import calculate_alert_roi

    roi = await calculate_alert_roi(
        db=db,
        customer_id=customer_id,
        lookback_days=days,
    )

    return roi
