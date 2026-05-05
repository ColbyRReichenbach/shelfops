"""
API Integration Tests — Report endpoints (inventory-health, forecast-accuracy,
stockout-risk, vendor-scorecard).
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import CUSTOMER_ID

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
async def reports_db(test_db):
    """Seed the test DB with entities needed by report endpoints."""
    from db.models import (
        Customer,
        DemandForecast,
        ForecastAccuracy,
        InventoryLevel,
        Product,
        PurchaseOrder,
        ReorderPoint,
        Store,
        Supplier,
        Transaction,
    )

    cid = uuid.UUID(CUSTOMER_ID)

    customer = Customer(
        customer_id=cid,
        name="Report Grocers",
        email="reports@grocers.com",
        plan="professional",
    )
    test_db.add(customer)
    await test_db.flush()

    supplier = Supplier(
        customer_id=cid,
        name="Fresh Farms Distributor",
        contact_email="orders@freshfarms.com",
        lead_time_days=5,
    )
    test_db.add(supplier)
    await test_db.flush()

    store = Store(
        customer_id=cid,
        name="Downtown Store",
        city="Minneapolis",
        state="MN",
        zip_code="55401",
    )
    test_db.add(store)
    await test_db.flush()

    product = Product(
        customer_id=cid,
        sku="RPT-0001",
        name="Organic Milk",
        category="Dairy",
        unit_cost=3.50,
        unit_price=5.99,
        supplier_id=supplier.supplier_id,
    )
    test_db.add(product)
    await test_db.flush()

    # Second product for multi-row coverage
    product2 = Product(
        customer_id=cid,
        sku="RPT-0002",
        name="Greek Yogurt",
        category="Dairy",
        unit_cost=2.00,
        unit_price=4.49,
        supplier_id=supplier.supplier_id,
    )
    test_db.add(product2)
    await test_db.flush()

    await test_db.commit()

    return {
        "customer_id": cid,
        "supplier": supplier,
        "store": store,
        "product": product,
        "product2": product2,
    }


# ─── Inventory Health ────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestInventoryHealth:
    async def test_empty_returns_empty_list(self, client: AsyncClient):
        """No inventory/reorder data → empty list."""
        resp = await client.get("/api/v1/reports/inventory-health")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_critical_status(self, client: AsyncClient, reports_db, test_db):
        """quantity_on_hand ≤ 0.5×ROP → critical."""
        from db.models import InventoryLevel, ReorderPoint

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]

        test_db.add(
            ReorderPoint(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                reorder_point=100,
                safety_stock=20,
                economic_order_qty=200,
                lead_time_days=5,
            )
        )
        test_db.add(
            InventoryLevel(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                timestamp=datetime.utcnow(),
                quantity_on_hand=40,  # 40 ≤ 0.5×100 → critical
                quantity_available=40,
            )
        )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/inventory-health")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        row = next(r for r in data if r["product_id"] == str(pid))
        assert row["status"] == "critical"
        assert row["quantity_on_hand"] == 40
        assert row["reorder_point"] == 100

    async def test_warning_status(self, client: AsyncClient, reports_db, test_db):
        """0.5×ROP < quantity_on_hand ≤ ROP → warning."""
        from db.models import InventoryLevel, ReorderPoint

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]

        test_db.add(
            ReorderPoint(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                reorder_point=100,
                safety_stock=20,
                economic_order_qty=200,
                lead_time_days=5,
            )
        )
        test_db.add(
            InventoryLevel(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                timestamp=datetime.utcnow(),
                quantity_on_hand=75,  # 50 < 75 ≤ 100 → warning
                quantity_available=75,
            )
        )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/inventory-health")
        assert resp.status_code == 200
        data = resp.json()
        row = next(r for r in data if r["product_id"] == str(pid))
        assert row["status"] == "warning"

    async def test_above_rop_not_returned(self, client: AsyncClient, reports_db, test_db):
        """quantity_on_hand > ROP → NOT included in results (only at-risk items)."""
        from db.models import InventoryLevel, ReorderPoint

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]

        test_db.add(
            ReorderPoint(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                reorder_point=50,
                safety_stock=10,
                economic_order_qty=100,
                lead_time_days=3,
            )
        )
        test_db.add(
            InventoryLevel(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                timestamp=datetime.utcnow(),
                quantity_on_hand=200,  # 200 > 50 → healthy, excluded
                quantity_available=200,
            )
        )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/inventory-health")
        assert resp.status_code == 200
        pids = [r["product_id"] for r in resp.json()]
        assert str(pid) not in pids

    async def test_days_of_supply_with_sales(self, client: AsyncClient, reports_db, test_db):
        """days_of_supply = quantity_on_hand / avg_daily_sales when transactions exist."""
        from db.models import InventoryLevel, ReorderPoint, Transaction

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]

        test_db.add(
            ReorderPoint(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                reorder_point=100,
                safety_stock=20,
                economic_order_qty=200,
                lead_time_days=5,
            )
        )
        test_db.add(
            InventoryLevel(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                timestamp=datetime.utcnow(),
                quantity_on_hand=60,
                quantity_available=60,
            )
        )
        # Add transactions over last 30 days: 10 qty each → total 300 → avg 10/day
        for i in range(30):
            test_db.add(
                Transaction(
                    customer_id=cid,
                    store_id=sid,
                    product_id=pid,
                    timestamp=datetime.utcnow() - timedelta(days=i),
                    quantity=10,
                    unit_price=5.99,
                    total_amount=59.90,
                    transaction_type="sale",
                )
            )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/inventory-health")
        assert resp.status_code == 200
        data = resp.json()
        row = next(r for r in data if r["product_id"] == str(pid))
        # avg_daily_sales = 300/30 = 10; days_of_supply = 60/10 = 6.0
        assert row["days_of_supply"] == 6.0


# ─── Forecast Accuracy ───────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestForecastAccuracy:
    async def test_empty_returns_empty_list(self, client: AsyncClient):
        """No forecast accuracy data → empty list."""
        resp = await client.get("/api/v1/reports/forecast-accuracy")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_weekly_aggregation(self, client: AsyncClient, reports_db, test_db):
        """Rows in the same ISO week are aggregated together."""
        from db.models import ForecastAccuracy

        cid = reports_db["customer_id"]
        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id

        # Insert two rows in the same ISO week (Mon-Sun)
        today = date.today()
        # Find the most recent Monday
        monday = today - timedelta(days=today.weekday())

        test_db.add(
            ForecastAccuracy(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                forecast_date=monday,
                forecasted_demand=100.0,
                actual_demand=90.0,
                mae=10.0,
                mape=0.10,
                model_version="v1",
            )
        )
        test_db.add(
            ForecastAccuracy(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                forecast_date=monday + timedelta(days=2),  # Wednesday, same week
                forecasted_demand=80.0,
                actual_demand=85.0,
                mae=5.0,
                mape=0.06,
                model_version="v1",
            )
        )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/forecast-accuracy?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

        # Find the week containing our Monday
        week = next(w for w in data if w["week_start"] == monday.isoformat())
        assert week["sample_count"] == 2
        assert week["avg_mae"] == pytest.approx(7.5, abs=0.01)  # (10+5)/2
        assert week["avg_mape"] == pytest.approx(0.08, abs=0.01)  # (0.10+0.06)/2

    async def test_days_parameter(self, client: AsyncClient, reports_db, test_db):
        """Only rows within the lookback window are returned."""
        from db.models import ForecastAccuracy

        cid = reports_db["customer_id"]
        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id

        # One row 5 days ago (within 7-day window)
        test_db.add(
            ForecastAccuracy(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                forecast_date=date.today() - timedelta(days=5),
                forecasted_demand=100.0,
                actual_demand=95.0,
                mae=5.0,
                mape=0.05,
                model_version="v1",
            )
        )
        # One row 60 days ago (outside 7-day window)
        test_db.add(
            ForecastAccuracy(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                forecast_date=date.today() - timedelta(days=60),
                forecasted_demand=100.0,
                actual_demand=80.0,
                mae=20.0,
                mape=0.20,
                model_version="v1",
            )
        )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/forecast-accuracy?days=7")
        assert resp.status_code == 200
        data = resp.json()
        # Should only contain the recent row's week
        total_samples = sum(w["sample_count"] for w in data)
        assert total_samples == 1

    async def test_days_validation_bounds(self, client: AsyncClient):
        """days param must be 1-365."""
        resp = await client.get("/api/v1/reports/forecast-accuracy?days=0")
        assert resp.status_code == 422

        resp = await client.get("/api/v1/reports/forecast-accuracy?days=400")
        assert resp.status_code == 422


# ─── Stockout Risk ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestStockoutRisk:
    async def test_empty_returns_empty_list(self, client: AsyncClient):
        """No inventory/forecast data → empty list."""
        resp = await client.get("/api/v1/reports/stockout-risk")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_high_risk(self, client: AsyncClient, reports_db, test_db):
        """quantity_available < 0.5 × total_demand → high risk."""
        from db.models import DemandForecast, InventoryLevel

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]

        test_db.add(
            InventoryLevel(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                timestamp=datetime.utcnow(),
                quantity_on_hand=20,
                quantity_available=20,
            )
        )
        # Forecast 100 total demand over next 7 days → 20/100 = 0.2 < 0.5 → high
        for i in range(7):
            test_db.add(
                DemandForecast(
                    customer_id=cid,
                    store_id=sid,
                    product_id=pid,
                    forecast_date=date.today() + timedelta(days=i),
                    forecasted_demand=100 / 7,
                    model_version="v1",
                )
            )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/stockout-risk?horizon_days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        row = next(r for r in data if r["product_id"] == str(pid))
        assert row["risk_level"] == "high"
        assert row["quantity_available"] == 20
        assert row["total_forecasted_demand"] > 0
        assert row["days_until_stockout"] is not None

    async def test_medium_risk(self, client: AsyncClient, reports_db, test_db):
        """0.5 ≤ quantity_available/total_demand < 1.0 → medium risk."""
        from db.models import DemandForecast, InventoryLevel

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]

        test_db.add(
            InventoryLevel(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                timestamp=datetime.utcnow(),
                quantity_on_hand=60,
                quantity_available=60,
            )
        )
        # Forecast 100 total demand → 60/100 = 0.6 ≥ 0.5 → medium
        for i in range(7):
            test_db.add(
                DemandForecast(
                    customer_id=cid,
                    store_id=sid,
                    product_id=pid,
                    forecast_date=date.today() + timedelta(days=i),
                    forecasted_demand=100 / 7,
                    model_version="v1",
                )
            )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/stockout-risk?horizon_days=7")
        assert resp.status_code == 200
        data = resp.json()
        row = next(r for r in data if r["product_id"] == str(pid))
        assert row["risk_level"] == "medium"

    async def test_no_risk_when_inventory_exceeds_demand(self, client: AsyncClient, reports_db, test_db):
        """quantity_available ≥ total_demand → NOT in results."""
        from db.models import DemandForecast, InventoryLevel

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]

        test_db.add(
            InventoryLevel(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                timestamp=datetime.utcnow(),
                quantity_on_hand=500,
                quantity_available=500,
            )
        )
        # Forecast 50 total demand → 500 ≥ 50 → not at risk
        for i in range(7):
            test_db.add(
                DemandForecast(
                    customer_id=cid,
                    store_id=sid,
                    product_id=pid,
                    forecast_date=date.today() + timedelta(days=i),
                    forecasted_demand=50 / 7,
                    model_version="v1",
                )
            )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/stockout-risk?horizon_days=7")
        assert resp.status_code == 200
        pids = [r["product_id"] for r in resp.json()]
        assert str(pid) not in pids

    async def test_horizon_days_validation(self, client: AsyncClient):
        """horizon_days must be 1-90."""
        resp = await client.get("/api/v1/reports/stockout-risk?horizon_days=0")
        assert resp.status_code == 422

        resp = await client.get("/api/v1/reports/stockout-risk?horizon_days=100")
        assert resp.status_code == 422

    async def test_days_until_stockout_calculation(self, client: AsyncClient, reports_db, test_db):
        """days_until_stockout = floor(qty / daily_rate)."""
        from db.models import DemandForecast, InventoryLevel

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]

        test_db.add(
            InventoryLevel(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                timestamp=datetime.utcnow(),
                quantity_on_hand=30,
                quantity_available=30,
            )
        )
        # 7 forecast days, 10/day = 70 total → daily_rate = 10
        # days_until_stockout = int(30 / 10) = 3
        for i in range(7):
            test_db.add(
                DemandForecast(
                    customer_id=cid,
                    store_id=sid,
                    product_id=pid,
                    forecast_date=date.today() + timedelta(days=i),
                    forecasted_demand=10.0,
                    model_version="v1",
                )
            )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/stockout-risk?horizon_days=7")
        assert resp.status_code == 200
        data = resp.json()
        row = next(r for r in data if r["product_id"] == str(pid))
        assert row["days_until_stockout"] == 3


# ─── Vendor Scorecard ────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestVendorScorecard:
    async def test_empty_returns_empty_list(self, client: AsyncClient):
        """No suppliers with POs → empty list."""
        resp = await client.get("/api/v1/reports/vendor-scorecard")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_scorecard_with_received_po(self, client: AsyncClient, reports_db, test_db):
        """Received PO produces on_time_rate, fill_rate, and avg_lead_time_days."""
        from db.models import PurchaseOrder

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]
        supplier_id = reports_db["supplier"].supplier_id

        suggested = datetime(2026, 3, 1)
        promised = date(2026, 3, 6)
        actual = date(2026, 3, 5)  # On time (before promised)

        test_db.add(
            PurchaseOrder(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                supplier_id=supplier_id,
                quantity=100,
                status="received",
                source_type="vendor_direct",
                suggested_at=suggested,
                promised_delivery_date=promised,
                actual_delivery_date=actual,
                received_qty=95,  # fill_rate = 95/100 = 0.95
            )
        )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/vendor-scorecard")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        row = next(r for r in data if r["supplier_id"] == str(supplier_id))
        assert row["supplier_name"] == "Fresh Farms Distributor"
        assert row["total_pos"] == 1
        assert row["on_time_rate"] == pytest.approx(1.0)
        assert row["fill_rate"] == pytest.approx(0.95, abs=0.01)
        # lead_time = (2026-03-05) - (2026-03-01) = 4 days
        assert row["avg_lead_time_days"] == pytest.approx(4.0, abs=0.1)

    async def test_late_delivery_on_time_rate(self, client: AsyncClient, reports_db, test_db):
        """Late delivery → on_time_rate = 0."""
        from db.models import PurchaseOrder

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]
        supplier_id = reports_db["supplier"].supplier_id

        test_db.add(
            PurchaseOrder(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                supplier_id=supplier_id,
                quantity=50,
                status="received",
                source_type="vendor_direct",
                suggested_at=datetime(2026, 3, 1),
                promised_delivery_date=date(2026, 3, 5),
                actual_delivery_date=date(2026, 3, 8),  # Late
                received_qty=50,
            )
        )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/vendor-scorecard")
        assert resp.status_code == 200
        data = resp.json()
        row = next(r for r in data if r["supplier_id"] == str(supplier_id))
        assert row["on_time_rate"] == pytest.approx(0.0)

    async def test_mixed_on_time_and_late(self, client: AsyncClient, reports_db, test_db):
        """One on-time + one late → on_time_rate = 0.5."""
        from db.models import PurchaseOrder

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]
        supplier_id = reports_db["supplier"].supplier_id

        # On time
        test_db.add(
            PurchaseOrder(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                supplier_id=supplier_id,
                quantity=50,
                status="received",
                source_type="vendor_direct",
                suggested_at=datetime(2026, 3, 1),
                promised_delivery_date=date(2026, 3, 5),
                actual_delivery_date=date(2026, 3, 4),
                received_qty=50,
            )
        )
        # Late
        test_db.add(
            PurchaseOrder(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                supplier_id=supplier_id,
                quantity=50,
                status="received",
                source_type="vendor_direct",
                suggested_at=datetime(2026, 3, 1),
                promised_delivery_date=date(2026, 3, 5),
                actual_delivery_date=date(2026, 3, 8),
                received_qty=50,
            )
        )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/vendor-scorecard")
        assert resp.status_code == 200
        data = resp.json()
        row = next(r for r in data if r["supplier_id"] == str(supplier_id))
        assert row["on_time_rate"] == pytest.approx(0.5, abs=0.01)
        assert row["total_pos"] == 2

    async def test_suggested_po_no_received_metrics(self, client: AsyncClient, reports_db, test_db):
        """Supplier with only suggested POs → null metrics but total_pos counted."""
        from db.models import PurchaseOrder

        sid = reports_db["store"].store_id
        pid = reports_db["product"].product_id
        cid = reports_db["customer_id"]
        supplier_id = reports_db["supplier"].supplier_id

        test_db.add(
            PurchaseOrder(
                customer_id=cid,
                store_id=sid,
                product_id=pid,
                supplier_id=supplier_id,
                quantity=30,
                status="suggested",
                source_type="vendor_direct",
                promised_delivery_date=date.today() + timedelta(days=5),
            )
        )
        await test_db.flush()
        await test_db.commit()

        resp = await client.get("/api/v1/reports/vendor-scorecard")
        assert resp.status_code == 200
        data = resp.json()
        row = next(r for r in data if r["supplier_id"] == str(supplier_id))
        assert row["total_pos"] == 1
        assert row["on_time_rate"] is None
        assert row["fill_rate"] is None
        assert row["avg_lead_time_days"] is None
