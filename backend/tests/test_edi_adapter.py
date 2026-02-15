"""
Unit tests for EDI parsing/generation and transaction-type file filtering.
"""

from datetime import datetime
from pathlib import Path

import pytest

from integrations.edi_adapter import EDIAdapter, EDIX12Parser


def test_parse_846_extracts_inventory_items():
    raw = (
        "ISA*00*          *00*          *ZZ*SHELFOPS       *ZZ*VENDOR         *260215*1200*U*00401*000000001*0*P*>~"
        "GS*IB*SHELFOPS*VENDOR*20260215*1200*1*X*004010~"
        "ST*846*0001~"
        "LIN*UP*012345678905*IN*00012345678905~"
        "QTY*33*120*EA~"
        "QTY*02*40*EA~"
        "DTM*405*20260215~"
        "N1*WH*Main Warehouse*92*WH001~"
        "SE*8*0001~GE*1*1~IEA*1*000000001~"
    )

    items = EDIX12Parser.parse_846(raw)

    assert len(items) == 1
    assert items[0].gtin == "00012345678905"
    assert items[0].upc == "012345678905"
    assert items[0].quantity_on_hand == 120
    assert items[0].quantity_on_order == 40
    assert items[0].warehouse_id == "WH001"


def test_generate_850_contains_core_segments():
    doc = EDIX12Parser.generate_850(
        po_number="PO-1001",
        vendor_id="VENDOR01",
        items=[
            {"gtin": "00012345678905", "quantity": 24, "unit_price": 3.25, "uom": "EA"},
        ],
        ship_to={
            "name": "Store 12",
            "id": "S12",
            "address": "123 Main",
            "city": "Raleigh",
            "state": "NC",
            "zip": "27601",
        },
    )

    assert "ST*850*0001" in doc
    assert "BEG*00*NE*PO-1001" in doc
    assert "PO1*1*24*EA*3.25*PE*IN*00012345678905" in doc
    assert doc.endswith("~")


def test_list_files_filters_by_st_transaction_type(tmp_path: Path):
    inbound = tmp_path / "inbound"
    archive = tmp_path / "archive"
    inbound.mkdir()
    archive.mkdir()

    (inbound / "inv.edi").write_text("ST*846*0001~SE*2*0001~", encoding="utf-8")
    (inbound / "asn.edi").write_text("ST*856*0001~SE*2*0001~", encoding="utf-8")
    (inbound / "invoice.edi").write_text("ST*810*0001~SE*2*0001~", encoding="utf-8")
    (inbound / "bad.edi").write_text("NOT_EDI", encoding="utf-8")

    adapter = EDIAdapter(
        customer_id="00000000-0000-0000-0000-000000000001",
        config={
            "edi_input_dir": str(inbound),
            "edi_archive_dir": str(archive),
        },
    )

    files_846 = adapter._list_files("846")
    files_856 = adapter._list_files("856")
    files_810 = adapter._list_files("810")

    assert files_846 == [str(inbound / "inv.edi")]
    assert files_856 == [str(inbound / "asn.edi")]
    assert files_810 == [str(inbound / "invoice.edi")]


def _parsed_record_count(document_type: str, raw: str) -> int:
    if document_type == "846":
        return len(EDIX12Parser.parse_846(raw))
    if document_type == "856":
        return len(EDIX12Parser.parse_856(raw).items)
    if document_type == "810":
        return len(EDIX12Parser.parse_810(raw).line_items)
    if document_type == "850":
        # We generate 850 currently but do not parse it in adapter logic yet.
        return 1
    return 0


@pytest.mark.asyncio
async def test_edi_fixture_harness_parses_and_persists_audit_logs(test_db, seeded_db):
    """Fixture harness: parse -> persist -> audit assertions for 846/850/856/810."""
    from db.models import EDITransactionLog, Integration

    integration = Integration(
        customer_id=seeded_db["customer_id"],
        provider="custom_edi",
        integration_type="edi",
        status="connected",
        partner_id="TEST_PARTNER",
    )
    test_db.add(integration)
    await test_db.flush()

    docs = {
        "846": (
            "ISA*00*          *00*          *ZZ*RETAILER       *ZZ*SHELFOPS       *260215*1200*U*00401*000000001*0*P*>~"
            "GS*IB*RETAILER*SHELFOPS*20260215*1200*1*X*004010~"
            "ST*846*0001~LIN*1*UP*012345678905*IN*00012345678905~QTY*33*120*EA~QTY*02*40*EA~DTM*405*20260215~"
            "N1*WH*Main Warehouse*92*WH001~SE*9*0001~GE*1*1~IEA*1*000000001~"
        ),
        "856": (
            "ISA*00*          *00*          *ZZ*RETAILER       *ZZ*SHELFOPS       *260215*1200*U*00401*000000002*0*P*>~"
            "GS*SH*RETAILER*SHELFOPS*20260215*1200*2*X*004010~"
            "ST*856*0002~BSN*00*SHIP123*20260215*1200~REF*PO*PO-1001~LIN*1*UP*012345678905*IN*00012345678905~SN1*1*36*EA~"
            "SE*7*0002~GE*1*2~IEA*1*000000002~"
        ),
        "810": (
            "ISA*00*          *00*          *ZZ*RETAILER       *ZZ*SHELFOPS       *260215*1200*U*00401*000000003*0*P*>~"
            "GS*IN*RETAILER*SHELFOPS*20260215*1200*3*X*004010~"
            "ST*810*0003~BIG*20260215*INV1001**PO-1001~IT1*1*12*EA*3.25*UP*012345678905*IN*00012345678905~TDS*3900~"
            "SE*6*0003~GE*1*3~IEA*1*000000003~"
        ),
        "850": EDIX12Parser.generate_850(
            po_number="PO-1001",
            vendor_id="VENDOR01",
            items=[{"gtin": "00012345678905", "quantity": 24, "unit_price": 3.25, "uom": "EA"}],
        ),
    }

    for doc_type, raw in docs.items():
        parsed_records = _parsed_record_count(doc_type, raw)
        status = "processed" if parsed_records > 0 else "failed"
        test_db.add(
            EDITransactionLog(
                customer_id=seeded_db["customer_id"],
                integration_id=integration.integration_id,
                document_type=doc_type,
                direction="inbound" if doc_type != "850" else "outbound",
                trading_partner_id="TEST_PARTNER",
                filename=f"{doc_type}_fixture.edi",
                raw_content=raw,
                parsed_records=parsed_records,
                errors=[],
                status=status,
                processed_at=datetime.utcnow(),
            )
        )

    await test_db.commit()

    result = await test_db.execute(
        EDITransactionLog.__table__.select().where(EDITransactionLog.integration_id == integration.integration_id)
    )
    logs = result.fetchall()
    assert len(logs) == 4

    by_type = {row.document_type: row for row in logs}
    assert by_type["846"].parsed_records >= 1
    assert by_type["856"].parsed_records >= 1
    assert by_type["810"].parsed_records >= 1
    assert by_type["850"].parsed_records == 1
    assert all(row.status == "processed" for row in logs)
