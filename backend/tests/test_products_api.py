"""
API Integration Tests — Product CRUD with seeded data.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestProductsIntegration:

    async def test_list_products_with_data(self, client: AsyncClient, seeded_db):
        """Seeded DB returns products."""
        resp = await client.get("/api/v1/products/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["sku"] == "SKU-0001"

    async def test_get_product_by_id(self, client: AsyncClient, seeded_db):
        """Get seeded product by ID."""
        product_id = str(seeded_db["product"].product_id)
        resp = await client.get(f"/api/v1/products/{product_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Product"
        assert data["category"] == "Dairy"
        assert float(data["unit_price"]) == 5.99

    async def test_get_product_not_found(self, client: AsyncClient):
        """Non-existent product returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000099"
        resp = await client.get(f"/api/v1/products/{fake_id}")
        assert resp.status_code == 404

    async def test_create_product(self, client: AsyncClient, seeded_db):
        """Create a new product."""
        product_data = {
            "sku": "SKU-NEW-001",
            "name": "Organic Milk",
            "category": "Dairy",
            "unit_cost": 2.50,
            "unit_price": 4.99,
            "supplier_id": str(seeded_db["supplier"].supplier_id),
        }
        resp = await client.post("/api/v1/products/", json=product_data)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sku"] == "SKU-NEW-001"
        assert data["name"] == "Organic Milk"

    async def test_update_product(self, client: AsyncClient, seeded_db):
        """Patch product price."""
        product_id = str(seeded_db["product"].product_id)
        resp = await client.patch(
            f"/api/v1/products/{product_id}",
            json={"unit_price": 6.49},
        )
        assert resp.status_code == 200
        assert float(resp.json()["unit_price"]) == 6.49

    async def test_filter_products_by_category(self, client: AsyncClient, seeded_db):
        """Filter products by category."""
        resp = await client.get("/api/v1/products/?category=Dairy")
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["category"] == "Dairy" for p in data)
