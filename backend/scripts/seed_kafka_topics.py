"""
Kafka Topic Seeder — Publish synthetic POS and inventory events to Redpanda.

Generates deterministic synthetic events and publishes them to the two topics
consumed by EventStreamAdapter:
  - pos.transactions.completed  (transaction.completed events)
  - inventory.adjustments       (inventory.adjusted events)

Run:
  PYTHONPATH=backend python scripts/seed_kafka_topics.py
  PYTHONPATH=backend python scripts/seed_kafka_topics.py --transactions 200 --inventory 50
  PYTHONPATH=backend python scripts/seed_kafka_topics.py --bootstrap-servers broker:9092

Requires:
  aiokafka>=0.10.0  (listed in backend/requirements.txt)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

# ── Synthetic-data constants ──────────────────────────────────────────────────

STORES = [f"STORE_{n:03d}" for n in range(1, 6)]   # STORE_001 … STORE_005
REGISTERS = [f"POS_{n:02d}" for n in range(1, 6)]  # POS_01 … POS_05

PAYMENT_METHODS = ["credit_card", "debit_card", "cash", "mobile_pay"]
ADJUSTMENT_REASONS = ["cycle_count", "receiving", "damage", "transfer", "sale"]

# 20 realistic 12-digit GTINs (leading zero, numeric only)
_SKU_POOL = [
    f"0{random.randint(10_000_000_000, 99_999_999_999)}"
    for _ in range(20)
]

UNIT_PRICE_MIN = 1.99
UNIT_PRICE_MAX = 49.99

# Base timestamp: 30 days ago from a fixed reference so output is deterministic
_BASE_TS = datetime(2026, 1, 25, 0, 0, 0, tzinfo=timezone.utc)


# ── Event generators ──────────────────────────────────────────────────────────

def _iso(dt: datetime) -> str:
    """Format datetime as ISO-8601 UTC string matching consumer expectations."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_transaction_event(index: int) -> dict[str, Any]:
    """
    Build one transaction.completed event.

    SKUs, prices, and quantities are drawn from a seeded RNG so output
    is fully reproducible across runs.
    """
    num_items = random.randint(1, 8)
    items: list[dict[str, Any]] = []
    for _ in range(num_items):
        sku = random.choice(_SKU_POOL)
        qty = random.randint(1, 6)
        unit_price = round(random.uniform(UNIT_PRICE_MIN, UNIT_PRICE_MAX), 2)
        items.append(
            {
                "sku": sku,
                "quantity": qty,
                "unit_price": unit_price,
                "total": round(qty * unit_price, 2),
            }
        )

    total_amount = round(sum(it["total"] for it in items), 2)

    # Spread events across 30 days, distributed through store operating hours
    offset_seconds = random.randint(0, 30 * 24 * 3600 - 1)
    ts = _BASE_TS + timedelta(seconds=offset_seconds)
    # Skew toward operating hours 07:00–22:00; keep within that window
    ts = ts.replace(hour=(ts.hour % 15) + 7)

    return {
        "event_id": f"evt_{uuid.UUID(int=index + 0x1000).hex[-12:]}",
        "event_type": "transaction.completed",
        "store_id": random.choice(STORES),
        "timestamp": _iso(ts),
        "register_id": random.choice(REGISTERS),
        "items": items,
        "payment_method": random.choice(PAYMENT_METHODS),
        "total_amount": total_amount,
    }


def make_inventory_event(index: int) -> dict[str, Any]:
    """
    Build one inventory.adjusted event.

    Each event covers 1–4 SKUs, simulating a partial cycle count or
    receiving shipment for a subset of the assortment.
    """
    num_skus = random.randint(1, 4)
    items: list[dict[str, Any]] = []
    for _ in range(num_skus):
        items.append(
            {
                "sku": random.choice(_SKU_POOL),
                "quantity_on_hand": random.randint(0, 500),
                "quantity_on_order": random.randint(0, 200),
            }
        )

    # Inventory adjustments tend to happen in the morning before store open
    offset_days = random.randint(0, 29)
    ts = _BASE_TS + timedelta(days=offset_days, hours=random.randint(5, 8))

    return {
        "event_id": f"evt_{uuid.UUID(int=index + 0x9000).hex[-12:]}",
        "event_type": "inventory.adjusted",
        "store_id": random.choice(STORES),
        "timestamp": _iso(ts),
        "reason": random.choice(ADJUSTMENT_REASONS),
        "items": items,
    }


# ── Kafka producer ────────────────────────────────────────────────────────────

async def publish_events(
    bootstrap_servers: str,
    transactions_topic: str,
    inventory_topic: str,
    num_transactions: int,
    num_inventory: int,
) -> None:
    """
    Connect to Redpanda, generate synthetic events, and publish them.

    Raises SystemExit(1) on connection failure so callers get a non-zero
    exit code without an unhandled traceback.
    """
    try:
        from aiokafka import AIOKafkaProducer
    except ImportError:
        print("ERROR: aiokafka is not installed. Run: pip install aiokafka>=0.10.0")
        sys.exit(1)

    print(f"Connecting to Redpanda at {bootstrap_servers} ...")

    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        # Serialize values as UTF-8 JSON; keys are topic-prefixed UUIDs
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        # Wait for all in-sync replicas before acknowledging
        acks="all",
        # Compress in transit to reduce broker write amplification
        compression_type="gzip",
        request_timeout_ms=10_000,
        connections_max_idle_ms=30_000,
    )

    try:
        await producer.start()
    except Exception as exc:
        print(f"ERROR: Could not connect to Redpanda at {bootstrap_servers}: {exc}")
        sys.exit(1)

    wall_start = time.monotonic()

    try:
        # ── Publish transaction events ────────────────────────────────────
        print(f"Publishing {num_transactions} transaction events to '{transactions_topic}' ...")
        txn_published = 0
        for i in range(num_transactions):
            event = make_transaction_event(i)
            key = f"txn-{event['store_id']}-{i}"
            await producer.send(transactions_topic, value=event, key=key)
            txn_published += 1

        # ── Publish inventory adjustment events ──────────────────────────
        print(f"Publishing {num_inventory} inventory events to '{inventory_topic}' ...")
        inv_published = 0
        for i in range(num_inventory):
            event = make_inventory_event(i)
            key = f"inv-{event['store_id']}-{i}"
            await producer.send(inventory_topic, value=event, key=key)
            inv_published += 1

        # Flush ensures all buffered records are delivered before we report
        await producer.flush()

    except Exception as exc:
        print(f"ERROR: Failed while publishing events: {exc}")
        sys.exit(1)
    finally:
        await producer.stop()

    elapsed = time.monotonic() - wall_start

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("Kafka seed complete")
    print("=" * 60)
    print(f"  Bootstrap servers : {bootstrap_servers}")
    print(f"  Topics seeded     : {transactions_topic}, {inventory_topic}")
    print(f"  Transactions      : {txn_published} events published")
    print(f"  Inventory         : {inv_published} events published")
    print(f"  Total events      : {txn_published + inv_published}")
    print(f"  Time taken        : {elapsed:.2f}s")
    print("=" * 60)


# ── CLI entry point ───────────────────────────────────────────────────────────

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed Redpanda (Kafka-compatible) topics with synthetic ShelfOps events.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:9092",
        metavar="HOST:PORT",
        help="Redpanda/Kafka bootstrap server address",
    )
    parser.add_argument(
        "--transactions",
        type=int,
        default=100,
        metavar="N",
        help="Number of transaction.completed events to publish",
    )
    parser.add_argument(
        "--inventory",
        type=int,
        default=20,
        metavar="N",
        help="Number of inventory.adjusted events to publish",
    )
    parser.add_argument(
        "--transactions-topic",
        default="pos.transactions.completed",
        metavar="TOPIC",
        help="Kafka topic for POS transaction events",
    )
    parser.add_argument(
        "--inventory-topic",
        default="inventory.adjustments",
        metavar="TOPIC",
        help="Kafka topic for inventory adjustment events",
    )
    return parser.parse_args(argv)


# Public alias for backward compatibility
parse_args = _parse_args


def main() -> None:
    # Fix the RNG seed before generating the SKU pool and any event data so
    # that every run with the same arguments produces identical output.
    random.seed(42)

    # Re-populate the SKU pool now that the seed is fixed (the module-level
    # pool was built before seed(42) was called).
    global _SKU_POOL
    _SKU_POOL = [
        f"0{random.randint(10_000_000_000, 99_999_999_999)}"
        for _ in range(20)
    ]

    args = _parse_args()

    if args.transactions < 0:
        print("ERROR: --transactions must be >= 0")
        sys.exit(1)
    if args.inventory < 0:
        print("ERROR: --inventory must be >= 0")
        sys.exit(1)

    asyncio.run(
        publish_events(
            bootstrap_servers=args.bootstrap_servers,
            transactions_topic=args.transactions_topic,
            inventory_topic=args.inventory_topic,
            num_transactions=args.transactions,
            num_inventory=args.inventory,
        )
    )


if __name__ == "__main__":
    main()
