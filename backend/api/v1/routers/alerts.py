"""
Alerts Router — Alert management endpoints.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_tenant_db
from db.models import Action, Alert, PurchaseOrder

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class AlertResponse(BaseModel):
    alert_id: UUID
    customer_id: UUID
    store_id: UUID
    product_id: UUID
    alert_type: str
    severity: str
    message: str
    alert_metadata: dict | None
    status: str
    created_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class AlertActionCreate(BaseModel):
    action_type: str
    notes: str | None = None


class AlertSummary(BaseModel):
    total: int
    open: int
    acknowledged: int
    resolved: int
    critical: int
    high: int


class AlertOrderCreate(BaseModel):
    quantity: int
    estimated_cost: float | None = None


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    store_id: UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List alerts with filters."""
    query = select(Alert)
    if store_id:
        query = query.where(Alert.store_id == store_id)
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)
    query = query.order_by(Alert.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/summary", response_model=AlertSummary)
async def get_alert_summary(
    store_id: UUID | None = None,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get alert summary counts."""
    base = select(Alert)
    if store_id:
        base = base.where(Alert.store_id == store_id)

    total_q = select(func.count()).select_from(base.subquery())
    open_q = select(func.count()).select_from(base.where(Alert.status == "open").subquery())
    ack_q = select(func.count()).select_from(base.where(Alert.status == "acknowledged").subquery())
    resolved_q = select(func.count()).select_from(base.where(Alert.status == "resolved").subquery())
    critical_q = select(func.count()).select_from(base.where(Alert.severity == "critical").subquery())
    high_q = select(func.count()).select_from(base.where(Alert.severity == "high").subquery())

    total = (await db.execute(total_q)).scalar() or 0
    open_count = (await db.execute(open_q)).scalar() or 0
    ack = (await db.execute(ack_q)).scalar() or 0
    resolved = (await db.execute(resolved_q)).scalar() or 0
    critical = (await db.execute(critical_q)).scalar() or 0
    high = (await db.execute(high_q)).scalar() or 0

    return AlertSummary(
        total=total,
        open=open_count,
        acknowledged=ack,
        resolved=resolved,
        critical=critical,
        high=high,
    )


@router.patch("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    """Acknowledge an alert."""
    result = await db.execute(select(Alert).where(Alert.alert_id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != "open":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot acknowledge alert in '{alert.status}' status. Must be 'open'.",
        )

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.utcnow()

    action = Action(
        customer_id=alert.customer_id,
        alert_id=alert_id,
        action_type="acknowledged",
        taken_by=user.get("email", "unknown"),
    )
    db.add(action)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.patch("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: UUID,
    body: AlertActionCreate,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    """Resolve an alert with notes."""
    result = await db.execute(select(Alert).where(Alert.alert_id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status not in ("open", "acknowledged"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resolve alert in '{alert.status}' status. Must be 'open' or 'acknowledged'.",
        )

    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()

    action = Action(
        customer_id=alert.customer_id,
        alert_id=alert_id,
        action_type="resolved",
        notes=body.notes,
        taken_by=user.get("email", "unknown"),
    )
    db.add(action)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.patch("/{alert_id}/dismiss", response_model=AlertResponse)
async def dismiss_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    """Dismiss an alert."""
    result = await db.execute(select(Alert).where(Alert.alert_id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status not in ("open", "acknowledged"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot dismiss alert in '{alert.status}' status. Must be 'open' or 'acknowledged'.",
        )

    alert.status = "dismissed"

    action = Action(
        customer_id=alert.customer_id,
        alert_id=alert_id,
        action_type="dismissed",
        taken_by=user.get("email", "unknown"),
    )
    db.add(action)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.post("/{alert_id}/order")
async def create_order_from_alert(
    alert_id: UUID,
    body: AlertOrderCreate,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    """Create a purchase order from an alert atomically."""
    result = await db.execute(select(Alert).where(Alert.alert_id == alert_id).with_for_update())
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status not in ("open", "acknowledged"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create order for alert in '{alert.status}' status. Must be 'open' or 'acknowledged'.",
        )

    metadata = dict(alert.alert_metadata or {})
    if metadata.get("linked_po_id"):
        raise HTTPException(status_code=409, detail="Alert already linked to a purchase order")

    po = PurchaseOrder(
        customer_id=alert.customer_id,
        store_id=alert.store_id,
        product_id=alert.product_id,
        quantity=body.quantity,
        estimated_cost=body.estimated_cost,
        status="suggested",
        source_type="alert",
        source_id=alert.alert_id,
    )
    db.add(po)
    await db.flush()

    metadata["linked_po_id"] = str(po.po_id)
    alert.alert_metadata = metadata
    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()

    action = Action(
        customer_id=alert.customer_id,
        alert_id=alert_id,
        action_type="ordered",
        notes=f"Created PO {po.po_id}",
        taken_by=user.get("email", "unknown"),
    )
    db.add(action)
    await db.commit()

    return {"po_id": po.po_id, "alert_id": alert.alert_id, "status": po.status}
