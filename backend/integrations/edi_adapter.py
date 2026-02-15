"""
EDI X12 Integration Adapter

Parses and generates EDI X12 documents used by enterprise retailers
like Target, Lowe's, Walmart, and their trading partners.

Supported document types:
  - EDI 846  Inventory Inquiry/Advice   (inbound  → inventory_levels)
  - EDI 856  Advance Ship Notice        (inbound  → purchase_orders)
  - EDI 810  Invoice                    (inbound  → financial reconciliation)
  - EDI 850  Purchase Order             (outbound → generated from AI recommendations)

How enterprise retail actually works:
  1. Retailer drops EDI files on an SFTP server (or sends via AS2)
  2. We poll the directory and pick up new files on a schedule
  3. Files are parsed, validated, and loaded into the database
  4. Every document is logged in edi_transaction_log for audit compliance

This module handles the PARSING logic.  File transport is handled by
sftp_adapter.py (polling) or event_adapter.py (streaming).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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

# ── EDI X12 Segment Delimiter ─────────────────────────────────────────────
# Standard X12 uses ~ as segment terminator,  * as element separator
SEGMENT_TERMINATOR = "~"
ELEMENT_SEPARATOR = "*"


# ── Parsed document containers ────────────────────────────────────────────


@dataclass
class EDI846Item:
    """Single inventory line from an EDI 846 document."""

    gtin: str  # GS1 Global Trade Item Number
    upc: str = ""  # Universal Product Code (subset of GTIN)
    quantity_on_hand: int = 0
    quantity_on_order: int = 0
    warehouse_id: str = ""  # Retailer's internal location code
    unit_of_measure: str = "EA"  # EA=each, CS=case, PL=pallet
    as_of_date: datetime | None = None


@dataclass
class EDI856Shipment:
    """Parsed ASN (Advance Ship Notice) from EDI 856."""

    shipment_id: str
    ship_date: datetime | None = None
    expected_delivery: datetime | None = None
    carrier: str = ""
    tracking_number: str = ""
    items: list[dict[str, Any]] = field(default_factory=list)
    # Each item: {gtin, quantity, po_number, lot_number}


@dataclass
class EDI810Invoice:
    """Parsed invoice from EDI 810."""

    invoice_number: str
    invoice_date: datetime | None = None
    po_number: str = ""
    total_amount: float = 0.0
    line_items: list[dict[str, Any]] = field(default_factory=list)
    # Each line: {gtin, quantity, unit_price, line_total}


# ── EDI X12 Parser ────────────────────────────────────────────────────────


class EDIX12Parser:
    """
    Parses raw EDI X12 documents into structured data.

    X12 format overview:
        ISA*...*~         ← Interchange header
        GS*...*~          ← Functional group header
        ST*846*0001~      ← Transaction set header (846 = Inventory)
        ...segments...
        SE*...*~          ← Transaction set trailer
        GE*...*~          ← Functional group trailer
        IEA*...*~         ← Interchange trailer

    We extract the transaction type from the ST segment, then
    dispatch to the appropriate parser method.
    """

    @staticmethod
    def detect_transaction_type(raw: str) -> str | None:
        """Extract the EDI document type (846, 856, 810, 850) from ST segment."""
        segments = EDIX12Parser._split_segments(raw)
        for seg in segments:
            elements = seg.split(ELEMENT_SEPARATOR)
            if elements[0].strip() == "ST" and len(elements) >= 2:
                return elements[1].strip()
        return None

    @staticmethod
    def _extract_id_value_pairs(elements: list[str]) -> list[tuple[str, str]]:
        """
        Extract qualifier/value token pairs from an X12 segment.

        Many real docs include sequence numbers before qualifiers (e.g.
        `LIN*1*UP*...*IN*...`). This helper scans adjacent tokens so parsers
        can handle both numbered and unnumbered variants.
        """
        pairs: list[tuple[str, str]] = []
        for idx in range(1, len(elements) - 1):
            qualifier = elements[idx].strip()
            value = elements[idx + 1].strip()
            if qualifier and value:
                pairs.append((qualifier, value))
        return pairs

    @staticmethod
    def parse_846(raw: str) -> list[EDI846Item]:
        """
        Parse EDI 846 — Inventory Inquiry/Advice.

        Relevant segments:
            LIN — Item identification (GTIN/UPC)
            QTY — Quantity information
            DTM — Date/time reference
            N1  — Party identification (warehouse)
        """
        segments = EDIX12Parser._split_segments(raw)
        items: list[EDI846Item] = []
        current_item: dict[str, Any] = {}

        for seg in segments:
            elements = seg.split(ELEMENT_SEPARATOR)
            seg_id = elements[0].strip()

            if seg_id == "LIN" and len(elements) >= 4:
                # If we were building an item, save it
                if current_item.get("gtin"):
                    items.append(EDI846Item(**current_item))
                # Start a new item
                # LIN*1*UP*012345678901*IN*GTIN14DIGIT~
                current_item = {"gtin": "", "upc": ""}
                for qualifier, value in EDIX12Parser._extract_id_value_pairs(elements):
                    if qualifier == "UP":
                        current_item["upc"] = value
                        if not current_item["gtin"]:
                            current_item["gtin"] = value
                    elif qualifier == "IN":
                        current_item["gtin"] = value

            elif seg_id == "QTY" and len(elements) >= 3:
                # QTY*33*500*EA~  (33=On Hand, 02=On Order)
                qualifier = elements[1].strip()
                qty = int(float(elements[2].strip()))
                if qualifier == "33":
                    current_item["quantity_on_hand"] = qty
                elif qualifier == "02":
                    current_item["quantity_on_order"] = qty
                if len(elements) >= 4:
                    current_item["unit_of_measure"] = elements[3].strip()

            elif seg_id == "DTM" and len(elements) >= 3:
                # DTM*405*20240115~  (405=as-of date)
                date_str = elements[2].strip()
                if len(date_str) == 8:
                    try:
                        current_item["as_of_date"] = datetime.strptime(date_str, "%Y%m%d")
                    except ValueError:
                        pass

            elif seg_id == "N1" and len(elements) >= 3:
                # N1*WH*WarehouseName*92*WH001~  (WH=warehouse)
                if elements[1].strip() == "WH" and len(elements) >= 5:
                    current_item["warehouse_id"] = elements[4].strip()

        # Don't forget the last item
        if current_item.get("gtin"):
            items.append(EDI846Item(**current_item))

        return items

    @staticmethod
    def parse_856(raw: str) -> EDI856Shipment:
        """
        Parse EDI 856 — Advance Ship Notice.

        Hierarchical format:
            BSN — Beginning segment (shipment ID, date)
            HL  — Hierarchy levels (shipment → order → item)
            TD5 — Carrier/routing
            REF — Reference numbers (tracking, PO)
            LIN — Item identification
            SN1 — Item quantity
        """
        segments = EDIX12Parser._split_segments(raw)
        shipment = EDI856Shipment(shipment_id="")
        current_item: dict[str, Any] = {}

        for seg in segments:
            elements = seg.split(ELEMENT_SEPARATOR)
            seg_id = elements[0].strip()

            if seg_id == "BSN" and len(elements) >= 4:
                shipment.shipment_id = elements[2].strip()
                date_str = elements[3].strip()
                if len(date_str) == 8:
                    try:
                        shipment.ship_date = datetime.strptime(date_str, "%Y%m%d")
                    except ValueError:
                        pass

            elif seg_id == "TD5" and len(elements) >= 5:
                shipment.carrier = elements[3].strip()

            elif seg_id == "REF" and len(elements) >= 3:
                qualifier = elements[1].strip()
                if qualifier == "CN":
                    shipment.tracking_number = elements[2].strip()
                elif qualifier == "PO":
                    current_item["po_number"] = elements[2].strip()

            elif seg_id == "LIN" and len(elements) >= 4:
                if current_item.get("gtin"):
                    shipment.items.append(current_item)
                current_item = {}
                for qualifier, value in EDIX12Parser._extract_id_value_pairs(elements):
                    if qualifier in ("UP", "IN"):
                        current_item["gtin"] = value

            elif seg_id == "SN1" and len(elements) >= 4:
                current_item["quantity"] = int(float(elements[2].strip()))

            elif seg_id == "DTM" and len(elements) >= 3:
                qualifier = elements[1].strip()
                date_str = elements[2].strip()
                if qualifier == "017" and len(date_str) == 8:
                    try:
                        shipment.expected_delivery = datetime.strptime(date_str, "%Y%m%d")
                    except ValueError:
                        pass

        if current_item.get("gtin"):
            shipment.items.append(current_item)

        return shipment

    @staticmethod
    def parse_810(raw: str) -> EDI810Invoice:
        """Parse EDI 810 — Invoice."""
        segments = EDIX12Parser._split_segments(raw)
        invoice = EDI810Invoice(invoice_number="")
        current_line: dict[str, Any] = {}

        for seg in segments:
            elements = seg.split(ELEMENT_SEPARATOR)
            seg_id = elements[0].strip()

            if seg_id == "BIG" and len(elements) >= 4:
                date_str = elements[1].strip()
                invoice.invoice_number = elements[2].strip()
                if len(date_str) == 8:
                    try:
                        invoice.invoice_date = datetime.strptime(date_str, "%Y%m%d")
                    except ValueError:
                        pass
                if len(elements) >= 5:
                    invoice.po_number = elements[4].strip()

            elif seg_id == "IT1" and len(elements) >= 7:
                if current_line.get("gtin"):
                    invoice.line_items.append(current_line)
                qty = int(float(elements[2].strip())) if len(elements) > 2 else 0
                unit_price = float(elements[4].strip()) if len(elements) > 4 else 0.0
                current_line = {
                    "quantity": qty,
                    "unit_price": unit_price,
                    "line_total": qty * unit_price,
                }
                for qualifier, value in EDIX12Parser._extract_id_value_pairs(elements):
                    if qualifier in ("UP", "IN"):
                        current_line["gtin"] = value

            elif seg_id == "TDS" and len(elements) >= 2:
                # Total dollar amount in cents
                invoice.total_amount = float(elements[1].strip()) / 100

        if current_line.get("gtin"):
            invoice.line_items.append(current_line)

        return invoice

    @staticmethod
    def generate_850(
        po_number: str,
        vendor_id: str,
        items: list[dict[str, Any]],
        ship_to: dict[str, str] | None = None,
    ) -> str:
        """
        Generate EDI 850 — Purchase Order.

        This is what ShelfOps produces when the AI recommends a reorder
        and the planner clicks "Approve".

        Args:
            po_number: Internal PO reference
            vendor_id: Supplier/vendor identifier
            items: List of {gtin, quantity, unit_price, uom}
            ship_to: Optional {name, address, city, state, zip}
        """
        now = datetime.utcnow()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M")

        segments = [
            f"ISA*00*          *00*          *ZZ*SHELFOPS       *ZZ*{vendor_id:<15}*{now.strftime('%y%m%d')}*{time_str}*U*00401*000000001*0*P*>",
            f"GS*PO*SHELFOPS*{vendor_id}*{date_str}*{time_str}*1*X*004010",
            "ST*850*0001",
            f"BEG*00*NE*{po_number}**{date_str}",
        ]

        if ship_to:
            segments.append(f"N1*ST*{ship_to.get('name', '')}*92*{ship_to.get('id', '')}")
            segments.append(f"N3*{ship_to.get('address', '')}")
            segments.append(f"N4*{ship_to.get('city', '')}*{ship_to.get('state', '')}*{ship_to.get('zip', '')}")

        seg_count = len(segments)
        for i, item in enumerate(items, start=1):
            gtin = item.get("gtin", "")
            qty = item.get("quantity", 0)
            price = item.get("unit_price", 0.0)
            uom = item.get("uom", "EA")
            segments.append(f"PO1*{i}*{qty}*{uom}*{price:.2f}*PE*IN*{gtin}")
            seg_count += 1

        seg_count += 4  # ST + SE + GE + IEA
        segments.append(f"SE*{seg_count}*0001")
        segments.append("GE*1*1")
        segments.append("IEA*1*000000001")

        return SEGMENT_TERMINATOR.join(segments) + SEGMENT_TERMINATOR

    @staticmethod
    def _split_segments(raw: str) -> list[str]:
        """Split raw EDI into segments, handling various line endings."""
        # Remove line breaks (some systems add them for readability)
        cleaned = re.sub(r"[\r\n]+", "", raw.strip())
        segments = [s.strip() for s in cleaned.split(SEGMENT_TERMINATOR) if s.strip()]
        return segments


# ── EDI Adapter (implements RetailIntegrationAdapter) ──────────────────────


class EDIAdapter(RetailIntegrationAdapter):
    """
    Enterprise EDI X12 integration adapter.

    Config expects:
        {
            "edi_input_dir": "/data/edi/inbound",
            "edi_output_dir": "/data/edi/outbound",
            "edi_archive_dir": "/data/edi/archive",
            "partner_id": "TARGET_CORP",
            "edi_types": ["846", "856", "810"]
        }
    """

    @property
    def adapter_type(self) -> IntegrationType:
        return IntegrationType.EDI

    def __init__(self, customer_id: str, config: dict[str, Any]):
        super().__init__(customer_id, config)
        self.input_dir = config.get("edi_input_dir", "/data/edi/inbound")
        self.output_dir = config.get("edi_output_dir", "/data/edi/outbound")
        self.archive_dir = config.get("edi_archive_dir", "/data/edi/archive")
        self.partner_id = config.get("partner_id", "UNKNOWN")
        self.parser = EDIX12Parser()

    async def test_connection(self) -> bool:
        """Verify EDI directories are accessible."""
        import os

        return os.path.isdir(self.input_dir)

    async def sync_stores(self) -> SyncResult:
        """
        EDI doesn't typically carry store master data.
        Stores are loaded via SFTP flat file or manual config.
        """
        self.logger.info("sync_stores: EDI does not carry store data; use SFTP adapter")
        return SyncResult(status=SyncStatus.NO_DATA)

    async def sync_products(self) -> SyncResult:
        """
        EDI 846 can carry product identifiers (GTIN/UPC).
        We extract unique products from inventory documents.
        """
        self.logger.info("sync_products: extracting from EDI 846 files")
        result = SyncResult(status=SyncStatus.SUCCESS)
        files = self._list_files("846")

        for filepath in files:
            try:
                raw = self._read_file(filepath)
                items = self.parser.parse_846(raw)
                result.records_processed += len(items)
                result.metadata.setdefault("products", []).extend(
                    [{"gtin": item.gtin, "upc": item.upc} for item in items]
                )
                self._archive_file(filepath)
            except Exception as e:
                result.records_failed += 1
                result.errors.append(f"{filepath}: {str(e)}")

        if result.records_failed > 0 and result.records_processed == 0:
            result.status = SyncStatus.FAILED
        elif result.records_failed > 0:
            result.status = SyncStatus.PARTIAL

        return result.complete()

    async def sync_transactions(self, since: datetime | None = None) -> SyncResult:
        """
        EDI 810 invoices can be mapped to transaction records.
        """
        self.logger.info("sync_transactions: parsing EDI 810 invoices")
        result = SyncResult(status=SyncStatus.SUCCESS)
        files = self._list_files("810")

        for filepath in files:
            try:
                raw = self._read_file(filepath)
                invoice = self.parser.parse_810(raw)
                result.records_processed += len(invoice.line_items)
                result.metadata.setdefault("invoices", []).append(
                    {
                        "invoice_number": invoice.invoice_number,
                        "total": invoice.total_amount,
                        "lines": len(invoice.line_items),
                    }
                )
                self._archive_file(filepath)
            except Exception as e:
                result.records_failed += 1
                result.errors.append(f"{filepath}: {str(e)}")

        return result.complete()

    async def sync_inventory(self) -> SyncResult:
        """
        Parse EDI 846 files to update inventory levels.
        This is the primary use case for the EDI adapter.
        """
        self.logger.info("sync_inventory: parsing EDI 846 documents")
        result = SyncResult(status=SyncStatus.SUCCESS)
        files = self._list_files("846")

        for filepath in files:
            try:
                raw = self._read_file(filepath)
                items = self.parser.parse_846(raw)
                result.records_processed += len(items)
                result.metadata.setdefault("inventory_items", []).extend(
                    [
                        {
                            "gtin": item.gtin,
                            "qty_on_hand": item.quantity_on_hand,
                            "qty_on_order": item.quantity_on_order,
                            "warehouse": item.warehouse_id,
                            "as_of": item.as_of_date.isoformat() if item.as_of_date else None,
                        }
                        for item in items
                    ]
                )
                self._archive_file(filepath)
            except Exception as e:
                result.records_failed += 1
                result.errors.append(f"{filepath}: {str(e)}")

        return result.complete()

    # ── File helpers ───────────────────────────────────────────────────────

    def _list_files(self, edi_type: str) -> list[str]:
        """
        List unprocessed EDI files for a specific transaction type.

        We cannot rely on filename conventions from trading partners, so we
        inspect each document's ST segment and keep only files matching the
        requested type (e.g. 846, 856, 810, 850).
        """
        import os

        if not os.path.isdir(self.input_dir):
            return []
        matched_files: list[str] = []
        for filename in sorted(os.listdir(self.input_dir)):
            if not (filename.endswith(".edi") or filename.endswith(".x12") or filename.endswith(".txt")):
                continue

            filepath = os.path.join(self.input_dir, filename)
            try:
                raw = self._read_file(filepath)
                txn_type = self.parser.detect_transaction_type(raw)
                if txn_type == edi_type:
                    matched_files.append(filepath)
            except Exception:
                # Ignore unreadable or malformed files; parser paths surface errors
                # when specific sync methods process eligible documents.
                continue

        return matched_files

    @staticmethod
    def _read_file(filepath: str) -> str:
        with open(filepath, encoding="utf-8") as f:
            return f.read()

    def _archive_file(self, filepath: str) -> None:
        """Move processed file to the archive directory."""
        import os
        import shutil

        os.makedirs(self.archive_dir, exist_ok=True)
        shutil.move(filepath, os.path.join(self.archive_dir, os.path.basename(filepath)))
