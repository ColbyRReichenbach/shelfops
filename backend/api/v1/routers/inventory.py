"""
Inventory Router — Current stock levels and reorder status.

Agent: full-stack-engineer
Skill: fastapi
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from api.deps import get_tenant_db
from db.models import InventoryLevel, ReorderPoint, Product, Store

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


# ─── Schemas ────────────────────────────────────────────────────────────────

class InventoryItemResponse(BaseModel):
    store_id: UUID
    store_name: str
    product_id: UUID
    product_name: str
    category: str | None
    sku: str
    quantity_on_hand: int
    quantity_available: int
    reorder_point: int | None
    safety_stock: int | None
    status: str  # "ok", "low", "critical", "out_of_stock"
    last_updated: datetime

    model_config = {"from_attributes": True}


class InventorySummary(BaseModel):
    total_items: int
    in_stock: int
    low_stock: int
    critical: int
    out_of_stock: int


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/summary", response_model=InventorySummary)
async def get_inventory_summary(
    store_id: UUID | None = None,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get high-level inventory status counts."""
    # Get latest inventory snapshot per store-product
    latest = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            func.max(InventoryLevel.timestamp).label("max_ts"),
        )
        .group_by(InventoryLevel.store_id, InventoryLevel.product_id)
    )
    if store_id:
        latest = latest.where(InventoryLevel.store_id == store_id)
    latest_sub = latest.subquery()

    query = (
        select(
            InventoryLevel.quantity_on_hand,
            ReorderPoint.reorder_point,
            ReorderPoint.safety_stock,
        )
        .join(
            latest_sub,
            and_(
                InventoryLevel.store_id == latest_sub.c.store_id,
                InventoryLevel.product_id == latest_sub.c.product_id,
                InventoryLevel.timestamp == latest_sub.c.max_ts,
            ),
        )
        .outerjoin(
            ReorderPoint,
            and_(
                ReorderPoint.store_id == InventoryLevel.store_id,
                ReorderPoint.product_id == InventoryLevel.product_id,
            ),
        )
    )

    result = await db.execute(query)
    rows = result.all()

    total = len(rows)
    out_of_stock = sum(1 for r in rows if r.quantity_on_hand == 0)
    critical = sum(
        1 for r in rows
        if r.quantity_on_hand > 0
        and r.safety_stock is not None
        and r.quantity_on_hand <= r.safety_stock
    )
    low = sum(
        1 for r in rows
        if r.reorder_point is not None
        and r.quantity_on_hand > (r.safety_stock or 0)
        and r.quantity_on_hand <= r.reorder_point
    )
    in_stock = total - out_of_stock - critical - low

    return InventorySummary(
        total_items=total,
        in_stock=in_stock,
        low_stock=low,
        critical=critical,
        out_of_stock=out_of_stock,
    )


@router.get("/", response_model=list[InventoryItemResponse])
async def list_inventory(
    store_id: UUID | None = None,
    status: str | None = None,
    category: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List current inventory levels with product/store details."""
    # Subquery: latest timestamp per store-product
    latest = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            func.max(InventoryLevel.timestamp).label("max_ts"),
        )
        .group_by(InventoryLevel.store_id, InventoryLevel.product_id)
    )
    if store_id:
        latest = latest.where(InventoryLevel.store_id == store_id)
    latest_sub = latest.subquery()

    query = (
        select(
            InventoryLevel.store_id,
            Store.name.label("store_name"),
            InventoryLevel.product_id,
            Product.name.label("product_name"),
            Product.category,
            Product.sku,
            InventoryLevel.quantity_on_hand,
            InventoryLevel.quantity_available,
            ReorderPoint.reorder_point,
            ReorderPoint.safety_stock,
            InventoryLevel.timestamp.label("last_updated"),
        )
        .join(
            latest_sub,
            and_(
                InventoryLevel.store_id == latest_sub.c.store_id,
                InventoryLevel.product_id == latest_sub.c.product_id,
                InventoryLevel.timestamp == latest_sub.c.max_ts,
            ),
        )
        .join(Product, Product.product_id == InventoryLevel.product_id)
        .join(Store, Store.store_id == InventoryLevel.store_id)
        .outerjoin(
            ReorderPoint,
            and_(
                ReorderPoint.store_id == InventoryLevel.store_id,
                ReorderPoint.product_id == InventoryLevel.product_id,
            ),
        )
    )

    if category:
        query = query.where(Product.category == category)

    # Fetch all to compute status, then filter
    result = await db.execute(query)
    rows = result.all()

    items = []
    for row in rows:
        qty = row.quantity_on_hand
        rp = row.reorder_point
        ss = row.safety_stock

        if qty == 0:
            item_status = "out_of_stock"
        elif ss is not None and qty <= ss:
            item_status = "critical"
        elif rp is not None and qty <= rp:
            item_status = "low"
        else:
            item_status = "ok"

        if status and item_status != status:
            continue

        items.append(InventoryItemResponse(
            store_id=row.store_id,
            store_name=row.store_name,
            product_id=row.product_id,
            product_name=row.product_name,
            category=row.category,
            sku=row.sku,
            quantity_on_hand=row.quantity_on_hand,
            quantity_available=row.quantity_available,
            reorder_point=rp,
            safety_stock=ss,
            status=item_status,
            last_updated=row.last_updated,
        ))

    return items[skip : skip + limit]
