"""
SFTP Batch-File Ingest Worker

Downloads and processes flat files (CSV / fixed-width) from SFTP servers
configured for each tenant and persists normalized records into the ShelfOps
database.

Architecture:
    SFTP server (retailer-managed)
        → SFTPAdapter (sync_stores / sync_products / sync_transactions / sync_inventory)
        → stores / products / transactions / inventory_levels tables
        → IntegrationSyncLog audit records

Scheduling:
    Beat fires every 15 minutes via dispatch_active_tenants.  Each active tenant
    is checked for a connected sftp Integration.  If none exists the task returns
    immediately (skipped).  This means tenants that have not configured an SFTP
    connection pay zero overhead.

Configuration (stored in Integration.config JSON):
    {
        "sftp_host":          "sftp.retailer.com",
        "sftp_port":          22,
        "sftp_username":      "shelfops_svc",
        "sftp_key_path":      "/keys/retailer_rsa",
        "remote_dir":         "/outbound/inventory",
        "local_staging_dir":  "/data/sftp/staging",
        "archive_dir":        "/data/sftp/archive",
        "file_format":        "csv",
        "delimiter":          ",",
        "file_patterns": {
            "inventory":     "INV_SNAPSHOT_*.csv",
            "transactions":  "DAILY_SALES_*.csv",
            "products":      "ITEM_MASTER_*.csv",
            "stores":        "STORE_MASTER_*.csv"
        }
    }
"""

from __future__ import annotations

import asyncio
import uuid

import structlog

from integrations.sftp_adapter import SFTPAdapter
from workers.celery_app import celery_app
from workers.sync import run_sftp_sync_pipeline

logger = structlog.get_logger()


@celery_app.task(
    name="workers.sftp_ingest.ingest_sftp_batch",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def ingest_sftp_batch(self, customer_id: str):
    """
    Download and ingest SFTP batch files for a single tenant.

    Scheduled via Celery Beat every 15 minutes through dispatch_active_tenants.

    Flow:
      1. Query for a connected sftp Integration for this customer.
      2. If none, return immediately (skipped) — zero overhead for non-SFTP tenants.
      3. Build SFTPAdapter from Integration.config.
      4. Run run_sftp_sync_pipeline: stores → products → transactions → inventory.
      5. Persist IntegrationSyncLog records and stamp last_sync_at.
    """
    run_id = self.request.id or "manual"
    logger.info("sftp_ingest.started", customer_id=customer_id, run_id=run_id)

    async def _ingest():
        from datetime import datetime, timezone

        from sqlalchemy import select, update
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
                        Integration.integration_type == "sftp",
                        Integration.status == "connected",
                    )
                )
                integration = result.scalar_one_or_none()

                if not integration:
                    logger.info(
                        "sftp_ingest.skipped",
                        customer_id=customer_id,
                        reason="no_sftp_integration",
                    )
                    return {"status": "skipped", "reason": "no_sftp_integration"}

                config: dict = (
                    integration.config if isinstance(integration.config, dict) else {}
                )
                adapter = SFTPAdapter(customer_id, config)

                pipeline_result = await run_sftp_sync_pipeline(
                    db,
                    customer_id=uuid.UUID(customer_id),
                    adapter=adapter,
                )

                # Stamp last_sync_at on the integration row.
                now = datetime.now(timezone.utc)
                await db.execute(
                    update(Integration)
                    .where(Integration.integration_id == integration.integration_id)
                    .values(last_sync_at=now, updated_at=now)
                )
                await db.commit()

                logger.info(
                    "sftp_ingest.completed",
                    customer_id=customer_id,
                    run_id=run_id,
                    result=pipeline_result,
                )
                return {"status": "success", "customer_id": customer_id, **pipeline_result}
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.error("sftp_ingest.failed", customer_id=customer_id, error=str(exc))
        raise
