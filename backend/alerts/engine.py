"""
Alert Engine — Stockout detection, anomaly detection, and alert lifecycle.

Agent: full-stack-engineer + data-engineer
Skill: alert-systems
Patterns used: Rule-based detection, alert deduplication, Redis pub/sub

Alert Types:
  - stockout_predicted: Forecasted demand > available inventory
  - anomaly_detected: Sales/inventory anomaly via z-score
  - reorder_recommended: Inventory below reorder point
  - forecast_accuracy_low: Model MAPE > threshold
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.models import (
    Alert,
    DemandForecast,
    ForecastAccuracy,
    InventoryLevel,
    Product,
    ReorderPoint,
)
from retail.planogram import is_product_active_in_store
from retail.shrinkage import apply_shrinkage_adjustment, get_shrink_rate

settings = get_settings()

# ──────────────────────────────────────────────────────────────────────────
# Detection Rules
# ──────────────────────────────────────────────────────────────────────────

SEVERITY_THRESHOLDS = {
    "stockout_days": {
        "critical": 1,  # Stockout in ≤ 1 day
        "high": 3,  # Stockout in ≤ 3 days
        "medium": 5,  # Stockout in ≤ 5 days
        "low": 7,  # Stockout in ≤ 7 days
    },
    "anomaly_z_score": {
        "critical": 4.0,
        "high": 3.0,
        "medium": 2.5,
        "low": 2.0,
    },
}


def classify_severity(stockout_days: float) -> str:
    """Classify alert severity based on days until stockout."""
    thresholds = SEVERITY_THRESHOLDS["stockout_days"]
    if stockout_days <= thresholds["critical"]:
        return "critical"
    elif stockout_days <= thresholds["high"]:
        return "high"
    elif stockout_days <= thresholds["medium"]:
        return "medium"
    return "low"


def classify_anomaly_severity(z_score: float) -> str:
    """Classify anomaly severity based on z-score."""
    thresholds = SEVERITY_THRESHOLDS["anomaly_z_score"]
    z = abs(z_score)
    if z >= thresholds["critical"]:
        return "critical"
    elif z >= thresholds["high"]:
        return "high"
    elif z >= thresholds["medium"]:
        return "medium"
    return "low"


# ──────────────────────────────────────────────────────────────────────────
# Stockout Detection
# ──────────────────────────────────────────────────────────────────────────


async def detect_stockouts(
    db: AsyncSession,
    customer_id: str,
) -> list[dict[str, Any]]:
    """
    Compare current inventory against forecast demand.
    Returns list of stockout alert dicts.
    """
    # Get latest inventory per store-product
    inv_subq = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            func.max(InventoryLevel.timestamp).label("latest_ts"),
        )
        .where(InventoryLevel.customer_id == customer_id)
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
    inventories = {(str(inv.store_id), str(inv.product_id)): inv for inv in inv_result.scalars().all()}

    # Get 7-day forecasts
    today = datetime.utcnow().date()
    forecast_result = await db.execute(
        select(DemandForecast).where(
            DemandForecast.customer_id == customer_id,
            DemandForecast.forecast_date >= today,
            DemandForecast.forecast_date <= today + timedelta(days=7),
        )
    )
    forecasts = forecast_result.scalars().all()

    # Aggregate 7-day demand per store-product
    demand_map: dict[tuple[str, str], float] = {}
    for fc in forecasts:
        key = (str(fc.store_id), str(fc.product_id))
        demand_map[key] = demand_map.get(key, 0) + fc.forecasted_demand

    # Detect stockouts
    alerts = []
    for key, total_demand in demand_map.items():
        inv = inventories.get(key)
        if inv is None:
            continue

        # Apply shrinkage adjustment to get realistic available inventory
        raw_available = inv.quantity_available
        days_since = (datetime.utcnow() - inv.timestamp).days if inv.timestamp else 0
        shrink_rate = await get_shrink_rate(db, uuid.UUID(key[1]), uuid.UUID(key[0]), uuid.UUID(customer_id))
        available = apply_shrinkage_adjustment(raw_available, days_since, shrink_rate)

        if available < total_demand:
            days_of_supply = available / max(total_demand / 7, 0.01)
            severity = classify_severity(days_of_supply)

            # Get product name
            product = await db.get(Product, uuid.UUID(key[1]))
            product_name = product.name if product else "Unknown"

            alerts.append(
                {
                    "customer_id": customer_id,
                    "store_id": key[0],
                    "product_id": key[1],
                    "alert_type": "stockout_predicted",
                    "severity": severity,
                    "message": (
                        f"Stockout predicted in {days_of_supply:.0f} days for {product_name}. "
                        f"Current stock: {available}, 7-day forecast demand: {total_demand:.0f}"
                    ),
                    "metadata": {
                        "current_stock": available,
                        "raw_stock": raw_available,
                        "shrinkage_adjusted": available != raw_available,
                        "shrink_rate_pct": round(shrink_rate * 100, 2),
                        "forecast_demand_7d": round(total_demand, 1),
                        "days_of_supply": round(days_of_supply, 1),
                    },
                }
            )

    return alerts


# ──────────────────────────────────────────────────────────────────────────
# Reorder Detection
# ──────────────────────────────────────────────────────────────────────────


async def detect_reorder_needed(
    db: AsyncSession,
    customer_id: str,
) -> list[dict[str, Any]]:
    """
    Check inventory against reorder points.
    Returns list of reorder alert dicts.
    """
    # Get reorder points
    rp_result = await db.execute(select(ReorderPoint).where(ReorderPoint.customer_id == customer_id))
    reorder_points = rp_result.scalars().all()

    # Latest inventory
    inv_subq = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            func.max(InventoryLevel.timestamp).label("latest_ts"),
        )
        .where(InventoryLevel.customer_id == customer_id)
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
    inventories = {(str(inv.store_id), str(inv.product_id)): inv for inv in inv_result.scalars().all()}

    alerts = []
    for rp in reorder_points:
        key = (str(rp.store_id), str(rp.product_id))
        inv = inventories.get(key)
        if inv is None:
            continue

        # Skip products not active in this store (delisted, seasonal_out, etc.)
        if not await is_product_active_in_store(db, rp.product_id, rp.store_id):
            continue

        if inv.quantity_available <= rp.reorder_point:
            product = await db.get(Product, rp.product_id)
            product_name = product.name if product else "Unknown"
            suggested_qty = rp.economic_order_qty

            alerts.append(
                {
                    "customer_id": customer_id,
                    "store_id": key[0],
                    "product_id": key[1],
                    "alert_type": "reorder_recommended",
                    "severity": "medium" if inv.quantity_available > rp.safety_stock else "high",
                    "message": (
                        f"Reorder recommended for {product_name}. "
                        f"Stock: {inv.quantity_available}, reorder point: {rp.reorder_point}. "
                        f"Suggested order qty: {suggested_qty}"
                    ),
                    "metadata": {
                        "current_stock": inv.quantity_available,
                        "reorder_point": rp.reorder_point,
                        "safety_stock": rp.safety_stock,
                        "suggested_qty": suggested_qty,
                    },
                }
            )

    return alerts


# ──────────────────────────────────────────────────────────────────────────
# Alert Deduplication
# ──────────────────────────────────────────────────────────────────────────


async def deduplicate_alerts(
    db: AsyncSession,
    new_alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Filter out alerts that already exist as open for the same
    store + product + alert_type combination.
    """
    if not new_alerts:
        return []

    # Fetch existing open alerts
    existing = await db.execute(
        select(Alert.store_id, Alert.product_id, Alert.alert_type).where(Alert.status.in_(["open", "acknowledged"]))
    )
    existing_keys = {(str(row.store_id), str(row.product_id), row.alert_type) for row in existing.all()}

    return [a for a in new_alerts if (a["store_id"], a["product_id"], a["alert_type"]) not in existing_keys]


# ──────────────────────────────────────────────────────────────────────────
# Alert Creation + Publishing
# ──────────────────────────────────────────────────────────────────────────


async def create_alerts(
    db: AsyncSession,
    alerts: list[dict[str, Any]],
) -> list[Alert]:
    """Persist alerts to database and return created records."""
    created = []
    for alert_data in alerts:
        alert = Alert(
            customer_id=alert_data["customer_id"],
            store_id=alert_data["store_id"],
            product_id=alert_data["product_id"],
            alert_type=alert_data["alert_type"],
            severity=alert_data["severity"],
            message=alert_data["message"],
            metadata_=alert_data.get("metadata", {}),
        )
        db.add(alert)
        created.append(alert)

    await db.commit()
    return created


async def publish_alerts(alerts: list[Alert]) -> int:
    """
    Publish new alerts to Redis pub/sub for real-time WebSocket delivery.
    Returns number of subscribers notified.
    """
    if not alerts:
        return 0

    redis = aioredis.from_url(settings.redis_url)
    try:
        total_subs = 0
        for alert in alerts:
            payload = json.dumps(
                {
                    "type": "alert",
                    "payload": {
                        "alert_id": str(alert.alert_id),
                        "alert_type": alert.alert_type,
                        "severity": alert.severity,
                        "message": alert.message,
                        "store_id": str(alert.store_id),
                        "product_id": str(alert.product_id),
                        "created_at": alert.created_at.isoformat(),
                    },
                }
            )
            channel = f"alerts:{alert.customer_id}"
            subs = await redis.publish(channel, payload)
            total_subs += subs
        return total_subs
    finally:
        await redis.aclose()


# ──────────────────────────────────────────────────────────────────────────
# Master Alert Pipeline (run periodically)
# ──────────────────────────────────────────────────────────────────────────


async def run_alert_pipeline(db: AsyncSession, customer_id: str) -> dict[str, int]:
    """
    Full alert pipeline:
    1. Detect stockouts
    2. Detect reorder needs
    3. Deduplicate
    4. Persist
    5. Publish via Redis

    Returns counts of alerts created by type.
    """
    # 1 + 2: Detect
    stockout_alerts = await detect_stockouts(db, customer_id)
    reorder_alerts = await detect_reorder_needed(db, customer_id)
    all_new = stockout_alerts + reorder_alerts

    # 3: Dedup
    unique_alerts = await deduplicate_alerts(db, all_new)

    # 4: Persist
    created = await create_alerts(db, unique_alerts)

    # 5: Publish
    await publish_alerts(created)

    return {
        "stockout_predicted": sum(1 for a in created if a.alert_type == "stockout_predicted"),
        "reorder_recommended": sum(1 for a in created if a.alert_type == "reorder_recommended"),
        "total": len(created),
    }
