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
