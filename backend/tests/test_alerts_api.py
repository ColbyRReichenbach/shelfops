"""
API Integration Tests — Alert endpoints with seeded data.
"""

import pytest
from httpx import AsyncClient


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

    async def test_create_order_from_alert(self, client: AsyncClient, seeded_alerts):
        """Open alert can create a linked purchase order once."""
        open_alert = next(a for a in seeded_alerts["alerts"] if a.status == "open")

        resp = await client.post(
            f"/api/v1/alerts/{open_alert.alert_id}/order",
            json={"quantity": 12, "estimated_cost": 42.0},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["alert_id"] == str(open_alert.alert_id)
        assert payload["status"] == "suggested"

        second = await client.post(
            f"/api/v1/alerts/{open_alert.alert_id}/order",
            json={"quantity": 12, "estimated_cost": 42.0},
        )
        assert second.status_code in {400, 409}
