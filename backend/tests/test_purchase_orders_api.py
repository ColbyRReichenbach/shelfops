"""
API Integration Tests — Purchase Order Workflow.

Tests the approve/reject/receive endpoints with a seeded database.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestPurchaseOrdersAPI:

    async def test_health_check(self, client: AsyncClient):
        """Sanity check that the test client works."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_list_purchase_orders_empty(self, client: AsyncClient):
        """Empty DB returns empty list."""
        response = await client.get("/api/v1/purchase-orders/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_purchase_orders_with_data(self, client: AsyncClient, seeded_db):
        """Seeded DB returns the suggested PO."""
        response = await client.get("/api/v1/purchase-orders/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["status"] == "suggested"
        assert data[0]["quantity"] == 48

    async def test_list_suggested_orders(self, client: AsyncClient, seeded_db):
        """Filter for suggested orders only."""
        response = await client.get("/api/v1/purchase-orders/suggested")
        assert response.status_code == 200
        data = response.json()
        assert all(po["status"] == "suggested" for po in data)

    async def test_get_purchase_order_by_id(self, client: AsyncClient, seeded_db):
        """Get a specific PO by ID."""
        po_id = str(seeded_db["po"].po_id)
        response = await client.get(f"/api/v1/purchase-orders/{po_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["po_id"] == po_id
        assert data["quantity"] == 48

    async def test_get_purchase_order_not_found(self, client: AsyncClient):
        """Non-existent PO returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000099"
        response = await client.get(f"/api/v1/purchase-orders/{fake_id}")
        assert response.status_code == 404

    async def test_approve_purchase_order(self, client: AsyncClient, seeded_db):
        """Approve a suggested PO."""
        po_id = str(seeded_db["po"].po_id)
        response = await client.post(
            f"/api/v1/purchase-orders/{po_id}/approve",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    async def test_reject_purchase_order_requires_reason(self, client: AsyncClient, seeded_db):
        """Reject without reason_code should fail with 422."""
        po_id = str(seeded_db["po"].po_id)
        response = await client.post(
            f"/api/v1/purchase-orders/{po_id}/reject",
            json={},
        )
        assert response.status_code == 422

    async def test_reject_purchase_order_with_reason(self, client: AsyncClient, seeded_db):
        """Reject with valid reason_code succeeds."""
        po_id = str(seeded_db["po"].po_id)
        response = await client.post(
            f"/api/v1/purchase-orders/{po_id}/reject",
            json={"reason_code": "overstock", "notes": "Already have enough inventory"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    async def test_po_summary(self, client: AsyncClient, seeded_db):
        """Summary endpoint returns counts by status."""
        response = await client.get("/api/v1/purchase-orders/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert isinstance(data["total"], int)
