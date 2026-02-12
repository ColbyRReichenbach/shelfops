"""
Vendor Metrics Worker — Daily vendor scorecard recalculation.

Updates supplier reliability scores based on actual delivery performance:
  - On-time delivery rate (within ±1 day of promised date)
  - Average actual lead time vs promised
  - Lead time variance (std dev)

These metrics feed into the inventory optimizer's safety stock calculation:
  Low reliability → higher safety stock multiplier → more buffer inventory.

Schedule: crontab(hour=1, minute=0) — daily at 1 AM
Queue: sync
"""

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="workers.vendor_metrics.update_vendor_scorecards",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def update_vendor_scorecards(self, customer_id: str):
    """
    Daily job: Recalculate vendor reliability metrics from PO receiving data.

    For each supplier with received POs in the last 90 days:
    1. Calculate on-time delivery rate
    2. Calculate average actual lead time
    3. Calculate lead time variance (std dev)
    4. Update supplier record
    """
    run_id = self.request.id or "manual"
    logger.info("vendor_metrics.started", customer_id=customer_id, run_id=run_id)

    async def _update():
        from core.config import get_settings
        from db.models import PurchaseOrder, Supplier

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            updated = 0

            async with async_session() as db:
                cutoff = datetime.utcnow() - timedelta(days=90)

                # Get all active suppliers for this customer
                result = await db.execute(
                    select(Supplier).where(
                        Supplier.customer_id == customer_id,
                        Supplier.status == "active",
                    )
                )
                suppliers = result.scalars().all()

                for supplier in suppliers:
                    # Get received POs for this supplier in rolling 90-day window
                    po_result = await db.execute(
                        select(PurchaseOrder).where(
                            PurchaseOrder.customer_id == customer_id,
                            PurchaseOrder.supplier_id == supplier.supplier_id,
                            PurchaseOrder.status == "received",
                            PurchaseOrder.received_at >= cutoff,
                        )
                    )
                    received_pos = po_result.scalars().all()

                    if not received_pos:
                        continue

                    # Calculate metrics
                    on_time_count = 0
                    lead_times = []

                    for po in received_pos:
                        if po.actual_delivery_date and po.promised_delivery_date:
                            days_diff = (po.actual_delivery_date - po.promised_delivery_date).days
                            if abs(days_diff) <= 1:
                                on_time_count += 1

                        if po.actual_delivery_date and po.ordered_at:
                            actual_lt = (po.actual_delivery_date - po.ordered_at.date()).days
                            if actual_lt > 0:
                                lead_times.append(actual_lt)

                    total_pos = len(received_pos)

                    # Update supplier metrics
                    supplier.on_time_delivery_rate = round(on_time_count / total_pos, 3) if total_pos > 0 else None
                    supplier.last_delivery_date = max(
                        (po.actual_delivery_date for po in received_pos if po.actual_delivery_date),
                        default=None,
                    )

                    if lead_times:
                        import statistics

                        supplier.avg_lead_time_actual = round(statistics.mean(lead_times), 1)
                        supplier.lead_time_variance = (
                            round(statistics.stdev(lead_times), 1) if len(lead_times) > 1 else 0.0
                        )

                        # Update composite reliability score
                        # Weighted: 60% on-time rate + 40% lead time consistency
                        on_time_score = supplier.on_time_delivery_rate or 0.5
                        consistency_score = max(0, 1.0 - (supplier.lead_time_variance or 0) / supplier.lead_time_days)
                        supplier.reliability_score = round(0.6 * on_time_score + 0.4 * max(0, consistency_score), 3)

                    updated += 1

                await db.commit()
        finally:
            await engine.dispose()

        summary = {
            "status": "success",
            "customer_id": customer_id,
            "suppliers_updated": updated,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("vendor_metrics.completed", **summary)
        return summary

    try:
        return asyncio.run(_update())
    except Exception as exc:
        logger.error("vendor_metrics.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)
