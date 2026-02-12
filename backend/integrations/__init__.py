"""
Integration adapters package.

Pluggable adapter pattern for connecting ShelfOps to any retail data source:
  - Square / Shopify / Clover  (SMB — REST API)
  - EDI X12                    (Enterprise — file-based)
  - SFTP batch files           (Enterprise — file-based)
  - Kafka / Pub/Sub            (Enterprise — event streaming)

Usage:
    from integrations.base import get_adapter, IntegrationType

    adapter = get_adapter(
        integration_type=IntegrationType.EDI,
        customer_id="...",
        config={"edi_input_dir": "/data/edi/inbound", ...},
    )
    result = await adapter.sync_inventory()
"""

from integrations.base import (
    IntegrationType,
    RetailIntegrationAdapter,
    SyncResult,
    SyncStatus,
    get_adapter,
    register_adapter,
)
from integrations.edi_adapter import EDIAdapter, EDIX12Parser
from integrations.event_adapter import EventStreamAdapter
from integrations.sftp_adapter import FlatFileParser, SFTPAdapter

__all__ = [
    "IntegrationType",
    "SyncResult",
    "SyncStatus",
    "RetailIntegrationAdapter",
    "get_adapter",
    "register_adapter",
    "EDIAdapter",
    "EDIX12Parser",
    "SFTPAdapter",
    "FlatFileParser",
    "EventStreamAdapter",
]
