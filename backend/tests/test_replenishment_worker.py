from __future__ import annotations

import asyncio
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.models  # noqa: F401
from db.models import ReplenishmentRecommendation
from db.session import Base
from tests.test_recommendation_service import CUSTOMER_ID, _seed_recommendation_fixture
from workers.replenishment import generate_recommendation_queue


def _sqlite_engine(tmp_path):
    db_path = tmp_path / "replenishment_worker.db"
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)


async def _setup_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def test_replenishment_queue_beat_entry_registered():
    from workers.celery_app import celery_app

    beat = celery_app.conf.beat_schedule
    assert "generate-recommendation-queue-nightly" in beat
    entry = beat["generate-recommendation-queue-nightly"]
    assert entry["kwargs"]["task_name"] == "workers.replenishment.generate_recommendation_queue"
    assert entry["kwargs"]["task_kwargs"]["horizon_days"] == 7
    assert entry["options"]["queue"] == "sync"


def test_replenishment_task_route_registered():
    from workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert "workers.replenishment.*" in routes
    assert routes["workers.replenishment.*"]["queue"] == "ml"


def test_generate_recommendation_queue_task_creates_queue_rows(tmp_path, monkeypatch):
    engine = _sqlite_engine(tmp_path)
    asyncio.run(_setup_db(engine))

    db_url = str(engine.url)
    monkeypatch.setattr("core.config.get_settings", lambda: SimpleNamespace(database_url=db_url))

    async def _seed():
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as db:
            await _seed_recommendation_fixture(db)

    asyncio.run(_seed())

    result = generate_recommendation_queue.run(customer_id=str(CUSTOMER_ID), horizon_days=7, model_version="v3")

    assert result["status"] == "success"
    assert result["candidate_pairs"] == 1
    assert result["generated_count"] == 1
    assert result["open_queue_count"] == 1

    async def _check():
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as db:
            count = await db.scalar(select(func.count(ReplenishmentRecommendation.recommendation_id)))
            assert count == 1

    asyncio.run(_check())
    asyncio.run(engine.dispose())
