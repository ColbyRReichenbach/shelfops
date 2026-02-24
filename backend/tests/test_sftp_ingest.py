"""
Tests for workers.sftp_ingest — SFTP batch-file ingest Celery task.

Mirrors test_kafka_ingest.py in structure.  Uses an in-process SQLite DB so
no real SFTP server or Postgres is needed.

Covers:
  - ingest_sftp_batch: skips when no sftp integration exists
  - ingest_sftp_batch: skips when integration is disconnected
  - ingest_sftp_batch: runs pipeline and stamps last_sync_at on connected integration
  - celery_app beat schedule: sftp-sync-15m entry is registered
  - celery_app task_routes: workers.sftp_ingest.* routes to sync queue
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.models  # noqa: F401 — registers all ORM models before create_all
from db.session import Base
from workers.sftp_ingest import ingest_sftp_batch

CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
INTEGRATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")


def _sqlite_engine(tmp_path):
    db_path = tmp_path / "sftp_ingest_test.db"
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)


async def _setup_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── celery_app registration ────────────────────────────────────────────────


def test_sftp_ingest_beat_entry_registered():
    from workers.celery_app import celery_app

    beat = celery_app.conf.beat_schedule
    assert "sftp-sync-15m" in beat, "Beat entry 'sftp-sync-15m' not in beat_schedule"
    entry = beat["sftp-sync-15m"]
    assert entry["kwargs"]["task_name"] == "workers.sftp_ingest.ingest_sftp_batch"
    assert entry["options"]["queue"] == "sync"


def test_sftp_ingest_task_route():
    from workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert "workers.sftp_ingest.*" in routes
    assert routes["workers.sftp_ingest.*"]["queue"] == "sync"


# ── ingest_sftp_batch task ─────────────────────────────────────────────────


def test_ingest_sftp_batch_skips_when_no_integration(tmp_path, monkeypatch):
    """Returns skipped when the tenant has no sftp integration."""
    engine = _sqlite_engine(tmp_path)
    asyncio.run(_setup_db(engine))

    db_url = str(engine.url)
    monkeypatch.setattr("core.config.get_settings", lambda: SimpleNamespace(database_url=db_url))

    from db.models import Customer

    async def _seed():
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as db:
            db.add(
                Customer(
                    customer_id=CUSTOMER_ID,
                    name="SFTP Tenant",
                    email="sftp@example.com",
                    status="active",
                    plan="professional",
                )
            )
            await db.commit()

    asyncio.run(_seed())

    result = ingest_sftp_batch.run(customer_id=str(CUSTOMER_ID))
    assert result["status"] == "skipped"
    assert result["reason"] == "no_sftp_integration"

    asyncio.run(engine.dispose())


def test_ingest_sftp_batch_skips_disconnected_integration(tmp_path, monkeypatch):
    """Returns skipped when integration exists but status=disconnected."""
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
                    name="SFTP Tenant",
                    email="sftp@example.com",
                    status="active",
                    plan="professional",
                )
            )
            db.add(
                Integration(
                    integration_id=INTEGRATION_ID,
                    customer_id=CUSTOMER_ID,
                    provider="custom_sftp",
                    integration_type="sftp",
                    status="disconnected",
                    config={"local_staging_dir": "/tmp/staging"},
                )
            )
            await db.commit()

    asyncio.run(_seed())

    result = ingest_sftp_batch.run(customer_id=str(CUSTOMER_ID))
    assert result["status"] == "skipped"

    asyncio.run(engine.dispose())


def test_ingest_sftp_batch_runs_pipeline_and_stamps_last_sync_at(tmp_path, monkeypatch):
    """
    When a connected sftp integration exists, the task runs the pipeline and
    stamps last_sync_at on the Integration row.
    """
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
                    name="SFTP Tenant",
                    email="sftp@example.com",
                    status="active",
                    plan="professional",
                )
            )
            db.add(
                Integration(
                    integration_id=INTEGRATION_ID,
                    customer_id=CUSTOMER_ID,
                    provider="custom_sftp",
                    integration_type="sftp",
                    status="connected",
                    config={"local_staging_dir": str(tmp_path / "staging")},
                )
            )
            await db.commit()

    asyncio.run(_seed())

    # Stub run_sftp_sync_pipeline to avoid real SFTP calls.
    pipeline_return = {"status": "success", "sources": {"inventory": {"records_processed": 5}}}

    with patch("workers.sftp_ingest.run_sftp_sync_pipeline", new=AsyncMock(return_value=pipeline_return)):
        result = ingest_sftp_batch.run(customer_id=str(CUSTOMER_ID))

    assert result["status"] == "success"

    # Verify last_sync_at was stamped.
    async def _check():
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as db:
            integ = (
                await db.execute(select(Integration).where(Integration.integration_id == INTEGRATION_ID))
            ).scalar_one()
            assert integ.last_sync_at is not None

    asyncio.run(_check())
    asyncio.run(engine.dispose())
