"""
Unit Tests — Counterfactual analysis (opportunity cost).
"""

import uuid
from datetime import date, datetime, timedelta

import pytest


@pytest.fixture
async def seeded_counterfactual(test_db, seeded_db):
    """Seed data for counterfactual analysis."""
    from db.models import DemandForecast, InventoryLevel

    customer_id = seeded_db["customer_id"]
    store = seeded_db["store"]
    product = seeded_db["product"]
    analysis_date = date.today() - timedelta(days=1)

    # Create a forecast
    forecast = DemandForecast(
        customer_id=customer_id,
        store_id=store.store_id,
        product_id=product.product_id,
        forecast_date=analysis_date,
        forecasted_demand=50.0,
        model_version="v1-cold-start",
    )
    test_db.add(forecast)

    # Create inventory snapshot — stockout (qty=0)
    inv = InventoryLevel(
        customer_id=customer_id,
        store_id=store.store_id,
        product_id=product.product_id,
        timestamp=datetime.combine(analysis_date, datetime.min.time()),
        quantity_on_hand=0,
        quantity_available=0,
        source="test_seed",
    )
    test_db.add(inv)

    await test_db.flush()
    await test_db.commit()

    return {"analysis_date": analysis_date, **seeded_db}


@pytest.mark.asyncio
class TestCounterfactualAnalysis:
    async def test_stockout_detected(self, test_db, seeded_counterfactual):
        """Stockout detected when inventory=0 and forecast>0."""
        from business.counterfactual import analyze_daily_opportunity_cost

        result = await analyze_daily_opportunity_cost(
            test_db,
            customer_id=seeded_counterfactual["customer_id"],
            analysis_date=seeded_counterfactual["analysis_date"],
        )
        assert result["stockout_events"] >= 1
        assert result["total_stockout_cost"] > 0

    async def test_empty_date_returns_zero(self, test_db, seeded_db):
        """Date with no forecasts returns zero events."""
        from business.counterfactual import analyze_daily_opportunity_cost

        result = await analyze_daily_opportunity_cost(
            test_db,
            customer_id=seeded_db["customer_id"],
            analysis_date=date.today() - timedelta(days=365),
        )
        assert result["stockout_events"] == 0
        assert result["overstock_events"] == 0
        assert result["records_created"] == 0

    async def test_result_shape(self, test_db, seeded_counterfactual):
        """Result dict has expected keys."""
        from business.counterfactual import analyze_daily_opportunity_cost

        result = await analyze_daily_opportunity_cost(
            test_db,
            customer_id=seeded_counterfactual["customer_id"],
            analysis_date=seeded_counterfactual["analysis_date"],
        )
        expected_keys = [
            "date",
            "stockout_events",
            "overstock_events",
            "total_stockout_cost",
            "total_overstock_cost",
            "total_opportunity_cost",
            "records_created",
        ]
        for key in expected_keys:
            assert key in result
