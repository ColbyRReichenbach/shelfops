"""
SFTP Batch File Integration Adapter

Enterprise retailers commonly exchange data via SFTP file drops:
  - Nightly inventory snapshots (CSV / fixed-width / XML)
  - Daily transaction extracts
  - Store master updates
  - Product catalog refreshes

Typical pattern at Target/Lowe's:
  1. Their system generates a flat file at 2 AM
  2. File is dropped on a shared SFTP server
  3. Our system polls the SFTP directory every 15 minutes
  4. Files are downloaded, parsed, validated, and loaded into the DB
  5. Processed files are moved to an archive directory

This adapter handles both SFTP transport and file parsing.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from integrations.base import (
    IntegrationType,
    RetailIntegrationAdapter,
    SyncResult,
    SyncStatus,
)

logger = structlog.get_logger()


# ── File format parsers ───────────────────────────────────────────────────


class FlatFileParser:
    """
    Parses common retail flat file formats into normalized dicts.

    Supported formats:
        - CSV (comma, tab, pipe delimited)
        - Fixed-width (column position-based)

    Each method returns a list of dicts with standardized field names
    ready for mapping to ShelfOps models.
    """

    @staticmethod
    def parse_csv(
        content: str,
        delimiter: str = ",",
        field_mapping: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Parse delimited text into records.

        Args:
            content: Raw file content
            delimiter: Column separator (comma, tab, pipe)
            field_mapping: Optional column rename map
                e.g. {"ITEM_NBR": "sku", "ON_HAND_QTY": "quantity_on_hand"}
        """
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        records = []

        for row in reader:
            if field_mapping:
                mapped = {}
                for src, dst in field_mapping.items():
                    if src in row:
                        mapped[dst] = row[src]
                records.append(mapped)
            else:
                records.append(dict(row))

        return records

    @staticmethod
    def parse_fixed_width(
        content: str,
        field_specs: list[tuple[str, int, int]],
    ) -> list[dict[str, Any]]:
        """
        Parse fixed-width format (common in legacy retail systems).

        Args:
            field_specs: List of (field_name, start_pos, end_pos)
                e.g. [("sku", 0, 12), ("qty", 12, 20), ("price", 20, 30)]
        """
        records = []
        lines = content.strip().split("\n")

        for line in lines:
            if not line.strip():
                continue
            record = {}
            for field_name, start, end in field_specs:
                record[field_name] = line[start:end].strip()
            records.append(record)

        return records


# ── Default field mappings for common retail file formats ──────────────────

DEFAULT_INVENTORY_MAPPING = {
    # Common column names → ShelfOps fields
    "ITEM_NBR": "sku",
    "ITEM_NUMBER": "sku",
    "SKU": "sku",
    "UPC": "upc",
    "GTIN": "gtin",
    "STORE_NBR": "store_code",
    "STORE_NUMBER": "store_code",
    "LOCATION_ID": "store_code",
    "ON_HAND_QTY": "quantity_on_hand",
    "QTY_ON_HAND": "quantity_on_hand",
    "ON_ORDER_QTY": "quantity_on_order",
    "QTY_ON_ORDER": "quantity_on_order",
    "SNAPSHOT_DATE": "as_of_date",
    "DATE": "as_of_date",
}

DEFAULT_TRANSACTION_MAPPING = {
    "TRANS_ID": "external_id",
    "TRANSACTION_ID": "external_id",
    "ITEM_NBR": "sku",
    "SKU": "sku",
    "STORE_NBR": "store_code",
    "STORE_NUMBER": "store_code",
    "QTY_SOLD": "quantity",
    "QUANTITY": "quantity",
    "UNIT_PRICE": "unit_price",
    "SALE_AMT": "total_amount",
    "TOTAL_AMOUNT": "total_amount",
    "TRANS_DATE": "timestamp",
    "SALE_DATE": "timestamp",
    "TRANS_TYPE": "transaction_type",
}

DEFAULT_PRODUCT_MAPPING = {
    "ITEM_NBR": "sku",
    "SKU": "sku",
    "UPC": "upc",
    "GTIN": "gtin",
    "ITEM_DESC": "name",
    "DESCRIPTION": "name",
    "PRODUCT_NAME": "name",
    "DEPT": "category",
    "CATEGORY": "category",
    "SUBCATEGORY": "subcategory",
    "BRAND": "brand",
    "UNIT_COST": "unit_cost",
    "UNIT_PRICE": "unit_price",
    "RETAIL_PRICE": "unit_price",
}

DEFAULT_STORE_MAPPING = {
    "STORE_NBR": "external_code",
    "STORE_NUMBER": "external_code",
    "LOCATION_ID": "external_code",
    "STORE_NAME": "name",
    "NAME": "name",
    "ADDRESS": "address",
    "CITY": "city",
    "STATE": "state",
    "ZIP": "zip_code",
    "ZIP_CODE": "zip_code",
    "LATITUDE": "lat",
    "LONGITUDE": "lon",
    "TIMEZONE": "timezone",
}


# ── SFTP Adapter ──────────────────────────────────────────────────────────


class SFTPAdapter(RetailIntegrationAdapter):
    """
    SFTP batch file integration adapter.

    Config expects:
        {
            "sftp_host": "sftp.retailer.com",
            "sftp_port": 22,
            "sftp_username": "shelfops_svc",
            "sftp_key_path": "/keys/retailer_rsa",
            "remote_dir": "/outbound/inventory",
            "local_staging_dir": "/data/sftp/staging",
            "archive_dir": "/data/sftp/archive",
            "file_format": "csv",
            "delimiter": ",",
            "file_patterns": {
                "inventory": "INV_SNAPSHOT_*.csv",
                "transactions": "DAILY_SALES_*.csv",
                "products": "ITEM_MASTER_*.csv",
                "stores": "STORE_MASTER_*.csv"
            },
            "field_mappings": {
                "inventory": {"ITEM_NBR": "sku", ...},
                "transactions": {"TRANS_ID": "external_id", ...}
            }
        }
    """

    @property
    def adapter_type(self) -> IntegrationType:
        return IntegrationType.SFTP

    def __init__(self, customer_id: str, config: dict[str, Any]):
        super().__init__(customer_id, config)
        self.sftp_host = config.get("sftp_host", "localhost")
        self.sftp_port = config.get("sftp_port", 22)
        self.sftp_username = config.get("sftp_username", "")
        self.sftp_key_path = config.get("sftp_key_path", "")
        self.remote_dir = config.get("remote_dir", "/outbound")
        self.local_staging = config.get("local_staging_dir", "/data/sftp/staging")
        self.archive_dir = config.get("archive_dir", "/data/sftp/archive")
        self.file_format = config.get("file_format", "csv")
        self.delimiter = config.get("delimiter", ",")
        self.file_patterns = config.get("file_patterns", {})
        self.field_mappings = config.get("field_mappings", {})
        self.parser = FlatFileParser()

    async def test_connection(self) -> bool:
        """Test SFTP connectivity."""
        try:
            import asyncssh

            async with asyncssh.connect(
                self.sftp_host,
                port=self.sftp_port,
                username=self.sftp_username,
                client_keys=[self.sftp_key_path] if self.sftp_key_path else [],
                known_hosts=None,
            ) as conn:
                async with conn.start_sftp_client() as sftp:
                    await sftp.listdir(self.remote_dir)
                    return True
        except Exception as e:
            self.logger.error("sftp_connection_failed", error=str(e))
            return False

    async def sync_stores(self) -> SyncResult:
        """Download and parse store master file."""
        return await self._sync_file_type(
            "stores",
            DEFAULT_STORE_MAPPING,
        )

    async def sync_products(self) -> SyncResult:
        """Download and parse product catalog file."""
        return await self._sync_file_type(
            "products",
            DEFAULT_PRODUCT_MAPPING,
        )

    async def sync_transactions(self, since: datetime | None = None) -> SyncResult:
        """Download and parse daily transaction files."""
        return await self._sync_file_type(
            "transactions",
            DEFAULT_TRANSACTION_MAPPING,
        )

    async def sync_inventory(self) -> SyncResult:
        """Download and parse inventory snapshot files."""
        return await self._sync_file_type(
            "inventory",
            DEFAULT_INVENTORY_MAPPING,
        )

    async def _sync_file_type(
        self,
        file_type: str,
        default_mapping: dict[str, str],
    ) -> SyncResult:
        """
        Generic file sync: download matching files, parse, return records.
        """
        result = SyncResult(status=SyncStatus.SUCCESS)
        mapping = self.field_mappings.get(file_type, default_mapping)

        # In production, we'd actually SFTP download. In dev, read from staging.
        staging_path = Path(self.local_staging) / file_type
        if not staging_path.exists():
            self.logger.info("no_files_found", file_type=file_type, path=str(staging_path))
            return SyncResult(status=SyncStatus.NO_DATA).complete()

        for filepath in sorted(staging_path.glob("*")):
            if filepath.is_dir():
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
                records = self.parser.parse_csv(
                    content,
                    delimiter=self.delimiter,
                    field_mapping=mapping,
                )
                result.records_processed += len(records)
                result.metadata.setdefault("records", []).extend(records)

                # Archive processed file
                archive_path = Path(self.archive_dir) / file_type
                archive_path.mkdir(parents=True, exist_ok=True)
                filepath.rename(archive_path / filepath.name)

            except Exception as e:
                result.records_failed += 1
                result.errors.append(f"{filepath.name}: {str(e)}")

        if result.records_failed > 0 and result.records_processed == 0:
            result.status = SyncStatus.FAILED
        elif result.records_failed > 0:
            result.status = SyncStatus.PARTIAL

        return result.complete()
