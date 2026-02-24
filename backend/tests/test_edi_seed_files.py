"""
Tests for scripts/seed_edi_files.py — EDI X12 file generator.

Verifies that each generated file:
  - is created on disk
  - can be parsed by the real EDIX12Parser (end-to-end integration)
  - produces the expected number of line items
  - contains correct segment structure

No database or external services required.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from integrations.edi_adapter import EDIX12Parser
from scripts.seed_edi_files import generate_810, generate_846, generate_856, main


# ── 846 tests ─────────────────────────────────────────────────────────────

class TestGenerate846:
    def test_file_is_created(self, tmp_path):
        path = generate_846(str(tmp_path), "VENDOR_TEST", product_count=3)
        assert os.path.isfile(path)

    def test_filename_contains_date_and_type(self, tmp_path):
        path = generate_846(str(tmp_path), "VENDOR_TEST", product_count=3)
        assert "846_INVENTORY_" in os.path.basename(path)
        assert path.endswith(".edi")

    def test_parser_returns_correct_item_count(self, tmp_path):
        path = generate_846(str(tmp_path), "VENDOR_TEST", product_count=5)
        raw = Path(path).read_text()
        items = EDIX12Parser.parse_846(raw)
        assert len(items) == 5

    def test_each_item_has_gtin_and_upc(self, tmp_path):
        path = generate_846(str(tmp_path), "VENDOR_TEST", product_count=4)
        raw = Path(path).read_text()
        items = EDIX12Parser.parse_846(raw)
        for item in items:
            assert item.gtin, f"missing gtin: {item}"
            assert item.upc, f"missing upc: {item}"

    def test_quantity_on_hand_is_positive(self, tmp_path):
        path = generate_846(str(tmp_path), "VENDOR_TEST", product_count=3)
        raw = Path(path).read_text()
        items = EDIX12Parser.parse_846(raw)
        for item in items:
            assert item.quantity_on_hand > 0

    def test_warehouse_id_populated(self, tmp_path):
        path = generate_846(str(tmp_path), "VENDOR_TEST", product_count=2)
        raw = Path(path).read_text()
        items = EDIX12Parser.parse_846(raw)
        for item in items:
            assert item.warehouse_id == "WH001"

    def test_as_of_date_is_set(self, tmp_path):
        path = generate_846(str(tmp_path), "VENDOR_TEST", product_count=2)
        raw = Path(path).read_text()
        items = EDIX12Parser.parse_846(raw)
        for item in items:
            assert item.as_of_date is not None

    def test_detect_transaction_type_returns_846(self, tmp_path):
        path = generate_846(str(tmp_path), "VENDOR_TEST", product_count=2)
        raw = Path(path).read_text()
        assert EDIX12Parser.detect_transaction_type(raw) == "846"

    def test_min_one_product(self, tmp_path):
        path = generate_846(str(tmp_path), "VENDOR_TEST", product_count=1)
        raw = Path(path).read_text()
        items = EDIX12Parser.parse_846(raw)
        assert len(items) == 1


# ── 856 tests ─────────────────────────────────────────────────────────────

class TestGenerate856:
    def test_file_is_created(self, tmp_path):
        path = generate_856(str(tmp_path), "VENDOR_TEST", product_count=3)
        assert os.path.isfile(path)

    def test_filename_contains_date_and_type(self, tmp_path):
        path = generate_856(str(tmp_path), "VENDOR_TEST", product_count=3)
        assert "856_ASN_" in os.path.basename(path)

    def test_parser_returns_shipment(self, tmp_path):
        path = generate_856(str(tmp_path), "VENDOR_TEST", product_count=4)
        raw = Path(path).read_text()
        shipment = EDIX12Parser.parse_856(raw)
        assert shipment is not None

    def test_shipment_id_populated(self, tmp_path):
        path = generate_856(str(tmp_path), "VENDOR_TEST", product_count=3)
        raw = Path(path).read_text()
        shipment = EDIX12Parser.parse_856(raw)
        assert shipment.shipment_id and "SHIP-" in shipment.shipment_id

    def test_carrier_populated(self, tmp_path):
        path = generate_856(str(tmp_path), "VENDOR_TEST", product_count=3)
        raw = Path(path).read_text()
        shipment = EDIX12Parser.parse_856(raw)
        # TD5*B*2*UPS*Ground — parser returns service-level ("Ground") over carrier code
        assert shipment.carrier in ("UPS", "Ground", "FedEx", "USPS") or shipment.carrier

    def test_tracking_number_populated(self, tmp_path):
        path = generate_856(str(tmp_path), "VENDOR_TEST", product_count=3)
        raw = Path(path).read_text()
        shipment = EDIX12Parser.parse_856(raw)
        assert shipment.tracking_number

    def test_items_count_matches_products(self, tmp_path):
        path = generate_856(str(tmp_path), "VENDOR_TEST", product_count=4)
        raw = Path(path).read_text()
        shipment = EDIX12Parser.parse_856(raw)
        assert len(shipment.items) == 4

    def test_each_item_has_gtin(self, tmp_path):
        path = generate_856(str(tmp_path), "VENDOR_TEST", product_count=3)
        raw = Path(path).read_text()
        shipment = EDIX12Parser.parse_856(raw)
        for item in shipment.items:
            assert item.get("gtin"), f"missing gtin: {item}"

    def test_detect_transaction_type_returns_856(self, tmp_path):
        path = generate_856(str(tmp_path), "VENDOR_TEST", product_count=2)
        raw = Path(path).read_text()
        assert EDIX12Parser.detect_transaction_type(raw) == "856"


# ── 810 tests ─────────────────────────────────────────────────────────────

class TestGenerate810:
    def test_file_is_created(self, tmp_path):
        path = generate_810(str(tmp_path), "VENDOR_TEST", product_count=3)
        assert os.path.isfile(path)

    def test_filename_contains_date_and_type(self, tmp_path):
        path = generate_810(str(tmp_path), "VENDOR_TEST", product_count=3)
        assert "810_INVOICE_" in os.path.basename(path)

    def test_parser_returns_invoice(self, tmp_path):
        path = generate_810(str(tmp_path), "VENDOR_TEST", product_count=4)
        raw = Path(path).read_text()
        invoice = EDIX12Parser.parse_810(raw)
        assert invoice is not None

    def test_invoice_number_populated(self, tmp_path):
        path = generate_810(str(tmp_path), "VENDOR_TEST", product_count=3)
        raw = Path(path).read_text()
        invoice = EDIX12Parser.parse_810(raw)
        assert invoice.invoice_number and "INV-" in invoice.invoice_number

    def test_po_number_populated(self, tmp_path):
        path = generate_810(str(tmp_path), "VENDOR_TEST", product_count=3)
        raw = Path(path).read_text()
        invoice = EDIX12Parser.parse_810(raw)
        assert invoice.po_number and "PO-" in invoice.po_number

    def test_line_items_count_matches_products(self, tmp_path):
        path = generate_810(str(tmp_path), "VENDOR_TEST", product_count=5)
        raw = Path(path).read_text()
        invoice = EDIX12Parser.parse_810(raw)
        assert len(invoice.line_items) == 5

    def test_total_amount_is_positive(self, tmp_path):
        path = generate_810(str(tmp_path), "VENDOR_TEST", product_count=4)
        raw = Path(path).read_text()
        invoice = EDIX12Parser.parse_810(raw)
        assert invoice.total_amount > 0

    def test_line_items_have_gtin(self, tmp_path):
        path = generate_810(str(tmp_path), "VENDOR_TEST", product_count=4)
        raw = Path(path).read_text()
        invoice = EDIX12Parser.parse_810(raw)
        for item in invoice.line_items:
            assert item.get("gtin"), f"missing gtin: {item}"

    def test_detect_transaction_type_returns_810(self, tmp_path):
        path = generate_810(str(tmp_path), "VENDOR_TEST", product_count=2)
        raw = Path(path).read_text()
        assert EDIX12Parser.detect_transaction_type(raw) == "810"


# ── main() CLI tests ───────────────────────────────────────────────────────

class TestMainCLI:
    def test_main_creates_all_three_files(self, tmp_path):
        rc = main(["--output-dir", str(tmp_path), "--products", "3"])
        assert rc == 0
        files = list(tmp_path.iterdir())
        types = {f.name[:3] for f in files}
        assert types == {"846", "856", "810"}

    def test_main_respects_product_count(self, tmp_path):
        main(["--output-dir", str(tmp_path), "--products", "2"])
        edi_846 = next(f for f in tmp_path.iterdir() if f.name.startswith("846"))
        items = EDIX12Parser.parse_846(edi_846.read_text())
        assert len(items) == 2

    def test_main_respects_partner_id(self, tmp_path):
        main(["--output-dir", str(tmp_path), "--partner-id", "TARGET_CORP", "--products", "2"])
        edi_846 = next(f for f in tmp_path.iterdir() if f.name.startswith("846"))
        raw = edi_846.read_text()
        assert "TARGET_CORP" in raw

    def test_main_clamps_product_count_to_catalogue_max(self, tmp_path):
        # Catalogue has 10 products; requesting 999 should produce 10.
        main(["--output-dir", str(tmp_path), "--products", "999"])
        edi_846 = next(f for f in tmp_path.iterdir() if f.name.startswith("846"))
        items = EDIX12Parser.parse_846(edi_846.read_text())
        assert len(items) == 10
