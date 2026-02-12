"""
Promotion Tracking Worker — Weekly promotion effectiveness measurement.

Schedule: crontab(hour=5, minute=0, day_of_week="monday")
Queue: sync
"""

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="workers.promo_tracking.measure_completed_promotions",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def measure_completed_promotions(self, customer_id: str):
    """
    Weekly job: Evaluate promotions that ended in the last 14 days.

    Measures actual lift vs expected lift and flags outliers (>30% variance).
    """
    import uuid
    run_id = self.request.id or "manual"
    logger.info("promo_tracking.started", customer_id=customer_id, run_id=run_id)

    async def _measure():
        from core.config import get_settings
        from retail.promo_tracking import measure_promotion_effectiveness

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, class_=AsyncSession)

        async with async_session() as db:
            result = await measure_promotion_effectiveness(
                db, uuid.UUID(customer_id), lookback_days=14
            )

        await engine.dispose()

        summary = {
            "status": "success",
            "customer_id": customer_id,
            **result,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("promo_tracking.completed", **summary)
        return summary

    try:
        return asyncio.run(_measure())
    except Exception as exc:
        logger.error("promo_tracking.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)
