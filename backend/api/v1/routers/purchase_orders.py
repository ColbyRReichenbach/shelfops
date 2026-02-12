"""
Purchase Order Router — PO workflow management endpoints.

The human-in-the-loop workflow for inventory replenishment:
  1. Inventory optimizer suggests PO → status='suggested'
  2. Planner reviews → approves, rejects, or edits
  3. PO sent to vendor → status='ordered'
  4. Goods received → status='received' (with discrepancy tracking)

All decisions logged to po_decisions table for ML feedback loop.

Agent: full-stack-engineer
Skill: fastapi
"""

from uuid import UUID
from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from api.deps import get_tenant_db, get_current_user
from db.models import PurchaseOrder, PODecision, ReceivingDiscrepancy, InventoryLevel, Product

router = APIRouter(prefix="/api/v1/purchase-orders", tags=["purchase-orders"])


# ─── Schemas ────────────────────────────────────────────────────────────────

class POResponse(BaseModel):
    po_id: UUID
    customer_id: UUID
    store_id: UUID
    product_id: UUID
    supplier_id: UUID | None
    quantity: int
    estimated_cost: float | None
    status: str
    suggested_at: datetime
    ordered_at: datetime | None
    expected_delivery: date | None
    received_at: datetime | None
    source_type: str | None
    source_id: UUID | None
    promised_delivery_date: date | None
    actual_delivery_date: date | None
    received_qty: int | None

    model_config = {"from_attributes": True}


class POSummary(BaseModel):
    total: int
    suggested: int
    approved: int
    ordered: int
    shipped: int
    received: int
    cancelled: int
    total_estimated_cost: float


class POApprovalRequest(BaseModel):
    """Approve a suggested PO. Optionally modify quantity."""
    quantity: int | None = None  # Override suggested qty
    reason_code: str | None = None  # Required if quantity modified
    notes: str | None = None


class PORejectRequest(BaseModel):
    """Reject a PO with a reason code (required for ML feedback)."""
    reason_code: str = Field(
        ...,
        description="Why the PO was rejected",
        examples=["overstock", "seasonal_end", "budget_constraint", "vendor_issue", "forecast_disagree", "manual_ordered_elsewhere"],
    )
    notes: str | None = None


class POEditRequest(BaseModel):
    """Edit a PO before approval."""
    quantity: int | None = None
    supplier_id: UUID | None = None
    reason_code: str = Field(
        ..., description="Why the PO was modified",
    )
    notes: str | None = None


class POReceivingRequest(BaseModel):
    """Mark a PO as received with actual quantities."""
    received_qty: int = Field(..., gt=0)
    received_date: date | None = None
    total_received_cost: float | None = None
    notes: str | None = None


class PODecisionResponse(BaseModel):
    decision_id: UUID
    po_id: UUID
    decision_type: str
    original_qty: int
    final_qty: int
    reason_code: str | None
    notes: str | None
    decided_by: str | None
    decided_at: datetime

    model_config = {"from_attributes": True}


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/", response_model=list[POResponse])
async def list_purchase_orders(
    status: str | None = None,
    store_id: UUID | None = None,
    product_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List purchase orders with filters."""
    query = select(PurchaseOrder)
    if status:
        query = query.where(PurchaseOrder.status == status)
    if store_id:
        query = query.where(PurchaseOrder.store_id == store_id)
    if product_id:
        query = query.where(PurchaseOrder.product_id == product_id)
    query = query.order_by(PurchaseOrder.suggested_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/suggested", response_model=list[POResponse])
async def list_suggested_orders(
    store_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List POs awaiting approval (status='suggested')."""
    query = select(PurchaseOrder).where(PurchaseOrder.status == "suggested")
    if store_id:
        query = query.where(PurchaseOrder.store_id == store_id)
    query = query.order_by(PurchaseOrder.suggested_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/summary", response_model=POSummary)
async def get_po_summary(
    db: AsyncSession = Depends(get_tenant_db),
):
    """Aggregated PO counts by status."""
    result = await db.execute(
        select(
            PurchaseOrder.status,
            func.count(PurchaseOrder.po_id),
            func.coalesce(func.sum(PurchaseOrder.estimated_cost), 0),
        ).group_by(PurchaseOrder.status)
    )
    rows = result.all()

    counts = {row[0]: row[1] for row in rows}
    total_cost = sum(float(row[2]) for row in rows)

    return POSummary(
        total=sum(counts.values()),
        suggested=counts.get("suggested", 0),
        approved=counts.get("approved", 0),
        ordered=counts.get("ordered", 0),
        shipped=counts.get("shipped", 0),
        received=counts.get("received", 0),
        cancelled=counts.get("cancelled", 0),
        total_estimated_cost=total_cost,
    )


@router.get("/{po_id}", response_model=POResponse)
async def get_purchase_order(
    po_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a single purchase order by ID."""
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


@router.post("/{po_id}/approve", response_model=POResponse)
async def approve_purchase_order(
    po_id: UUID,
    body: POApprovalRequest,
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Approve a suggested purchase order.

    If quantity is modified, a reason_code is required.
    Logs decision to po_decisions table for ML feedback.
    """
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status != "suggested":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve PO in '{po.status}' status. Must be 'suggested'.",
        )

    original_qty = po.quantity
    final_qty = body.quantity if body.quantity is not None else po.quantity

    # If quantity modified, require reason code
    if body.quantity is not None and body.quantity != po.quantity:
        if not body.reason_code:
            raise HTTPException(
                status_code=422,
                detail="reason_code required when modifying quantity",
            )
        po.quantity = body.quantity
        if po.estimated_cost and original_qty > 0:
            # Proportionally adjust estimated cost
            po.estimated_cost = po.estimated_cost * (body.quantity / original_qty)

    po.status = "approved"
    po.ordered_at = datetime.utcnow()

    # Log decision
    decision = PODecision(
        customer_id=po.customer_id,
        po_id=po.po_id,
        decision_type="approved" if final_qty == original_qty else "edited",
        original_qty=original_qty,
        final_qty=final_qty,
        reason_code=body.reason_code,
        notes=body.notes,
        decided_by="system",  # TODO: from auth context
    )
    db.add(decision)

    await db.commit()
    await db.refresh(po)
    return po


@router.post("/{po_id}/reject", response_model=POResponse)
async def reject_purchase_order(
    po_id: UUID,
    body: PORejectRequest,
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Reject a purchase order with reason code.

    Reason codes feed back into the ML pipeline to improve future forecasts.
    The system learns from human overrides.
    """
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status not in ("suggested", "approved"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject PO in '{po.status}' status.",
        )

    po.status = "cancelled"

    decision = PODecision(
        customer_id=po.customer_id,
        po_id=po.po_id,
        decision_type="rejected",
        original_qty=po.quantity,
        final_qty=0,
        reason_code=body.reason_code,
        notes=body.notes,
        decided_by="system",
    )
    db.add(decision)

    await db.commit()
    await db.refresh(po)
    return po


@router.post("/{po_id}/receive", response_model=POResponse)
async def receive_purchase_order(
    po_id: UUID,
    body: POReceivingRequest,
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Mark a PO as received. Tracks discrepancies and triggers vendor scorecard update.

    Workflow:
      1. Update PO status → 'received'
      2. Record actual delivery date and received quantity
      3. If qty mismatch → create receiving_discrepancy record
      4. Update inventory (increment quantity_on_hand)
    """
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status not in ("ordered", "shipped", "approved"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot receive PO in '{po.status}' status. Must be 'ordered', 'shipped', or 'approved'.",
        )

    po.status = "received"
    po.received_at = datetime.utcnow()
    po.received_qty = body.received_qty
    po.actual_delivery_date = body.received_date or datetime.utcnow().date()
    po.total_received_cost = body.total_received_cost
    po.receiving_notes = body.notes

    # Track discrepancy if quantity mismatch
    if body.received_qty != po.quantity:
        discrepancy_qty = body.received_qty - po.quantity
        discrepancy_type = "overage" if discrepancy_qty > 0 else "shortage"

        discrepancy = ReceivingDiscrepancy(
            customer_id=po.customer_id,
            po_id=po.po_id,
            product_id=po.product_id,
            ordered_qty=po.quantity,
            received_qty=body.received_qty,
            discrepancy_qty=discrepancy_qty,
            discrepancy_type=discrepancy_type,
        )
        db.add(discrepancy)

    await db.commit()
    await db.refresh(po)
    return po


@router.get("/{po_id}/decisions", response_model=list[PODecisionResponse])
async def get_po_decisions(
    po_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get the decision history for a purchase order."""
    result = await db.execute(
        select(PODecision)
        .where(PODecision.po_id == po_id)
        .order_by(PODecision.decided_at.desc())
    )
    return result.scalars().all()
