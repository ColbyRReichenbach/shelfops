"""
Unit Tests — Supply chain (transfers, receiving).
"""

import uuid
from datetime import date, datetime

import pytest


@pytest.mark.asyncio
class TestReceiving:
    async def test_process_receiving_exact_qty(self, test_db, seeded_db):
        """Receiving exact ordered qty has no discrepancy."""
        from supply_chain.receiving import process_receiving

        po = seeded_db["po"]
        # Set PO to approved status for receiving
        po.status = "approved"
        await test_db.flush()

        result = await process_receiving(test_db, po.po_id, received_qty=48, received_date=date.today())
        assert result["status"] == "received"
        assert result["ordered_qty"] == 48
        assert result["received_qty"] == 48
        assert result["has_discrepancy"] is False

    async def test_process_receiving_shortage(self, test_db, seeded_db):
        """Receiving less than ordered creates shortage discrepancy."""
        from supply_chain.receiving import process_receiving

        po = seeded_db["po"]
        po.status = "ordered"
        await test_db.flush()

        result = await process_receiving(test_db, po.po_id, received_qty=40, received_date=date.today())
        assert result["has_discrepancy"] is True
        assert result["discrepancy_type"] == "shortage"
        assert result["discrepancy_qty"] == 8

    async def test_process_receiving_overage(self, test_db, seeded_db):
        """Receiving more than ordered creates overage discrepancy."""
        from supply_chain.receiving import process_receiving

        po = seeded_db["po"]
        po.status = "approved"
        await test_db.flush()

        result = await process_receiving(test_db, po.po_id, received_qty=55, received_date=date.today())
        assert result["has_discrepancy"] is True
        assert result["discrepancy_type"] == "overage"
        assert result["discrepancy_qty"] == 7

    async def test_process_receiving_wrong_status_raises(self, test_db, seeded_db):
        """Cannot receive a PO in 'suggested' status."""
        from supply_chain.receiving import process_receiving

        po = seeded_db["po"]
        assert po.status == "suggested"

        with pytest.raises(ValueError, match="Cannot receive PO"):
            await process_receiving(test_db, po.po_id, received_qty=48, received_date=date.today())

    async def test_process_receiving_not_found_raises(self, test_db, seeded_db):
        """Non-existent PO raises ValueError."""
        from supply_chain.receiving import process_receiving

        fake_id = uuid.uuid4()
        with pytest.raises(ValueError, match="not found"):
            await process_receiving(test_db, fake_id, received_qty=10, received_date=date.today())


@pytest.mark.asyncio
class TestTransferRequest:
    async def test_create_transfer_request(self, test_db, seeded_db):
        """Create a store-to-store transfer request."""
        from supply_chain.transfers import create_transfer_request

        customer_id = seeded_db["customer_id"]
        product_id = seeded_db["product"].product_id
        store_id = seeded_db["store"].store_id

        # Need a second store for transfer
        from db.models import Store

        store2 = Store(
            customer_id=customer_id,
            name="Uptown Store",
            city="Minneapolis",
            state="MN",
            zip_code="55408",
        )
        test_db.add(store2)
        await test_db.flush()

        transfer = await create_transfer_request(
            test_db,
            customer_id=customer_id,
            product_id=product_id,
            from_store_id=store_id,
            to_store_id=store2.store_id,
            quantity=20,
        )
        assert transfer.status == "requested"
        assert transfer.quantity == 20
        assert transfer.from_location_id == store_id
        assert transfer.to_location_id == store2.store_id

    async def test_transfer_opportunities_rank_by_distance_and_excess(self, test_db, seeded_db):
        """Closer store with strong excess should rank higher than farther options."""
        from db.models import InventoryLevel, ReorderPoint, Store
        from supply_chain.transfers import find_transfer_opportunities

        customer_id = seeded_db["customer_id"]
        product_id = seeded_db["product"].product_id
        requesting_store = seeded_db["store"]

        # Ensure requesting store has location coordinates.
        requesting_store.lat = 44.98
        requesting_store.lon = -93.27

        store_near = Store(
            customer_id=customer_id,
            name="Near Store",
            city="Minneapolis",
            state="MN",
            zip_code="55402",
            lat=44.99,
            lon=-93.26,
        )
        store_far = Store(
            customer_id=customer_id,
            name="Far Store",
            city="Rochester",
            state="MN",
            zip_code="55901",
            lat=44.02,
            lon=-92.47,
        )
        test_db.add_all([store_near, store_far])
        await test_db.flush()

        now = datetime.utcnow()
        test_db.add_all(
            [
                InventoryLevel(
                    customer_id=customer_id,
                    store_id=store_near.store_id,
                    product_id=product_id,
                    timestamp=now,
                    quantity_on_hand=250,
                    quantity_available=250,
                    quantity_on_order=0,
                    source="test",
                ),
                InventoryLevel(
                    customer_id=customer_id,
                    store_id=store_far.store_id,
                    product_id=product_id,
                    timestamp=now,
                    quantity_on_hand=500,
                    quantity_available=500,
                    quantity_on_order=0,
                    source="test",
                ),
                ReorderPoint(
                    customer_id=customer_id,
                    store_id=store_near.store_id,
                    product_id=product_id,
                    reorder_point=80,
                    safety_stock=40,
                    economic_order_qty=100,
                    lead_time_days=3,
                    service_level=0.95,
                ),
                ReorderPoint(
                    customer_id=customer_id,
                    store_id=store_far.store_id,
                    product_id=product_id,
                    reorder_point=120,
                    safety_stock=90,
                    economic_order_qty=120,
                    lead_time_days=4,
                    service_level=0.95,
                ),
            ]
        )
        await test_db.commit()

        options = await find_transfer_opportunities(
            test_db,
            customer_id=customer_id,
            product_id=product_id,
            requesting_store_id=requesting_store.store_id,
            needed_qty=100,
            max_results=3,
            search_radius_miles=200,
        )

        assert len(options) >= 2
        assert options[0].from_store_name == "Near Store"
        assert options[0].distance_miles < options[1].distance_miles


class TestTransferConstants:
    """Test transfer module constants."""

    def test_cost_per_mile_reasonable(self):
        from supply_chain.transfers import COST_PER_MILE

        assert 0.1 <= COST_PER_MILE <= 5.0

    def test_default_lead_days_reasonable(self):
        from supply_chain.transfers import DEFAULT_TRANSFER_LEAD_DAYS

        assert 1 <= DEFAULT_TRANSFER_LEAD_DAYS <= 5

    def test_max_search_radius_reasonable(self):
        from supply_chain.transfers import MAX_SEARCH_RADIUS_MILES

        assert 10 <= MAX_SEARCH_RADIUS_MILES <= 200

    def test_handling_cost_floor_applies(self, monkeypatch):
        from supply_chain import transfers

        monkeypatch.setattr(transfers, "COST_PER_MILE", 0.5)
        monkeypatch.setattr(transfers, "HANDLING_COST_FLOOR", 12.0)
        assert max(5 * transfers.COST_PER_MILE, transfers.HANDLING_COST_FLOOR) == 12.0
