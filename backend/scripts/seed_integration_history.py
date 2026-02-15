#!/usr/bin/env python3
"""
Seed Integration Sync History — Populate sync log with realistic metadata.

Generates 30 days of sync metadata showing how ShelfOps would ingest data
from multiple enterprise sources:
  - Square POS: Every 15 min, ~1200 transaction records per sync
  - EDI 846: Daily 2:00 AM, ~7500 inventory records
  - SFTP CSV: Nightly 11:00 PM, ~500 product catalog updates
  - Kafka: Real-time, ~50 store transfer events/day

Includes 2-3 failures per month for realism (timeout, partial sync, reconnect).

NOTE: This is architecture demonstration — adapters are implemented and tested,
sync metadata simulated for demo purposes. Real enterprise data would flow
through the adapters in production.

Usage:
  python scripts/seed_integration_history.py
  python scripts/seed_integration_history.py --days 30

Requires: Database connection with integration_sync_log table (migration 006).
"""

import argparse
import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEV_CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Integration definitions with realistic sync patterns
INTEGRATIONS = [
    {
        "type": "POS",
        "name": "Square POS",
        "sync_type": "transactions",
        "interval_minutes": 15,
        "records_range": (800, 1600),
        "duration_range": (3, 12),  # seconds
        "failure_rate": 0.02,  # 2% failure
        "start_hour": 6,  # POS active 6 AM - 11 PM
        "end_hour": 23,
    },
    {
        "type": "EDI",
        "name": "EDI 846 Inventory",
        "sync_type": "inventory",
        "interval_minutes": 1440,  # Daily
        "fixed_hour": 2,  # 2:00 AM
        "records_range": (6500, 8500),
        "duration_range": (45, 120),  # seconds
        "failure_rate": 0.05,
    },
    {
        "type": "SFTP",
        "name": "SFTP Product Catalog",
        "sync_type": "products",
        "interval_minutes": 1440,
        "fixed_hour": 23,  # 11:00 PM
        "records_range": (350, 600),
        "duration_range": (15, 45),
        "failure_rate": 0.03,
    },
    {
        "type": "Kafka",
        "name": "Kafka Store Transfers",
        "sync_type": "transfers",
        "interval_minutes": 60,  # Hourly batches
        "records_range": (3, 12),
        "duration_range": (1, 3),
        "failure_rate": 0.01,
        "start_hour": 0,
        "end_hour": 24,
    },
]

FAILURE_REASONS = [
    "Connection timeout after 30s",
    "Authentication token expired",
    "Partial sync: 3 records failed validation",
    "SFTP host unreachable (DNS resolution failed)",
    "EDI document parse error: invalid ISA segment",
    "Kafka consumer lag exceeded threshold (5000 messages)",
    "Rate limit exceeded (429 Too Many Requests)",
    "SSL certificate verification failed",
]


def generate_sync_entries(days: int) -> list[dict]:
    """Generate realistic sync log entries for the given number of days."""
    entries = []
    now = datetime.utcnow()

    for day_offset in range(days, 0, -1):
        base_date = now - timedelta(days=day_offset)

        for integration in INTEGRATIONS:
            if integration["interval_minutes"] == 1440:
                # Daily sync at fixed hour
                hour = integration.get("fixed_hour", 2)
                sync_time = base_date.replace(hour=hour, minute=random.randint(0, 5), second=0, microsecond=0)
                entries.append(_create_entry(integration, sync_time))
            else:
                # Periodic sync throughout the day
                start_h = integration.get("start_hour", 0)
                end_h = integration.get("end_hour", 24)
                interval = integration["interval_minutes"]

                current = base_date.replace(hour=start_h, minute=0, second=0, microsecond=0)
                day_end = base_date.replace(hour=min(end_h, 23), minute=59, second=59, microsecond=0)

                while current <= day_end:
                    # Add some jitter (±2 min)
                    jitter = timedelta(minutes=random.uniform(-2, 2))
                    sync_time = current + jitter
                    entries.append(_create_entry(integration, sync_time))
                    current += timedelta(minutes=interval)

    return entries


def _create_entry(integration: dict, sync_time: datetime) -> dict:
    """Create a single sync log entry."""
    is_failure = random.random() < integration["failure_rate"]
    duration = random.uniform(*integration["duration_range"])
    records = random.randint(*integration["records_range"])

    if is_failure:
        is_partial = random.random() < 0.4  # 40% of failures are partial
        status = "partial" if is_partial else "failed"
        records = int(records * 0.3) if is_partial else 0
        error = random.choice(FAILURE_REASONS)
    else:
        status = "success"
        error = None

    completed_at = sync_time + timedelta(seconds=duration) if status != "failed" else None

    return {
        "sync_id": uuid.uuid4(),
        "customer_id": DEV_CUSTOMER_ID,
        "integration_type": integration["type"],
        "integration_name": integration["name"],
        "sync_type": integration["sync_type"],
        "records_synced": records,
        "sync_status": status,
        "started_at": sync_time,
        "completed_at": completed_at,
        "error_message": error,
        "sync_metadata": {
            "duration_sec": round(duration, 1),
            "batch_id": str(uuid.uuid4())[:8],
        },
    }


async def seed_to_database(entries: list[dict]) -> int:
    """Insert sync log entries into the database."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    try:
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        async with async_session() as db:
            # Set tenant context
            await db.execute(text(f"SET app.current_customer_id = '{DEV_CUSTOMER_ID}'"))

            for entry in entries:
                await db.execute(
                    text("""
                        INSERT INTO integration_sync_log
                        (sync_id, customer_id, integration_type, integration_name,
                         sync_type, records_synced, sync_status, started_at,
                         completed_at, error_message, sync_metadata)
                        VALUES (:sync_id, :customer_id, :integration_type, :integration_name,
                                :sync_type, :records_synced, :sync_status, :started_at,
                                :completed_at, :error_message, :sync_metadata::jsonb)
                    """),
                    {
                        **entry,
                        "sync_id": str(entry["sync_id"]),
                        "customer_id": str(entry["customer_id"]),
                        "sync_metadata": str(entry["sync_metadata"]).replace("'", '"'),
                    },
                )

            await db.commit()
            return len(entries)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Seed integration sync history")
    parser.add_argument("--days", type=int, default=30, help="Days of history (default: 30)")
    parser.add_argument("--db", action="store_true", help="Write to database (requires connection)")
    args = parser.parse_args()

    print("=" * 60)
    print("  ShelfOps Integration Sync History Seeder")
    print("=" * 60)
    print(f"  Days:     {args.days}")
    print(f"  Database: {'yes' if args.db else 'dry-run (print only)'}")
    print()

    entries = generate_sync_entries(args.days)

    # Summary
    by_type = {}
    by_status = {}
    for e in entries:
        by_type[e["integration_name"]] = by_type.get(e["integration_name"], 0) + 1
        by_status[e["sync_status"]] = by_status.get(e["sync_status"], 0) + 1

    print(f"  Generated {len(entries)} sync log entries:")
    print()
    print(f"  {'Integration':<25} {'Count':<8}")
    print(f"  {'-' * 25} {'-' * 8}")
    for name, count in sorted(by_type.items()):
        print(f"  {name:<25} {count:<8}")

    print()
    print(f"  {'Status':<15} {'Count':<8} {'%':<8}")
    print(f"  {'-' * 15} {'-' * 8} {'-' * 8}")
    for status, count in sorted(by_status.items()):
        pct = count / len(entries) * 100
        print(f"  {status:<15} {count:<8} {pct:<.1f}%")

    if args.db:
        print("\n  Writing to database...")
        count = asyncio.run(seed_to_database(entries))
        print(f"  Inserted {count} entries.")
    else:
        print("\n  Dry run — use --db to write to database.")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
