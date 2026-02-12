"""
Seed Commercial Readiness Data — DCs, sourcing rules, shrinkage, planograms.

Supplements seed_test_data.py with data for the new commercial-readiness tables.
Run AFTER seed_test_data.py has been run.

Run: PYTHONPATH=backend python backend/scripts/seed_commercial_data.py
"""

import asyncio
import uuid
import random
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from db.models import (
    DistributionCenter, ProductSourcingRule, DCInventory, ShrinkageRate,
    Planogram, Supplier, Store, Product, PurchaseOrder, StoreTransfer,
)
from core.config import get_settings

settings = get_settings()

CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# DC locations in the Midwest (near the seeded stores)
DC_CONFIGS = [
    {
        "name": "Midwest Regional DC",
        "address": "1200 Distribution Way",
        "city": "Rockford",
        "state": "IL",
        "zip_code": "61101",
        "lat": 42.2711,
        "lon": -89.0940,
        "capacity_cubic_feet": 500000,
        "operating_costs_per_day": 8500.0,
    },
]

# NRF shrinkage rates by category
SHRINK_RATES = {
    "Beverages": ("spoilage", 0.012),
    "Snacks": ("theft", 0.010),
    "Dairy": ("spoilage", 0.025),
    "Produce": ("spoilage", 0.048),
    "Frozen": ("damage", 0.015),
    "Bakery": ("spoilage", 0.080),
    "Meat": ("spoilage", 0.040),
    "Household": ("theft", 0.018),
}


async def seed_commercial_data():
    """Seed data for commercial readiness tables."""
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        # Load existing entities
        stores_result = await db.execute(
            select(Store).where(Store.customer_id == CUSTOMER_ID)
        )
        stores = stores_result.scalars().all()

        products_result = await db.execute(
            select(Product).where(Product.customer_id == CUSTOMER_ID)
        )
        products = products_result.scalars().all()

        suppliers_result = await db.execute(
            select(Supplier).where(Supplier.customer_id == CUSTOMER_ID)
        )
        suppliers = suppliers_result.scalars().all()

        if not stores or not products:
            print("No stores or products found. Run seed_test_data.py first.")
            return

        supplier = suppliers[0] if suppliers else None

        # ── Distribution Centers ────────────────────────────────
        dcs = []
        for dc_cfg in DC_CONFIGS:
            dc = DistributionCenter(
                customer_id=CUSTOMER_ID,
                **dc_cfg,
            )
            db.add(dc)
            dcs.append(dc)
        await db.flush()
        print(f"  Created {len(dcs)} distribution centers")

        # ── Update Supplier with reliability data ───────────────
        if supplier:
            supplier.distance_miles = 180.0
            supplier.cost_per_order = 200.0
            supplier.on_time_delivery_rate = 0.87
            supplier.avg_lead_time_actual = 6.2
            supplier.lead_time_variance = 1.8
            supplier.last_delivery_date = date.today() - timedelta(days=3)
            supplier.reliability_score = 0.82

            # Create a second supplier with lower reliability
            supplier2 = Supplier(
                customer_id=CUSTOMER_ID,
                name="Pacific Coast Foods",
                contact_email="orders@pacificcoast.com",
                lead_time_days=10,
                min_order_quantity=50,
                distance_miles=420.0,
                cost_per_order=350.0,
                on_time_delivery_rate=0.62,
                avg_lead_time_actual=12.5,
                lead_time_variance=3.5,
                last_delivery_date=date.today() - timedelta(days=8),
                reliability_score=0.58,
            )
            db.add(supplier2)
            await db.flush()
            print("  Updated suppliers with reliability data")

        # ── Product Sourcing Rules ──────────────────────────────
        # 60% of products sourced from DC (fast), 40% vendor direct (slow)
        dc = dcs[0]
        sourcing_rules_created = 0

        for i, product in enumerate(products):
            if i % 5 < 3:
                # DC sourcing (priority 1) with vendor fallback (priority 2)
                db.add(ProductSourcingRule(
                    customer_id=CUSTOMER_ID,
                    product_id=product.product_id,
                    source_type="dc",
                    source_id=dc.dc_id,
                    lead_time_days=2,
                    lead_time_variance_days=1,
                    min_order_qty=12,
                    cost_per_order=50.0,
                    priority=1,
                    active=True,
                ))
                if supplier:
                    db.add(ProductSourcingRule(
                        customer_id=CUSTOMER_ID,
                        product_id=product.product_id,
                        source_type="vendor_direct",
                        source_id=supplier.supplier_id,
                        lead_time_days=supplier.lead_time_days,
                        lead_time_variance_days=2,
                        min_order_qty=supplier.min_order_quantity or 24,
                        cost_per_order=200.0,
                        priority=2,
                        active=True,
                    ))
                sourcing_rules_created += 2
            else:
                # Vendor direct only
                target_supplier = supplier2 if i % 2 == 0 and supplier2 else supplier
                if target_supplier:
                    db.add(ProductSourcingRule(
                        customer_id=CUSTOMER_ID,
                        product_id=product.product_id,
                        source_type="vendor_direct",
                        source_id=target_supplier.supplier_id,
                        lead_time_days=target_supplier.lead_time_days,
                        lead_time_variance_days=3,
                        min_order_qty=target_supplier.min_order_quantity or 24,
                        cost_per_order=target_supplier.cost_per_order or 200.0,
                        priority=1,
                        active=True,
                    ))
                    sourcing_rules_created += 1

        await db.flush()
        print(f"  Created {sourcing_rules_created} sourcing rules")

        # ── DC Inventory ────────────────────────────────────────
        dc_inv_count = 0
        for product in products:
            qty = random.randint(200, 2000)
            allocated = random.randint(0, min(50, qty))
            db.add(DCInventory(
                customer_id=CUSTOMER_ID,
                dc_id=dc.dc_id,
                product_id=product.product_id,
                quantity_on_hand=qty,
                quantity_allocated=allocated,
                quantity_in_transit=random.randint(0, 100),
                quantity_available=qty - allocated,
            ))
            dc_inv_count += 1
        await db.flush()
        print(f"  Created {dc_inv_count} DC inventory records")

        # ── Shrinkage Rates ─────────────────────────────────────
        shrink_count = 0
        for category, (shrink_type, rate) in SHRINK_RATES.items():
            db.add(ShrinkageRate(
                customer_id=CUSTOMER_ID,
                category=category,
                shrink_rate_pct=rate,
                shrink_type=shrink_type,
                measurement_period_days=365,
            ))
            shrink_count += 1
        await db.flush()
        print(f"  Created {shrink_count} shrinkage rates")

        # ── Planograms ──────────────────────────────────────────
        planogram_count = 0
        aisles = ["A", "B", "C", "D", "E"]
        for store in stores:
            for product in products:
                aisle = random.choice(aisles)
                bay = str(random.randint(1, 12))
                shelf = str(random.randint(1, 5))
                facings = random.randint(1, 4)

                db.add(Planogram(
                    customer_id=CUSTOMER_ID,
                    store_id=store.store_id,
                    product_id=product.product_id,
                    aisle=aisle,
                    bay=bay,
                    shelf=shelf,
                    facings=facings,
                    min_presentation_qty=facings * 2,
                    max_capacity=facings * 8,
                    status="active",
                    effective_date=date(2025, 1, 1),
                ))
                planogram_count += 1
        await db.flush()
        print(f"  Created {planogram_count} planograms")

        # ── Update Products with lifecycle + holding cost ───────
        for product in products:
            product.lifecycle_state = "active"
            product.planogram_required = True
            product.holding_cost_per_unit_per_day = round(
                (product.unit_cost or 5.0) * 0.25 / 365, 4
            )

        # Set 2 products as seasonal_out for demo
        if len(products) > 15:
            products[14].lifecycle_state = "seasonal_out"
            products[15].lifecycle_state = "seasonal_out"
        await db.flush()
        print(f"  Updated {len(products)} products with lifecycle states")

        # ── Sample Purchase Orders ──────────────────────────────
        po_count = 0
        for store in stores[:2]:
            for product in random.sample(products, k=5):
                qty = random.randint(24, 100)
                po = PurchaseOrder(
                    customer_id=CUSTOMER_ID,
                    store_id=store.store_id,
                    product_id=product.product_id,
                    supplier_id=supplier.supplier_id if supplier else None,
                    quantity=qty,
                    status="suggested",
                    source_type="dc" if random.random() < 0.6 else "vendor_direct",
                    source_id=dc.dc_id if random.random() < 0.6 else (supplier.supplier_id if supplier else None),
                    promised_delivery_date=date.today() + timedelta(days=random.randint(2, 10)),
                )
                db.add(po)
                po_count += 1
        await db.flush()
        print(f"  Created {po_count} suggested purchase orders")

        await db.commit()
        print(f"\nDone! Seeded commercial readiness data for customer {CUSTOMER_ID}")


if __name__ == "__main__":
    asyncio.run(seed_commercial_data())
