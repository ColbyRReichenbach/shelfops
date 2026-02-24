"""
Tests for workers.kafka_ingest — Kafka / Pub/Sub event-stream ingest task.

Strategy: use an in-process SQLite DB (aiosqlite) so tests run without a live
Postgres or Kafka broker.  The EventStreamAdapter is replaced with a lightweight
test double that returns a canned SyncResult.

Covers:
  - ingest_kafka_events: skips when no event_stream integration exists
  - ingest_kafka_events: skips when integration is disconnected
  - run_kafka_ingest_pipeline: calls sync_transactions + sync_inventory and
    writes two IntegrationSyncLog rows
  - run_kafka_ingest_pipeline: correctly handles FAILED adapter result
    (writes log with status='failed', does NOT raise)
  - run_kafka_ingest_pipeline: stamps last_sync_at on the Integration row
  - celery_app beat schedule: kafka-ingest-5m entry is registered
  - celery_app task_routes: workers.kafka_ingest.* routes to the sync queue
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.models  # noqa: F401 — ensures all ORM models register with Base.metadata before create_all
from db.session import Base
from workers.kafka_ingest import ingest_kafka_events, run_kafka_ingest_pipeline

# ── Helpers ────────────────────────────────────────────────────────────────

CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
INTEGRATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _make_sync_result(status_value: str, records: int = 3, errors: list | None = None):
    """Build a minimal SyncResult-like namespace accepted by run_kafka_ingest_pipeline."""
    from integrations.base import SyncStatus

    status_map = {
        "success": SyncStatus.SUCCESS,
        "failed": SyncStatus.FAILED,
        "no_data": SyncStatus.NO_DATA,
    }
    return SimpleNamespace(
        status=status_map[status_value],
        records_processed=records,
        records_failed=0,
        errors=errors or [],
        metadata={},
    )


def _make_integration(
    status: str = "connected",
    integration_type: str = "event_stream",
    config: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        integration_id=INTEGRATION_ID,
        customer_id=CUSTOMER_ID,
        status=status,
        integration_type=integration_type,
        config=config
        or {
            "broker_type": "kafka",
            "bootstrap_servers": "localhost:9092",
            "topics": {
                "transactions": "pos.transactions.completed",
                "inventory": "inventory.adjustments",
            },
            "consumer_group": "shelfops-ingest",
        },
    )


def _sqlite_engine(tmp_path):
    db_path = tmp_path / "kafka_ingest_test.db"
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)


async def _setup_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Tests: celery_app registration ────────────────────────────────────────


def test_kafka_ingest_beat_entry_registered():
    from workers.celery_app import celery_app

    beat = celery_app.conf.beat_schedule
    assert "kafka-ingest-5m" in beat, "Beat entry 'kafka-ingest-5m' not found in beat_schedule"
    entry = beat["kafka-ingest-5m"]
    assert entry["kwargs"]["task_name"] == "workers.kafka_ingest.ingest_kafka_events"
    assert entry["options"]["queue"] == "sync"


def test_kafka_ingest_task_route():
    from workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert "workers.kafka_ingest.*" in routes
    assert routes["workers.kafka_ingest.*"]["queue"] == "sync"


# ── Tests: ingest_kafka_events Celery task ────────────────────────────────


def test_ingest_kafka_events_skips_when_no_integration(tmp_path, monkeypatch):
    """Task returns skipped when the tenant has no event_stream integration."""
    engine = _sqlite_engine(tmp_path)
    asyncio.run(_setup_db(engine))

    db_url = str(engine.url)
    monkeypatch.setattr("core.config.get_settings", lambda: SimpleNamespace(database_url=db_url))

    # Seed a customer but no Integration row.
    from db.models import Customer

    async def _seed():
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as db:
            db.add(
                Customer(
                    customer_id=CUSTOMER_ID,
                    name="Test Tenant",
                    email="test@example.com",
                    status="active",
                    plan="professional",
                )
            )
            await db.commit()

    asyncio.run(_seed())

    result = ingest_kafka_events.run(customer_id=str(CUSTOMER_ID))
    assert result["status"] == "skipped"
    assert result["reason"] == "no_event_stream_integration"

    asyncio.run(engine.dispose())


def test_ingest_kafka_events_skips_disconnected_integration(tmp_path, monkeypatch):
    """Task skips an integration that exists but has status='disconnected'."""
    engine = _sqlite_engine(tmp_path)
    asyncio.run(_setup_db(engine))

    db_url = str(engine.url)
    monkeypatch.setattr("core.config.get_settings", lambda: SimpleNamespace(database_url=db_url))

    from db.models import Customer, Integration

    async def _seed():
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as db:
            db.add(
                Customer(
                    customer_id=CUSTOMER_ID,
                    name="Test Tenant",
                    email="test@example.com",
                    status="active",
                    plan="professional",
                )
            )
            db.add(
                Integration(
                    integration_id=INTEGRATION_ID,
                    customer_id=CUSTOMER_ID,
                    provider="kafka",
                    integration_type="event_stream",
                    status="disconnected",  # ← disconnected
                    config={"broker_type": "kafka"},
                )
            )
            await db.commit()

    asyncio.run(_seed())

    result = ingest_kafka_events.run(customer_id=str(CUSTOMER_ID))
    assert result["status"] == "skipped"

    asyncio.run(engine.dispose())


def test_ingest_kafka_events_processes_multiple_connected_integrations(tmp_path, monkeypatch):
    """Task processes all connected event_stream integrations for the tenant."""
    engine = _sqlite_engine(tmp_path)
    asyncio.run(_setup_db(engine))

    db_url = str(engine.url)
    monkeypatch.setattr("core.config.get_settings", lambda: SimpleNamespace(database_url=db_url))

    from db.models import Customer, Integration

    pubsub_integration_id = uuid.UUID("00000000-0000-0000-0000-000000000003")

    async def _seed():
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as db:
            db.add(
                Customer(
                    customer_id=CUSTOMER_ID,
                    name="Test Tenant",
                    email="test@example.com",
                    status="active",
                    plan="professional",
                )
            )
            db.add(
                Integration(
                    integration_id=INTEGRATION_ID,
                    customer_id=CUSTOMER_ID,
                    provider="kafka",
                    integration_type="event_stream",
                    status="connected",
                    config={"broker_type": "kafka"},
                )
            )
            db.add(
                Integration(
                    integration_id=pubsub_integration_id,
                    customer_id=CUSTOMER_ID,
                    provider="pubsub",
                    integration_type="event_stream",
                    status="connected",
                    config={"broker_type": "pubsub"},
                )
            )
            await db.commit()

    asyncio.run(_seed())

    with patch("workers.kafka_ingest.run_kafka_ingest_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = {"status": "success"}
        result = ingest_kafka_events.run(customer_id=str(CUSTOMER_ID))

    assert result["status"] == "success"
    assert result["integrations_processed"] == 2
    assert mock_pipeline.await_count == 2

    asyncio.run(engine.dispose())


# ── Tests: run_kafka_ingest_pipeline ──────────────────────────────────────


@pytest.mark.asyncio
async def test_run_kafka_ingest_pipeline_writes_sync_logs(tmp_path):
    """
    Happy-path: both adapter calls succeed, two IntegrationSyncLog rows are
    written, Integration.last_sync_at is stamped.
    """
    engine = _sqlite_engine(tmp_path)
    await _setup_db(engine)

    from db.models import Customer, Integration, IntegrationSyncLog

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        db.add(
            Customer(
                customer_id=CUSTOMER_ID,
                name="Kafka Tenant",
                email="kafka@example.com",
                status="active",
                plan="professional",
            )
        )
        db.add(
            Integration(
                integration_id=INTEGRATION_ID,
                customer_id=CUSTOMER_ID,
                provider="kafka",
                integration_type="event_stream",
                status="connected",
                config={
                    "broker_type": "kafka",
                    "bootstrap_servers": "localhost:9092",
                    "topics": {
                        "transactions": "pos.transactions.completed",
                        "inventory": "inventory.adjustments",
                    },
                    "consumer_group": "shelfops-ingest",
                },
            )
        )
        await db.commit()

    async with sf() as db:
        result_obj = await db.execute(select(Integration).where(Integration.integration_id == INTEGRATION_ID))
        integration = result_obj.scalar_one()

        success_result = _make_sync_result("success", records=10)

        with patch("workers.kafka_ingest.EventStreamAdapter") as MockAdapter:
            instance = MockAdapter.return_value
            instance.sync_transactions = AsyncMock(return_value=success_result)
            instance.sync_inventory = AsyncMock(return_value=success_result)

            summary = await run_kafka_ingest_pipeline(db, customer_id=CUSTOMER_ID, integration=integration)

    assert summary["status"] == "success"
    assert summary["transactions"]["records_processed"] == 10
    assert summary["inventory"]["records_processed"] == 10
    assert summary["transactions"]["status"] == "success"
    assert summary["inventory"]["status"] == "success"

    # Verify DB state.
    async with sf() as db:
        logs = (
            (
                await db.execute(
                    select(IntegrationSyncLog).where(
                        IntegrationSyncLog.customer_id == CUSTOMER_ID,
                        IntegrationSyncLog.integration_type == "Kafka",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(logs) == 2
        assert {r.sync_type for r in logs} == {"transactions", "inventory"}
        assert all(r.sync_status == "success" for r in logs)
        assert all(r.records_synced == 10 for r in logs)

        # last_sync_at should have been stamped.
        integ = (await db.execute(select(Integration).where(Integration.integration_id == INTEGRATION_ID))).scalar_one()
        assert integ.last_sync_at is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_run_kafka_ingest_pipeline_handles_failed_adapter(tmp_path):
    """
    When the adapter returns FAILED (broker unreachable), the pipeline writes a
    'failed' sync log but does NOT raise — so the task does not enqueue a retry
    for a transient network outage.
    """
    engine = _sqlite_engine(tmp_path)
    await _setup_db(engine)

    from db.models import Customer, Integration, IntegrationSyncLog

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        db.add(
            Customer(
                customer_id=CUSTOMER_ID,
                name="Kafka Tenant",
                email="kafka@example.com",
                status="active",
                plan="professional",
            )
        )
        db.add(
            Integration(
                integration_id=INTEGRATION_ID,
                customer_id=CUSTOMER_ID,
                provider="kafka",
                integration_type="event_stream",
                status="connected",
                config={"broker_type": "kafka", "bootstrap_servers": "bad-host:9092"},
            )
        )
        await db.commit()

    async with sf() as db:
        result_obj = await db.execute(select(Integration).where(Integration.integration_id == INTEGRATION_ID))
        integration = result_obj.scalar_one()

        failed_result = _make_sync_result("failed", records=0, errors=["Connection refused"])

        with patch("workers.kafka_ingest.EventStreamAdapter") as MockAdapter:
            instance = MockAdapter.return_value
            instance.sync_transactions = AsyncMock(return_value=failed_result)
            instance.sync_inventory = AsyncMock(return_value=failed_result)

            # Should NOT raise even though adapter returned FAILED.
            summary = await run_kafka_ingest_pipeline(db, customer_id=CUSTOMER_ID, integration=integration)

    assert summary["status"] == "success"  # pipeline itself succeeded; individual status shows failure
    assert summary["transactions"]["status"] == "failed"
    assert summary["inventory"]["status"] == "failed"

    async with sf() as db:
        logs = (
            (
                await db.execute(
                    select(IntegrationSyncLog).where(
                        IntegrationSyncLog.customer_id == CUSTOMER_ID,
                        IntegrationSyncLog.integration_type == "Kafka",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(logs) == 2
        assert all(r.sync_status == "failed" for r in logs)
        assert all(r.error_message is not None for r in logs)

    await engine.dispose()


@pytest.mark.asyncio
async def test_run_kafka_ingest_pipeline_no_data_is_recorded(tmp_path):
    """
    When a topic has no messages (NO_DATA), the log is written with status
    'no_data' and records_synced=0 — not treated as a failure.
    """
    engine = _sqlite_engine(tmp_path)
    await _setup_db(engine)

    from db.models import Customer, Integration, IntegrationSyncLog

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        db.add(
            Customer(
                customer_id=CUSTOMER_ID,
                name="Kafka Tenant",
                email="kafka@example.com",
                status="active",
                plan="professional",
            )
        )
        db.add(
            Integration(
                integration_id=INTEGRATION_ID,
                customer_id=CUSTOMER_ID,
                provider="kafka",
                integration_type="event_stream",
                status="connected",
                config={"broker_type": "kafka"},
            )
        )
        await db.commit()

    async with sf() as db:
        result_obj = await db.execute(select(Integration).where(Integration.integration_id == INTEGRATION_ID))
        integration = result_obj.scalar_one()

        no_data_result = _make_sync_result("no_data", records=0)

        with patch("workers.kafka_ingest.EventStreamAdapter") as MockAdapter:
            instance = MockAdapter.return_value
            instance.sync_transactions = AsyncMock(return_value=no_data_result)
            instance.sync_inventory = AsyncMock(return_value=no_data_result)

            summary = await run_kafka_ingest_pipeline(db, customer_id=CUSTOMER_ID, integration=integration)

    assert summary["transactions"]["status"] == "no_data"
    assert summary["inventory"]["status"] == "no_data"

    async with sf() as db:
        logs = (
            (
                await db.execute(
                    select(IntegrationSyncLog).where(
                        IntegrationSyncLog.customer_id == CUSTOMER_ID,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(logs) == 2
        assert all(r.sync_status == "no_data" for r in logs)
        assert all(r.records_synced == 0 for r in logs)

    await engine.dispose()
