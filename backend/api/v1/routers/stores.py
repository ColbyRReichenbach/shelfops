"""
Stores Router — CRUD for store locations.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_current_user, get_tenant_db
from db.models import Store

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
    return result.scalars().all()


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
    return store


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
