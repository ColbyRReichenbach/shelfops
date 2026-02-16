"""
Stores Router — CRUD for store locations.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_tenant_db
from db.models import Alert, InventoryLevel, ReorderPoint, Store

router = APIRouter(prefix="/api/v1/stores", tags=["stores"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class StoreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str | None = None
    city: str | None = None
    state: str | None = Field(None, min_length=2, max_length=2)
    zip_code: str | None = None
    lat: float | None = None
    lon: float | None = None
    timezone: str = "America/New_York"


class StoreUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    lat: float | None = None
    lon: float | None = None
    timezone: str | None = None
    status: str | None = None


class StoreResponse(BaseModel):
    store_id: UUID
    customer_id: UUID
    name: str
    address: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    lat: float | None
    lon: float | None
    timezone: str
    status: str
    created_at: datetime
    updated_at: datetime
    health_score: float | None = None
    last_sync: datetime | None = None

    model_config = {"from_attributes": True}


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/", response_model=list[StoreResponse])
async def list_stores(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all stores for the current customer."""
    query = select(Store)
    if status:
        query = query.where(Store.status == status)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    stores = result.scalars().all()
    health_map = await _build_store_health_map(db, [store.store_id for store in stores])
    return [_serialize_store(store, health_map) for store in stores]


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a single store by ID."""
    result = await db.execute(select(Store).where(Store.store_id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    health_map = await _build_store_health_map(db, [store.store_id])
    return _serialize_store(store, health_map)


@router.post("/", response_model=StoreResponse, status_code=201)
async def create_store(
    store: StoreCreate,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    """Create a new store."""
    db_store = Store(
        **store.model_dump(),
        customer_id=user["customer_id"],
    )
    db.add(db_store)
    await db.commit()
    await db.refresh(db_store)
    return db_store


@router.patch("/{store_id}", response_model=StoreResponse)
async def update_store(
    store_id: UUID,
    update: StoreUpdate,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a store."""
    result = await db.execute(select(Store).where(Store.store_id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    store.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(store)
    return store


@router.delete("/{store_id}", status_code=204)
async def delete_store(
    store_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a store."""
    result = await db.execute(select(Store).where(Store.store_id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    await db.delete(store)
    await db.commit()


def _serialize_store(store: Store, health_map: dict[UUID, dict]) -> dict:
    health = health_map.get(store.store_id, {})
    return {
        "store_id": store.store_id,
        "customer_id": store.customer_id,
        "name": store.name,
        "address": store.address,
        "city": store.city,
        "state": store.state,
        "zip_code": store.zip_code,
        "lat": store.lat,
        "lon": store.lon,
        "timezone": store.timezone,
        "status": store.status,
        "created_at": store.created_at,
        "updated_at": store.updated_at,
        "health_score": health.get("health_score"),
        "last_sync": health.get("last_sync"),
    }


async def _build_store_health_map(db: AsyncSession, store_ids: list[UUID]) -> dict[UUID, dict]:
    """
    Compute a 0-100 store health score from real operational signals:
      - Out-of-stock and low-stock pressure from latest inventory snapshots
      - Open/acknowledged alert burden by severity
      - Data freshness (hours since last inventory sync)
    """
    if not store_ids:
        return {}

    inv_latest_subq = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            func.max(InventoryLevel.timestamp).label("latest_ts"),
        )
        .where(InventoryLevel.store_id.in_(store_ids))
        .group_by(InventoryLevel.store_id, InventoryLevel.product_id)
        .subquery()
    )

    inv_rows_result = await db.execute(
        select(
            InventoryLevel.store_id,
            InventoryLevel.quantity_available,
            InventoryLevel.timestamp,
            ReorderPoint.reorder_point,
        )
        .join(
            inv_latest_subq,
            and_(
                InventoryLevel.store_id == inv_latest_subq.c.store_id,
                InventoryLevel.product_id == inv_latest_subq.c.product_id,
                InventoryLevel.timestamp == inv_latest_subq.c.latest_ts,
            ),
        )
        .join(
            ReorderPoint,
            and_(
                ReorderPoint.store_id == InventoryLevel.store_id,
                ReorderPoint.product_id == InventoryLevel.product_id,
            ),
            isouter=True,
        )
    )

    inventory_stats: dict[UUID, dict] = {
        store_id: {
            "total_items": 0,
            "out_of_stock": 0,
            "low_stock": 0,
            "last_sync": None,
        }
        for store_id in store_ids
    }
    for row in inv_rows_result.all():
        stats = inventory_stats.setdefault(
            row.store_id,
            {"total_items": 0, "out_of_stock": 0, "low_stock": 0, "last_sync": None},
        )
        stats["total_items"] += 1
        qty_available = int(row.quantity_available or 0)
        if qty_available <= 0:
            stats["out_of_stock"] += 1
        if row.reorder_point is not None and qty_available <= int(row.reorder_point):
            stats["low_stock"] += 1
        ts = row.timestamp
        if ts and (stats["last_sync"] is None or ts > stats["last_sync"]):
            stats["last_sync"] = ts

    alerts_result = await db.execute(
        select(Alert.store_id, Alert.severity, func.count().label("count"))
        .where(
            Alert.store_id.in_(store_ids),
            Alert.status.in_(["open", "acknowledged"]),
        )
        .group_by(Alert.store_id, Alert.severity)
    )

    alert_stats: dict[UUID, dict[str, int]] = {store_id: {} for store_id in store_ids}
    for row in alerts_result.all():
        severity_counts = alert_stats.setdefault(row.store_id, {})
        severity_counts[str(row.severity)] = int(row.count or 0)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    health_map: dict[UUID, dict] = {}
    for store_id in store_ids:
        inv = inventory_stats.get(store_id, {})
        sev = alert_stats.get(store_id, {})
        total_items = max(1, int(inv.get("total_items") or 0))
        out_ratio = (inv.get("out_of_stock", 0) or 0) / total_items
        low_ratio = (inv.get("low_stock", 0) or 0) / total_items

        critical = sev.get("critical", 0)
        high = sev.get("high", 0)
        medium = sev.get("medium", 0)

        score = 100.0
        score -= out_ratio * 45.0
        score -= low_ratio * 20.0
        score -= min(25.0, critical * 5.0 + high * 2.5 + medium * 1.0)

        last_sync = inv.get("last_sync")
        if last_sync is None:
            score -= 15.0
        else:
            hours_since_sync = (now - last_sync).total_seconds() / 3600.0
            if hours_since_sync > 48:
                score -= 20.0
            elif hours_since_sync > 24:
                score -= 10.0

        health_map[store_id] = {
            "health_score": round(max(0.0, min(100.0, score)), 1),
            "last_sync": last_sync,
        }

    return health_map
