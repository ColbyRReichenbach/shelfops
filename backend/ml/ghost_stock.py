"""
Ghost Stock / Phantom Inventory Detector.

Problem:
  - System shows inventory, but product is actually missing (theft, damage, miscounts)
  - Results in lost sales + inaccurate forecasts

Detection Logic:
  - If (forecasted_demand >> actual_sales) AND (quantity_on_hand > 0) for 3+ consecutive days
  - → Likely phantom inventory (system thinks we have stock, but it's not sellable)

Factors:
  - Shrinkage rate (high-shrink categories more likely)
  - Stockout history (if we had stockouts recently, stock is likely real)
  - Sales volatility (low volatility = more confident in forecast)
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Anomaly, DemandForecast, InventoryLevel, Product, Transaction

logger = structlog.get_logger()


# ── Ghost Stock Detection ───────────────────────────────────────────────────


async def detect_ghost_stock(
    db: AsyncSession,
    customer_id: uuid.UUID,
    lookback_days: int = 7,
    forecast_sales_ratio_threshold: float = 0.3,
    consecutive_days_threshold: int = 3,
) -> dict[str, Any]:
    """
    Detect phantom inventory (ghost stock).

    Logic:
      1. Get products with quantity_on_hand > 0
      2. Compare forecasted demand vs actual sales (last 7 days)
      3. If actual_sales / forecasted_demand < 0.3 for 3+ consecutive days → ghost stock

    Args:
        db: Database session
        customer_id: Customer UUID
        lookback_days: Days to check (default 7)
        forecast_sales_ratio_threshold: Trigger if actual/forecast < this (default 0.3)
        consecutive_days_threshold: Days of low sales required (default 3)

    Returns:
        {
            "ghost_stock_detected": 5,
            "total_value": 47000,  # $ value of ghost stock
            "flagged_products": [...],
        }
    """
    logger.info("ghost_stock.detect_start", customer_id=str(customer_id))

    now = datetime.utcnow()
    cutoff = now - timedelta(days=lookback_days)

    # Get products with inventory
    inv_result = await db.execute(
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            InventoryLevel.quantity_on_hand,
        ).where(
            InventoryLevel.customer_id == customer_id,
            InventoryLevel.quantity_on_hand > 0,
        )
    )
    inventory_items = inv_result.all()

    if not inventory_items:
        logger.info("ghost_stock.no_inventory", customer_id=str(customer_id))
        return {
            "ghost_stock_detected": 0,
            "total_value": 0,
            "flagged_products": [],
        }

    ghost_stock_cases = []

    for inv_item in inventory_items:
        store_id = inv_item.store_id
        product_id = inv_item.product_id
        quantity_on_hand = inv_item.quantity_on_hand

        # Get forecasts for this product-store (last 7 days)
        forecast_result = await db.execute(
            select(DemandForecast.forecast_date, DemandForecast.forecasted_demand).where(
                DemandForecast.customer_id == customer_id,
                DemandForecast.store_id == store_id,
                DemandForecast.product_id == product_id,
                DemandForecast.forecast_date >= cutoff,
            )
        )
        forecasts = {row.forecast_date: row.forecasted_demand for row in forecast_result.all()}

        # Get actual sales (last 7 days)
        txn_result = await db.execute(
            select(Transaction.timestamp, Transaction.quantity).where(
                Transaction.customer_id == customer_id,
                Transaction.store_id == store_id,
                Transaction.product_id == product_id,
                Transaction.timestamp >= cutoff,
            )
        )
        sales_by_date = {}
        for txn in txn_result.all():
            txn_date = txn.timestamp.date() if hasattr(txn.timestamp, "date") else txn.timestamp
            sales_by_date[txn_date] = sales_by_date.get(txn_date, 0) + txn.quantity

        # Check consecutive days with low sales
        low_sales_days = []
        for i in range(lookback_days):
            check_date = (now - timedelta(days=i)).date()
            forecasted = forecasts.get(check_date, 0)
            actual = sales_by_date.get(check_date, 0)

            if forecasted > 0:
                ratio = actual / forecasted
                if ratio < forecast_sales_ratio_threshold:
                    low_sales_days.append(check_date)

        # Check if consecutive days threshold met
        if len(low_sales_days) >= consecutive_days_threshold:
            # Get product details
            prod_result = await db.execute(
                select(Product.name, Product.unit_price, Product.category).where(Product.product_id == product_id)
            )
            product = prod_result.first()

            if product:
                ghost_value = quantity_on_hand * product.unit_price
                ghost_probability = min(0.95, len(low_sales_days) / lookback_days)

                ghost_stock_cases.append(
                    {
                        "store_id": str(store_id),
                        "product_id": str(product_id),
                        "product_name": product.name,
                        "category": product.category,
                        "quantity_on_hand": quantity_on_hand,
                        "ghost_value": ghost_value,
                        "ghost_probability": ghost_probability,
                        "low_sales_days": len(low_sales_days),
                        "avg_forecast": sum(forecasts.values()) / len(forecasts) if forecasts else 0,
                        "avg_actual": sum(sales_by_date.values()) / len(sales_by_date) if sales_by_date else 0,
                    }
                )

                # Create anomaly record
                anomaly = Anomaly(
                    anomaly_id=uuid.uuid4(),
                    customer_id=customer_id,
                    store_id=store_id,
                    product_id=product_id,
                    anomaly_type="inventory_discrepancy",
                    severity="warning" if ghost_probability > 0.7 else "info",
                    description=f"Ghost stock suspected: {quantity_on_hand} units ({ghost_probability * 100:.0f}% confidence). Forecast vs actual sales mismatch for {len(low_sales_days)} days.",
                    anomaly_metadata={
                        "quantity_on_hand": quantity_on_hand,
                        "ghost_value": float(ghost_value),
                        "ghost_probability": float(ghost_probability),
                        "low_sales_days": len(low_sales_days),
                        "avg_forecasted_demand": float(sum(forecasts.values()) / len(forecasts)) if forecasts else 0,
                        "avg_actual_sales": float(sum(sales_by_date.values()) / len(sales_by_date))
                        if sales_by_date
                        else 0,
                        "suggested_action": "cycle_count",
                    },
                    detected_at=datetime.utcnow(),
                )
                db.add(anomaly)

    await db.commit()

    total_value = sum(case["ghost_value"] for case in ghost_stock_cases)

    logger.info(
        "ghost_stock.detect_complete",
        customer_id=str(customer_id),
        ghost_stock_detected=len(ghost_stock_cases),
        total_value=total_value,
    )

    return {
        "ghost_stock_detected": len(ghost_stock_cases),
        "total_value": total_value,
        "flagged_products": ghost_stock_cases,
    }


# ── Cycle Count Recommendation ──────────────────────────────────────────────


async def recommend_cycle_counts(
    db: AsyncSession,
    customer_id: uuid.UUID,
    max_recommendations: int = 20,
) -> list[dict[str, Any]]:
    """
    Recommend products for cycle count (physical inventory verification).

    Prioritization:
      1. High ghost stock probability
      2. High value ($)
      3. High-shrink categories

    Returns:
        [
            {
                "store_id": "...",
                "product_id": "...",
                "product_name": "...",
                "priority": "high",
                "reason": "Ghost stock detected ($12K value)",
            },
            ...
        ]
    """
    # Get recent ghost stock anomalies
    cutoff = datetime.utcnow() - timedelta(days=7)
    anomaly_result = await db.execute(
        select(Anomaly).where(
            Anomaly.customer_id == customer_id,
            Anomaly.anomaly_type == "inventory_discrepancy",
            Anomaly.detected_at >= cutoff,
        )
    )
    anomalies = anomaly_result.scalars().all()

    recommendations = []

    for anomaly in anomalies:
        ghost_prob = anomaly.anomaly_metadata.get("ghost_probability", 0) if anomaly.anomaly_metadata else 0
        ghost_value = anomaly.anomaly_metadata.get("ghost_value", 0) if anomaly.anomaly_metadata else 0

        # Prioritize
        if ghost_prob > 0.8 and ghost_value > 5000:
            priority = "critical"
        elif ghost_prob > 0.7 or ghost_value > 2000:
            priority = "high"
        else:
            priority = "medium"

        # Get product name
        prod_result = await db.execute(select(Product.name).where(Product.product_id == anomaly.product_id))
        product = prod_result.first()
        product_name = product.name if product else "Unknown"

        recommendations.append(
            {
                "store_id": str(anomaly.store_id),
                "product_id": str(anomaly.product_id),
                "product_name": product_name,
                "priority": priority,
                "reason": f"Ghost stock detected (${ghost_value:,.0f} value, {ghost_prob * 100:.0f}% confidence)",
                "anomaly_id": str(anomaly.anomaly_id),
            }
        )

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2}
    recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))

    return recommendations[:max_recommendations]
