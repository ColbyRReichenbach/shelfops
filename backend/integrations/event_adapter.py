"""
Event Stream Integration Adapter (Kafka / Google Pub/Sub)

Modern enterprise retailers are moving from nightly batch files
toward real-time event streaming for POS transactions, inventory
updates, and supply chain events.

Architecture:
    POS Terminal → Kafka Topic → ShelfOps Consumer → Database
                                                   → Alert Engine
                                                   → ML Pipeline

This adapter consumes events from Kafka (or Google Pub/Sub) and
normalizes them into ShelfOps records.

Event schemas follow retail industry conventions:
    - transaction.completed  → transactions table
    - inventory.adjusted     → inventory_levels table
    - product.updated        → products table
    - shipment.received      → purchase_orders table
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import structlog

from integrations.base import (
    IntegrationType,
    RetailIntegrationAdapter,
    SyncResult,
    SyncStatus,
)

logger = structlog.get_logger()


# ── Event schema definitions ──────────────────────────────────────────────

TRANSACTION_EVENT_SCHEMA = {
    "required_fields": ["event_id", "store_id", "timestamp", "items"],
    "item_fields": ["sku", "quantity", "unit_price", "total"],
}

INVENTORY_EVENT_SCHEMA = {
    "required_fields": ["event_id", "store_id", "timestamp", "items"],
    "item_fields": ["sku", "quantity_on_hand"],
}


def validate_event(event: dict[str, Any], schema: dict) -> list[str]:
    """Validate an event against its schema, returning list of errors."""
    errors = []
    for field in schema["required_fields"]:
        if field not in event:
            errors.append(f"Missing required field: {field}")
    return errors


def normalize_transaction_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Normalize a POS transaction event into ShelfOps transaction records.

    Input (Kafka event):
        {
            "event_id": "evt_12345",
            "event_type": "transaction.completed",
            "store_id": "STORE_042",
            "timestamp": "2024-01-15T14:23:45Z",
            "register_id": "POS_03",
            "items": [
                {"sku": "012345678901", "quantity": 2, "unit_price": 4.99, "total": 9.98},
                {"sku": "012345678902", "quantity": 1, "unit_price": 12.50, "total": 12.50}
            ],
            "payment_method": "credit_card",
            "total_amount": 22.48
        }

    Output: list of ShelfOps-normalized transaction dicts
    """
    records = []
    for item in event.get("items", []):
        records.append(
            {
                "external_id": event.get("event_id", ""),
                "store_code": event.get("store_id", ""),
                "sku": item.get("sku", ""),
                "quantity": item.get("quantity", 0),
                "unit_price": item.get("unit_price", 0.0),
                "total_amount": item.get("total", 0.0),
                "transaction_type": "sale",
                "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
            }
        )
    return records


def normalize_inventory_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Normalize an inventory adjustment event.

    Input (Kafka event):
        {
            "event_id": "evt_67890",
            "event_type": "inventory.adjusted",
            "store_id": "STORE_042",
            "timestamp": "2024-01-15T06:00:00Z",
            "reason": "cycle_count",
            "items": [
                {"sku": "012345678901", "quantity_on_hand": 45, "quantity_on_order": 100}
            ]
        }
    """
    records = []
    for item in event.get("items", []):
        records.append(
            {
                "store_code": event.get("store_id", ""),
                "sku": item.get("sku", ""),
                "quantity_on_hand": item.get("quantity_on_hand", 0),
                "quantity_on_order": item.get("quantity_on_order", 0),
                "source": f"event_{event.get('reason', 'unknown')}",
                "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
            }
        )
    return records


# ── Event Stream Adapter ──────────────────────────────────────────────────


class EventStreamAdapter(RetailIntegrationAdapter):
    """
    Real-time event streaming adapter (Kafka / Pub/Sub).

    Config expects:
        {
            "broker_type": "kafka",             # or "pubsub"
            "bootstrap_servers": "localhost:9092",
            "topics": {
                "transactions": "pos.transactions.completed",
                "inventory": "inventory.adjustments",
                "products": "catalog.updates"
            },
            "consumer_group": "shelfops-ingest",
            "schema_registry_url": "http://localhost:8081",
            "auto_offset_reset": "earliest",
            "max_poll_records": 500,

            # For Google Pub/Sub:
            "gcp_project_id": "retail-project",
            "subscriptions": {
                "transactions": "shelfops-transactions-sub",
                "inventory": "shelfops-inventory-sub"
            }
        }
    """

    @property
    def adapter_type(self) -> IntegrationType:
        return IntegrationType.EVENT_STREAM

    def __init__(self, customer_id: str, config: dict[str, Any]):
        super().__init__(customer_id, config)
        self.broker_type = config.get("broker_type", "kafka")
        self.bootstrap_servers = config.get("bootstrap_servers", "localhost:9092")
        self.topics = config.get("topics", {})
        self.consumer_group = config.get("consumer_group", "shelfops-ingest")
        self.max_poll_records = config.get("max_poll_records", 500)

    async def test_connection(self) -> bool:
        """Test Kafka/Pub/Sub connectivity."""
        if self.broker_type == "kafka":
            return await self._test_kafka()
        elif self.broker_type == "pubsub":
            return await self._test_pubsub()
        return False

    async def _test_kafka(self) -> bool:
        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                group_id=f"{self.consumer_group}-healthcheck",
            )
            await consumer.start()
            topics = await consumer.topics()
            await consumer.stop()
            self.logger.info("kafka_connected", topics=list(topics))
            return True
        except Exception as e:
            self.logger.error("kafka_connection_failed", error=str(e))
            return False

    async def _test_pubsub(self) -> bool:
        try:
            from google.cloud import pubsub_v1

            subscriber = pubsub_v1.SubscriberClient()
            project_id = self.config.get("gcp_project_id", "")
            # Just test that we can list subscriptions
            project_path = f"projects/{project_id}"
            list(subscriber.list_subscriptions(request={"project": project_path}))
            return True
        except Exception as e:
            self.logger.error("pubsub_connection_failed", error=str(e))
            return False

    async def sync_stores(self) -> SyncResult:
        """Store data typically isn't streamed — use SFTP adapter."""
        return SyncResult(status=SyncStatus.NO_DATA).complete()

    async def sync_products(self) -> SyncResult:
        """Consume product catalog update events."""
        topic = self.topics.get("products")
        if not topic:
            return SyncResult(status=SyncStatus.NO_DATA).complete()

        return await self._consume_topic(
            topic=topic,
            normalizer=lambda e: [e.get("product", {})],
            label="products",
        )

    async def sync_transactions(self, since: datetime | None = None) -> SyncResult:
        """Consume POS transaction events in real time."""
        topic = self.topics.get("transactions")
        if not topic:
            return SyncResult(status=SyncStatus.NO_DATA).complete()

        return await self._consume_topic(
            topic=topic,
            normalizer=normalize_transaction_event,
            label="transactions",
        )

    async def sync_inventory(self) -> SyncResult:
        """Consume inventory adjustment events."""
        topic = self.topics.get("inventory")
        if not topic:
            return SyncResult(status=SyncStatus.NO_DATA).complete()

        return await self._consume_topic(
            topic=topic,
            normalizer=normalize_inventory_event,
            label="inventory",
        )

    async def _consume_topic(
        self,
        topic: str,
        normalizer,
        label: str,
    ) -> SyncResult:
        """
        Consume up to max_poll_records from a Kafka topic,
        normalize each event, and return as a SyncResult.
        """
        result = SyncResult(status=SyncStatus.SUCCESS)

        if self.broker_type == "kafka":
            try:
                from aiokafka import AIOKafkaConsumer

                consumer = AIOKafkaConsumer(
                    topic,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=self.consumer_group,
                    auto_offset_reset=self.config.get("auto_offset_reset", "earliest"),
                    enable_auto_commit=True,
                    max_poll_records=self.max_poll_records,
                    consumer_timeout_ms=5000,
                )
                await consumer.start()

                try:
                    batch = await consumer.getmany(timeout_ms=5000)
                    for tp, messages in batch.items():
                        for msg in messages:
                            try:
                                event = json.loads(msg.value.decode("utf-8"))
                                records = normalizer(event)
                                result.records_processed += len(records)
                                result.metadata.setdefault(label, []).extend(records)
                            except Exception as e:
                                result.records_failed += 1
                                result.errors.append(f"offset={msg.offset}: {str(e)}")
                finally:
                    await consumer.stop()

            except ImportError:
                result.status = SyncStatus.FAILED
                result.errors.append("aiokafka not installed")
            except Exception as e:
                result.status = SyncStatus.FAILED
                result.errors.append(str(e))

        elif self.broker_type == "pubsub":
            try:
                from google.cloud import pubsub_v1

                subscriber = pubsub_v1.SubscriberClient()
                subscription = self.config.get("subscriptions", {}).get(label)
                if not subscription:
                    return SyncResult(status=SyncStatus.NO_DATA).complete()

                project_id = self.config.get("gcp_project_id", "")
                sub_path = subscriber.subscription_path(project_id, subscription)

                response = subscriber.pull(
                    request={"subscription": sub_path, "max_messages": self.max_poll_records},
                    timeout=10,
                )
                ack_ids = []
                for msg in response.received_messages:
                    try:
                        event = json.loads(msg.message.data.decode("utf-8"))
                        records = normalizer(event)
                        result.records_processed += len(records)
                        result.metadata.setdefault(label, []).extend(records)
                        ack_ids.append(msg.ack_id)
                    except Exception as e:
                        result.records_failed += 1
                        result.errors.append(str(e))

                if ack_ids:
                    subscriber.acknowledge(request={"subscription": sub_path, "ack_ids": ack_ids})

            except ImportError:
                result.status = SyncStatus.FAILED
                result.errors.append("google-cloud-pubsub not installed")
            except Exception as e:
                result.status = SyncStatus.FAILED
                result.errors.append(str(e))

        return result.complete()
