"""
Planogram Lifecycle — Product-Shelf Assignment & Active Status Checks.

Prevents the system from reordering products that shouldn't be on shelf:
  - Delisted products (discontinued by retailer)
  - Seasonal products in off-season (e.g., sunscreen in December)
  - Products pending planogram reset (aisle reorganization)

Also provides minimum presentation quantity — the floor count needed
to maintain proper shelf appearance (facings × depth).

Agent: data-engineer
Skill: postgresql
"""

import uuid
from datetime import date, datetime

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Planogram, Product

logger = structlog.get_logger()

# Product lifecycle states that should NOT trigger reorder alerts
NON_ORDERABLE_STATES = frozenset(
    {
        "delisted",
        "discontinued",
        "seasonal_out",
        "pending_activation",
    }
)


async def is_product_active_in_store(
    db: AsyncSession,
    product_id: uuid.UUID,
    store_id: uuid.UUID,
    check_date: date | None = None,
) -> bool:
    """
    Check if a product should be actively stocked at a store.

    A product is active if:
    1. Product lifecycle_state is orderable (not delisted/discontinued/seasonal_out)
    2. An active planogram exists for this (store, product) covering the check date

    If no planogram exists, falls back to product lifecycle_state only.
    """
    if check_date is None:
        check_date = date.today()

    # Check product lifecycle state
    product = await db.get(Product, product_id)
    if product is None:
        return False

    lifecycle = getattr(product, "lifecycle_state", "active") or "active"
    if lifecycle in NON_ORDERABLE_STATES:
        return False

    # Check planogram (if planogram_required)
    planogram_required = getattr(product, "planogram_required", False)
    if not planogram_required:
        return True  # No planogram needed, lifecycle check was sufficient

    result = await db.execute(
        select(Planogram).where(
            Planogram.store_id == store_id,
            Planogram.product_id == product_id,
            Planogram.status == "active",
            Planogram.effective_date <= check_date,
            # end_date is NULL (indefinite) or >= check_date
            (Planogram.end_date.is_(None)) | (Planogram.end_date >= check_date),
        )
    )
    planogram = result.scalar_one_or_none()

    if planogram is None:
        logger.warning(
            "planogram.missing_for_required_product",
            product_id=str(product_id),
            store_id=str(store_id),
        )
        return False

    return True


async def get_min_presentation_qty(
    db: AsyncSession,
    product_id: uuid.UUID,
    store_id: uuid.UUID,
) -> int:
    """
    Return the minimum units needed to maintain shelf presentation.

    Based on planogram facings × minimum depth. If no planogram exists,
    returns a sensible default of 2 units (one facing, minimum depth).
    """
    result = await db.execute(
        select(Planogram).where(
            Planogram.store_id == store_id,
            Planogram.product_id == product_id,
            Planogram.status == "active",
        )
    )
    planogram = result.scalar_one_or_none()

    if planogram and planogram.min_presentation_qty:
        return planogram.min_presentation_qty

    # Default: assume 1 facing × 2 deep
    return 2
