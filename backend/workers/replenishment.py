"""Scheduled replenishment queue generation tasks."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="workers.replenishment.generate_recommendation_queue",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    acks_late=True,
)
def generate_recommendation_queue(
    self,
    customer_id: str,
    horizon_days: int = 7,
    model_version: str | None = None,
):
    """Generate or refresh the buyer queue for a tenant on a schedule."""
    from core.config import get_settings
    from recommendations.service import RecommendationService

    run_id = self.request.id or "manual"
    logger.info(
        "replenishment_queue.started",
        customer_id=customer_id,
        run_id=run_id,
        horizon_days=horizon_days,
        model_version=model_version,
    )

    async def _run():
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)
            async with async_session() as db:
                try:
                    await db.execute(
                        text("SELECT set_config('app.current_customer_id', :customer_id, false)"),
                        {"customer_id": customer_id},
                    )
                except Exception:
                    pass

                service = RecommendationService(db)
                summary = await service.generate_queue(
                    customer_id=uuid.UUID(customer_id),
                    horizon_days=int(horizon_days),
                    model_version=model_version,
                )
                return {
                    "status": "success",
                    "customer_id": customer_id,
                    "run_id": run_id,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    **summary,
                }
        finally:
            await engine.dispose()

    try:
        summary = asyncio.run(_run())
        logger.info("replenishment_queue.completed", **summary)
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.error("replenishment_queue.failed", customer_id=customer_id, error=str(exc), exc_info=True)
        raise self.retry(exc=exc)
