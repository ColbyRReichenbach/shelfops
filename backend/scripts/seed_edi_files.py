"""
seed_edi_files.py — Generate real EDI X12 test files for ShelfOps inbound processing.

Produces files that the existing EDIX12Parser in integrations/edi_adapter.py can
parse without modification.  Segment terminator is ~ (tilde), element separator
is * (asterisk), and each segment is written on its own line ending with ~.

Usage:
    PYTHONPATH=backend python scripts/seed_edi_files.py
    PYTHONPATH=backend python scripts/seed_edi_files.py --output-dir /tmp/edi --products 5
    PYTHONPATH=backend python scripts/seed_edi_files.py --partner-id TARGET_CORP
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

# X12 delimiters — must match EDIX12Parser constants
SEG = "~"
ELM = "*"

# Date strings used across all three document types
TODAY = date.today()
DATE8 = TODAY.strftime("%Y%m%d")   # 20260224
DATE6 = TODAY.strftime("%y%m%d")   # 260224
TIME4 = "1200"

# Catalogue of realistic product GTIN/UPC pairs used by the 846, 856, and 810.
# GTINs are 14-digit GS1 identifiers; UPCs are the embedded 12-digit subset.
_PRODUCT_CATALOGUE = [
    ("00012345678905", "012345678901"),
    ("00098765432104", "098765432109"),
    ("00011223344550", "011223344552"),
    ("00099887766554", "099887766553"),
    ("00055443322116", "055443322115"),
    ("00077665544332", "077665544331"),
    ("00033221144880", "033221144882"),
    ("00066554433221", "066554433220"),
    ("00044332211990", "044332211991"),
    ("00088776655443", "088776655442"),
]


def _seg(*elements: str) -> str:
    """Join elements with * and append ~ terminator."""
    return ELM.join(elements) + SEG


def _isa_header(sender: str, receiver: str, control_number: str) -> str:
    """Build a standard ISA interchange header segment."""
    # ISA has fixed-width fields: sender/receiver are padded to 15 chars
    sender_padded = f"{sender:<15}"
    receiver_padded = f"{receiver:<15}"
    return (
        f"ISA{ELM}00{ELM}          {ELM}00{ELM}          "
        f"{ELM}ZZ{ELM}{sender_padded}{ELM}ZZ{ELM}{receiver_padded}"
        f"{ELM}{DATE6}{ELM}{TIME4}{ELM}U{ELM}00401{ELM}{control_number}"
        f"{ELM}0{ELM}P{ELM}>{SEG}"
    )


# ── EDI 846 — Inventory Inquiry/Advice ────────────────────────────────────


def generate_846(
    output_dir: str,
    partner_id: str,
    product_count: int,
) -> str:
    """
    Generate an EDI 846 Inventory Inquiry file.

    Parser expectations (from EDIX12Parser.parse_846):
      LIN*<seq>*UP*<upc>*IN*<gtin>~     — item identification
      QTY*33*<qty>*EA~                   — quantity on hand  (qualifier 33)
      QTY*02*<qty>*EA~                   — quantity on order (qualifier 02)
      DTM*405*<YYYYMMDD>~                — as-of date
      N1*WH*<name>*92*<warehouse_id>~    — warehouse identification
    """
    products = _PRODUCT_CATALOGUE[:product_count]
    control = "000000001"
    filename = f"846_INVENTORY_{DATE8}.edi"
    filepath = os.path.join(output_dir, filename)

    lines: list[str] = []

    # Interchange envelope
    lines.append(_isa_header("SHELFOPS", partner_id, control))
    lines.append(_seg("GS", "IQ", "SHELFOPS", partner_id, DATE8, TIME4, "1", "X", "004010"))
    lines.append(_seg("ST", "846", "0001"))

    # Item loop
    for seq, (gtin, upc) in enumerate(products, start=1):
        # Quantity and on-order values vary across items so the seed data is
        # not entirely uniform — makes test scenarios more realistic.
        qty_on_hand = 100 + seq * 50
        qty_on_order = 10 + seq * 5

        lines.append(_seg("LIN", str(seq), "UP", upc, "IN", gtin))
        lines.append(_seg("QTY", "33", str(qty_on_hand), "EA"))
        lines.append(_seg("QTY", "02", str(qty_on_order), "EA"))
        lines.append(_seg("DTM", "405", DATE8))
        lines.append(_seg("N1", "WH", "Main Warehouse", "92", "WH001"))

    # Transaction trailer: count ST + all item segments (5 per item) + SE
    # ST=1, per-item=5*n, SE=1 → total = 2 + 5*n
    segment_count = 2 + 5 * len(products)
    lines.append(_seg("SE", str(segment_count), "0001"))
    lines.append(_seg("GE", "1", "1"))
    lines.append(_seg("IEA", "1", control))

    content = "\n".join(lines) + "\n"
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(content)

    return filepath


# ── EDI 856 — Advance Ship Notice ─────────────────────────────────────────


def generate_856(
    output_dir: str,
    partner_id: str,
    product_count: int,
) -> str:
    """
    Generate an EDI 856 Advance Ship Notice (ASN) file.

    Parser expectations (from EDIX12Parser.parse_856):
      BSN*00*<shipment_id>*<YYYYMMDD>*<HHMM>~  — shipment ID and ship date
      TD5*B*2*UPS*Ground~                        — carrier; element[4] preferred
      REF*CN*<tracking_number>~                  — tracking number
      REF*PO*<po_number>~                        — PO reference (per item)
      LIN*<seq>*UP*<upc>~                        — item identification
      SN1*<seq>*<quantity>*EA~                   — item quantity
      DTM*017*<YYYYMMDD>~                        — expected delivery (qualifier 017)
    """
    products = _PRODUCT_CATALOGUE[:product_count]
    control = "000000002"
    shipment_id = f"SHIP-{DATE8}-001"
    tracking = "1Z9999W99999999999"
    po_number = f"PO-{DATE8}-001"
    delivery_date = (TODAY + timedelta(days=5)).strftime("%Y%m%d")
    filename = f"856_ASN_{DATE8}.edi"
    filepath = os.path.join(output_dir, filename)

    lines: list[str] = []

    lines.append(_isa_header(partner_id, "SHELFOPS", control))
    lines.append(_seg("GS", "SH", partner_id, "SHELFOPS", DATE8, TIME4, "2", "X", "004010"))
    lines.append(_seg("ST", "856", "0001"))
    lines.append(_seg("BSN", "00", shipment_id, DATE8, TIME4))
    lines.append(_seg("TD5", "B", "2", "UPS", "Ground"))
    lines.append(_seg("REF", "CN", tracking))

    # Shipment-level HL
    lines.append(_seg("HL", "1", "", "S"))
    # Order-level HL
    lines.append(_seg("HL", "2", "1", "O"))
    lines.append(_seg("REF", "PO", po_number))

    # Item loop — each item gets its own HL, LIN, SN1, and DTM
    for seq, (gtin, upc) in enumerate(products, start=1):
        hl_id = seq + 2  # HL 3, 4, 5, ...
        quantity = 24 + seq * 12
        lines.append(_seg("HL", str(hl_id), "2", "I"))
        lines.append(_seg("LIN", str(seq), "UP", upc))
        lines.append(_seg("SN1", str(seq), str(quantity), "EA"))
        lines.append(_seg("DTM", "017", delivery_date))

    # Segment count: ST + BSN + TD5 + REF(CN) + HL(S) + HL(O) + REF(PO)
    #               + per-item 4 segments (HL+LIN+SN1+DTM) + SE
    segment_count = 2 + 6 + 4 * len(products)
    lines.append(_seg("SE", str(segment_count), "0001"))
    lines.append(_seg("GE", "1", "2"))
    lines.append(_seg("IEA", "1", control))

    content = "\n".join(lines) + "\n"
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(content)

    return filepath


# ── EDI 810 — Invoice ──────────────────────────────────────────────────────


def generate_810(
    output_dir: str,
    partner_id: str,
    product_count: int,
) -> str:
    """
    Generate an EDI 810 Invoice file.

    Parser expectations (from EDIX12Parser.parse_810):
      BIG*<YYYYMMDD>*<invoice_number>**<po_number>~  — BIG element[1]=date,
                                                         element[2]=invoice_num,
                                                         element[4]=po_number
      IT1*<seq>*<qty>*EA*<unit_price>*PE*UP*<upc>~   — line item (UP qualifier)
      IT1*<seq>*<qty>*CS*<unit_price>*PE*IN*<gtin>~  — line item (IN qualifier)
      TDS*<total_cents>~                              — total in integer cents
    """
    products = _PRODUCT_CATALOGUE[:product_count]
    control = "000000003"
    invoice_number = f"INV-{DATE8}-001"
    po_number = f"PO-{DATE8}-001"
    filename = f"810_INVOICE_{DATE8}.edi"
    filepath = os.path.join(output_dir, filename)

    lines: list[str] = []

    lines.append(_isa_header(partner_id, "SHELFOPS", control))
    lines.append(_seg("GS", "IN", partner_id, "SHELFOPS", DATE8, TIME4, "3", "X", "004010"))
    lines.append(_seg("ST", "810", "0001"))
    # BIG: date, invoice_number, (blank cross-ref), po_number
    lines.append(_seg("BIG", DATE8, invoice_number, "", po_number))

    total_cents = 0
    for seq, (gtin, upc) in enumerate(products, start=1):
        quantity = 12 + seq * 6
        unit_price = 2.50 + seq * 1.25
        line_total = quantity * unit_price
        total_cents += round(line_total * 100)

        # Alternate between UP and IN qualifiers so both parser branches are
        # exercised when all generated files are processed together.
        if seq % 2 == 1:
            qualifier = "UP"
            identifier = upc
        else:
            qualifier = "IN"
            identifier = gtin

        lines.append(
            _seg(
                "IT1",
                str(seq),
                str(quantity),
                "EA",
                f"{unit_price:.2f}",
                "PE",
                qualifier,
                identifier,
            )
        )

    lines.append(_seg("TDS", str(total_cents)))

    # Segment count: ST + BIG + IT1*n + TDS + SE = 2 + n + 1 + 1 = 4 + n
    segment_count = 4 + len(products)
    lines.append(_seg("SE", str(segment_count), "0001"))
    lines.append(_seg("GE", "1", "3"))
    lines.append(_seg("IEA", "1", control))

    content = "\n".join(lines) + "\n"
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(content)

    return filepath


# ── CLI entry point ────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate EDI X12 seed files for ShelfOps inbound processing.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        default="/data/edi/inbound",
        help="Directory to write generated EDI files into.",
    )
    parser.add_argument(
        "--products",
        type=int,
        default=8,
        metavar="COUNT",
        help="Number of product line items to include in each document (max 10).",
    )
    parser.add_argument(
        "--partner-id",
        default="VENDOR_001",
        help="Trading partner identifier written into ISA/GS envelope headers.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    product_count = max(1, min(args.products, len(_PRODUCT_CATALOGUE)))
    output_dir: str = args.output_dir
    partner_id: str = args.partner_id

    os.makedirs(output_dir, exist_ok=True)

    written: list[str] = []

    path_846 = generate_846(output_dir, partner_id, product_count)
    written.append(path_846)

    path_856 = generate_856(output_dir, partner_id, product_count)
    written.append(path_856)

    path_810 = generate_810(output_dir, partner_id, product_count)
    written.append(path_810)

    print(f"EDI seed files written to {output_dir}:")
    for path in written:
        size = os.path.getsize(path)
        print(f"  {os.path.basename(path):40s}  {size:>6d} bytes")

    print(f"\nTotal: {len(written)} file(s), {product_count} product(s) per document.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
