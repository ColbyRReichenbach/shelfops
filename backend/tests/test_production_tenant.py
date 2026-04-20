from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import select

from db.models import Customer, Product, RecommendationOutcome, ReplenishmentRecommendation, Store
from scripts.production_tenant import PRODUCTION_CUSTOMER_ID, ensure_production_tenant


async def test_ensure_production_tenant_wipes_recommendations_and_outcomes(test_db):
    customer = Customer(
        customer_id=PRODUCTION_CUSTOMER_ID,
        name="Old Demo Tenant",
        email="legacy@example.com",
        plan="enterprise",
        status="active",
        is_demo=True,
    )
    test_db.add(customer)
    await test_db.flush()

    store = Store(customer_id=PRODUCTION_CUSTOMER_ID, name="Legacy Store", city="Minneapolis", state="MN")
    product = Product(
        customer_id=PRODUCTION_CUSTOMER_ID,
        sku="SKU-LEGACY",
        name="Legacy Product",
        category="Grocery",
        unit_cost=2.5,
        unit_price=4.0,
    )
    test_db.add_all([store, product])
    await test_db.flush()

    recommendation = ReplenishmentRecommendation(
        customer_id=PRODUCTION_CUSTOMER_ID,
        store_id=store.store_id,
        product_id=product.product_id,
        status="open",
        forecast_model_version="v1",
        policy_version="legacy",
        horizon_days=7,
        recommended_quantity=24,
        quantity_available=5,
        quantity_on_order=0,
        inventory_position=5,
        reorder_point=18,
        safety_stock=6,
        economic_order_qty=24,
        lead_time_days=4,
        service_level=0.95,
        estimated_unit_cost=2.5,
        estimated_total_cost=60.0,
        source_type="vendor_direct",
        source_id=uuid.uuid4(),
        interval_method="uncalibrated",
        calibration_status="uncalibrated",
        no_order_stockout_risk="high",
        order_overstock_risk="low",
        recommendation_rationale={
            "forecast_start_date": date.today().isoformat(),
            "forecast_end_date": date.today().isoformat(),
            "horizon_demand_mean": 18,
        },
        created_at=datetime.utcnow(),
    )
    test_db.add(recommendation)
    await test_db.flush()

    outcome = RecommendationOutcome(
        recommendation_id=recommendation.recommendation_id,
        customer_id=PRODUCTION_CUSTOMER_ID,
        store_id=store.store_id,
        product_id=product.product_id,
        horizon_start_date=date.today(),
        horizon_end_date=date.today(),
        actual_sales_qty=12,
        actual_demand_qty=12,
        ending_inventory_qty=3,
        stockout_event=False,
        overstock_event=False,
        forecast_error_abs=2,
        estimated_stockout_value=0,
        estimated_overstock_cost=0,
        net_estimated_value=15,
        demand_confidence="measured",
        value_confidence="estimated",
        status="closed",
        computed_at=datetime.utcnow(),
    )
    test_db.add(outcome)
    await test_db.commit()

    result = await ensure_production_tenant(test_db, wipe_synthetic=True)
    await test_db.commit()

    remaining_recommendations = (await test_db.execute(select(ReplenishmentRecommendation))).scalars().all()
    remaining_outcomes = (await test_db.execute(select(RecommendationOutcome))).scalars().all()
    refreshed_customer = await test_db.get(Customer, PRODUCTION_CUSTOMER_ID)

    assert result["wiped"]["replenishment_recommendations"] == 1
    assert result["wiped"]["recommendation_outcomes"] == 1
    assert remaining_recommendations == []
    assert remaining_outcomes == []
    assert refreshed_customer is not None
    assert refreshed_customer.name == "Production Pilot"
    assert refreshed_customer.is_demo is False
