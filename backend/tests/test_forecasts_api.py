"""
API Integration Tests — Forecast endpoints with seeded data.
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.fixture
async def seeded_forecasts(test_db, seeded_db):
    """Seed forecasts and accuracy records for testing."""
    from db.models import DemandForecast, ForecastAccuracy

    store = seeded_db["store"]
    product = seeded_db["product"]
    customer_id = seeded_db["customer_id"]

    forecasts = []
    for i in range(5):
        fc = DemandForecast(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            forecast_date=date.today() + timedelta(days=i),
            forecasted_demand=100 + i * 10,
            lower_bound=80 + i * 10,
            upper_bound=120 + i * 10,
            confidence=0.90,
            model_version="v1-cold-start",
        )
        test_db.add(fc)
        forecasts.append(fc)

    # Add accuracy records
    for i in range(3):
        acc = ForecastAccuracy(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            forecast_date=date.today() - timedelta(days=i + 1),
            forecasted_demand=100.0,
            actual_demand=95.0 + i,
            mae=5.0 - i,
            mape=5.0 - i,
            model_version="v1-cold-start",
            evaluated_at=datetime.utcnow() - timedelta(days=i),
        )
        test_db.add(acc)

    await test_db.flush()
    await test_db.commit()
    return {"forecasts": forecasts, **seeded_db}


@pytest.mark.asyncio
class TestForecastsAPI:
    async def test_list_forecasts_with_data(self, client: AsyncClient, seeded_forecasts):
        """Seeded DB returns forecasts."""
        resp = await client.get("/api/v1/forecasts/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5

    async def test_list_forecasts_filter_by_store(self, client: AsyncClient, seeded_forecasts):
        """Filter forecasts by store_id."""
        store_id = str(seeded_forecasts["store"].store_id)
        resp = await client.get(f"/api/v1/forecasts/?store_id={store_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert all(f["store_id"] == store_id for f in data)

    async def test_list_forecasts_filter_by_product(self, client: AsyncClient, seeded_forecasts):
        """Filter forecasts by product_id."""
        product_id = str(seeded_forecasts["product"].product_id)
        resp = await client.get(f"/api/v1/forecasts/?product_id={product_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert all(f["product_id"] == product_id for f in data)

    async def test_list_forecasts_filter_by_date_range(self, client: AsyncClient, seeded_forecasts):
        """Filter forecasts by date range."""
        start = str(date.today())
        end = str(date.today() + timedelta(days=2))
        resp = await client.get(f"/api/v1/forecasts/?start_date={start}&end_date={end}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for f in data:
            assert f["forecast_date"] >= start
            assert f["forecast_date"] <= end

    async def test_list_forecasts_limit(self, client: AsyncClient, seeded_forecasts):
        """Limit param works."""
        resp = await client.get("/api/v1/forecasts/?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2

    async def test_forecast_accuracy_summary(self, client: AsyncClient, seeded_forecasts):
        """Accuracy endpoint returns grouped results."""
        resp = await client.get("/api/v1/forecasts/accuracy")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "avg_mae" in data[0]
        assert "avg_mape" in data[0]
        assert "num_forecasts" in data[0]

    async def test_forecast_response_shape(self, client: AsyncClient, seeded_forecasts):
        """Forecast response includes confidence interval fields."""
        resp = await client.get("/api/v1/forecasts/?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        fc = data[0]
        assert "forecasted_demand" in fc
        assert "lower_bound" in fc
        assert "upper_bound" in fc
        assert "confidence" in fc
        assert "model_version" in fc
