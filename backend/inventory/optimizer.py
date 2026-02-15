"""
Inventory Optimizer — Dynamic Reorder Point Calculation.

The critical piece that closes the "Action Gap": transforms ML forecasts
into actionable reorder points. Runs nightly via Celery beat.

Algorithm:
  ROP = (Avg Daily Demand × Lead Time) + Safety Stock
  Safety Stock = Z-score × √(Lead Time) × Demand Std Dev × Vendor Reliability Multiplier
  EOQ = √((2 × Annual Demand × Order Cost) / Holding Cost)

Inputs:
  - demand_forecasts (ML predictions for next 14 days)
  - product_sourcing_rules (DC vs vendor lead time)
  - suppliers (reliability score for safety stock multiplier)
  - reorder_points (current values to compare against)

Outputs:
  - Updated reorder_points table
  - reorder_history audit trail
  - Alerts for significant ROP changes

Agent: data-engineer + ml-engineer
Skill: postgresql, ml-forecasting
"""

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    DemandForecast,
    Product,
    ReorderHistory,
    ReorderPoint,
    Store,
    Supplier,
)
from supply_chain.sourcing import LeadTimeEstimate, SourcingDecision, SourcingEngine

logger = structlog.get_logger()

# Service level → Z-score mapping (standard normal distribution)
Z_SCORES = {
    0.90: 1.282,
    0.95: 1.645,
    0.975: 1.960,
    0.99: 2.326,
}

# Vendor reliability → safety stock multiplier
# Low reliability = higher buffer needed
RELIABILITY_MULTIPLIERS = {
    (0.95, 1.01): 1.0,  # 95%+ on-time → no penalty
    (0.80, 0.95): 1.2,  # 80-94% → 20% buffer
    (0.60, 0.80): 1.5,  # 60-79% → 50% buffer
    (0.00, 0.60): 1.8,  # <60% → 80% buffer (unreliable)
}


@dataclass
class ReorderCalculation:
    """Result of a dynamic reorder point calculation."""

    reorder_point: int
    safety_stock: int
    economic_order_qty: int
    lead_time_days: float
    avg_daily_demand: float
    demand_std_dev: float
    source_type: str
    source_name: str
    vendor_reliability: float
    safety_stock_multiplier: float
    rationale: dict[str, Any]


def get_reliability_multiplier(reliability_score: float) -> float:
    """Map vendor reliability (0-1) to a safety stock multiplier (1.0-1.8)."""
    for (low, high), multiplier in RELIABILITY_MULTIPLIERS.items():
        if low <= reliability_score < high:
            return multiplier
    return 1.0


def get_z_score(service_level: float) -> float:
    """Get Z-score for a given service level target."""
    # Find closest match
    closest = min(Z_SCORES.keys(), key=lambda x: abs(x - service_level))
    return Z_SCORES[closest]


class InventoryOptimizer:
    """Calculate optimal reorder points based on forecasts + supply chain."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.sourcing = SourcingEngine(db)

    async def calculate_dynamic_reorder_point(
        self,
        customer_id: uuid.UUID,
        store_id: uuid.UUID,
        product_id: uuid.UUID,
        forecast_horizon_days: int = 14,
        service_level: float = 0.95,
    ) -> ReorderCalculation | None:
        """
        Calculate optimal ROP for a (store, product) pair.

        Returns None if insufficient data (no forecasts available).
        """
        # 1. Get demand forecast
        demand = await self._get_forecast_demand(customer_id, store_id, product_id, forecast_horizon_days)
        if demand is None:
            return None

        avg_daily_demand, demand_std_dev = demand

        # 2. Get sourcing strategy (DC vs vendor + lead time)
        sourcing = await self.sourcing.get_sourcing_strategy(customer_id, store_id, product_id)
        if sourcing:
            lead_time = sourcing.lead_time.mean_days
            lead_time_var = sourcing.lead_time.variance_days
            source_type = sourcing.source_type
            source_name = sourcing.source_name
            min_order_qty = sourcing.min_order_qty
            cost_per_order = sourcing.cost_per_order
        else:
            # Fallback: use product's supplier lead time directly
            product = await self.db.get(Product, product_id)
            supplier = await self.db.get(Supplier, product.supplier_id) if product and product.supplier_id else None
            lead_time = supplier.lead_time_days if supplier else 7
            lead_time_var = supplier.lead_time_variance if supplier and supplier.lead_time_variance else 1.0
            source_type = "vendor_direct"
            source_name = supplier.name if supplier else "Unknown"
            min_order_qty = supplier.min_order_quantity if supplier else 1
            cost_per_order = supplier.cost_per_order if supplier and supplier.cost_per_order else 50.0

        # 3. Get vendor reliability multiplier
        vendor_reliability = 0.95  # Default
        if sourcing and sourcing.source_type == "vendor_direct":
            supplier = await self.db.get(Supplier, sourcing.source_id)
            if supplier:
                vendor_reliability = supplier.reliability_score or 0.95
        reliability_multiplier = get_reliability_multiplier(vendor_reliability)

        # 4. Calculate safety stock
        z_score = get_z_score(service_level)

        # Safety stock accounts for BOTH demand variability AND lead time variability
        # SS = Z × √( LT × σ_demand² + D² × σ_LT² ) × reliability_multiplier × cluster_multiplier
        demand_component = lead_time * (demand_std_dev**2)
        leadtime_component = (avg_daily_demand**2) * (lead_time_var**2)
        combined_std = math.sqrt(demand_component + leadtime_component)

        # Cluster-aware multiplier: high-volume stores (tier 0) get +15%,
        # low-volume stores (tier 2) get -15% to optimize holding costs
        store = await self.db.get(Store, store_id)
        cluster_tier = store.cluster_tier if store and store.cluster_tier is not None else 1
        cluster_multipliers = {0: 1.15, 1: 1.00, 2: 0.85}
        cluster_multiplier = cluster_multipliers.get(cluster_tier, 1.00)

        safety_stock = max(1, round(z_score * combined_std * reliability_multiplier * cluster_multiplier))

        # 5. Calculate reorder point
        reorder_point = max(1, round(avg_daily_demand * lead_time + safety_stock))

        # 6. Calculate EOQ
        product = await self.db.get(Product, product_id)
        holding_cost = (
            product.holding_cost_per_unit_per_day * 365
            if product and product.holding_cost_per_unit_per_day
            else (product.unit_cost * 0.25 if product and product.unit_cost else 5.0)
            # Default: 25% of unit cost per year (industry standard)
        )
        annual_demand = avg_daily_demand * 365
        eoq = self._calculate_eoq(annual_demand, cost_per_order, holding_cost)
        eoq = max(eoq, min_order_qty)

        rationale = {
            "source_type": source_type,
            "source_name": source_name,
            "lead_time_days": lead_time,
            "lead_time_variance": lead_time_var,
            "avg_daily_demand": round(avg_daily_demand, 2),
            "demand_std_dev": round(demand_std_dev, 2),
            "service_level": service_level,
            "z_score": z_score,
            "vendor_reliability": vendor_reliability,
            "reliability_multiplier": reliability_multiplier,
            "cluster_tier": cluster_tier,
            "cluster_multiplier": cluster_multiplier,
            "safety_stock_formula": (
                f"Z({z_score:.3f}) × √(LT({lead_time}) × σd²({demand_std_dev:.1f}) "
                f"+ D²({avg_daily_demand:.1f}) × σLT²({lead_time_var})) "
                f"× reliability({reliability_multiplier}) × cluster({cluster_multiplier})"
            ),
            "holding_cost_annual": round(holding_cost, 2),
            "cost_per_order": cost_per_order,
            "min_order_qty": min_order_qty,
            "forecast_horizon_days": forecast_horizon_days,
        }

        return ReorderCalculation(
            reorder_point=reorder_point,
            safety_stock=safety_stock,
            economic_order_qty=eoq,
            lead_time_days=lead_time,
            avg_daily_demand=avg_daily_demand,
            demand_std_dev=demand_std_dev,
            source_type=source_type,
            source_name=source_name,
            vendor_reliability=vendor_reliability,
            safety_stock_multiplier=reliability_multiplier,
            rationale=rationale,
        )

    async def optimize_store_product(
        self,
        customer_id: uuid.UUID,
        store_id: uuid.UUID,
        product_id: uuid.UUID,
        change_threshold_pct: float = 0.10,
    ) -> dict[str, Any] | None:
        """
        Recalculate ROP for a single (store, product) and update if changed.

        Returns a summary dict if updated, or None if no change needed.
        """
        calc = await self.calculate_dynamic_reorder_point(customer_id, store_id, product_id)
        if calc is None:
            return None

        # Get current reorder point
        result = await self.db.execute(
            select(ReorderPoint).where(
                ReorderPoint.store_id == store_id,
                ReorderPoint.product_id == product_id,
            )
        )
        current_rp = result.scalar_one_or_none()

        if current_rp is None:
            # No existing ROP — create one
            new_rp = ReorderPoint(
                customer_id=customer_id,
                store_id=store_id,
                product_id=product_id,
                reorder_point=calc.reorder_point,
                safety_stock=calc.safety_stock,
                economic_order_qty=calc.economic_order_qty,
                lead_time_days=round(calc.lead_time_days),
                service_level=0.95,
                last_calculated=datetime.utcnow(),
            )
            self.db.add(new_rp)

            # Log to history
            self.db.add(
                ReorderHistory(
                    customer_id=customer_id,
                    store_id=store_id,
                    product_id=product_id,
                    old_reorder_point=0,
                    new_reorder_point=calc.reorder_point,
                    old_safety_stock=0,
                    new_safety_stock=calc.safety_stock,
                    old_eoq=0,
                    new_eoq=calc.economic_order_qty,
                    calculation_rationale=calc.rationale,
                )
            )

            return {
                "action": "created",
                "store_id": str(store_id),
                "product_id": str(product_id),
                "reorder_point": calc.reorder_point,
                "safety_stock": calc.safety_stock,
                "eoq": calc.economic_order_qty,
            }

        # Check if change exceeds threshold
        old_rop = current_rp.reorder_point
        pct_change = abs(calc.reorder_point - old_rop) / max(old_rop, 1)

        if pct_change < change_threshold_pct:
            return None  # Not enough change to warrant update

        # Log history BEFORE updating
        self.db.add(
            ReorderHistory(
                customer_id=customer_id,
                store_id=store_id,
                product_id=product_id,
                old_reorder_point=current_rp.reorder_point,
                new_reorder_point=calc.reorder_point,
                old_safety_stock=current_rp.safety_stock,
                new_safety_stock=calc.safety_stock,
                old_eoq=current_rp.economic_order_qty,
                new_eoq=calc.economic_order_qty,
                calculation_rationale=calc.rationale,
            )
        )

        # Update the reorder point
        current_rp.reorder_point = calc.reorder_point
        current_rp.safety_stock = calc.safety_stock
        current_rp.economic_order_qty = calc.economic_order_qty
        current_rp.lead_time_days = round(calc.lead_time_days)
        current_rp.last_calculated = datetime.utcnow()

        return {
            "action": "updated",
            "store_id": str(store_id),
            "product_id": str(product_id),
            "old_reorder_point": old_rop,
            "new_reorder_point": calc.reorder_point,
            "pct_change": round(pct_change * 100, 1),
            "source": calc.source_type,
            "lead_time": calc.lead_time_days,
        }

    async def _get_forecast_demand(
        self,
        customer_id: uuid.UUID,
        store_id: uuid.UUID,
        product_id: uuid.UUID,
        horizon_days: int,
    ) -> tuple[float, float] | None:
        """
        Get average daily demand and std dev from forecast data.

        Returns (avg_daily_demand, demand_std_dev) or None if no forecasts.
        """
        today = datetime.utcnow().date()
        result = await self.db.execute(
            select(
                func.avg(DemandForecast.forecasted_demand),
                func.stddev(DemandForecast.forecasted_demand),
                func.count(DemandForecast.forecast_id),
            ).where(
                DemandForecast.customer_id == customer_id,
                DemandForecast.store_id == store_id,
                DemandForecast.product_id == product_id,
                DemandForecast.forecast_date >= today,
                DemandForecast.forecast_date <= today + timedelta(days=horizon_days),
            )
        )
        row = result.one()
        avg_demand, std_demand, count = row

        if count == 0 or avg_demand is None:
            return None

        # Ensure non-negative and handle edge cases
        avg_daily = max(0.01, float(avg_demand))
        std_dev = max(0.01, float(std_demand or avg_daily * 0.3))

        return avg_daily, std_dev

    @staticmethod
    def _calculate_eoq(
        annual_demand: float,
        cost_per_order: float,
        holding_cost_annual: float,
    ) -> int:
        """
        Economic Order Quantity (Wilson formula).

        EOQ = √((2 × D × S) / H)
        Where: D = annual demand, S = order cost, H = annual holding cost per unit
        """
        if annual_demand <= 0 or cost_per_order <= 0 or holding_cost_annual <= 0:
            return 1

        eoq = math.sqrt((2 * annual_demand * cost_per_order) / holding_cost_annual)
        return max(1, round(eoq))
