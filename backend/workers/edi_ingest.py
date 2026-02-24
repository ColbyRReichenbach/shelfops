"""
EDI X12 Batch-File Ingest Worker

Polls the configured inbound EDI directory for unprocessed X12 files and
ingests them via EDIAdapter into the ShelfOps database.

Architecture:
    /data/edi/inbound/*.edi  (or .x12 / .txt)
        → EDIAdapter (sync_products / sync_inventory / sync_transactions)
        → products / inventory_levels / transactions tables
        → IntegrationSyncLog audit records

Scheduling:
    Beat fires every 15 minutes via dispatch_active_tenants.  Each active tenant
    is checked for a connected edi Integration.  If none exists the task returns
    immediately (skipped) — zero overhead for non-EDI tenants.

    Processed files are archived to edi_archive_dir by EDIAdapter._archive_file()
    so they are not re-processed on the next poll.

Configuration (stored in Integration.config JSON):
    {
        "edi_input_dir":   "/data/edi/inbound",
        "edi_output_dir":  "/data/edi/outbound",
        "edi_archive_dir": "/data/edi/archive",
        "partner_id":      "VENDOR_001",
        "edi_types":       ["846", "856", "810"]
    }
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from integrations.edi_adapter import EDIAdapter
from workers.celery_app import celery_app

logger = structlog.get_logger()


async def run_edi_ingest_pipeline(
    db,
    *,
    customer_id: uuid.UUID,
    integration: Any,
) -> dict[str, Any]:
    """
    Run one full EDI poll-and-persist cycle for a single tenant integration.

    Calls sync_products, sync_inventory, and sync_transactions on the
    EDIAdapter.  Each method inspects the inbound directory, processes
    matching files, and archives them.  Results are written to
    IntegrationSyncLog and last_sync_at is stamped on the Integration row.

    Returns a summary dict with keys: status, products, inventory, transactions.
    """
    from sqlalchemy import update

    from db.models import Integration, IntegrationSyncLog

    started_at = datetime.now(timezone.utc)
    config: dict = integration.config if isinstance(integration.config, dict) else {}
    adapter = EDIAdapter(str(customer_id), config)

    summary: dict[str, Any] = {}

    for sync_type, runner in (
        ("products", adapter.sync_products),
        ("inventory", adapter.sync_inventory),
        ("transactions", adapter.sync_transactions),
    ):
        result = await runner()
        sync_status = result.status.value  # "success" | "failed" | "partial" | "no_data"

        db.add(
            IntegrationSyncLog(
                customer_id=customer_id,
                integration_type="EDI",
                integration_name=f"EDI {sync_type.title()}",
                sync_type=sync_type,
                records_synced=result.records_processed,
                sync_status=sync_status,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message="; ".join(result.errors) if result.errors else None,
                sync_metadata=result.metadata if result.metadata else None,
            )
        )
        summary[sync_type] = {
            "records_processed": result.records_processed,
            "records_failed": result.records_failed,
            "status": sync_status,
        }

        logger.info(
            "edi_ingest.sync_complete",
            customer_id=str(customer_id),
            sync_type=sync_type,
            records_processed=result.records_processed,
            status=sync_status,
        )

    # Stamp last_sync_at on the integration row and persist sync logs.
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Integration)
        .where(Integration.integration_id == integration.integration_id)
        .values(last_sync_at=now, updated_at=now)
    )
    await db.commit()

    return {"status": "success", "customer_id": str(customer_id), **summary}


@celery_app.task(
    name="workers.edi_ingest.ingest_edi_batch",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def ingest_edi_batch(self, customer_id: str):
    """
    Poll the EDI inbound directory and ingest X12 files for a single tenant.

    Scheduled via Celery Beat every 15 minutes through dispatch_active_tenants.

    Flow:
      1. Query for a connected edi Integration for this customer.
      2. If none, return immediately (skipped) — zero overhead for non-EDI tenants.
      3. Build EDIAdapter from Integration.config.
      4. Run run_edi_ingest_pipeline: products → inventory → transactions.
      5. Persist IntegrationSyncLog records and stamp last_sync_at.
    """
    run_id = self.request.id or "manual"
    logger.info("edi_ingest.started", customer_id=customer_id, run_id=run_id)

    async def _ingest():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from core.config import get_settings
        from db.models import Integration

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)
            async with async_session() as db:
                result = await db.execute(
                    select(Integration).where(
                        Integration.customer_id == customer_id,
                        Integration.integration_type == "edi",
                        Integration.status == "connected",
                    )
                )
                integration = result.scalar_one_or_none()

                if not integration:
                    logger.info(
                        "edi_ingest.skipped",
                        customer_id=customer_id,
                        reason="no_edi_integration",
                    )
                    return {"status": "skipped", "reason": "no_edi_integration"}

                pipeline_result = await run_edi_ingest_pipeline(
                    db,
                    customer_id=uuid.UUID(customer_id),
                    integration=integration,
                )

                logger.info(
                    "edi_ingest.completed",
                    customer_id=customer_id,
                    run_id=run_id,
                    result=pipeline_result,
                )
                return pipeline_result
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.error("edi_ingest.failed", customer_id=customer_id, error=str(exc))
        raise
