"""
Seed Test Data — Creates realistic demo data for development.

Run: python scripts/seed_test_data.py
"""

import asyncio
import uuid
from datetime import datetime, timedelta
import random

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from db.session import Base
from db.models import (
    Customer, Store, Product, Supplier, Transaction,
    InventoryLevel, DemandForecast, ReorderPoint, Alert, Promotion,
)
from core.config import get_settings

settings = get_settings()

# Seed data constants
CATEGORIES = ["Beverages", "Snacks", "Dairy", "Produce", "Frozen", "Bakery", "Meat", "Household"]
BRANDS = ["NatureBest", "FreshFirst", "PureChoice", "ValuePack", "GreenHarvest"]
CITIES = [
    ("Minneapolis", "MN", "55401"), ("Chicago", "IL", "60601"),
    ("Milwaukee", "WI", "53202"), ("Des Moines", "IA", "50309"),
]


async def seed_data():
    """Create demo data for development."""
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        # ── Customer ─────────────────────────────────────────
        customer = Customer(
            customer_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            name="Midwest Grocers",
            email="admin@midwestgrocers.com",
            plan="professional",
        )
        db.add(customer)
        await db.flush()

        # ── Supplier ─────────────────────────────────────────
        supplier = Supplier(
            customer_id=customer.customer_id,
            name="Heartland Distributors",
            contact_email="orders@heartland.com",
            lead_time_days=5,
        )
        db.add(supplier)
        await db.flush()

        # ── Stores ───────────────────────────────────────────
        stores = []
        for city, state, zip_code in CITIES:
            store = Store(
                customer_id=customer.customer_id,
                name=f"{city} Store",
                city=city,
                state=state,
                zip_code=zip_code,
            )
            db.add(store)
            stores.append(store)
        await db.flush()

        # ── Products ─────────────────────────────────────────
        products = []
        for i in range(20):
            cat = CATEGORIES[i % len(CATEGORIES)]
            product = Product(
                customer_id=customer.customer_id,
                sku=f"SKU-{i+1:04d}",
                name=f"{random.choice(BRANDS)} {cat} Item #{i+1}",
                category=cat,
                brand=random.choice(BRANDS),
                unit_cost=round(random.uniform(1.0, 15.0), 2),
                unit_price=round(random.uniform(2.0, 25.0), 2),
                is_perishable=cat in ["Dairy", "Produce", "Meat", "Bakery"],
                is_seasonal=random.random() < 0.2,
                supplier_id=supplier.supplier_id,
            )
            db.add(product)
            products.append(product)
        await db.flush()

        # ── Transactions (90 days) ───────────────────────────
        now = datetime.utcnow()
        for day_offset in range(90):
            day = now - timedelta(days=day_offset)
            for store in stores:
                for product in random.sample(products, k=random.randint(5, 15)):
                    qty = random.randint(1, 20)
                    txn = Transaction(
                        customer_id=customer.customer_id,
                        store_id=store.store_id,
                        product_id=product.product_id,
                        timestamp=day.replace(
                            hour=random.randint(8, 21),
                            minute=random.randint(0, 59),
                        ),
                        quantity=qty,
                        unit_price=product.unit_price,
                        total_amount=round(qty * product.unit_price, 2),
                    )
                    db.add(txn)

        # ── Inventory Levels ─────────────────────────────────
        for store in stores:
            for product in products:
                qty = random.randint(10, 200)
                inv = InventoryLevel(
                    customer_id=customer.customer_id,
                    store_id=store.store_id,
                    product_id=product.product_id,
                    quantity_on_hand=qty,
                    quantity_available=qty,
                )
                db.add(inv)

        # ── Reorder Points ───────────────────────────────────
        for store in stores:
            for product in products:
                rp = ReorderPoint(
                    customer_id=customer.customer_id,
                    store_id=store.store_id,
                    product_id=product.product_id,
                    reorder_point=random.randint(15, 50),
                    safety_stock=random.randint(5, 20),
                    economic_order_qty=random.randint(50, 200),
                    lead_time_days=supplier.lead_time_days,
                )
                db.add(rp)

        # ── Sample Alerts ────────────────────────────────────
        for store in stores[:2]:
            for product in random.sample(products, k=3):
                alert = Alert(
                    customer_id=customer.customer_id,
                    store_id=store.store_id,
                    product_id=product.product_id,
                    alert_type="stockout_predicted",
                    severity=random.choice(["medium", "high", "critical"]),
                    message=f"Stockout predicted in {random.randint(1, 5)} days for {product.name}",
                )
                db.add(alert)

        await db.commit()
        print(f"✅ Seeded: 1 customer, {len(stores)} stores, {len(products)} products, ~{90 * len(stores) * 10} transactions")


if __name__ == "__main__":
    asyncio.run(seed_data())
