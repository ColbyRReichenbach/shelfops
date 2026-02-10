"""
Tests for the Enterprise Integration Adapter Layer

Covers:
  - EDI X12 parsing (846, 856, 810)
  - EDI 850 generation
  - Adapter base class / registry
  - SFTP flat file parsing
  - Event stream normalization
"""

import pytest
from datetime import datetime
from integrations.base import (
    IntegrationType,
    SyncResult,
    SyncStatus,
    RetailIntegrationAdapter,
    get_adapter,
    _ADAPTER_REGISTRY,
)
from integrations.edi_adapter import EDIX12Parser, EDI846Item, EDI856Shipment, EDI810Invoice
from integrations.sftp_adapter import FlatFileParser
from integrations.event_adapter import (
    normalize_transaction_event,
    normalize_inventory_event,
    validate_event,
    TRANSACTION_EVENT_SCHEMA,
)


# ── EDI 846 (Inventory) Tests ─────────────────────────────────────────────

class TestEDI846Parser:
    """Test parsing of EDI 846 — Inventory Inquiry/Advice."""

    SAMPLE_846 = (
        "ISA*00*          *00*          *ZZ*TARGETCORP     *ZZ*SHELFOPS       *240115*1430*U*00401*000000001*0*P*>~"
        "GS*IB*TARGETCORP*SHELFOPS*20240115*1430*1*X*004010~"
        "ST*846*0001~"
        "LIN*1*UP*012345678901*IN*00012345678901~"
        "QTY*33*500*EA~"
        "QTY*02*100*EA~"
        "DTM*405*20240115~"
        "N1*WH*DistCenter-1*92*DC001~"
        "LIN*2*UP*012345678902~"
        "QTY*33*250*CS~"
        "DTM*405*20240115~"
        "SE*10*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )

    def test_detect_type(self):
        assert EDIX12Parser.detect_transaction_type(self.SAMPLE_846) == "846"

    def test_parse_846_item_count(self):
        items = EDIX12Parser.parse_846(self.SAMPLE_846)
        assert len(items) == 2

    def test_parse_846_first_item_gtin(self):
        items = EDIX12Parser.parse_846(self.SAMPLE_846)
        assert items[0].gtin == "00012345678901"
        assert items[0].upc == "012345678901"

    def test_parse_846_first_item_quantities(self):
        items = EDIX12Parser.parse_846(self.SAMPLE_846)
        assert items[0].quantity_on_hand == 500
        assert items[0].quantity_on_order == 100
        assert items[0].unit_of_measure == "EA"

    def test_parse_846_warehouse(self):
        items = EDIX12Parser.parse_846(self.SAMPLE_846)
        assert items[0].warehouse_id == "DC001"

    def test_parse_846_date(self):
        items = EDIX12Parser.parse_846(self.SAMPLE_846)
        assert items[0].as_of_date == datetime(2024, 1, 15)

    def test_parse_846_second_item(self):
        items = EDIX12Parser.parse_846(self.SAMPLE_846)
        assert items[1].upc == "012345678902"
        assert items[1].quantity_on_hand == 250
        assert items[1].unit_of_measure == "CS"

    def test_parse_846_empty_document(self):
        empty = "ISA*00*~GS*IB*~ST*846*0001~SE*3*0001~GE*1*1~IEA*1*~"
        items = EDIX12Parser.parse_846(empty)
        assert items == []


# ── EDI 856 (ASN) Tests ───────────────────────────────────────────────────

class TestEDI856Parser:
    """Test parsing of EDI 856 — Advance Ship Notice."""

    SAMPLE_856 = (
        "ISA*00*          *00*          *ZZ*VENDOR         *ZZ*SHELFOPS       *240115*0800*U*00401*000000002*0*P*>~"
        "GS*SH*VENDOR*SHELFOPS*20240115*0800*2*X*004010~"
        "ST*856*0001~"
        "BSN*00*SHP12345*20240115*0800~"
        "TD5*O*2*FEDX*Ground~"
        "REF*CN*TRACK789456123~"
        "LIN*1*UP*012345678901~"
        "SN1*1*50*EA~"
        "REF*PO*PO-2024-001~"
        "DTM*017*20240118~"
        "SE*9*0001~"
        "GE*1*2~"
        "IEA*1*000000002~"
    )

    def test_detect_type(self):
        assert EDIX12Parser.detect_transaction_type(self.SAMPLE_856) == "856"

    def test_parse_856_shipment_id(self):
        shipment = EDIX12Parser.parse_856(self.SAMPLE_856)
        assert shipment.shipment_id == "SHP12345"

    def test_parse_856_carrier(self):
        shipment = EDIX12Parser.parse_856(self.SAMPLE_856)
        assert shipment.carrier == "Ground"

    def test_parse_856_tracking(self):
        shipment = EDIX12Parser.parse_856(self.SAMPLE_856)
        assert shipment.tracking_number == "TRACK789456123"

    def test_parse_856_items(self):
        shipment = EDIX12Parser.parse_856(self.SAMPLE_856)
        assert len(shipment.items) == 1
        assert shipment.items[0]["gtin"] == "012345678901"
        assert shipment.items[0]["quantity"] == 50

    def test_parse_856_expected_delivery(self):
        shipment = EDIX12Parser.parse_856(self.SAMPLE_856)
        assert shipment.expected_delivery == datetime(2024, 1, 18)


# ── EDI 810 (Invoice) Tests ───────────────────────────────────────────────

class TestEDI810Parser:
    """Test parsing of EDI 810 — Invoice."""

    SAMPLE_810 = (
        "ISA*00*          *00*          *ZZ*VENDOR         *ZZ*SHELFOPS       *240120*1200*U*00401*000000003*0*P*>~"
        "GS*IN*VENDOR*SHELFOPS*20240120*1200*3*X*004010~"
        "ST*810*0001~"
        "BIG*20240120*INV-2024-0042**PO-2024-001~"
        "IT1*1*50*EA*4.99**UP*012345678901~"
        "IT1*2*100*EA*2.50**IN*00012345678902~"
        "TDS*49950~"
        "SE*6*0001~"
        "GE*1*3~"
        "IEA*1*000000003~"
    )

    def test_parse_810_invoice_number(self):
        invoice = EDIX12Parser.parse_810(self.SAMPLE_810)
        assert invoice.invoice_number == "INV-2024-0042"

    def test_parse_810_po_number(self):
        invoice = EDIX12Parser.parse_810(self.SAMPLE_810)
        assert invoice.po_number == "PO-2024-001"

    def test_parse_810_total(self):
        invoice = EDIX12Parser.parse_810(self.SAMPLE_810)
        assert invoice.total_amount == 499.50

    def test_parse_810_line_items(self):
        invoice = EDIX12Parser.parse_810(self.SAMPLE_810)
        assert len(invoice.line_items) == 2
        assert invoice.line_items[0]["quantity"] == 50
        assert invoice.line_items[0]["unit_price"] == 4.99


# ── EDI 850 (PO Generation) Tests ─────────────────────────────────────────

class TestEDI850Generator:
    """Test generation of EDI 850 — Purchase Order."""

    def test_generate_850_structure(self):
        raw = EDIX12Parser.generate_850(
            po_number="PO-2024-100",
            vendor_id="VENDOR001",
            items=[
                {"gtin": "012345678901", "quantity": 100, "unit_price": 4.99, "uom": "EA"},
                {"gtin": "012345678902", "quantity": 50, "unit_price": 12.50, "uom": "CS"},
            ],
        )
        assert "ST*850*0001" in raw
        assert "BEG*00*NE*PO-2024-100" in raw
        assert "PO1*1*100*EA*4.99*PE*IN*012345678901" in raw
        assert "PO1*2*50*CS*12.50*PE*IN*012345678902" in raw

    def test_generate_850_with_ship_to(self):
        raw = EDIX12Parser.generate_850(
            po_number="PO-TEST",
            vendor_id="V1",
            items=[{"gtin": "123", "quantity": 10, "unit_price": 1.0}],
            ship_to={"name": "Store A", "id": "S001", "address": "123 Main", "city": "LA", "state": "CA", "zip": "90001"},
        )
        assert "N1*ST*Store A*92*S001" in raw
        assert "N4*LA*CA*90001" in raw


# ── Flat File Parser Tests ─────────────────────────────────────────────────

class TestFlatFileParser:
    """Test SFTP flat file parsing."""

    SAMPLE_CSV = "ITEM_NBR,UPC,ON_HAND_QTY,STORE_NBR\n100001,012345678901,500,STORE_042\n100002,012345678902,250,STORE_042\n"

    def test_parse_csv_basic(self):
        records = FlatFileParser.parse_csv(self.SAMPLE_CSV)
        assert len(records) == 2
        assert records[0]["ITEM_NBR"] == "100001"

    def test_parse_csv_with_mapping(self):
        mapping = {"ITEM_NBR": "sku", "UPC": "upc", "ON_HAND_QTY": "quantity_on_hand"}
        records = FlatFileParser.parse_csv(self.SAMPLE_CSV, field_mapping=mapping)
        assert records[0]["sku"] == "100001"
        assert records[0]["upc"] == "012345678901"
        assert records[0]["quantity_on_hand"] == "500"

    def test_parse_csv_tab_delimited(self):
        tsv = "SKU\tQTY\n001\t100\n002\t200\n"
        records = FlatFileParser.parse_csv(tsv, delimiter="\t")
        assert len(records) == 2
        assert records[1]["QTY"] == "200"

    def test_parse_fixed_width(self):
        content = "001       500  4.99\n002       250  12.50\n"
        specs = [("sku", 0, 10), ("qty", 10, 15), ("price", 15, 20)]
        records = FlatFileParser.parse_fixed_width(content, specs)
        assert len(records) == 2
        assert records[0]["sku"] == "001"
        assert records[0]["qty"] == "500"


# ── Event Normalization Tests ──────────────────────────────────────────────

class TestEventNormalization:
    """Test Kafka/Pub/Sub event normalization."""

    def test_normalize_transaction_event(self):
        event = {
            "event_id": "evt_001",
            "store_id": "STORE_042",
            "timestamp": "2024-01-15T14:23:45Z",
            "items": [
                {"sku": "012345678901", "quantity": 2, "unit_price": 4.99, "total": 9.98},
            ],
        }
        records = normalize_transaction_event(event)
        assert len(records) == 1
        assert records[0]["external_id"] == "evt_001"
        assert records[0]["sku"] == "012345678901"
        assert records[0]["quantity"] == 2
        assert records[0]["transaction_type"] == "sale"

    def test_normalize_inventory_event(self):
        event = {
            "event_id": "evt_002",
            "store_id": "STORE_042",
            "timestamp": "2024-01-15T06:00:00Z",
            "reason": "cycle_count",
            "items": [
                {"sku": "012345678901", "quantity_on_hand": 45, "quantity_on_order": 100},
            ],
        }
        records = normalize_inventory_event(event)
        assert len(records) == 1
        assert records[0]["quantity_on_hand"] == 45
        assert records[0]["source"] == "event_cycle_count"

    def test_validate_event_valid(self):
        event = {"event_id": "1", "store_id": "2", "timestamp": "now", "items": []}
        errors = validate_event(event, TRANSACTION_EVENT_SCHEMA)
        assert errors == []

    def test_validate_event_missing_fields(self):
        event = {"event_id": "1"}
        errors = validate_event(event, TRANSACTION_EVENT_SCHEMA)
        assert len(errors) == 3  # missing store_id, timestamp, items


# ── SyncResult Tests ───────────────────────────────────────────────────────

class TestSyncResult:
    """Test the SyncResult data class."""

    def test_sync_result_complete(self):
        result = SyncResult(status=SyncStatus.SUCCESS, records_processed=100)
        result.complete()
        assert result.completed_at is not None
        assert result.records_processed == 100

    def test_sync_result_defaults(self):
        result = SyncResult(status=SyncStatus.FAILED)
        assert result.records_processed == 0
        assert result.errors == []
        assert result.metadata == {}
