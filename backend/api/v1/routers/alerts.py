"""
Alerts Router — Alert management endpoints.
"""

import math
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_tenant_db
from db.models import Action, Alert, PODecision, Product, PurchaseOrder, Transaction

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


class AlertOrderRequest(BaseModel):
    quantity: int | None = None
    reason_code: str | None = None
    notes: str | None = None


class AlertOrderResponse(BaseModel):
    status: str
    message: str
    po: dict
    alert: dict
    decision_id: UUID


class ReorderContextResponse(BaseModel):
    alert_id: UUID
    avg_sold_per_day_28d: float | None
    avg_sold_per_week_28d: float | None
    days_of_cover_current: float | None
    days_of_cover_after_order: float | None
    is_perishable: bool | None
    shelf_life_days: int | None
    suggested_qty: int | None
    lookback_days: int


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


@router.post("/{alert_id}/order", response_model=AlertOrderResponse)
async def order_from_alert(
    alert_id: UUID,
    body: AlertOrderRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    """
    Atomically convert a reorder alert into an approved purchase order.

    Workflow:
      1. Validate reorder alert and status
      2. Create PO (approved) and decision log
      3. Resolve alert and track linked_po_id metadata
      4. Log ordered action for auditability
    """
    result = await db.execute(select(Alert).where(Alert.alert_id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.alert_type != "reorder_recommended":
        raise HTTPException(status_code=422, detail="Only reorder_recommended alerts can be ordered")

    metadata = alert.alert_metadata.copy() if isinstance(alert.alert_metadata, dict) else {}
    linked_po_id = metadata.get("linked_po_id")

    # Idempotency: if this alert already links to a resolved order, return it.
    if alert.status == "resolved" and linked_po_id:
        try:
            existing_po_id = UUID(str(linked_po_id))
        except ValueError as exc:
            raise HTTPException(status_code=500, detail="Alert has invalid linked_po_id metadata") from exc

        existing_po = await db.get(PurchaseOrder, existing_po_id)
        if existing_po:
            existing_decision_result = await db.execute(
                select(PODecision)
                .where(PODecision.po_id == existing_po.po_id)
                .order_by(PODecision.decided_at.desc())
                .limit(1)
            )
            existing_decision = existing_decision_result.scalar_one_or_none()
            decision_id = existing_decision.decision_id if existing_decision else UUID("00000000-0000-0000-0000-000000000000")
            return AlertOrderResponse(
                status="success",
                message="Order already exists for this alert",
                po=_serialize_po(existing_po),
                alert=_serialize_alert(alert),
                decision_id=decision_id,
            )

    if alert.status not in ("open", "acknowledged"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot order from alert in '{alert.status}' status. Must be 'open' or 'acknowledged'.",
        )

    suggested_qty_raw = metadata.get("suggested_qty")
    suggested_qty = _parse_optional_positive_int(suggested_qty_raw)
    final_qty = body.quantity if body.quantity is not None else suggested_qty

    if final_qty is None:
        raise HTTPException(
            status_code=422,
            detail="Unable to determine order quantity. Provide quantity or include suggested_qty in alert metadata.",
        )
    if final_qty <= 0:
        raise HTTPException(status_code=422, detail="quantity must be greater than 0")
    if suggested_qty is not None and final_qty != suggested_qty and not body.reason_code:
        raise HTTPException(status_code=422, detail="reason_code required when overriding suggested_qty")

    product = await db.get(Product, alert.product_id)
    estimated_cost = float(final_qty * product.unit_cost) if product and product.unit_cost is not None else None

    po = PurchaseOrder(
        customer_id=alert.customer_id,
        store_id=alert.store_id,
        product_id=alert.product_id,
        supplier_id=product.supplier_id if product else None,
        quantity=final_qty,
        estimated_cost=estimated_cost,
        status="approved",
        ordered_at=datetime.utcnow(),
        source_type="vendor_direct",
    )
    db.add(po)
    await db.flush()

    decision = PODecision(
        customer_id=alert.customer_id,
        po_id=po.po_id,
        decision_type="edited" if suggested_qty is not None and final_qty != suggested_qty else "approved",
        original_qty=suggested_qty if suggested_qty is not None else final_qty,
        final_qty=final_qty,
        reason_code=body.reason_code,
        notes=body.notes,
        decided_by=user.get("email", "unknown"),
    )
    db.add(decision)

    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    metadata["linked_po_id"] = str(po.po_id)
    alert.alert_metadata = metadata

    action = Action(
        customer_id=alert.customer_id,
        alert_id=alert.alert_id,
        action_type="ordered",
        notes=body.notes,
        taken_by=user.get("email", "unknown"),
    )
    db.add(action)

    await db.commit()
    await db.refresh(alert)
    await db.refresh(po)

    return AlertOrderResponse(
        status="success",
        message="Order created and alert resolved",
        po=_serialize_po(po),
        alert=_serialize_alert(alert),
        decision_id=decision.decision_id,
    )


@router.get("/reorder-context", response_model=list[ReorderContextResponse])
async def get_reorder_context(
    statuses: str = Query("open,acknowledged"),
    lookback_days: int = Query(28, ge=7, le=90),
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Return decision context for reorder alerts.

    Context includes recent sales velocity and days-of-cover calculations so HITL
    approvers can manually right-size quantity (especially for perishables).
    """
    parsed_statuses = [s.strip() for s in statuses.split(",") if s.strip()]
    if not parsed_statuses:
        parsed_statuses = ["open", "acknowledged"]

    alerts_result = await db.execute(
        select(Alert)
        .where(
            Alert.alert_type == "reorder_recommended",
            Alert.status.in_(parsed_statuses),
        )
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    alerts = alerts_result.scalars().all()
    if not alerts:
        return []

    store_ids = {alert.store_id for alert in alerts}
    product_ids = {alert.product_id for alert in alerts}
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    sales_result = await db.execute(
        select(
            Transaction.store_id,
            Transaction.product_id,
            func.coalesce(func.sum(Transaction.quantity), 0).label("qty_sold"),
        )
        .where(
            Transaction.transaction_type == "sale",
            Transaction.timestamp >= cutoff,
            Transaction.store_id.in_(store_ids),
            Transaction.product_id.in_(product_ids),
        )
        .group_by(Transaction.store_id, Transaction.product_id)
    )
    sales_by_pair = {(row.store_id, row.product_id): float(row.qty_sold or 0) for row in sales_result.all()}

    product_result = await db.execute(
        select(Product.product_id, Product.is_perishable, Product.shelf_life_days).where(Product.product_id.in_(product_ids))
    )
    product_context = {
        row.product_id: {
            "is_perishable": bool(row.is_perishable) if row.is_perishable is not None else None,
            "shelf_life_days": row.shelf_life_days,
        }
        for row in product_result.all()
    }

    response: list[ReorderContextResponse] = []
    for alert in alerts:
        metadata = alert.alert_metadata if isinstance(alert.alert_metadata, dict) else {}
        current_stock = _parse_optional_nonnegative_number(metadata.get("current_stock"))
        suggested_qty = _parse_optional_positive_int(metadata.get("suggested_qty"))
        qty_28d = sales_by_pair.get((alert.store_id, alert.product_id), 0.0)
        avg_daily = qty_28d / lookback_days if lookback_days > 0 else None
        avg_weekly = avg_daily * 7 if avg_daily is not None else None

        days_of_cover_current = None
        days_of_cover_after = None
        if avg_daily and avg_daily > 0:
            if current_stock is not None:
                days_of_cover_current = current_stock / avg_daily
                if suggested_qty is not None:
                    days_of_cover_after = (current_stock + suggested_qty) / avg_daily

        prod = product_context.get(alert.product_id, {})
        response.append(
            ReorderContextResponse(
                alert_id=alert.alert_id,
                avg_sold_per_day_28d=round(avg_daily, 2) if avg_daily is not None else None,
                avg_sold_per_week_28d=round(avg_weekly, 2) if avg_weekly is not None else None,
                days_of_cover_current=round(days_of_cover_current, 1) if days_of_cover_current is not None else None,
                days_of_cover_after_order=round(days_of_cover_after, 1) if days_of_cover_after is not None else None,
                is_perishable=prod.get("is_perishable"),
                shelf_life_days=prod.get("shelf_life_days"),
                suggested_qty=suggested_qty,
                lookback_days=lookback_days,
            )
        )

    return response


def _parse_optional_positive_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_optional_nonnegative_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < 0:
        return None
    return parsed


def _serialize_po(po: PurchaseOrder) -> dict:
    return {
        "po_id": str(po.po_id),
        "customer_id": str(po.customer_id),
        "store_id": str(po.store_id),
        "product_id": str(po.product_id),
        "supplier_id": str(po.supplier_id) if po.supplier_id else None,
        "quantity": po.quantity,
        "estimated_cost": po.estimated_cost,
        "status": po.status,
        "suggested_at": po.suggested_at.isoformat() if po.suggested_at else None,
        "ordered_at": po.ordered_at.isoformat() if po.ordered_at else None,
        "expected_delivery": po.expected_delivery.isoformat() if po.expected_delivery else None,
        "received_at": po.received_at.isoformat() if po.received_at else None,
        "source_type": po.source_type,
        "source_id": str(po.source_id) if po.source_id else None,
        "promised_delivery_date": po.promised_delivery_date.isoformat() if po.promised_delivery_date else None,
        "actual_delivery_date": po.actual_delivery_date.isoformat() if po.actual_delivery_date else None,
        "received_qty": po.received_qty,
    }


def _serialize_alert(alert: Alert) -> dict:
    return {
        "alert_id": str(alert.alert_id),
        "customer_id": str(alert.customer_id),
        "store_id": str(alert.store_id),
        "product_id": str(alert.product_id),
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "message": alert.message,
        "alert_metadata": alert.alert_metadata,
        "status": alert.status,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }
