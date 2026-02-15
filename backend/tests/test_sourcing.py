"""
Tests for the Supply Chain Sourcing Engine.

Covers:
  - Haversine distance calculation
  - Lead time estimation helpers
"""

import pytest

from supply_chain.sourcing import haversine_miles

# ── Haversine Distance ─────────────────────────────────────────────────


class TestHaversineDistance:
    def test_same_point_is_zero(self):
        """Same coordinates should return 0."""
        dist = haversine_miles(42.0, -89.0, 42.0, -89.0)
        assert dist == 0.0

    def test_known_distance_chicago_milwaukee(self):
        """Chicago (41.88, -87.63) to Milwaukee (43.04, -87.91) ≈ 82 miles."""
        dist = haversine_miles(41.88, -87.63, 43.04, -87.91)
        assert 75 < dist < 95

    def test_known_distance_minneapolis_chicago(self):
        """Minneapolis (44.98, -93.27) to Chicago (41.88, -87.63) ≈ 355 miles."""
        dist = haversine_miles(44.98, -93.27, 41.88, -87.63)
        assert 340 < dist < 370

    def test_symmetry(self):
        """Distance A→B should equal distance B→A."""
        d1 = haversine_miles(42.0, -89.0, 44.0, -93.0)
        d2 = haversine_miles(44.0, -93.0, 42.0, -89.0)
        assert abs(d1 - d2) < 0.01

    def test_short_distance(self):
        """Points 0.01 degrees apart ≈ 0.5-1 mile."""
        dist = haversine_miles(42.00, -89.00, 42.01, -89.00)
        assert 0.3 < dist < 1.5

    def test_cross_country(self):
        """NYC to LA ≈ 2,450 miles."""
        dist = haversine_miles(40.71, -74.01, 34.05, -118.24)
        assert 2400 < dist < 2500


@pytest.mark.asyncio
class TestStoreSpecificLeadTime:
    async def test_sourcing_strategy_varies_by_store_rules(self, test_db, seeded_db):
        """Two stores can resolve to different lead times for the same product."""
        from db.models import ProductSourcingRule, Store
        from supply_chain.sourcing import SourcingEngine

        customer_id = seeded_db["customer_id"]
        product_id = seeded_db["product"].product_id
        supplier_id = seeded_db["supplier"].supplier_id
        store_a = seeded_db["store"]

        store_b = Store(
            customer_id=customer_id,
            name="North Store",
            city="St Paul",
            state="MN",
            zip_code="55101",
            lat=44.95,
            lon=-93.09,
        )
        test_db.add(store_b)
        await test_db.flush()

        test_db.add_all(
            [
                ProductSourcingRule(
                    customer_id=customer_id,
                    product_id=product_id,
                    store_id=store_a.store_id,
                    source_type="vendor_direct",
                    source_id=supplier_id,
                    lead_time_days=3,
                    lead_time_variance_days=1,
                    priority=1,
                    active=True,
                ),
                ProductSourcingRule(
                    customer_id=customer_id,
                    product_id=product_id,
                    store_id=store_b.store_id,
                    source_type="vendor_direct",
                    source_id=supplier_id,
                    lead_time_days=9,
                    lead_time_variance_days=2,
                    priority=1,
                    active=True,
                ),
            ]
        )
        await test_db.commit()

        engine = SourcingEngine(test_db)
        lead_a = await engine.calculate_total_leadtime(customer_id, store_a.store_id, product_id)
        lead_b = await engine.calculate_total_leadtime(customer_id, store_b.store_id, product_id)

        assert lead_a.mean_days == 3
        assert lead_b.mean_days == 9
        assert lead_a.mean_days != lead_b.mean_days

    async def test_reorder_calculation_changes_with_store_lead_time(self, test_db, seeded_db):
        """Inventory optimizer output should change when store lead time differs."""
        from db.models import ProductSourcingRule, Store
        from inventory.optimizer import InventoryOptimizer

        customer_id = seeded_db["customer_id"]
        product_id = seeded_db["product"].product_id
        supplier_id = seeded_db["supplier"].supplier_id
        store_a = seeded_db["store"]

        store_b = Store(
            customer_id=customer_id,
            name="South Store",
            city="Bloomington",
            state="MN",
            zip_code="55431",
            lat=44.84,
            lon=-93.30,
        )
        test_db.add(store_b)
        await test_db.flush()

        test_db.add_all(
            [
                ProductSourcingRule(
                    customer_id=customer_id,
                    product_id=product_id,
                    store_id=store_a.store_id,
                    source_type="vendor_direct",
                    source_id=supplier_id,
                    lead_time_days=2,
                    lead_time_variance_days=1,
                    priority=1,
                    active=True,
                ),
                ProductSourcingRule(
                    customer_id=customer_id,
                    product_id=product_id,
                    store_id=store_b.store_id,
                    source_type="vendor_direct",
                    source_id=supplier_id,
                    lead_time_days=8,
                    lead_time_variance_days=1,
                    priority=1,
                    active=True,
                ),
            ]
        )
        await test_db.commit()

        optimizer = InventoryOptimizer(test_db)

        # Avoid SQLite stddev limitations in test DB by stubbing demand retrieval.
        async def _stub_forecast_demand(*_args, **_kwargs):
            return (100.0, 10.0)

        optimizer._get_forecast_demand = _stub_forecast_demand

        calc_a = await optimizer.calculate_dynamic_reorder_point(customer_id, store_a.store_id, product_id)
        calc_b = await optimizer.calculate_dynamic_reorder_point(customer_id, store_b.store_id, product_id)

        assert calc_a is not None and calc_b is not None
        assert calc_a.lead_time_days == 2
        assert calc_b.lead_time_days == 8
        assert calc_a.reorder_point < calc_b.reorder_point
