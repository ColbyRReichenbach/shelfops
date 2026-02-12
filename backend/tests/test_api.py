"""
API Tests — Smoke tests for all routes.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestHealthCheck:
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
class TestStoresAPI:
    async def test_list_stores_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/stores/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_create_store(self, client: AsyncClient):
        store_data = {
            "name": "Downtown Store",
            "city": "Minneapolis",
            "state": "MN",
            "zip_code": "55401",
        }
        response = await client.post("/api/v1/stores/", json=store_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Downtown Store"
        assert data["city"] == "Minneapolis"
        assert data["status"] == "active"

    async def test_get_store_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/stores/00000000-0000-0000-0000-000000000099")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestProductsAPI:
    async def test_list_products_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/products/")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
class TestAlertsAPI:
    async def test_list_alerts_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/alerts/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_alert_summary_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/alerts/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["open"] == 0


@pytest.mark.asyncio
class TestForecastsAPI:
    async def test_list_forecasts_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/forecasts/")
        assert response.status_code == 200
        assert response.json() == []
