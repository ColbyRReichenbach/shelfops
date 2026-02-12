"""
Receiving Module — PO Receiving Workflow & Discrepancy Tracking.

Called when a purchase order is physically received at a store.
Handles the receiving workflow:
1. Update PO status and delivery dates
2. Compare received vs ordered quantities
3. Create discrepancy records for mismatches
4. Update store inventory levels
5. Trigger vendor scorecard recalculation

Agent: data-engineer
Skill: postgresql
"""

import uuid
from datetime import date, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    InventoryLevel,
    PurchaseOrder,
    ReceivingDiscrepancy,
)

logger = structlog.get_logger()


async def process_receiving(
    db: AsyncSession,
    po_id: uuid.UUID,
    received_qty: int,
    received_date: date,
    notes: str | None = None,
) -> dict:
    """
    Process PO receiving event.

    Returns summary dict with discrepancy info if any.
    """
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise ValueError(f"PO {po_id} not found")

    if po.status not in ("ordered", "approved"):
        raise ValueError(f"Cannot receive PO in status '{po.status}'")

    # 1. Update PO
    po.status = "received"
    po.received_qty = received_qty
    po.actual_delivery_date = received_date
    po.receiving_notes = notes

    # 2. Check for discrepancy
    discrepancy = None
    ordered_qty = po.quantity
    diff = received_qty - ordered_qty

    if diff != 0:
        if diff < 0:
            disc_type = "shortage"
        elif diff > 0:
            disc_type = "overage"
        else:
            disc_type = "shortage"

        discrepancy = ReceivingDiscrepancy(
            customer_id=po.customer_id,
            po_id=po_id,
            product_id=po.product_id,
            ordered_qty=ordered_qty,
            received_qty=received_qty,
            discrepancy_qty=abs(diff),
            discrepancy_type=disc_type,
            resolution_status="pending",
        )
        db.add(discrepancy)

    # 3. Update inventory (add received quantity)
    inv_result = await db.execute(
        select(InventoryLevel)
        .where(
            InventoryLevel.store_id == po.store_id,
            InventoryLevel.product_id == po.product_id,
        )
        .order_by(InventoryLevel.timestamp.desc())
        .limit(1)
    )
    latest_inv = inv_result.scalar_one_or_none()

    if latest_inv:
        # Create new inventory snapshot with received stock
        new_inv = InventoryLevel(
            customer_id=po.customer_id,
            store_id=po.store_id,
            product_id=po.product_id,
            quantity_on_hand=latest_inv.quantity_on_hand + received_qty,
            quantity_on_order=max(0, latest_inv.quantity_on_order - ordered_qty),
            quantity_in_transit=max(0, (latest_inv.quantity_in_transit or 0) - ordered_qty),
            quantity_available=(latest_inv.quantity_on_hand + received_qty) - latest_inv.quantity_reserved,
            quantity_reserved=latest_inv.quantity_reserved,
            timestamp=datetime.utcnow(),
        )
        db.add(new_inv)

    result = {
        "po_id": str(po_id),
        "status": "received",
        "ordered_qty": ordered_qty,
        "received_qty": received_qty,
        "has_discrepancy": diff != 0,
    }

    if diff != 0:
        result["discrepancy_type"] = disc_type
        result["discrepancy_qty"] = abs(diff)

    logger.info("receiving.processed", **result)
    return result
