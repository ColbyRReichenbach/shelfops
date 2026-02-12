"""
Seed Forecast Data — Generates demand forecasts and accuracy records.

Agent: data-engineer
Skill: postgresql
Workflow: setup-database.md (Step 7: Seed Test Data)

Generates 14 days of forecasts for all store/product combinations,
plus historical accuracy records for the past 30 days.

Run: PYTHONPATH=backend python backend/scripts/seed_forecasts.py
"""

import asyncio
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings
from db.models import (
    DemandForecast,
    ForecastAccuracy,
    Product,
    Promotion,
    Store,
)

settings = get_settings()

DEV_CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"
MODEL_VERSION = "v1"


async def seed_forecasts():
    """Generate forecast + accuracy data for dashboard charts."""
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        # Fetch existing stores and products
        stores_result = await db.execute(select(Store).where(Store.customer_id == DEV_CUSTOMER_ID))
        stores = stores_result.scalars().all()

        products_result = await db.execute(select(Product).where(Product.customer_id == DEV_CUSTOMER_ID))
        products = products_result.scalars().all()

        if not stores or not products:
            print("No stores/products found. Run seed_test_data.py first.")
            return

        today = date.today()
        forecast_count = 0
        accuracy_count = 0
        promo_count = 0

        # ── Demand Forecasts: next 14 days ────────────────────────
        for store in stores:
            for product in products:
                # Base demand varies by category
                base_demand = {
                    "Beverages": 25,
                    "Snacks": 18,
                    "Dairy": 15,
                    "Produce": 12,
                    "Frozen": 10,
                    "Bakery": 8,
                    "Meat": 7,
                    "Household": 5,
                }.get(product.category, 10)

                for day_offset in range(14):
                    forecast_date = today + timedelta(days=day_offset)
                    # Add day-of-week pattern (weekend bump)
                    dow = forecast_date.weekday()
                    weekend_mult = 1.3 if dow >= 5 else 1.0
                    # Add some noise
                    demand = max(1, int(base_demand * weekend_mult * random.uniform(0.7, 1.4)))
                    # Confidence decreases with distance
                    confidence = max(0.5, 0.95 - day_offset * 0.03)
                    margin = demand * (1 - confidence) * 2

                    forecast = DemandForecast(
                        customer_id=DEV_CUSTOMER_ID,
                        store_id=store.store_id,
                        product_id=product.product_id,
                        forecast_date=forecast_date,
                        forecasted_demand=float(demand),
                        lower_bound=max(0, float(demand - margin)),
                        upper_bound=float(demand + margin),
                        confidence=confidence,
                        model_version=MODEL_VERSION,
                    )
                    db.add(forecast)
                    forecast_count += 1

        # ── Forecast Accuracy: past 30 days ───────────────────────
        for store in stores:
            for product in products:
                base_demand = {
                    "Beverages": 25,
                    "Snacks": 18,
                    "Dairy": 15,
                    "Produce": 12,
                    "Frozen": 10,
                    "Bakery": 8,
                    "Meat": 7,
                    "Household": 5,
                }.get(product.category, 10)

                for day_offset in range(1, 31):
                    eval_date = today - timedelta(days=day_offset)
                    dow = eval_date.weekday()
                    weekend_mult = 1.3 if dow >= 5 else 1.0

                    actual = max(1, int(base_demand * weekend_mult * random.uniform(0.6, 1.5)))
                    forecasted = max(1, int(base_demand * weekend_mult * random.uniform(0.75, 1.35)))

                    mae = abs(actual - forecasted)
                    mape = mae / actual if actual > 0 else 0

                    acc = ForecastAccuracy(
                        customer_id=DEV_CUSTOMER_ID,
                        store_id=store.store_id,
                        product_id=product.product_id,
                        forecast_date=eval_date,
                        forecasted_demand=float(forecasted),
                        actual_demand=float(actual),
                        mae=float(mae),
                        mape=float(mape),
                        model_version=MODEL_VERSION,
                    )
                    db.add(acc)
                    accuracy_count += 1

        # ── Sample Promotions ─────────────────────────────────────
        promo_products = random.sample(products, k=min(5, len(products)))
        for product in promo_products:
            promo = Promotion(
                customer_id=DEV_CUSTOMER_ID,
                store_id=random.choice(stores).store_id,
                product_id=product.product_id,
                name=f"{product.category} Weekend Sale",
                discount_pct=round(random.uniform(0.1, 0.3), 2),
                start_date=today - timedelta(days=random.randint(0, 7)),
                end_date=today + timedelta(days=random.randint(3, 14)),
                expected_lift=round(random.uniform(1.2, 2.0), 2),
                status="active",
            )
            db.add(promo)
            promo_count += 1

        await db.commit()
        print(
            f"Seeded: {forecast_count} forecasts (14 days), "
            f"{accuracy_count} accuracy records (30 days), "
            f"{promo_count} promotions"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_forecasts())
