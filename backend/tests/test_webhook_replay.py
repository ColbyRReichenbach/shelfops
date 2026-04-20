from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from api.v1.routers.integrations import settings
from db.models import Integration, WebhookEventLog


@pytest.fixture
async def seeded_square_integration(test_db, seeded_db):
    from core.security import encrypt

    integration = Integration(
        customer_id=seeded_db["customer_id"],
        provider="square",
        access_token_encrypted=encrypt("test-access-token"),
        refresh_token_encrypted=encrypt("test-refresh-token"),
        merchant_id="MERCHANT123",
        status="connected",
    )
    test_db.add(integration)
    await test_db.commit()
    return integration


@pytest.mark.asyncio
async def test_square_webhook_is_persisted_before_processing(client, seeded_square_integration, monkeypatch, test_db):
    dispatched = []

    def _fake_dispatch(redis_key, task_fn, *task_args):
        dispatched.append((redis_key, task_args))
        return True

    monkeypatch.setattr("api.v1.routers.integrations._debounce_and_dispatch", _fake_dispatch)
    monkeypatch.setattr(
        "workers.sync.sync_square_inventory",
        SimpleNamespace(delay=lambda *args, **kwargs: None),
        raising=False,
    )

    raw_body = json.dumps({"type": "inventory.count.updated", "merchant_id": "MERCHANT123"})
    signature = hmac.new(settings.square_webhook_secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    response = await client.post(
        "/api/v1/integrations/square/webhook",
        content=raw_body,
        headers={"content-type": "application/json", "x-square-hmacsha256-signature": signature},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert dispatched

    event_log = (await test_db.execute(select(WebhookEventLog))).scalar_one()
    assert event_log.merchant_id == "MERCHANT123"
    assert event_log.status == "processed"
    assert event_log.delivery_attempts == 1


@pytest.mark.asyncio
async def test_failed_webhook_can_be_replayed(client, seeded_square_integration, monkeypatch, test_db):
    monkeypatch.setattr(
        "api.v1.routers.integrations._debounce_and_dispatch",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("redis down")),
    )

    raw_body = json.dumps({"type": "inventory.count.updated", "merchant_id": "MERCHANT123"})
    signature = hmac.new(settings.square_webhook_secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    response = await client.post(
        "/api/v1/integrations/square/webhook",
        content=raw_body,
        headers={"content-type": "application/json", "x-square-hmacsha256-signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"

    event_log = (await test_db.execute(select(WebhookEventLog))).scalar_one()

    monkeypatch.setattr("api.v1.routers.integrations._debounce_and_dispatch", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "workers.sync.sync_square_inventory",
        SimpleNamespace(delay=lambda *args, **kwargs: None),
        raising=False,
    )
    replay_response = await client.post(f"/api/v1/integrations/webhooks/{event_log.webhook_event_id}/replay")
    assert replay_response.status_code == 200
    assert replay_response.json()["status"] == "replayed"

    await test_db.refresh(event_log)
    assert event_log.status == "replayed"
    assert event_log.delivery_attempts == 2


@pytest.mark.asyncio
async def test_dead_letter_events_appear_in_api(client, seeded_square_integration, test_db):
    event = WebhookEventLog(
        customer_id=seeded_square_integration.customer_id,
        integration_id=seeded_square_integration.integration_id,
        provider="square",
        merchant_id="MERCHANT123",
        event_type="order.created",
        status="dead_letter",
        delivery_attempts=3,
        payload={"type": "order.created"},
        headers={"x-test": "1"},
        last_error="permanent failure",
        received_at=datetime.utcnow(),
    )
    test_db.add(event)
    await test_db.commit()

    response = await client.get("/api/v1/integrations/webhooks/dead-letter")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "dead_letter"
    assert payload[0]["last_error"] == "permanent failure"
