"""
Store Transfer Optimizer — Cross-Store Inventory Rebalancing.

When a store faces imminent stockout, sometimes the fastest remedy is to
transfer excess stock from a nearby store (2-day transfer) rather than
wait for a vendor order (7-14 days).

Algorithm:
1. Find stores within radius that have excess inventory (above safety stock + buffer)
2. Calculate transfer cost = distance × per-mile rate
3. Rank by (excess quantity × proximity)
4. Return top transfer options

Agent: data-engineer
Skill: postgresql
"""

import math
import uuid
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.models import (
    InventoryLevel,
    ReorderPoint,
    Store,
    StoreTransfer,
)
from retail.planogram import get_min_presentation_qty
from supply_chain.sourcing import haversine_miles

logger = structlog.get_logger()

_settings = get_settings()
# Transfer policy is configurable for tenant/operator realism.
COST_PER_MILE = float(_settings.transfer_cost_per_mile)
DEFAULT_TRANSFER_LEAD_DAYS = int(_settings.transfer_default_lead_days)
MAX_SEARCH_RADIUS_MILES = float(_settings.transfer_max_search_radius_miles)
NEARBY_DISTANCE_MILES = float(_settings.transfer_nearby_distance_miles)
HANDLING_COST_FLOOR = float(_settings.transfer_handling_cost_floor)


@dataclass
class TransferOption:
    """A potential store-to-store transfer opportunity."""

    from_store_id: uuid.UUID
    from_store_name: str
    distance_miles: float
    transfer_cost: float
    excess_quantity: int
    recommended_transfer_qty: int
    estimated_lead_days: int


async def find_transfer_opportunities(
    db: AsyncSession,
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    requesting_store_id: uuid.UUID,
    needed_qty: int = 0,
    max_results: int = 3,
    search_radius_miles: float = MAX_SEARCH_RADIUS_MILES,
) -> list[TransferOption]:
    """
    Find nearby stores with excess inventory for emergency rebalancing.

    Returns up to max_results transfer options, ranked by
    (excess inventory × proximity).
    """
    # Get requesting store location
    requesting_store = await db.get(Store, requesting_store_id)
    if not requesting_store or not requesting_store.lat or not requesting_store.lon:
        logger.warning("transfer.no_location", store_id=str(requesting_store_id))
        return []

    req_lat, req_lon = requesting_store.lat, requesting_store.lon

    # Get all other stores for this customer
    store_result = await db.execute(
        select(Store).where(
            Store.customer_id == customer_id,
            Store.store_id != requesting_store_id,
            Store.status == "active",
            Store.lat.isnot(None),
            Store.lon.isnot(None),
        )
    )
    candidate_stores = store_result.scalars().all()

    # Filter by distance
    nearby_stores = []
    for store in candidate_stores:
        dist = haversine_miles(req_lat, req_lon, store.lat, store.lon)
        if dist <= search_radius_miles:
            nearby_stores.append((store, dist))

    if not nearby_stores:
        return []

    # Get latest inventory for this product at nearby stores
    store_ids = [s.store_id for s, _ in nearby_stores]
    inv_subq = (
        select(
            InventoryLevel.store_id,
            func.max(InventoryLevel.timestamp).label("latest_ts"),
        )
        .where(
            InventoryLevel.customer_id == customer_id,
            InventoryLevel.product_id == product_id,
            InventoryLevel.store_id.in_(store_ids),
        )
        .group_by(InventoryLevel.store_id)
        .subquery()
    )
    inv_result = await db.execute(
        select(InventoryLevel).join(
            inv_subq,
            (InventoryLevel.store_id == inv_subq.c.store_id)
            & (InventoryLevel.timestamp == inv_subq.c.latest_ts)
            & (InventoryLevel.product_id == product_id),
        )
    )
    inventory_map = {inv.store_id: inv for inv in inv_result.scalars().all()}

    # Get reorder points for safety stock reference
    rp_result = await db.execute(
        select(ReorderPoint).where(
            ReorderPoint.product_id == product_id,
            ReorderPoint.store_id.in_(store_ids),
        )
    )
    rp_map = {rp.store_id: rp for rp in rp_result.scalars().all()}

    # Evaluate each store
    options = []
    for store, distance in nearby_stores:
        inv = inventory_map.get(store.store_id)
        if not inv or inv.quantity_available <= 0:
            continue

        rp = rp_map.get(store.store_id)
        safety_stock = rp.safety_stock if rp else 0

        # Excess = available above reserve floor, where reserve floor includes:
        # safety stock + static operating buffer + minimum shelf presentation qty.
        buffer = 20
        min_presentation_qty = await get_min_presentation_qty(db, product_id, store.store_id)
        reserve_floor = max(safety_stock + buffer, min_presentation_qty)
        excess = inv.quantity_available - reserve_floor
        if excess <= 0:
            continue

        variable_cost = distance * COST_PER_MILE
        transfer_cost = round(max(variable_cost, HANDLING_COST_FLOOR), 2)
        recommended_qty = min(excess, needed_qty) if needed_qty > 0 else excess
        lead_days = DEFAULT_TRANSFER_LEAD_DAYS if distance <= NEARBY_DISTANCE_MILES else DEFAULT_TRANSFER_LEAD_DAYS + 1

        options.append(
            TransferOption(
                from_store_id=store.store_id,
                from_store_name=store.name,
                distance_miles=round(distance, 1),
                transfer_cost=transfer_cost,
                excess_quantity=excess,
                recommended_transfer_qty=recommended_qty,
                estimated_lead_days=lead_days,
            )
        )

    # Rank by score: excess × (1 / distance) — more stock closer is better
    options.sort(key=lambda o: o.excess_quantity / max(o.distance_miles, 1), reverse=True)

    return options[:max_results]


async def create_transfer_request(
    db: AsyncSession,
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    from_store_id: uuid.UUID,
    to_store_id: uuid.UUID,
    quantity: int,
    reason_code: str = "stockout_emergency",
) -> StoreTransfer:
    """Create a store-to-store transfer request."""
    transfer = StoreTransfer(
        customer_id=customer_id,
        product_id=product_id,
        from_location_type="store",
        from_location_id=from_store_id,
        to_location_type="store",
        to_location_id=to_store_id,
        quantity=quantity,
        status="requested",
        reason_code=reason_code,
        requested_at=datetime.utcnow(),
    )
    db.add(transfer)
    await db.flush()

    logger.info(
        "transfer.created",
        transfer_id=str(transfer.transfer_id),
        from_store=str(from_store_id),
        to_store=str(to_store_id),
        product=str(product_id),
        quantity=quantity,
    )
    return transfer
