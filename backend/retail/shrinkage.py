"""
Shrinkage Adjuster — Category-Based Inventory Shrinkage Estimation.

Real retail inventory != system inventory. Shrinkage from theft, spoilage,
damage, and admin errors reduces available stock by 1-8% annually depending
on category. Ignoring this leads to phantom inventory — the system thinks
you have 100 units but only 92 are sellable.

Default rates based on NRF 2022-24 National Retail Security Survey benchmarks.

Agent: data-engineer
Skill: postgresql
"""

import uuid
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Product, ShrinkageRate

logger = structlog.get_logger()

# NRF 2022-24 benchmarks — annual shrink rate by category
DEFAULT_SHRINK_RATES: dict[str, float] = {
    "Bakery": 0.080,  # 8.0% (spoilage dominates)
    "Produce": 0.048,  # 4.8% (spoilage)
    "Dairy": 0.025,  # 2.5% (expiration)
    "Meat & Seafood": 0.040,  # 4.0% (spoilage + markdowns)
    "Deli": 0.055,  # 5.5% (prepared food waste)
    "Frozen": 0.015,  # 1.5% (low spoilage)
    "Center Store": 0.010,  # 1.0% (shelf-stable)
    "Beverages": 0.012,  # 1.2%
    "Health & Beauty": 0.020,  # 2.0% (ORC theft target)
    "Electronics": 0.015,  # 1.5% (high-value theft)
    "Apparel": 0.025,  # 2.5% (ORC + damage)
    "Home & Garden": 0.018,  # 1.8%
    "Hardware": 0.012,  # 1.2%
    "Toys": 0.020,  # 2.0%
    "Seasonal": 0.030,  # 3.0% (markdowns + damage)
}

# Overall retail average when category is unknown
DEFAULT_OVERALL_RATE = 0.016  # 1.6% (NRF average)


async def get_shrink_rate(
    db: AsyncSession,
    product_id: uuid.UUID,
    store_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> float:
    """
    Look up shrinkage rate for a product at a store.

    Priority:
    1. Store-specific rate from shrinkage_rates table
    2. Category default from shrinkage_rates table (store_id IS NULL)
    3. Hardcoded NRF benchmark by category
    4. Overall retail average (1.6%)
    """
    # Get product category
    product = await db.get(Product, product_id)
    category = product.category if product else None

    # Check store-specific rate first
    result = await db.execute(
        select(ShrinkageRate).where(
            ShrinkageRate.customer_id == customer_id,
            ShrinkageRate.store_id == store_id,
            ShrinkageRate.category == category,
        )
    )
    store_rate = result.scalar_one_or_none()
    if store_rate:
        return store_rate.shrink_rate_pct

    # Check category default (store_id is NULL)
    result = await db.execute(
        select(ShrinkageRate).where(
            ShrinkageRate.customer_id == customer_id,
            ShrinkageRate.store_id.is_(None),
            ShrinkageRate.category == category,
        )
    )
    category_rate = result.scalar_one_or_none()
    if category_rate:
        return category_rate.shrink_rate_pct

    # Fall back to NRF benchmarks
    if category and category in DEFAULT_SHRINK_RATES:
        return DEFAULT_SHRINK_RATES[category]

    return DEFAULT_OVERALL_RATE


def apply_shrinkage_adjustment(
    inventory_qty: int,
    days_since_last_count: int,
    shrink_rate: float,
) -> int:
    """
    Estimate actual available inventory after shrinkage.

    Formula: adjusted = inventory × (1 - shrink_rate × days / 365)

    Example: 100 units, 30 days since last physical count, 4.8% annual shrink
    → 100 × (1 - 0.048 × 30/365) = 99.6 → 99 units estimated available

    The longer since last physical count, the greater the adjustment.
    Capped: never reduce below 0 or more than 50% (sanity check).
    """
    if inventory_qty <= 0 or days_since_last_count <= 0:
        return max(0, inventory_qty)

    shrink_factor = 1.0 - (shrink_rate * days_since_last_count / 365.0)
    # Sanity: never adjust more than 50% down
    shrink_factor = max(0.50, shrink_factor)

    return max(0, round(inventory_qty * shrink_factor))
