"""
Unit Tests — Planogram lifecycle checks.
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestPlanogramLifecycle:
    async def test_active_product_returns_true(self, test_db, seeded_db):
        """Active product with no planogram requirement is active."""
        from retail.planogram import is_product_active_in_store

        product = seeded_db["product"]
        store = seeded_db["store"]
        result = await is_product_active_in_store(test_db, product.product_id, store.store_id)
        assert result is True

    async def test_delisted_product_returns_false(self, test_db, seeded_db):
        """Delisted product is not active."""
        from retail.planogram import is_product_active_in_store

        product = seeded_db["product"]
        product.lifecycle_state = "delisted"
        await test_db.flush()

        result = await is_product_active_in_store(test_db, product.product_id, seeded_db["store"].store_id)
        assert result is False

    async def test_seasonal_out_product_returns_false(self, test_db, seeded_db):
        """Seasonal-out product is not active."""
        from retail.planogram import is_product_active_in_store

        product = seeded_db["product"]
        product.lifecycle_state = "seasonal_out"
        await test_db.flush()

        result = await is_product_active_in_store(test_db, product.product_id, seeded_db["store"].store_id)
        assert result is False

    async def test_nonexistent_product_returns_false(self, test_db, seeded_db):
        """Non-existent product returns False."""
        from retail.planogram import is_product_active_in_store

        fake_id = uuid.uuid4()
        result = await is_product_active_in_store(test_db, fake_id, seeded_db["store"].store_id)
        assert result is False

    async def test_min_presentation_qty_default(self, test_db, seeded_db):
        """Default min presentation qty is 2 when no planogram exists."""
        from retail.planogram import get_min_presentation_qty

        result = await get_min_presentation_qty(test_db, seeded_db["product"].product_id, seeded_db["store"].store_id)
        assert result == 2

    async def test_min_presentation_qty_with_planogram(self, test_db, seeded_db):
        """Planogram min_presentation_qty is returned when set."""
        from db.models import Planogram
        from retail.planogram import get_min_presentation_qty

        planogram = Planogram(
            customer_id=seeded_db["customer_id"],
            store_id=seeded_db["store"].store_id,
            product_id=seeded_db["product"].product_id,
            effective_date=date.today() - timedelta(days=30),
            status="active",
            min_presentation_qty=6,
        )
        test_db.add(planogram)
        await test_db.flush()

        result = await get_min_presentation_qty(test_db, seeded_db["product"].product_id, seeded_db["store"].store_id)
        assert result == 6


class TestNonOrderableStates:
    """Test the non-orderable lifecycle states constant."""

    def test_expected_non_orderable_states(self):
        from retail.planogram import NON_ORDERABLE_STATES

        assert "delisted" in NON_ORDERABLE_STATES
        assert "discontinued" in NON_ORDERABLE_STATES
        assert "seasonal_out" in NON_ORDERABLE_STATES
        assert "pending_activation" in NON_ORDERABLE_STATES
        assert "active" not in NON_ORDERABLE_STATES
