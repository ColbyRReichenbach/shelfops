import uuid
from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import select

from db.models import InventoryLevel, RecommendationOutcome, Transaction
from recommendations.service import RecommendationService
from tests.test_recommendation_service import _seed_recommendation_fixture
from workers.monitoring import compute_recommendation_outcomes

CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _seed_closed_horizon_recommendation(db):
    store, product, supplier = await _seed_recommendation_fixture(db)
    service = RecommendationService(db)
    recommendation = await service.create_recommendation(
        customer_id=CUSTOMER_ID,
        store_id=store.store_id,
        product_id=product.product_id,
        horizon_days=7,
        model_version="v3",
    )
    accepted = await service.accept_recommendation(
        customer_id=CUSTOMER_ID,
        recommendation_id=recommendation.recommendation_id,
        actor="planner@test.com",
        notes="Approved for replay",
    )

    start_date = datetime.fromisoformat(f"{accepted.recommendation_rationale['forecast_start_date']}T00:00:00").date()
    end_date = datetime.fromisoformat(f"{accepted.recommendation_rationale['forecast_end_date']}T00:00:00").date()
    sale_quantities = [4, 4, 5, 4, 5, 5, 5]
    for offset, quantity in enumerate(sale_quantities):
        txn_date = start_date + timedelta(days=offset)
        db.add(
            Transaction(
                customer_id=CUSTOMER_ID,
                store_id=store.store_id,
                product_id=product.product_id,
                timestamp=datetime.combine(txn_date, time(hour=12)),
                quantity=quantity,
                unit_price=4.99,
                total_amount=quantity * 4.99,
                transaction_type="sale",
            )
        )

    db.add(
        InventoryLevel(
            customer_id=CUSTOMER_ID,
            store_id=store.store_id,
            product_id=product.product_id,
            timestamp=datetime.combine(end_date, time(hour=23, minute=59)),
            quantity_on_hand=0,
            quantity_on_order=0,
            quantity_reserved=0,
            quantity_available=0,
            source="outcome_fixture",
        )
    )
    await db.commit()
    return accepted, end_date


@pytest.mark.asyncio
async def test_compute_recommendation_outcome_from_simulated_actuals(test_db):
    recommendation, horizon_end = await _seed_closed_horizon_recommendation(test_db)

    outcomes = await compute_recommendation_outcomes(
        test_db,
        customer_id=CUSTOMER_ID,
        recommendation_id=recommendation.recommendation_id,
        as_of_date=horizon_end + timedelta(days=1),
    )

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.status == "closed"
    assert outcome.actual_sales_qty == 32.0
    assert outcome.actual_demand_qty == 32.0
    assert outcome.ending_inventory_qty == 0
    assert outcome.stockout_event is True
    assert outcome.overstock_event is False
    assert outcome.forecast_error_abs == 4.0
    assert outcome.demand_confidence == "estimated"
    assert outcome.value_confidence == "measured"
    assert outcome.net_estimated_value is not None
    assert outcome.net_estimated_value > 0

    persisted = (await test_db.execute(select(RecommendationOutcome))).scalar_one()
    assert persisted.recommendation_id == recommendation.recommendation_id


@pytest.mark.asyncio
async def test_replenishment_impact_reports_confidence_labels(client, test_db):
    _recommendation, horizon_end = await _seed_closed_horizon_recommendation(test_db)

    response = await client.get(
        f"/api/v1/replenishment/impact?as_of_date={(horizon_end + timedelta(days=1)).isoformat()}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_recommendations"] == 1
    assert payload["accepted_count"] == 1
    assert payload["closed_outcomes"] == 1
    assert payload["closed_outcomes_confidence"] == "measured"
    assert (
        payload["forecast_closeout"]["measurement_basis"] == "forecast_vs_observed_sales_proxy_with_inventory_closeout"
    )
    assert payload["forecast_closeout"]["average_forecast_error_abs"] == 4.0
    assert payload["forecast_closeout"]["average_forecast_error_abs_confidence"] == "measured"
    assert payload["forecast_closeout"]["stockout_events"] == 1
    assert payload["forecast_closeout"]["stockout_events_confidence"] == "measured"
    assert (
        payload["recommendation_policy"]["measurement_basis"]
        == "observed_sales_proxy_vs_do_nothing_inventory_position_baseline"
    )
    assert payload["recommendation_policy"]["decision_quantity_basis"] == "accepted_or_edited_po_quantity_else_zero"
    assert payload["recommendation_policy"]["evaluated_decisions"] == 1
    assert payload["recommendation_policy"]["net_policy_value_confidence"] == "estimated"
    assert payload["recommendation_policy"]["net_policy_value"] is not None
