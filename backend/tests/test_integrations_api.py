"""
API Integration Tests — Integration management endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def seeded_integration(test_db, seeded_db):
    """Seed an integration for testing."""
    from core.security import encrypt
    from db.models import Integration

    customer_id = seeded_db["customer_id"]

    integration = Integration(
        customer_id=customer_id,
        provider="square",
        access_token_encrypted=encrypt("test-access-token"),
        refresh_token_encrypted=encrypt("test-refresh-token"),
        merchant_id="MERCHANT123",
        status="connected",
    )
    test_db.add(integration)
    await test_db.flush()
    await test_db.commit()
    return {"integration": integration, **seeded_db}


@pytest.mark.asyncio
class TestIntegrationsAPI:
    async def test_list_integrations_empty(self, client: AsyncClient):
        """Empty DB returns no integrations."""
        resp = await client.get("/api/v1/integrations/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_integrations_with_data(self, client: AsyncClient, seeded_integration):
        """Seeded DB returns integration."""
        resp = await client.get("/api/v1/integrations/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["provider"] == "square"
        assert data[0]["status"] == "connected"
        assert data[0]["merchant_id"] == "MERCHANT123"

    async def test_disconnect_integration(self, client: AsyncClient, seeded_integration):
        """Disconnecting sets status to 'disconnected'."""
        integration_id = str(seeded_integration["integration"].integration_id)
        resp = await client.delete(f"/api/v1/integrations/{integration_id}")
        assert resp.status_code == 204

        # Verify it's disconnected
        list_resp = await client.get("/api/v1/integrations/")
        data = list_resp.json()
        match = [i for i in data if i["integration_id"] == integration_id]
        assert len(match) == 1
        assert match[0]["status"] == "disconnected"

    async def test_disconnect_not_found(self, client: AsyncClient):
        """Disconnecting nonexistent integration returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000099"
        resp = await client.delete(f"/api/v1/integrations/{fake_id}")
        assert resp.status_code == 404

    async def test_integration_response_shape(self, client: AsyncClient, seeded_integration):
        """Integration response has expected fields."""
        resp = await client.get("/api/v1/integrations/")
        assert resp.status_code == 200
        integ = resp.json()[0]
        for field in ["integration_id", "customer_id", "provider", "status", "created_at"]:
            assert field in integ

    async def test_square_connect_redirect(self, client: AsyncClient):
        """Square connect returns redirect to OAuth."""
        resp = await client.get("/api/v1/integrations/square/connect", follow_redirects=False)
        assert resp.status_code == 307
        assert "squareupsandbox.com" in resp.headers.get("location", "") or "squareup.com" in resp.headers.get(
            "location", ""
        )
