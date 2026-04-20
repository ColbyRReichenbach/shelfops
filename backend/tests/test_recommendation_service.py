import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from db.models import (
    Customer,
    DemandForecast,
    InventoryLevel,
    Product,
    ProductSourcingRule,
    ReplenishmentRecommendation,
    Store,
    Supplier,
)
from recommendations.service import RecommendationService

CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _seed_recommendation_fixture(db):
    customer = Customer(
        customer_id=CUSTOMER_ID,
        name="Recommendation Test Retail",
        email="recommendation@test.com",
        plan="professional",
    )
    db.add(customer)
    await db.flush()

    supplier = Supplier(
        customer_id=CUSTOMER_ID,
        name="Primary Vendor",
        contact_email="vendor@test.com",
        lead_time_days=5,
        min_order_quantity=12,
        reliability_score=0.82,
        cost_per_order=24.0,
        lead_time_variance=1.0,
    )
    db.add(supplier)
    await db.flush()

    store = Store(
        customer_id=CUSTOMER_ID,
        name="North Loop",
        city="Minneapolis",
        state="MN",
        zip_code="55401",
        cluster_tier=1,
    )
    db.add(store)
    await db.flush()

    product = Product(
        customer_id=CUSTOMER_ID,
        sku="REC-001",
        name="Sparkling Water",
        category="Beverages",
        unit_cost=2.50,
        unit_price=4.99,
        holding_cost_per_unit_per_day=0.245,
        supplier_id=supplier.supplier_id,
    )
    db.add(product)
    await db.flush()

    db.add(
        ProductSourcingRule(
            customer_id=CUSTOMER_ID,
            product_id=product.product_id,
            store_id=store.store_id,
            source_type="vendor_direct",
            source_id=supplier.supplier_id,
            lead_time_days=5,
            lead_time_variance_days=1,
            min_order_qty=12,
            cost_per_order=24.0,
            priority=1,
            active=True,
        )
    )
    db.add(
        InventoryLevel(
            customer_id=CUSTOMER_ID,
            store_id=store.store_id,
            product_id=product.product_id,
            timestamp=datetime.utcnow(),
            quantity_on_hand=8,
            quantity_on_order=2,
            quantity_reserved=0,
            quantity_available=8,
            source="test_fixture",
        )
    )

    today = datetime.utcnow().date()
    daily_rows = [
        (4.0, 3.0, 5.0),
        (4.0, 3.0, 5.0),
        (4.0, 3.0, 5.0),
        (4.0, 3.0, 5.0),
        (4.0, 3.0, 5.0),
        (4.0, 3.0, 5.0),
        (4.0, 3.0, 5.0),
    ]
    for offset, (mean, lower, upper) in enumerate(daily_rows):
        db.add(
            DemandForecast(
                customer_id=CUSTOMER_ID,
                store_id=store.store_id,
                product_id=product.product_id,
                forecast_date=today + timedelta(days=offset),
                forecasted_demand=mean,
                lower_bound=lower,
                upper_bound=upper,
                confidence=0.90,
                model_version="v3",
            )
        )

    await db.commit()
    return store, product, supplier


@pytest.mark.asyncio
async def test_create_recommendation_persists_deterministic_fixture(test_db):
    store, product, supplier = await _seed_recommendation_fixture(test_db)
    service = RecommendationService(test_db)

    recommendation = await service.create_recommendation(
        customer_id=CUSTOMER_ID,
        store_id=store.store_id,
        product_id=product.product_id,
        horizon_days=7,
        model_version="v3",
    )

    assert recommendation.forecast_model_version == "v3"
    assert recommendation.policy_version == "replenishment_v1"
    assert recommendation.horizon_days == 7
    today = datetime.utcnow().date()
    assert recommendation.forecast_start_date == today
    assert recommendation.forecast_end_date == today + timedelta(days=6)
    assert recommendation.interval_method == "split_conformal"
    assert recommendation.calibration_status == "calibrated"
    assert recommendation.lead_time_days == 5
    assert recommendation.quantity_available == 8
    assert recommendation.quantity_on_order == 2
    assert recommendation.inventory_position == 10
    assert recommendation.reorder_point == 28
    assert recommendation.safety_stock == 8
    assert recommendation.economic_order_qty == 28
    assert recommendation.recommended_quantity == 46
    assert recommendation.estimated_unit_cost == 2.5
    assert recommendation.estimated_total_cost == 115.0
    assert recommendation.source_type == "vendor_direct"
    assert recommendation.source_id == supplier.supplier_id
    assert recommendation.source_name == "Primary Vendor"
    assert recommendation.horizon_demand_mean == 28.0
    assert recommendation.horizon_demand_lower == 21.0
    assert recommendation.horizon_demand_upper == 35.0
    assert recommendation.lead_time_demand_mean == 20.0
    assert recommendation.lead_time_demand_upper == 25.0
    assert recommendation.no_order_stockout_risk == "high"
    assert recommendation.order_overstock_risk == "high"
    assert recommendation.recommendation_rationale["interval_coverage"] is not None

    result = await test_db.execute(select(ReplenishmentRecommendation))
    persisted = result.scalar_one()
    assert persisted.forecast_model_version == "v3"
    assert persisted.policy_version == "replenishment_v1"
    assert persisted.recommended_quantity == 46


@pytest.mark.asyncio
async def test_create_recommendation_requires_forecasts(test_db):
    store, product, _supplier = await _seed_recommendation_fixture(test_db)
    await test_db.execute(
        ReplenishmentRecommendation.__table__.delete()
    )
    await test_db.execute(DemandForecast.__table__.delete())
    await test_db.commit()

    service = RecommendationService(test_db)

    with pytest.raises(ValueError, match="no future forecasts available"):
        await service.create_recommendation(
            customer_id=CUSTOMER_ID,
            store_id=store.store_id,
            product_id=product.product_id,
            horizon_days=7,
            model_version="v3",
        )
