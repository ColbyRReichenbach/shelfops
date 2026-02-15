"""Tenant-aware scheduler helpers for Celery beat fan-out."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workers.celery_app import celery_app

logger = structlog.get_logger()

DEFAULT_ACTIVE_STATUSES = ("active", "trial")


@celery_app.task(
    name="workers.scheduler.dispatch_active_tenants",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def dispatch_active_tenants(
    self,
    task_name: str,
    task_kwargs: dict | None = None,
    statuses: list[str] | None = None,
):
    """
    Dispatch a customer-scoped task across all active tenants.
    """
    from core.config import get_settings
    from db.models import Customer

    run_id = self.request.id or "manual"
    payload = dict(task_kwargs or {})
    selected_statuses = tuple(statuses or DEFAULT_ACTIVE_STATUSES)

    if not task_name.startswith("workers."):
        return {"status": "failed", "reason": "invalid_task_name", "task_name": task_name}

    async def _dispatch():
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)
            async with async_session() as db:
                result = await db.execute(
                    select(Customer.customer_id).where(Customer.status.in_(selected_statuses)).order_by(Customer.created_at)
                )
                customers = [str(row.customer_id) for row in result.all()]

            dispatched = 0
            for customer_id in customers:
                kwargs = dict(payload)
                kwargs["customer_id"] = customer_id
                celery_app.send_task(task_name, kwargs=kwargs)
                dispatched += 1

            summary = {
                "status": "success",
                "task_name": task_name,
                "customer_count": len(customers),
                "dispatched_count": dispatched,
                "statuses": list(selected_statuses),
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
            }
            logger.info("scheduler.dispatch_complete", **summary)
            return summary
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_dispatch())
    except Exception as exc:  # noqa: BLE001
        logger.error("scheduler.dispatch_failed", task_name=task_name, error=str(exc), exc_info=True)
        raise self.retry(exc=exc)
