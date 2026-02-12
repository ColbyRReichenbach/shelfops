"""
Inventory Router — Current stock levels and reorder status.

Agent: full-stack-engineer
Skill: fastapi
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import InventoryLevel, Product, ReorderPoint, Store

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


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _latest_inventory_subquery(store_id: UUID | None = None):
    """Subquery: latest timestamp per (store_id, product_id)."""
    latest = select(
        InventoryLevel.store_id,
        InventoryLevel.product_id,
        func.max(InventoryLevel.timestamp).label("max_ts"),
    ).group_by(InventoryLevel.store_id, InventoryLevel.product_id)
    if store_id:
        latest = latest.where(InventoryLevel.store_id == store_id)
    return latest.subquery()


def _status_case_expression():
    """SQL CASE expression that computes inventory status."""
    return case(
        (InventoryLevel.quantity_on_hand == 0, literal("out_of_stock")),
        (
            and_(
                ReorderPoint.safety_stock.isnot(None),
                InventoryLevel.quantity_on_hand <= ReorderPoint.safety_stock,
            ),
            literal("critical"),
        ),
        (
            and_(
                ReorderPoint.reorder_point.isnot(None),
                InventoryLevel.quantity_on_hand <= ReorderPoint.reorder_point,
            ),
            literal("low"),
        ),
        else_=literal("ok"),
    ).label("status")


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/summary", response_model=InventorySummary)
async def get_inventory_summary(
    store_id: UUID | None = None,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get high-level inventory status counts."""
    latest_sub = _latest_inventory_subquery(store_id)
    status_col = _status_case_expression()

    query = (
        select(status_col)
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
    statuses = [row.status for row in result.all()]

    total = len(statuses)
    out_of_stock = statuses.count("out_of_stock")
    critical = statuses.count("critical")
    low = statuses.count("low")

    return InventorySummary(
        total_items=total,
        in_stock=total - out_of_stock - critical - low,
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
    latest_sub = _latest_inventory_subquery(store_id)
    status_col = _status_case_expression()

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
            status_col,
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

    # Filter by status in SQL — avoids loading all rows into memory
    if status:
        query = query.where(status_col == status)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return [
        InventoryItemResponse(
            store_id=row.store_id,
            store_name=row.store_name,
            product_id=row.product_id,
            product_name=row.product_name,
            category=row.category,
            sku=row.sku,
            quantity_on_hand=row.quantity_on_hand,
            quantity_available=row.quantity_available,
            reorder_point=row.reorder_point,
            safety_stock=row.safety_stock,
            status=row.status,
            last_updated=row.last_updated,
        )
        for row in result.all()
    ]
