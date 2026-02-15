import asyncio
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.session import Base
from workers.scheduler import dispatch_active_tenants


def test_dispatch_active_tenants_fans_out_only_active_and_trial(tmp_path, monkeypatch):
    from db.models import Customer

    db_path = tmp_path / "dispatch.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as db:
            db.add_all(
                [
                    Customer(
                        customer_id="00000000-0000-0000-0000-000000000101",
                        name="Active Tenant",
                        email="active@example.com",
                        status="active",
                        plan="professional",
                    ),
                    Customer(
                        customer_id="00000000-0000-0000-0000-000000000102",
                        name="Trial Tenant",
                        email="trial@example.com",
                        status="trial",
                        plan="starter",
                    ),
                    Customer(
                        customer_id="00000000-0000-0000-0000-000000000103",
                        name="Inactive Tenant",
                        email="inactive@example.com",
                        status="inactive",
                        plan="starter",
                    ),
                ]
            )
            await db.commit()

    asyncio.run(_seed())

    monkeypatch.setattr("core.config.get_settings", lambda: SimpleNamespace(database_url=db_url))

    dispatched_calls: list[tuple[str, dict]] = []

    def _capture_send_task(task_name: str, kwargs: dict):
        dispatched_calls.append((task_name, kwargs))
        return None

    monkeypatch.setattr("workers.scheduler.celery_app.send_task", _capture_send_task)

    result = dispatch_active_tenants.run(task_name="workers.sync.run_alert_check")
    assert result["status"] == "success"
    assert result["customer_count"] == 2
    assert result["dispatched_count"] == 2

    task_names = {task for task, _ in dispatched_calls}
    assert task_names == {"workers.sync.run_alert_check"}
    customer_ids = {kwargs["customer_id"] for _, kwargs in dispatched_calls}
    assert customer_ids == {
        "00000000-0000-0000-0000-000000000101",
        "00000000-0000-0000-0000-000000000102",
    }

    asyncio.run(engine.dispose())
