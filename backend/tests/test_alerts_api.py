"""
API Integration Tests — Alert endpoints with seeded data.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select


@pytest.fixture
async def seeded_alerts(test_db, seeded_db):
    """Seed alerts for testing."""
    from db.models import Alert

    store = seeded_db["store"]
    product = seeded_db["product"]
    customer_id = seeded_db["customer_id"]

    alerts = []
    configs = [
        ("stockout_predicted", "critical", "open"),
        ("reorder_recommended", "high", "open"),
        ("anomaly_detected", "medium", "acknowledged"),
        ("forecast_accuracy_low", "low", "resolved"),
    ]

    for alert_type, severity, status in configs:
        alert = Alert(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            alert_type=alert_type,
            severity=severity,
            message=f"Test {alert_type} alert",
            status=status,
        )
        test_db.add(alert)
        alerts.append(alert)

    await test_db.flush()
    await test_db.commit()
    return {"alerts": alerts, **seeded_db}


@pytest.mark.asyncio
class TestAlertsIntegration:
    async def test_list_alerts_with_data(self, client: AsyncClient, seeded_alerts):
        """Seeded DB returns alerts."""
        resp = await client.get("/api/v1/alerts/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 4

    async def test_filter_by_status(self, client: AsyncClient, seeded_alerts):
        """Filter alerts by status."""
        resp = await client.get("/api/v1/alerts/?status=open")
        assert resp.status_code == 200
        data = resp.json()
        assert all(a["status"] == "open" for a in data)
        assert len(data) >= 2

    async def test_filter_by_severity(self, client: AsyncClient, seeded_alerts):
        """Filter alerts by severity."""
        resp = await client.get("/api/v1/alerts/?severity=critical")
        assert resp.status_code == 200
        data = resp.json()
        assert all(a["severity"] == "critical" for a in data)

    async def test_filter_by_alert_type(self, client: AsyncClient, seeded_alerts):
        """Filter alerts by type."""
        resp = await client.get("/api/v1/alerts/?alert_type=anomaly_detected")
        assert resp.status_code == 200
        data = resp.json()
        assert all(a["alert_type"] == "anomaly_detected" for a in data)

    async def test_filter_by_store(self, client: AsyncClient, seeded_alerts):
        """Filter alerts by store_id."""
        store_id = str(seeded_alerts["store"].store_id)
        resp = await client.get(f"/api/v1/alerts/?store_id={store_id}")
        assert resp.status_code == 200
        assert len(resp.json()) >= 4

    async def test_summary_counts(self, client: AsyncClient, seeded_alerts):
        """Summary returns correct breakdowns."""
        resp = await client.get("/api/v1/alerts/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 4
        assert data["open"] >= 2
        assert data["acknowledged"] >= 1
        assert data["resolved"] >= 1
        assert data["critical"] >= 1
        assert data["high"] >= 1

    async def test_pagination(self, client: AsyncClient, seeded_alerts):
        """Skip and limit work."""
        resp = await client.get("/api/v1/alerts/?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2

        resp2 = await client.get("/api/v1/alerts/?skip=2&limit=2")
        assert resp2.status_code == 200

    async def test_alert_response_shape(self, client: AsyncClient, seeded_alerts):
        """Alert response has expected fields."""
        resp = await client.get("/api/v1/alerts/?limit=1")
        assert resp.status_code == 200
        alert = resp.json()[0]
        for field in ["alert_id", "alert_type", "severity", "message", "status", "created_at"]:
            assert field in alert

    async def test_order_from_reorder_alert_creates_po_and_resolves_alert(
        self, client: AsyncClient, seeded_alerts, test_db
    ):
        """POST /alerts/{id}/order creates PO, decision, and ordered action."""
        from db.models import Action, Alert, PODecision, PurchaseOrder

        store = seeded_alerts["store"]
        product = seeded_alerts["product"]
        customer_id = seeded_alerts["customer_id"]
        alert = Alert(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            alert_type="reorder_recommended",
            severity="high",
            message="Reorder now",
            status="open",
            alert_metadata={"suggested_qty": 36, "reorder_point": 20, "current_stock": 8},
        )
        test_db.add(alert)
        await test_db.flush()
        await test_db.commit()

        resp = await client.post(f"/api/v1/alerts/{alert.alert_id}/order", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["po"]["status"] == "approved"
        assert body["po"]["quantity"] == 36
        assert body["alert"]["status"] == "resolved"
        assert body["alert"]["alert_metadata"]["linked_po_id"] == body["po"]["po_id"]

        po_id = uuid.UUID(body["po"]["po_id"])
        po = await test_db.get(PurchaseOrder, po_id)
        assert po is not None
        assert po.status == "approved"

        decision = await test_db.get(PODecision, uuid.UUID(body["decision_id"]))
        assert decision is not None
        assert decision.decision_type == "approved"
        assert decision.final_qty == 36

        db_alert = await test_db.get(Alert, alert.alert_id)
        assert db_alert is not None
        assert db_alert.status == "resolved"

        action_rows = (await test_db.execute(select(Action).where(Action.alert_id == alert.alert_id))).scalars().all()
        assert any(row.action_type == "ordered" for row in action_rows)

    async def test_order_from_alert_override_requires_reason(
        self, client: AsyncClient, seeded_alerts, test_db
    ):
        """Overriding suggested_qty requires reason_code."""
        from db.models import Alert

        store = seeded_alerts["store"]
        product = seeded_alerts["product"]
        customer_id = seeded_alerts["customer_id"]
        alert = Alert(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            alert_type="reorder_recommended",
            severity="high",
            message="Reorder now",
            status="open",
            alert_metadata={"suggested_qty": 40},
        )
        test_db.add(alert)
        await test_db.flush()
        await test_db.commit()

        resp = await client.post(
            f"/api/v1/alerts/{alert.alert_id}/order",
            json={"quantity": 25},
        )
        assert resp.status_code == 422
        assert "reason_code required" in resp.json()["detail"]

    async def test_order_from_non_reorder_alert_rejected(self, client: AsyncClient, seeded_alerts):
        """Only reorder_recommended alerts can be ordered."""
        alert = seeded_alerts["alerts"][0]  # stockout_predicted
        resp = await client.post(f"/api/v1/alerts/{alert.alert_id}/order", json={})
        assert resp.status_code == 422

    async def test_order_from_invalid_status_rejected(self, client: AsyncClient, seeded_alerts, test_db):
        """Resolved/dismissed alerts cannot be ordered."""
        from db.models import Alert

        store = seeded_alerts["store"]
        product = seeded_alerts["product"]
        customer_id = seeded_alerts["customer_id"]
        alert = Alert(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            alert_type="reorder_recommended",
            severity="high",
            message="Already resolved",
            status="resolved",
            alert_metadata={"suggested_qty": 22},
        )
        test_db.add(alert)
        await test_db.flush()
        await test_db.commit()

        resp = await client.post(f"/api/v1/alerts/{alert.alert_id}/order", json={})
        assert resp.status_code == 400

    async def test_order_endpoint_is_idempotent_with_linked_po(
        self, client: AsyncClient, seeded_alerts, test_db
    ):
        """Second submit returns existing order and does not create duplicate PO."""
        from db.models import Alert, PurchaseOrder

        store = seeded_alerts["store"]
        product = seeded_alerts["product"]
        customer_id = seeded_alerts["customer_id"]
        alert = Alert(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            alert_type="reorder_recommended",
            severity="high",
            message="Reorder idempotency",
            status="open",
            alert_metadata={"suggested_qty": 44},
        )
        test_db.add(alert)
        await test_db.flush()
        await test_db.commit()

        first = await client.post(f"/api/v1/alerts/{alert.alert_id}/order", json={})
        assert first.status_code == 200
        first_po_id = first.json()["po"]["po_id"]

        second = await client.post(f"/api/v1/alerts/{alert.alert_id}/order", json={})
        assert second.status_code == 200
        assert second.json()["message"] == "Order already exists for this alert"
        assert second.json()["po"]["po_id"] == first_po_id

        matching_po_count = (
            await test_db.execute(
                select(func.count())
                .select_from(PurchaseOrder)
                .where(
                    PurchaseOrder.store_id == store.store_id,
                    PurchaseOrder.product_id == product.product_id,
                    PurchaseOrder.quantity == 44,
                )
            )
        ).scalar_one()
        assert matching_po_count == 1
