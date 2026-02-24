"""
Tests for workers.edi_ingest — EDI X12 Celery ingest task.

Mirrors the pattern in test_sftp_ingest.py and test_kafka_ingest.py:
  - SQLite in-process DB (aiosqlite) to avoid requiring a running PostgreSQL.
  - EDIAdapter methods are patched to return deterministic SyncResult objects.
  - Validates beat schedule entry, task route, skip logic, and pipeline execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.models  # noqa: F401 — registers all ORM models before create_all()

# ── helpers ────────────────────────────────────────────────────────────────────


def _make_sync_result(status: str = "success", records: int = 3):
    """Return a minimal SyncResult-like object."""
    r = MagicMock()
    r.status.value = status
    r.records_processed = records
    r.records_failed = 0
    r.errors = []
    r.metadata = {"files_processed": 2}
    return r


async def _make_db(tmp_path):
    """Spin up a fresh SQLite DB with ShelfOps schema and return (engine, session)."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(db.models.Base.metadata.create_all)
    session = async_sessionmaker(engine, class_=AsyncSession)
    return engine, session


async def _seed_customer(db_session, customer_id: uuid.UUID):
    from db.models import Customer

    async with db_session() as db:
        db.add(
            Customer(
                customer_id=customer_id,
                name="EDI Demo Retailer",
                email=f"edi-{customer_id}@example.com",
                plan="enterprise",
                status="active",
            )
        )
        await db.commit()


async def _seed_integration(db_session, customer_id: uuid.UUID, *, status: str = "connected"):
    from db.models import Integration

    async with db_session() as db:
        integration = Integration(
            customer_id=customer_id,
            provider="custom_edi",
            integration_type="edi",
            status=status,
            config={
                "edi_input_dir": "/data/edi/inbound",
                "edi_archive_dir": "/data/edi/archive",
                "partner_id": "VENDOR_001",
            },
        )
        db.add(integration)
        await db.commit()
        await db.refresh(integration)
        return integration


# ── schedule / route assertions ────────────────────────────────────────────────


def test_edi_ingest_beat_entry_registered():
    from workers.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "edi-ingest-15m" in schedule
    entry = schedule["edi-ingest-15m"]
    assert entry["kwargs"]["task_name"] == "workers.edi_ingest.ingest_edi_batch"
    assert entry["options"]["queue"] == "sync"


def test_edi_ingest_task_route():
    from workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert "workers.edi_ingest.*" in routes
    assert routes["workers.edi_ingest.*"]["queue"] == "sync"


# ── ingest_edi_batch task ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_edi_batch_skips_when_no_integration(tmp_path):
    """If no connected EDI integration exists, pipeline must not be called."""
    from db.models import Integration
    from workers.edi_ingest import run_edi_ingest_pipeline

    customer_id = uuid.uuid4()
    engine, db_session = await _make_db(tmp_path)
    await _seed_customer(db_session, customer_id)
    # No Integration row seeded → query returns None

    mock_pipeline = AsyncMock(return_value={"status": "skipped"})
    with patch("workers.edi_ingest.run_edi_ingest_pipeline", mock_pipeline):
        async with db_session() as db:
            result = await db.execute(
                select(Integration).where(
                    Integration.customer_id == customer_id,
                    Integration.integration_type == "edi",
                    Integration.status == "connected",
                )
            )
            integration = result.scalar_one_or_none()
            assert integration is None

    mock_pipeline.assert_not_called()
    await engine.dispose()


@pytest.mark.asyncio
async def test_ingest_edi_batch_skips_disconnected_integration(tmp_path):
    """Disconnected integration is ignored — pipeline must not run."""
    from workers.edi_ingest import run_edi_ingest_pipeline

    customer_id = uuid.uuid4()
    engine, db_session = await _make_db(tmp_path)
    await _seed_customer(db_session, customer_id)
    await _seed_integration(db_session, customer_id, status="error")

    mock_pipeline = AsyncMock(return_value={"status": "success"})
    with patch("workers.edi_ingest.run_edi_ingest_pipeline", mock_pipeline):
        async with db_session() as db:
            from sqlalchemy import select

            from db.models import Integration

            result = await db.execute(
                select(Integration).where(
                    Integration.customer_id == customer_id,
                    Integration.integration_type == "edi",
                    Integration.status == "connected",
                )
            )
            integration = result.scalar_one_or_none()
            assert integration is None  # disconnected → not found by connected filter

    mock_pipeline.assert_not_called()
    await engine.dispose()


@pytest.mark.asyncio
async def test_run_edi_ingest_pipeline_writes_sync_logs(tmp_path):
    """run_edi_ingest_pipeline creates IntegrationSyncLog rows for all three sync types."""
    from db.models import Integration, IntegrationSyncLog
    from workers.edi_ingest import run_edi_ingest_pipeline

    customer_id = uuid.uuid4()
    engine, db_session = await _make_db(tmp_path)
    await _seed_customer(db_session, customer_id)
    integration = await _seed_integration(db_session, customer_id)

    success_result = _make_sync_result("success", 5)

    with patch("workers.edi_ingest.EDIAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.sync_products = AsyncMock(return_value=success_result)
        instance.sync_inventory = AsyncMock(return_value=success_result)
        instance.sync_transactions = AsyncMock(return_value=success_result)

        async with db_session() as db:
            result = await run_edi_ingest_pipeline(db, customer_id=customer_id, integration=integration)

    assert result["status"] == "success"
    assert "products" in result
    assert "inventory" in result
    assert "transactions" in result

    async with db_session() as db:
        rows = (await db.execute(select(IntegrationSyncLog))).scalars().all()

    assert len(rows) == 3
    sync_types = {r.sync_type for r in rows}
    assert sync_types == {"products", "inventory", "transactions"}
    assert all(r.sync_status == "success" for r in rows)
    assert all(r.records_synced == 5 for r in rows)

    await engine.dispose()


@pytest.mark.asyncio
async def test_run_edi_ingest_pipeline_stamps_last_sync_at(tmp_path):
    """After a successful run, Integration.last_sync_at is updated."""
    from db.models import Integration
    from workers.edi_ingest import run_edi_ingest_pipeline

    customer_id = uuid.uuid4()
    engine, db_session = await _make_db(tmp_path)
    await _seed_customer(db_session, customer_id)
    integration = await _seed_integration(db_session, customer_id)

    assert integration.last_sync_at is None

    with patch("workers.edi_ingest.EDIAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.sync_products = AsyncMock(return_value=_make_sync_result())
        instance.sync_inventory = AsyncMock(return_value=_make_sync_result())
        instance.sync_transactions = AsyncMock(return_value=_make_sync_result())

        async with db_session() as db:
            await run_edi_ingest_pipeline(db, customer_id=customer_id, integration=integration)

    async with db_session() as db:
        row = (
            await db.execute(select(Integration).where(Integration.integration_id == integration.integration_id))
        ).scalar_one()
    assert row.last_sync_at is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_run_edi_ingest_pipeline_records_partial_failure(tmp_path):
    """If one sync type fails, its log row captures the failure status."""
    from db.models import IntegrationSyncLog
    from workers.edi_ingest import run_edi_ingest_pipeline

    customer_id = uuid.uuid4()
    engine, db_session = await _make_db(tmp_path)
    await _seed_customer(db_session, customer_id)
    integration = await _seed_integration(db_session, customer_id)

    fail_result = _make_sync_result("failed", 0)
    fail_result.errors = ["parser error on file_001.edi"]
    ok_result = _make_sync_result("success", 4)

    with patch("workers.edi_ingest.EDIAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.sync_products = AsyncMock(return_value=ok_result)
        instance.sync_inventory = AsyncMock(return_value=fail_result)
        instance.sync_transactions = AsyncMock(return_value=ok_result)

        async with db_session() as db:
            result = await run_edi_ingest_pipeline(db, customer_id=customer_id, integration=integration)

    assert result["inventory"]["status"] == "failed"
    assert result["products"]["status"] == "success"

    async with db_session() as db:
        rows = (await db.execute(select(IntegrationSyncLog))).scalars().all()

    by_type = {r.sync_type: r for r in rows}
    assert by_type["inventory"].sync_status == "failed"
    assert by_type["inventory"].error_message == "parser error on file_001.edi"
    assert by_type["products"].sync_status == "success"

    await engine.dispose()
