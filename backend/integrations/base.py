"""
Retail Integration Adapter — Abstract Base Class

All data connectors (EDI, SFTP, Kafka, Square, Shopify) implement
this interface so the rest of the platform is source-agnostic.

The adapter pattern lets ShelfOps plug in to any retailer's tech
stack — from SMB POS systems to Fortune 500 EDI pipelines — without
changing business logic, ML models, or the dashboard.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


# ── Integration types ──────────────────────────────────────────────────────


class IntegrationType(str, Enum):
    """Supported integration protocols."""

    EDI = "edi"  # EDI X12 flat files (enterprise)
    SFTP = "sftp"  # Batch file ingestion (enterprise)
    EVENT_STREAM = "event_stream"  # Kafka / Pub/Sub (modern enterprise)
    REST_API = "rest_api"  # Square, Shopify, etc. (SMB)


class SyncStatus(str, Enum):
    """Result status of a sync operation."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Some records synced, some failed
    FAILED = "failed"
    NO_DATA = "no_data"


# ── Sync result container ─────────────────────────────────────────────────


@dataclass
class SyncResult:
    """Standardized return from every adapter sync method."""

    status: SyncStatus
    records_processed: int = 0
    records_failed: int = 0
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    def complete(self) -> "SyncResult":
        self.completed_at = datetime.utcnow()
        return self


# ── Abstract adapter ──────────────────────────────────────────────────────


class RetailIntegrationAdapter(ABC):
    """
    Base class for all retail data connectors.

    Every adapter must implement these methods so the sync worker
    can call them uniformly, regardless of whether the source is a
    Square REST API, an EDI 846 flat file, or a Kafka topic.

    Lifecycle:
        1. __init__(integration_config)  — load credentials / config
        2. test_connection()             — validate connectivity
        3. sync_stores()                 — import store/location data
        4. sync_products()               — import product catalog (GTINs)
        5. sync_transactions()           — import POS sales data
        6. sync_inventory()              — import current stock levels
        7. get_status()                  — report connector health
    """

    def __init__(self, customer_id: str, config: dict[str, Any]):
        self.customer_id = customer_id
        self.config = config
        self.logger = logger.bind(
            adapter=self.adapter_type.value,
            customer_id=customer_id,
        )

    @property
    @abstractmethod
    def adapter_type(self) -> IntegrationType:
        """Return the integration type this adapter handles."""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Validate that the adapter can reach the data source."""
        ...

    @abstractmethod
    async def sync_stores(self) -> SyncResult:
        """Import store / location master data."""
        ...

    @abstractmethod
    async def sync_products(self) -> SyncResult:
        """Import product catalog (SKUs, GTINs, categories)."""
        ...

    @abstractmethod
    async def sync_transactions(self, since: datetime | None = None) -> SyncResult:
        """Import sales transactions. Optionally incremental from `since`."""
        ...

    @abstractmethod
    async def sync_inventory(self) -> SyncResult:
        """Import current inventory levels per store/product."""
        ...

    async def get_status(self) -> dict[str, Any]:
        """Report health and last-sync metadata."""
        connected = await self.test_connection()
        return {
            "adapter_type": self.adapter_type.value,
            "customer_id": self.customer_id,
            "connected": connected,
            "checked_at": datetime.utcnow().isoformat(),
        }


# ── Adapter registry ──────────────────────────────────────────────────────

_ADAPTER_REGISTRY: dict[IntegrationType, type[RetailIntegrationAdapter]] = {}


def register_adapter(adapter_cls: type[RetailIntegrationAdapter]):
    """Decorator: register an adapter class for its integration type."""
    _ADAPTER_REGISTRY[adapter_cls.adapter_type.fget(None)] = adapter_cls  # type: ignore
    return adapter_cls


def get_adapter(
    integration_type: IntegrationType,
    customer_id: str,
    config: dict[str, Any],
) -> RetailIntegrationAdapter:
    """Factory: return the right adapter instance for the given type."""
    adapter_cls = _ADAPTER_REGISTRY.get(integration_type)
    if adapter_cls is None:
        raise ValueError(f"No adapter registered for integration type: {integration_type.value}")
    return adapter_cls(customer_id=customer_id, config=config)
