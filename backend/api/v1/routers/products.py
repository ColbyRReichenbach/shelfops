"""
Products Router — CRUD for product catalog.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_tenant_db
from db.models import Product

router = APIRouter(prefix="/api/v1/products", tags=["products"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    unit_cost: float | None = Field(None, ge=0)
    unit_price: float | None = Field(None, ge=0)
    weight: float | None = None
    case_pack_size: int = 1
    moq: int = 0
    shelf_life_days: int | None = None
    is_seasonal: bool = False
    is_perishable: bool = False
    supplier_id: UUID | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    unit_cost: float | None = None
    unit_price: float | None = None
    weight: float | None = None
    case_pack_size: int | None = None
    moq: int | None = None
    shelf_life_days: int | None = None
    is_seasonal: bool | None = None
    is_perishable: bool | None = None
    supplier_id: UUID | None = None
    status: str | None = None


class ProductResponse(BaseModel):
    product_id: UUID
    customer_id: UUID
    sku: str
    name: str
    category: str | None
    subcategory: str | None
    brand: str | None
    unit_cost: float | None
    unit_price: float | None
    weight: float | None
    case_pack_size: int
    moq: int
    shelf_life_days: int | None
    is_seasonal: bool
    is_perishable: bool
    status: str
    supplier_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/", response_model=list[ProductResponse])
async def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    category: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_tenant_db),
):
    """List products with optional category and status filters."""
    query = select(Product)
    if category:
        query = query.where(Product.category == category)
    if status:
        query = query.where(Product.status == status)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a single product by ID."""
    result = await db.execute(select(Product).where(Product.product_id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    """Create a new product."""
    db_product = Product(
        **product.model_dump(),
        customer_id=user["customer_id"],
    )
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    update: ProductUpdate,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a product."""
    result = await db.execute(select(Product).where(Product.product_id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    product.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a product."""
    result = await db.execute(select(Product).where(Product.product_id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()
