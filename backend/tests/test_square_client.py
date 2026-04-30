import pytest

from core.security import encrypt
from integrations.square import SquareClient


@pytest.mark.asyncio
async def test_square_inventory_counts_follow_cursor_pages(monkeypatch):
    client = SquareClient(encrypt("token"))
    seen_cursors = []

    async def fake_fetch(location_ids, cursor=None):
        seen_cursors.append(cursor)
        if cursor is None:
            return {"counts": [{"catalog_object_id": "item-1"}], "cursor": "next"}
        return {"counts": [{"catalog_object_id": "item-2"}]}

    monkeypatch.setattr(client, "_fetch_inventory_counts_page", fake_fetch)

    counts = await client.get_inventory_counts(["loc-1"])

    assert seen_cursors == [None, "next"]
    assert [row["catalog_object_id"] for row in counts] == ["item-1", "item-2"]


@pytest.mark.asyncio
async def test_square_orders_follow_cursor_pages(monkeypatch):
    client = SquareClient(encrypt("token"))
    seen_cursors = []

    async def fake_fetch(location_ids, cursor=None):
        seen_cursors.append(cursor)
        if cursor is None:
            return {"orders": [{"id": "order-1"}], "cursor": "next"}
        return {"orders": [{"id": "order-2"}]}

    monkeypatch.setattr(client, "_fetch_orders_page", fake_fetch)

    orders = await client.get_orders(["loc-1"])

    assert seen_cursors == [None, "next"]
    assert [row["id"] for row in orders] == ["order-1", "order-2"]
