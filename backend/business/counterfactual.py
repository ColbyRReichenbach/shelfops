"""
Counterfactual Analyzer — Opportunity Cost Quantification.

Answers the question: "What did stockouts and overstocks COST us?"

Stockout cost = lost_sales_qty × unit_price × margin_pct
Overstock cost = excess_units × holding_cost_per_unit_per_day

Results feed into the dashboard KPI: "Prevented 15 stockouts, saved $3,200"

Agent: data-engineer + ml-engineer
Skill: postgresql, ml-forecasting
"""

import uuid
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    DemandForecast,
    InventoryLevel,
    OpportunityCostLog,
    Product,
)

logger = structlog.get_logger()


async def analyze_daily_opportunity_cost(
    db: AsyncSession,
    customer_id: uuid.UUID,
    analysis_date: date,
) -> dict:
    """
    For each (store, product) on {analysis_date}:

    Scenario 1: Stockout (inventory = 0 or < demand)
      lost_sales = min(forecasted_demand, historical_avg_demand)
      cost = lost_sales × unit_price × margin_pct

    Scenario 2: Overstock (inventory > forecast × 2)
      excess = inventory - (forecast × 2)
      cost = excess × holding_cost_per_unit_per_day

    Inserts records into opportunity_cost_log.
    """
    # Get inventory snapshots for the analysis date
    day_start = datetime.combine(analysis_date, datetime.min.time())
    day_end = datetime.combine(analysis_date + timedelta(days=1), datetime.min.time())

    inv_subq = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            func.max(InventoryLevel.timestamp).label("latest_ts"),
        )
        .where(
            InventoryLevel.customer_id == customer_id,
            InventoryLevel.timestamp >= day_start,
            InventoryLevel.timestamp < day_end,
        )
        .group_by(InventoryLevel.store_id, InventoryLevel.product_id)
        .subquery()
    )

    inv_result = await db.execute(
        select(InventoryLevel).join(
            inv_subq,
            (InventoryLevel.store_id == inv_subq.c.store_id)
            & (InventoryLevel.product_id == inv_subq.c.product_id)
            & (InventoryLevel.timestamp == inv_subq.c.latest_ts),
        )
    )
    inventories = {(inv.store_id, inv.product_id): inv for inv in inv_result.scalars().all()}

    # Get forecasts for the analysis date
    forecast_result = await db.execute(
        select(DemandForecast).where(
            DemandForecast.customer_id == customer_id,
            DemandForecast.forecast_date == analysis_date,
        )
    )
    forecasts = {(fc.store_id, fc.product_id): fc for fc in forecast_result.scalars().all()}

    # Pre-load products for cost data
    product_ids = set(pid for _, pid in list(inventories.keys()) + list(forecasts.keys()))
    products = {}
    for pid in product_ids:
        p = await db.get(Product, pid)
        if p:
            products[pid] = p

    stockout_count = 0
    overstock_count = 0
    total_stockout_cost = 0.0
    total_overstock_cost = 0.0
    records_created = 0

    # Analyze all (store, product) pairs with forecasts
    for key, forecast in forecasts.items():
        store_id, product_id = key
        inv = inventories.get(key)
        product = products.get(product_id)

        if not product:
            continue

        available = inv.quantity_available if inv else 0
        forecasted = forecast.forecasted_demand or 0
        unit_price = product.unit_price or 0
        unit_cost = product.unit_cost or 0
        margin_pct = (unit_price - unit_cost) / unit_price if unit_price > 0 else 0.3
        holding_cost = getattr(product, "holding_cost_per_unit_per_day", None) or (unit_cost * 0.25 / 365)

        cost_type = None
        cost_amount = 0.0
        lost_units = 0

        if available <= 0 and forecasted > 0:
            # Full stockout
            cost_type = "stockout"
            lost_units = round(forecasted)
            cost_amount = lost_units * unit_price * margin_pct
            stockout_count += 1
            total_stockout_cost += cost_amount

        elif 0 < available < forecasted:
            # Partial stockout
            cost_type = "stockout"
            lost_units = round(forecasted - available)
            cost_amount = lost_units * unit_price * margin_pct
            stockout_count += 1
            total_stockout_cost += cost_amount

        elif forecasted > 0 and available > forecasted * 2:
            # Overstock
            cost_type = "overstock"
            lost_units = round(available - forecasted * 2)
            cost_amount = lost_units * holding_cost
            overstock_count += 1
            total_overstock_cost += cost_amount

        if cost_type and cost_amount > 0.01:
            holding = round(cost_amount, 2) if cost_type == "overstock" else 0.0
            opportunity = round(cost_amount, 2) if cost_type == "stockout" else 0.0
            db.add(
                OpportunityCostLog(
                    customer_id=customer_id,
                    store_id=store_id,
                    product_id=product_id,
                    date=analysis_date,
                    cost_type=cost_type,
                    lost_sales_qty=lost_units,
                    opportunity_cost=opportunity,
                    holding_cost=holding,
                    forecasted_demand=round(forecasted, 1),
                    actual_stock=available,
                    actual_sales=0,
                )
            )
            records_created += 1

    await db.commit()

    summary = {
        "date": analysis_date.isoformat(),
        "stockout_events": stockout_count,
        "overstock_events": overstock_count,
        "total_stockout_cost": round(total_stockout_cost, 2),
        "total_overstock_cost": round(total_overstock_cost, 2),
        "total_opportunity_cost": round(total_stockout_cost + total_overstock_cost, 2),
        "records_created": records_created,
    }

    logger.info("counterfactual.analyzed", **summary)
    return summary
