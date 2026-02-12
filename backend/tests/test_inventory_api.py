"""
API Integration Tests — Inventory endpoints with seeded data.
"""

import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient


@pytest.fixture
async def seeded_inventory(test_db, seeded_db):
    """Seed inventory levels and reorder points for testing."""
    from db.models import InventoryLevel, ReorderPoint

    store = seeded_db["store"]
    product = seeded_db["product"]
    customer_id = seeded_db["customer_id"]

    # Create inventory snapshot
    inv = InventoryLevel(
        customer_id=customer_id,
        store_id=store.store_id,
        product_id=product.product_id,
        timestamp=datetime.utcnow(),
        quantity_on_hand=50,
        quantity_available=45,
        quantity_on_order=10,
        source="test_seed",
    )
    test_db.add(inv)

    # Create reorder point
    rp = ReorderPoint(
        customer_id=customer_id,
        store_id=store.store_id,
        product_id=product.product_id,
        reorder_point=30,
        safety_stock=15,
        economic_order_qty=48,
        lead_time_days=7,
    )
    test_db.add(rp)

    await test_db.flush()
    await test_db.commit()
    return {"inventory": inv, "reorder_point": rp, **seeded_db}


@pytest.mark.asyncio
class TestInventoryAPI:
    async def test_inventory_summary(self, client: AsyncClient, seeded_inventory):
        """Summary returns correct counts."""
        resp = await client.get("/api/v1/inventory/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_items" in data
        assert "in_stock" in data
        assert "low_stock" in data
        assert "critical" in data
        assert "out_of_stock" in data
        assert data["total_items"] >= 1

    async def test_inventory_list(self, client: AsyncClient, seeded_inventory):
        """List returns inventory items with product/store details."""
        resp = await client.get("/api/v1/inventory/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        item = data[0]
        assert "store_name" in item
        assert "product_name" in item
        assert "quantity_on_hand" in item
        assert "status" in item
        assert item["status"] in ("ok", "low", "critical", "out_of_stock")

    async def test_inventory_list_filter_by_store(self, client: AsyncClient, seeded_inventory):
        """Filter inventory by store_id."""
        store_id = str(seeded_inventory["store"].store_id)
        resp = await client.get(f"/api/v1/inventory/?store_id={store_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert all(i["store_id"] == store_id for i in data)

    async def test_inventory_list_filter_by_category(self, client: AsyncClient, seeded_inventory):
        """Filter inventory by product category."""
        resp = await client.get("/api/v1/inventory/?category=Dairy")
        assert resp.status_code == 200
        data = resp.json()
        assert all(i["category"] == "Dairy" for i in data)

    async def test_inventory_status_ok(self, client: AsyncClient, seeded_inventory):
        """Product with qty=50 above ROP=30 should be 'ok'."""
        resp = await client.get("/api/v1/inventory/")
        assert resp.status_code == 200
        data = resp.json()
        product_id = str(seeded_inventory["product"].product_id)
        matching = [i for i in data if i["product_id"] == product_id]
        assert len(matching) == 1
        assert matching[0]["status"] == "ok"
        assert matching[0]["reorder_point"] == 30
        assert matching[0]["safety_stock"] == 15
