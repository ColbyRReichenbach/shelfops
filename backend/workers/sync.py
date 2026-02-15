"""
Data Sync Workers — Scheduled POS data synchronization.

Workers:
  1. sync_square_inventory: Fetch inventory counts from Square → upsert inventory_levels
  2. sync_square_transactions: Fetch orders from Square → upsert transactions
  3. run_alert_check: Run the alert engine after data sync
"""

import uuid
from datetime import datetime, timezone

import structlog

from workers.celery_app import celery_app

logger = structlog.get_logger()


async def run_edi_sync_pipeline(
    db,
    *,
    customer_id: uuid.UUID,
    integration_id: uuid.UUID,
    adapter,
    partner_id: str = "UNKNOWN",
) -> dict:
    """
    Worker-path EDI orchestration:
      parse files -> persist EDI audit logs -> persist integration sync logs.
    """
    from db.models import EDITransactionLog, IntegrationSyncLog

    started_at = datetime.utcnow()
    sync_type_map = {
        "846": "inventory",
        "850": "purchase_orders",
        "856": "shipments",
        "810": "invoices",
    }
    summary: dict[str, dict[str, int]] = {}

    for doc_type in ("846", "850", "856", "810"):
        files = adapter._list_files(doc_type)
        records_synced = 0
        file_failures = 0

        for filepath in files:
            filename = filepath.split("/")[-1]
            raw = ""
            parsed_records = 0
            status = "failed"
            errors: list[str] = []
            try:
                raw = adapter._read_file(filepath)
                if doc_type == "846":
                    parsed_records = len(adapter.parser.parse_846(raw))
                elif doc_type == "856":
                    parsed_records = len(adapter.parser.parse_856(raw).items)
                elif doc_type == "810":
                    parsed_records = len(adapter.parser.parse_810(raw).line_items)
                elif doc_type == "850":
                    parsed_records = 1 if adapter.parser.detect_transaction_type(raw) == "850" else 0
                status = "processed" if parsed_records > 0 else "failed"
                if status == "processed":
                    adapter._archive_file(filepath)
                else:
                    errors.append("No parsable records found")
            except Exception as exc:
                errors.append(str(exc))

            if status != "processed":
                file_failures += 1
            records_synced += parsed_records

            db.add(
                EDITransactionLog(
                    customer_id=customer_id,
                    integration_id=integration_id,
                    document_type=doc_type,
                    direction="outbound" if doc_type == "850" else "inbound",
                    trading_partner_id=partner_id,
                    filename=filename,
                    raw_content=raw,
                    parsed_records=parsed_records,
                    errors=errors,
                    status=status,
                    processed_at=datetime.utcnow(),
                )
            )

        sync_status = "success"
        if file_failures > 0 and records_synced == 0:
            sync_status = "failed"
        elif file_failures > 0:
            sync_status = "partial"

        db.add(
            IntegrationSyncLog(
                customer_id=customer_id,
                integration_type="EDI",
                integration_name=f"EDI {doc_type}",
                sync_type=sync_type_map[doc_type],
                records_synced=records_synced,
                sync_status=sync_status,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        )
        summary[doc_type] = {
            "files": len(files),
            "records_synced": records_synced,
            "file_failures": file_failures,
        }

    await db.commit()
    return {"status": "success", "documents": summary}


async def run_sftp_sync_pipeline(db, *, customer_id: uuid.UUID, adapter) -> dict:
    """
    Worker-path SFTP orchestration with persisted sync-health records.
    """
    from db.models import IntegrationSyncLog

    started_at = datetime.utcnow()
    steps = [
        ("stores", adapter.sync_stores),
        ("products", adapter.sync_products),
        ("transactions", adapter.sync_transactions),
        ("inventory", adapter.sync_inventory),
    ]

    summary: dict[str, dict[str, int | str]] = {}
    for sync_type, runner in steps:
        result = await runner()
        db.add(
            IntegrationSyncLog(
                customer_id=customer_id,
                integration_type="SFTP",
                integration_name=f"SFTP {sync_type.title()}",
                sync_type=sync_type,
                records_synced=result.records_processed,
                sync_status=result.status.value,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                error_message="; ".join(result.errors) if result.errors else None,
                sync_metadata=result.metadata if result.metadata else None,
            )
        )
        summary[sync_type] = {
            "records_processed": result.records_processed,
            "records_failed": result.records_failed,
            "status": result.status.value,
        }

    await db.commit()
    return {"status": "success", "sources": summary}


@celery_app.task(
    name="workers.sync.sync_square_inventory",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def sync_square_inventory(self, customer_id: str):
    """
    Sync inventory data from Square for a customer.
    Scheduled via Celery Beat (every 15 minutes).

    Flow:
      1. Fetch integration record (access token, merchant ID)
      2. Init SquareClient
      3. Call get_inventory_counts() for all locations
      4. Upsert inventory_levels records
      5. Update last_sync_at
    """
    import asyncio

    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    run_id = self.request.id or "manual"
    logger.info("sync.inventory.started", customer_id=customer_id, run_id=run_id)

    async def _sync():
        from core.config import get_settings
        from db.models import Integration, InventoryLevel, Store
        from integrations.square import SquareClient

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                # Fetch integration record
                result = await db.execute(
                    select(Integration).where(
                        Integration.customer_id == customer_id,
                        Integration.provider == "square",
                        Integration.status == "connected",
                    )
                )
                integration = result.scalar_one_or_none()

                if not integration:
                    logger.warning("sync.inventory.no_integration", customer_id=customer_id)
                    return {"status": "skipped", "reason": "no_square_integration"}

                # Fetch store mappings (location_id → store_id)
                stores_result = await db.execute(select(Store).where(Store.customer_id == customer_id))
                stores = {str(s.store_id): s for s in stores_result.scalars().all()}

                if not stores:
                    logger.warning("sync.inventory.no_stores", customer_id=customer_id)
                    return {"status": "skipped", "reason": "no_stores"}

                # Init Square client and fetch counts
                client = SquareClient(integration.access_token_encrypted)
                location_ids = list(stores.keys())

                try:
                    counts = await client.get_inventory_counts(location_ids)
                except Exception as exc:
                    logger.error(
                        "sync.inventory.api_error",
                        customer_id=customer_id,
                        error=str(exc),
                    )
                    raise self.retry(exc=exc)

                # Upsert inventory levels
                upserted = 0
                now = datetime.now(timezone.utc)

                for count in counts:
                    location_id = count.get("location_id")
                    catalog_id = count.get("catalog_object_id", "unknown")
                    quantity = int(float(count.get("quantity", 0)))

                    if location_id not in stores:
                        continue

                    level = InventoryLevel(
                        id=uuid.uuid4(),
                        customer_id=customer_id,
                        store_id=location_id,
                        product_id=catalog_id,
                        timestamp=now,
                        quantity_on_hand=quantity,
                        quantity_available=quantity,
                        source="square_sync",
                    )
                    db.add(level)
                    upserted += 1

                # Update last_sync_at
                await db.execute(
                    update(Integration)
                    .where(Integration.integration_id == integration.integration_id)
                    .values(last_sync_at=now, updated_at=now)
                )

                await db.commit()

                logger.info(
                    "sync.inventory.completed",
                    customer_id=customer_id,
                    records_upserted=upserted,
                )

                return {
                    "status": "success",
                    "customer_id": customer_id,
                    "records_upserted": upserted,
                    "synced_at": now.isoformat(),
                }
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_sync())
    except Exception as exc:
        logger.error("sync.inventory.failed", customer_id=customer_id, error=str(exc))
        raise


@celery_app.task(
    name="workers.sync.sync_square_transactions",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def sync_square_transactions(self, customer_id: str):
    """
    Sync recent transactions from Square.
    Scheduled via Celery Beat (every 30 minutes).

    Flow:
      1. Fetch integration record
      2. Call get_orders() for recent orders
      3. Map to transactions table, dedup via external_id
      4. Update last_sync_at
    """
    import asyncio

    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    run_id = self.request.id or "manual"
    logger.info("sync.transactions.started", customer_id=customer_id, run_id=run_id)

    async def _sync():
        from core.config import get_settings
        from db.models import Integration, Transaction
        from integrations.square import SquareClient

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                # Fetch integration
                result = await db.execute(
                    select(Integration).where(
                        Integration.customer_id == customer_id,
                        Integration.provider == "square",
                        Integration.status == "connected",
                    )
                )
                integration = result.scalar_one_or_none()

                if not integration:
                    logger.warning("sync.transactions.no_integration", customer_id=customer_id)
                    return {"status": "skipped", "reason": "no_square_integration"}

                client = SquareClient(integration.access_token_encrypted)

                try:
                    orders = await client.get_orders(location_ids=[])
                except Exception as exc:
                    logger.error(
                        "sync.transactions.api_error",
                        customer_id=customer_id,
                        error=str(exc),
                    )
                    raise self.retry(exc=exc)

                # Dedup: find existing external_ids
                existing_ids_result = await db.execute(
                    select(Transaction.external_id).where(
                        Transaction.customer_id == customer_id,
                        Transaction.external_id.isnot(None),
                    )
                )
                existing_ids = {row[0] for row in existing_ids_result.all()}

                # Insert new transactions
                inserted = 0
                now = datetime.now(timezone.utc)

                for order in orders:
                    order_id = order.get("id", "")
                    location_id = order.get("location_id", "")

                    for item in order.get("line_items", []):
                        external_id = f"{order_id}:{item.get('uid', '')}"
                        if external_id in existing_ids:
                            continue

                        catalog_id = item.get("catalog_object_id", "unknown")
                        quantity = int(item.get("quantity", "1"))
                        unit_price = int(item.get("base_price_money", {}).get("amount", 0)) / 100
                        total = int(item.get("total_money", {}).get("amount", 0)) / 100
                        discount = int(item.get("total_discount_money", {}).get("amount", 0)) / 100

                        txn = Transaction(
                            transaction_id=uuid.uuid4(),
                            customer_id=customer_id,
                            store_id=location_id,
                            product_id=catalog_id,
                            timestamp=now,
                            quantity=quantity,
                            unit_price=unit_price,
                            total_amount=total,
                            discount_amount=discount,
                            transaction_type="sale",
                            external_id=external_id,
                        )
                        db.add(txn)
                        inserted += 1

                # Update last_sync_at
                await db.execute(
                    update(Integration)
                    .where(Integration.integration_id == integration.integration_id)
                    .values(last_sync_at=now, updated_at=now)
                )

                await db.commit()

                logger.info(
                    "sync.transactions.completed",
                    customer_id=customer_id,
                    transactions_inserted=inserted,
                    duplicates_skipped=len(existing_ids),
                )

                return {
                    "status": "success",
                    "customer_id": customer_id,
                    "transactions_inserted": inserted,
                    "synced_at": now.isoformat(),
                }
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_sync())
    except Exception as exc:
        logger.error("sync.transactions.failed", customer_id=customer_id, error=str(exc))
        raise


@celery_app.task(
    name="workers.sync.run_alert_check",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def run_alert_check(self, customer_id: str):
    """
    Run the alert engine after data sync to detect new stockouts / reorder needs.
    Called automatically after sync tasks complete.
    """
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    logger.info("alerts.check.started", customer_id=customer_id)

    async def _check():
        from alerts.engine import run_alert_pipeline
        from core.config import get_settings

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                result = await run_alert_pipeline(db, customer_id)
                logger.info("alerts.check.completed", customer_id=customer_id, **result)
                return result
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_check())
    except Exception as exc:
        logger.error("alerts.check.failed", customer_id=customer_id, error=str(exc))
        raise
