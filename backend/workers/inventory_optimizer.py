"""
Inventory Optimizer Worker — Nightly reorder point recalculation.

Runs after forecast generation (2:30 AM UTC) to update reorder points
for all active (store, product) pairs based on latest demand forecasts,
supply chain lead times, and vendor reliability scores.

Schedule: crontab(hour=2, minute=30) — nightly
Queue: ml (long-running, separate from data sync)
"""

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="workers.inventory_optimizer.optimize_reorder_points",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def optimize_reorder_points(self, customer_id: str):
    """
    Nightly job: Recalculate ALL reorder points based on latest forecasts.

    Workflow:
      1. Get all active (store, product) pairs that have forecasts
      2. For each pair, call InventoryOptimizer.optimize_store_product()
      3. Log changes to reorder_history
      4. Report summary: how many updated, largest changes

    Args:
        customer_id: Tenant ID to optimize (in production, iterate over all customers)
    """
    run_id = self.request.id or "manual"
    logger.info("optimizer.started", customer_id=customer_id, run_id=run_id)

    async def _optimize():
        from core.config import get_settings
        from db.models import Product, ReorderPoint
        from inventory.optimizer import InventoryOptimizer

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                optimizer = InventoryOptimizer(db)

                # Get all active (store, product) pairs with existing reorder points
                result = await db.execute(
                    select(
                        ReorderPoint.store_id,
                        ReorderPoint.product_id,
                    ).where(
                        ReorderPoint.customer_id == customer_id,
                    )
                )
                pairs = result.all()

                updated = 0
                created = 0
                skipped = 0
                errors = 0
                changes = []

                for store_id, product_id in pairs:
                    try:
                        # Skip products that are not active
                        product = await db.get(Product, product_id)
                        if product and product.lifecycle_state not in ("active", "test"):
                            skipped += 1
                            continue

                        change = await optimizer.optimize_store_product(
                            customer_id=customer_id,
                            store_id=store_id,
                            product_id=product_id,
                        )

                        if change is None:
                            skipped += 1
                        elif change["action"] == "created":
                            created += 1
                            changes.append(change)
                        else:
                            updated += 1
                            changes.append(change)

                    except Exception as exc:
                        errors += 1
                        logger.error(
                            "optimizer.pair_failed",
                            store_id=str(store_id),
                            product_id=str(product_id),
                            error=str(exc),
                        )

                await db.commit()
        finally:
            await engine.dispose()

        summary = {
            "status": "success",
            "customer_id": customer_id,
            "run_id": run_id,
            "total_pairs": len(pairs),
            "updated": updated,
            "created": created,
            "skipped": skipped,
            "errors": errors,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Log top 5 largest changes for visibility
        significant_changes = sorted(
            [c for c in changes if c.get("pct_change")],
            key=lambda x: x.get("pct_change", 0),
            reverse=True,
        )[:5]

        logger.info(
            "optimizer.completed",
            **summary,
            top_changes=significant_changes,
        )

        return summary

    try:
        return asyncio.run(_optimize())
    except Exception as exc:
        logger.error("optimizer.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)
