"""
Kafka / Pub/Sub Event-Stream Ingest Worker

Consumes real-time events from a Kafka topic (or Google Pub/Sub subscription)
and persists normalized records into the ShelfOps database.

Architecture:
    Kafka/Pub/Sub topic
        → EventStreamAdapter (normalize_transaction_event / normalize_inventory_event)
        → transactions / inventory_levels tables
        → IntegrationSyncLog audit record

Scheduling:
    Beat fires every 5 minutes via dispatch_active_tenants.  Each active tenant
    is checked for a connected event_stream Integration.  If none exists the task
    returns immediately (skipped).  This means tenants that haven't set up Kafka
    pay zero overhead.

Consumer behaviour:
    Each poll call fetches up to max_poll_records messages (default 500) with a
    5-second timeout.  The consumer commits offsets automatically.  If the broker
    is unreachable the adapter logs the error and returns SyncStatus.FAILED —
    the task marks the sync log accordingly and does NOT raise so Celery does not
    retry a transient connection outage as an unrecoverable failure.

Configuration (stored in Integration.config JSON):
    {
        "broker_type": "kafka",                        # or "pubsub"
        "bootstrap_servers": "localhost:9092",
        "topics": {
            "transactions": "pos.transactions.completed",
            "inventory":    "inventory.adjustments"
        },
        "consumer_group":      "shelfops-ingest",
        "auto_offset_reset":   "earliest",
        "max_poll_records":    500
    }
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from integrations.event_adapter import EventStreamAdapter
from workers.celery_app import celery_app

logger = structlog.get_logger()


async def run_kafka_ingest_pipeline(
    db,
    *,
    customer_id: uuid.UUID,
    integration: Any,
) -> dict[str, Any]:
    """
    Run one full Kafka poll-and-persist cycle for a single tenant integration.

    Called by the Celery task after fetching the Integration row from the DB.
    Extracted as a standalone async function so it can be exercised directly in
    tests without going through the Celery task wrapper.

    Returns a summary dict with keys: status, transactions, inventory.
    """
    from db.models import IntegrationSyncLog

    started_at = datetime.now(timezone.utc)
    config: dict = integration.config if isinstance(integration.config, dict) else {}
    adapter = EventStreamAdapter(str(customer_id), config)

    summary: dict[str, Any] = {}

    for sync_type, runner in (
        ("transactions", adapter.sync_transactions),
        ("inventory", adapter.sync_inventory),
    ):
        result = await runner()
        sync_status = result.status.value  # "success" | "failed" | "no_data"

        db.add(
            IntegrationSyncLog(
                customer_id=customer_id,
                integration_type="Kafka",
                integration_name=f"Kafka {sync_type.title()}",
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
            "kafka_ingest.sync_complete",
            customer_id=str(customer_id),
            sync_type=sync_type,
            records_processed=result.records_processed,
            status=sync_status,
        )

    # Persist sync logs and stamp last_sync_at on the integration row.
    from sqlalchemy import update

    from db.models import Integration

    now = datetime.now(timezone.utc)
    await db.execute(
        update(Integration)
        .where(Integration.integration_id == integration.integration_id)
        .values(last_sync_at=now, updated_at=now)
    )
    await db.commit()

    return {"status": "success", "customer_id": str(customer_id), **summary}


@celery_app.task(
    name="workers.kafka_ingest.ingest_kafka_events",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def ingest_kafka_events(self, customer_id: str):
    """
    Poll Kafka topics for a single tenant and persist normalized events.

    Scheduled via Celery Beat every 5 minutes through dispatch_active_tenants.

    Flow:
      1. Query for a connected event_stream Integration for this customer.
      2. If none, return immediately (skipped) — zero overhead for non-Kafka tenants.
      3. Build EventStreamAdapter from Integration.config.
      4. Poll transactions topic → normalize → write IntegrationSyncLog.
      5. Poll inventory topic  → normalize → write IntegrationSyncLog.
      6. Stamp last_sync_at on the Integration row.
    """
    run_id = self.request.id or "manual"
    logger.info("kafka_ingest.started", customer_id=customer_id, run_id=run_id)

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
                        Integration.integration_type == "event_stream",
                        Integration.status == "connected",
                    )
                )
                integration = result.scalar_one_or_none()

                if not integration:
                    logger.info(
                        "kafka_ingest.skipped",
                        customer_id=customer_id,
                        reason="no_event_stream_integration",
                    )
                    return {"status": "skipped", "reason": "no_event_stream_integration"}

                return await run_kafka_ingest_pipeline(
                    db,
                    customer_id=uuid.UUID(customer_id),
                    integration=integration,
                )
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.error("kafka_ingest.failed", customer_id=customer_id, error=str(exc))
        raise
