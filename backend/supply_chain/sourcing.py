"""
Supply Chain Sourcing Engine — Determine optimal source for product replenishment.

Supports multi-tier distribution networks:
  - vendor_direct: Vendor → Store (7-14 day lead time)
  - dc: Vendor → DC → Store (2-3 day lead time from DC)
  - regional_dc: Vendor → Regional DC → Store
  - transfer: Store → Store (emergency rebalancing)

The sourcing engine resolves which source to use for each (store, product)
combination by checking product_sourcing_rules in priority order and
verifying DC stock availability before recommending DC fulfillment.

Agent: data-engineer
Skill: api-integration
"""

import math
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    DCInventory,
    DistributionCenter,
    ProductSourcingRule,
    Store,
    Supplier,
)


@dataclass
class LeadTimeEstimate:
    """Lead time estimate with variance for safety stock calculation."""

    mean_days: float
    variance_days: float  # Std dev — used in safety stock formula
    source: str  # Description for audit trail


@dataclass
class SourcingDecision:
    """Result of sourcing evaluation for a (store, product) pair."""

    source_type: str  # vendor_direct, dc, regional_dc, transfer
    source_id: UUID  # supplier_id or dc_id
    source_name: str
    lead_time: LeadTimeEstimate
    min_order_qty: int
    cost_per_order: float
    dc_stock_available: int | None  # Only set for DC sources
    priority: int
    rule_id: UUID


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in miles between two (lat, lon) points."""
    R = 3959  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


class SourcingEngine:
    """Determine optimal source for product replenishment."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_sourcing_strategy(
        self,
        customer_id: UUID,
        store_id: UUID,
        product_id: UUID,
        quantity: int = 1,
    ) -> SourcingDecision | None:
        """
        Returns the best available source for replenishing a product at a store.

        Algorithm:
        1. Query product_sourcing_rules for (product, store) ordered by priority.
        2. For DC sources: verify DC has enough stock to fulfill.
        3. If DC stock insufficient, fall through to next priority (vendor direct).
        4. Return first viable source, or None if no rules configured.
        """
        # Get sourcing rules: store-specific first, then global (store_id IS NULL)
        result = await self.db.execute(
            select(ProductSourcingRule)
            .where(
                ProductSourcingRule.customer_id == customer_id,
                ProductSourcingRule.product_id == product_id,
                ProductSourcingRule.active.is_(True),
            )
            .where((ProductSourcingRule.store_id == store_id) | (ProductSourcingRule.store_id.is_(None)))
            .order_by(
                # Prefer store-specific rules, then by priority
                ProductSourcingRule.store_id.is_(None).asc(),
                ProductSourcingRule.priority.asc(),
            )
        )
        rules = result.scalars().all()

        if not rules:
            return None

        for rule in rules:
            decision = await self._evaluate_rule(rule, quantity)
            if decision is not None:
                return decision

        # All rules exhausted (e.g., DC out of stock, no vendor fallback)
        return None

    async def _evaluate_rule(self, rule: ProductSourcingRule, quantity: int) -> SourcingDecision | None:
        """Evaluate a single sourcing rule. Returns None if rule can't fulfill."""

        if rule.source_type in ("dc", "regional_dc"):
            # Check DC inventory availability
            dc_stock = await self._get_dc_available_stock(rule.source_id, rule.product_id)
            if dc_stock is not None and dc_stock >= quantity:
                source_name = await self._get_dc_name(rule.source_id)
                return SourcingDecision(
                    source_type=rule.source_type,
                    source_id=rule.source_id,
                    source_name=source_name or "Unknown DC",
                    lead_time=LeadTimeEstimate(
                        mean_days=rule.lead_time_days,
                        variance_days=rule.lead_time_variance_days or 0,
                        source=f"{rule.source_type} (priority {rule.priority})",
                    ),
                    min_order_qty=rule.min_order_qty or 1,
                    cost_per_order=rule.cost_per_order or 0.0,
                    dc_stock_available=dc_stock,
                    priority=rule.priority,
                    rule_id=rule.rule_id,
                )
            # DC doesn't have enough stock — fall through to next priority
            return None

        elif rule.source_type == "vendor_direct":
            # Vendor always assumed to have stock (infinite supply assumption)
            supplier = await self._get_supplier(rule.source_id)
            supplier_name = supplier.name if supplier else "Unknown Vendor"

            # Use actual lead time if available from vendor scorecard
            actual_lead = rule.lead_time_days
            variance = rule.lead_time_variance_days or 0
            if supplier and supplier.avg_lead_time_actual:
                actual_lead = supplier.avg_lead_time_actual
            if supplier and supplier.lead_time_variance:
                variance = supplier.lead_time_variance

            return SourcingDecision(
                source_type=rule.source_type,
                source_id=rule.source_id,
                source_name=supplier_name,
                lead_time=LeadTimeEstimate(
                    mean_days=actual_lead,
                    variance_days=variance,
                    source=f"vendor_direct (priority {rule.priority})",
                ),
                min_order_qty=max(
                    rule.min_order_qty or 1,
                    supplier.min_order_quantity if supplier else 1,
                ),
                cost_per_order=rule.cost_per_order or (supplier.cost_per_order if supplier else 0.0) or 0.0,
                dc_stock_available=None,
                priority=rule.priority,
                rule_id=rule.rule_id,
            )

        # transfer type — handled by TransferOptimizer separately
        return None

    async def _get_dc_available_stock(self, dc_id: UUID, product_id: UUID) -> int | None:
        """Get latest available quantity at a DC for a given product."""
        result = await self.db.execute(
            select(DCInventory.quantity_available)
            .where(
                DCInventory.dc_id == dc_id,
                DCInventory.product_id == product_id,
            )
            .order_by(DCInventory.timestamp.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    async def _get_dc_name(self, dc_id: UUID) -> str | None:
        dc = await self.db.get(DistributionCenter, dc_id)
        return dc.name if dc else None

    async def _get_supplier(self, supplier_id: UUID) -> Supplier | None:
        return await self.db.get(Supplier, supplier_id)

    async def calculate_total_leadtime(
        self,
        customer_id: UUID,
        store_id: UUID,
        product_id: UUID,
    ) -> LeadTimeEstimate:
        """
        Convenience method: get lead time for the best available source.

        Falls back to a conservative default (7 days) if no sourcing rules exist.
        """
        decision = await self.get_sourcing_strategy(customer_id, store_id, product_id)
        if decision:
            return decision.lead_time

        # Fallback: no sourcing rules configured
        return LeadTimeEstimate(
            mean_days=7.0,
            variance_days=2.0,
            source="default (no sourcing rules configured)",
        )
