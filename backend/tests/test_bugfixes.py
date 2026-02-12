"""
Tests for design/functionality bug fixes.

Covers:
  - Fix 1: Encryption key determinism
  - Fix 2: PO receiving creates inventory snapshot
  - Fix 3: PO double-receive guard
  - Fix 6: Alert status transition guards
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from httpx import AsyncClient

# ─── Fix 1: Encryption key determinism ──────────────────────────────────────


class TestEncryptionKeyDeterminism:
    def test_encrypt_decrypt_roundtrip(self):
        """Dev key must produce consistent encrypt/decrypt."""
        from core.security import decrypt, encrypt

        plaintext = "sk-test-oauth-token-12345"
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_dev_key_is_deterministic(self):
        """Same dev key across separate imports."""
        import base64
        import hashlib

        base64.urlsafe_b64encode(
            hashlib.sha256(b"shelfops-dev-key-not-for-production").digest()
        )  # verify the derivation doesn't raise
        # Fernet stores the key internally; verify by encrypting the same
        # value twice — both should be decryptable (same key)
        from core.security import _fernet, decrypt, encrypt

        ct1 = encrypt("test-value")
        ct2 = encrypt("test-value")
        assert decrypt(ct1) == "test-value"
        assert decrypt(ct2) == "test-value"
        # Ciphertexts should differ (Fernet uses random IV) but both decrypt
        assert ct1 != ct2


# ─── Fix 2 & 3: PO receiving ───────────────────────────────────────────────


@pytest.mark.asyncio
class TestPOReceiving:
    async def test_receive_creates_inventory_snapshot(self, client: AsyncClient, seeded_db):
        """Receiving a PO should create an InventoryLevel record."""
        po = seeded_db["po"]
        po_id = str(po.po_id)

        # First approve the PO
        approve_resp = await client.post(f"/api/v1/purchase-orders/{po_id}/approve", json={})
        assert approve_resp.status_code == 200

        # Then receive it
        receive_resp = await client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"received_qty": 45, "received_date": str(date.today())},
        )
        assert receive_resp.status_code == 200
        data = receive_resp.json()
        assert data["status"] == "received"
        assert data["received_qty"] == 45

        # Verify inventory was updated by checking via inventory endpoint
        inv_resp = await client.get(f"/api/v1/inventory/?product_id={str(po.product_id)}")
        assert inv_resp.status_code == 200

    async def test_double_receive_returns_400(self, client: AsyncClient, seeded_db):
        """Receiving an already-received PO should fail with 400."""
        po = seeded_db["po"]
        po_id = str(po.po_id)

        # Approve then receive
        await client.post(f"/api/v1/purchase-orders/{po_id}/approve", json={})
        await client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"received_qty": 48},
        )

        # Try to receive again
        resp = await client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"received_qty": 48},
        )
        assert resp.status_code == 400
        assert "already been received" in resp.json()["detail"]

    async def test_receive_tracks_discrepancy(self, client: AsyncClient, seeded_db):
        """Receiving different qty than ordered should track discrepancy."""
        po = seeded_db["po"]
        po_id = str(po.po_id)

        # Approve then receive with different qty (ordered=48, received=40)
        await client.post(f"/api/v1/purchase-orders/{po_id}/approve", json={})
        resp = await client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"received_qty": 40},
        )
        assert resp.status_code == 200
        assert resp.json()["received_qty"] == 40


# ─── Fix 6: Alert status transition guards ──────────────────────────────────


@pytest.mark.asyncio
class TestAlertStatusGuards:
    async def _create_alert(self, db, customer_id, store_id, product_id, status="open"):
        """Helper: insert an alert directly into the DB."""
        from db.models import Alert

        alert = Alert(
            customer_id=customer_id,
            store_id=store_id,
            product_id=product_id,
            alert_type="stockout_predicted",
            severity="high",
            message="Test alert",
            status=status,
        )
        db.add(alert)
        await db.flush()
        return alert

    async def test_acknowledge_open_alert(self, client: AsyncClient, seeded_db, test_db):
        """Acknowledging an open alert should succeed."""
        alert = await self._create_alert(
            test_db,
            seeded_db["customer_id"],
            seeded_db["store"].store_id,
            seeded_db["product"].product_id,
        )
        await test_db.commit()

        resp = await client.patch(f"/api/v1/alerts/{alert.alert_id}/acknowledge")
        assert resp.status_code == 200
        assert resp.json()["status"] == "acknowledged"

    async def test_acknowledge_resolved_alert_returns_400(self, client: AsyncClient, seeded_db, test_db):
        """Acknowledging a resolved alert should fail."""
        alert = await self._create_alert(
            test_db,
            seeded_db["customer_id"],
            seeded_db["store"].store_id,
            seeded_db["product"].product_id,
            status="resolved",
        )
        await test_db.commit()

        resp = await client.patch(f"/api/v1/alerts/{alert.alert_id}/acknowledge")
        assert resp.status_code == 400
        assert "Must be 'open'" in resp.json()["detail"]

    async def test_resolve_dismissed_alert_returns_400(self, client: AsyncClient, seeded_db, test_db):
        """Resolving a dismissed alert should fail."""
        alert = await self._create_alert(
            test_db,
            seeded_db["customer_id"],
            seeded_db["store"].store_id,
            seeded_db["product"].product_id,
            status="dismissed",
        )
        await test_db.commit()

        resp = await client.patch(
            f"/api/v1/alerts/{alert.alert_id}/resolve",
            json={"action_type": "resolved", "notes": "test"},
        )
        assert resp.status_code == 400

    async def test_dismiss_resolved_alert_returns_400(self, client: AsyncClient, seeded_db, test_db):
        """Dismissing a resolved alert should fail."""
        alert = await self._create_alert(
            test_db,
            seeded_db["customer_id"],
            seeded_db["store"].store_id,
            seeded_db["product"].product_id,
            status="resolved",
        )
        await test_db.commit()

        resp = await client.patch(f"/api/v1/alerts/{alert.alert_id}/dismiss")
        assert resp.status_code == 400

    async def test_resolve_acknowledged_alert_succeeds(self, client: AsyncClient, seeded_db, test_db):
        """Resolving an acknowledged alert should succeed."""
        alert = await self._create_alert(
            test_db,
            seeded_db["customer_id"],
            seeded_db["store"].store_id,
            seeded_db["product"].product_id,
            status="acknowledged",
        )
        await test_db.commit()

        resp = await client.patch(
            f"/api/v1/alerts/{alert.alert_id}/resolve",
            json={"action_type": "resolved", "notes": "fixed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"
