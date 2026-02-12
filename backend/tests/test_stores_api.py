"""
API Integration Tests — Store CRUD with seeded data.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestStoresIntegration:
    async def test_create_and_list_store(self, client: AsyncClient):
        """Create a store, then list should include it."""
        store_data = {
            "name": "Uptown Store",
            "city": "Minneapolis",
            "state": "MN",
            "zip_code": "55408",
        }
        create_resp = await client.post("/api/v1/stores/", json=store_data)
        assert create_resp.status_code == 201
        store_id = create_resp.json()["store_id"]

        list_resp = await client.get("/api/v1/stores/")
        assert list_resp.status_code == 200
        store_ids = [s["store_id"] for s in list_resp.json()]
        assert store_id in store_ids

    async def test_get_store_by_id(self, client: AsyncClient, seeded_db):
        """Get seeded store by ID."""
        store_id = str(seeded_db["store"].store_id)
        resp = await client.get(f"/api/v1/stores/{store_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Downtown Store"
        assert resp.json()["city"] == "Minneapolis"

    async def test_update_store(self, client: AsyncClient, seeded_db):
        """Patch store name."""
        store_id = str(seeded_db["store"].store_id)
        resp = await client.patch(
            f"/api/v1/stores/{store_id}",
            json={"name": "Renamed Store"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed Store"

    async def test_delete_store(self, client: AsyncClient):
        """Create and delete a store."""
        create_resp = await client.post(
            "/api/v1/stores/",
            json={"name": "Temp Store", "city": "St Paul", "state": "MN", "zip_code": "55101"},
        )
        store_id = create_resp.json()["store_id"]

        del_resp = await client.delete(f"/api/v1/stores/{store_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"/api/v1/stores/{store_id}")
        assert get_resp.status_code == 404

    async def test_create_store_missing_name(self, client: AsyncClient):
        """Validation: name is required."""
        resp = await client.post(
            "/api/v1/stores/",
            json={"city": "Minneapolis", "state": "MN"},
        )
        assert resp.status_code == 422
