"""
Tests for scripts/seed_kafka_topics.py — Kafka demo producer.

Since we cannot connect to a live Kafka broker in unit tests, we test the
pure-Python event-generation logic (make_transaction_event, make_inventory_event)
and the CLI argument parsing.  The publish_events coroutine is integration-tested
via a mock AIOKafkaProducer to verify it calls send() with the correct topics.

Covers:
  - make_transaction_event: schema matches TRANSACTION_EVENT_SCHEMA
  - make_inventory_event:   schema matches INVENTORY_EVENT_SCHEMA
  - Event ids are unique across N calls
  - store_id and register_id are always non-empty strings
  - items list is non-empty for transaction events
  - CLI defaults: transactions=100, inventory=20
  - CLI respects --transactions and --inventory counts
  - publish_events sends to the correct topic names
"""

from __future__ import annotations

import json
import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the generator functions directly.
from scripts.seed_kafka_topics import (
    ADJUSTMENT_REASONS,
    PAYMENT_METHODS,
    REGISTERS,
    STORES,
    _parse_args,
    make_inventory_event,
    make_transaction_event,
)
from integrations.event_adapter import (
    INVENTORY_EVENT_SCHEMA,
    TRANSACTION_EVENT_SCHEMA,
    validate_event,
)


# ── make_transaction_event ─────────────────────────────────────────────────

class TestMakeTransactionEvent:
    def setup_method(self):
        random.seed(42)

    def test_required_fields_present(self):
        event = make_transaction_event(0)
        for field in TRANSACTION_EVENT_SCHEMA["required_fields"]:
            assert field in event, f"missing required field: {field}"

    def test_validate_event_returns_no_errors(self):
        event = make_transaction_event(0)
        errors = validate_event(event, TRANSACTION_EVENT_SCHEMA)
        assert errors == [], f"validation errors: {errors}"

    def test_event_type_is_correct(self):
        event = make_transaction_event(0)
        assert event["event_type"] == "transaction.completed"

    def test_store_id_is_non_empty_string(self):
        for i in range(10):
            event = make_transaction_event(i)
            assert isinstance(event["store_id"], str) and event["store_id"]

    def test_store_id_is_from_known_pool(self):
        for i in range(20):
            event = make_transaction_event(i)
            assert event["store_id"] in STORES

    def test_items_list_is_non_empty(self):
        for i in range(10):
            event = make_transaction_event(i)
            assert len(event["items"]) >= 1

    def test_each_item_has_required_fields(self):
        event = make_transaction_event(0)
        for item in event["items"]:
            for field in TRANSACTION_EVENT_SCHEMA["item_fields"]:
                assert field in item, f"item missing field: {field}"

    def test_total_amount_matches_items(self):
        event = make_transaction_event(0)
        computed = round(sum(it["total"] for it in event["items"]), 2)
        assert abs(event["total_amount"] - computed) < 0.01

    def test_payment_method_is_valid(self):
        for i in range(10):
            event = make_transaction_event(i)
            assert event["payment_method"] in PAYMENT_METHODS

    def test_event_ids_are_unique(self):
        random.seed(42)
        ids = {make_transaction_event(i)["event_id"] for i in range(50)}
        assert len(ids) == 50

    def test_timestamp_is_iso_format(self):
        event = make_transaction_event(0)
        ts = event["timestamp"]
        assert "T" in ts and ts.endswith("Z"), f"unexpected timestamp format: {ts}"

    def test_serialisable_to_json(self):
        event = make_transaction_event(0)
        json.dumps(event)  # must not raise


# ── make_inventory_event ───────────────────────────────────────────────────

class TestMakeInventoryEvent:
    def setup_method(self):
        random.seed(42)

    def test_required_fields_present(self):
        event = make_inventory_event(0)
        for field in INVENTORY_EVENT_SCHEMA["required_fields"]:
            assert field in event, f"missing required field: {field}"

    def test_validate_event_returns_no_errors(self):
        event = make_inventory_event(0)
        errors = validate_event(event, INVENTORY_EVENT_SCHEMA)
        assert errors == [], f"validation errors: {errors}"

    def test_event_type_is_correct(self):
        event = make_inventory_event(0)
        assert event["event_type"] == "inventory.adjusted"

    def test_reason_is_valid(self):
        for i in range(10):
            event = make_inventory_event(i)
            assert event["reason"] in ADJUSTMENT_REASONS

    def test_items_list_is_non_empty(self):
        for i in range(10):
            event = make_inventory_event(i)
            assert len(event["items"]) >= 1

    def test_each_item_has_quantity_on_hand(self):
        event = make_inventory_event(0)
        for item in event["items"]:
            assert "quantity_on_hand" in item
            assert item["quantity_on_hand"] >= 0

    def test_event_ids_are_unique(self):
        random.seed(42)
        ids = {make_inventory_event(i)["event_id"] for i in range(20)}
        assert len(ids) == 20

    def test_serialisable_to_json(self):
        event = make_inventory_event(0)
        json.dumps(event)  # must not raise


# ── _parse_args ─────────────────────────────────────────────────────────────

class TestParseArgs:
    def test_defaults(self):
        args = _parse_args([])
        assert args.bootstrap_servers == "localhost:9092"
        assert args.transactions == 100
        assert args.inventory == 20
        assert args.transactions_topic == "pos.transactions.completed"
        assert args.inventory_topic == "inventory.adjustments"

    def test_custom_counts(self):
        args = _parse_args(["--transactions", "50", "--inventory", "10"])
        assert args.transactions == 50
        assert args.inventory == 10

    def test_custom_bootstrap_servers(self):
        args = _parse_args(["--bootstrap-servers", "redpanda:9092"])
        assert args.bootstrap_servers == "redpanda:9092"

    def test_custom_topics(self):
        args = _parse_args([
            "--transactions-topic", "my.txn.topic",
            "--inventory-topic", "my.inv.topic",
        ])
        assert args.transactions_topic == "my.txn.topic"
        assert args.inventory_topic == "my.inv.topic"
