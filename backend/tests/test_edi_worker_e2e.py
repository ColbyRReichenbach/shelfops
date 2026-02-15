from pathlib import Path

import pytest

from integrations.edi_adapter import EDIAdapter, EDIX12Parser
from workers.sync import run_edi_sync_pipeline


def _write_edi_fixtures(inbound: Path) -> None:
    inbound.mkdir(parents=True, exist_ok=True)
    docs = {
        "846_inventory.edi": (
            "ISA*00*          *00*          *ZZ*RETAILER       *ZZ*SHELFOPS       *260215*1200*U*00401*000000001*0*P*>~"
            "GS*IB*RETAILER*SHELFOPS*20260215*1200*1*X*004010~"
            "ST*846*0001~LIN*1*UP*012345678905*IN*00012345678905~QTY*33*120*EA~QTY*02*40*EA~DTM*405*20260215~"
            "N1*WH*Main Warehouse*92*WH001~SE*9*0001~GE*1*1~IEA*1*000000001~"
        ),
        "856_shipment.edi": (
            "ISA*00*          *00*          *ZZ*RETAILER       *ZZ*SHELFOPS       *260215*1200*U*00401*000000002*0*P*>~"
            "GS*SH*RETAILER*SHELFOPS*20260215*1200*2*X*004010~"
            "ST*856*0002~BSN*00*SHIP123*20260215*1200~REF*PO*PO-1001~LIN*1*UP*012345678905*IN*00012345678905~SN1*1*36*EA~"
            "SE*7*0002~GE*1*2~IEA*1*000000002~"
        ),
        "810_invoice.edi": (
            "ISA*00*          *00*          *ZZ*RETAILER       *ZZ*SHELFOPS       *260215*1200*U*00401*000000003*0*P*>~"
            "GS*IN*RETAILER*SHELFOPS*20260215*1200*3*X*004010~"
            "ST*810*0003~BIG*20260215*INV1001**PO-1001~IT1*1*12*EA*3.25*UP*012345678905*IN*00012345678905~TDS*3900~"
            "SE*6*0003~GE*1*3~IEA*1*000000003~"
        ),
        "850_po.edi": EDIX12Parser.generate_850(
            po_number="PO-1001",
            vendor_id="VENDOR01",
            items=[{"gtin": "00012345678905", "quantity": 24, "unit_price": 3.25, "uom": "EA"}],
        ),
    }
    for filename, raw in docs.items():
        (inbound / filename).write_text(raw, encoding="utf-8")


@pytest.mark.asyncio
async def test_edi_worker_pipeline_parses_persists_and_audits(test_db, seeded_db, tmp_path: Path):
    from sqlalchemy import select

    from db.models import EDITransactionLog, Integration, IntegrationSyncLog

    inbound = tmp_path / "edi_inbound"
    archive = tmp_path / "edi_archive"
    archive.mkdir(parents=True, exist_ok=True)
    _write_edi_fixtures(inbound)

    integration = Integration(
        customer_id=seeded_db["customer_id"],
        provider="custom_edi",
        integration_type="edi",
        status="connected",
        partner_id="TEST_PARTNER",
    )
    test_db.add(integration)
    await test_db.flush()

    adapter = EDIAdapter(
        customer_id=str(seeded_db["customer_id"]),
        config={
            "edi_input_dir": str(inbound),
            "edi_archive_dir": str(archive),
            "partner_id": "TEST_PARTNER",
        },
    )

    result = await run_edi_sync_pipeline(
        test_db,
        customer_id=seeded_db["customer_id"],
        integration_id=integration.integration_id,
        adapter=adapter,
        partner_id="TEST_PARTNER",
    )
    assert result["status"] == "success"

    logs = (
        (
            await test_db.execute(
                select(EDITransactionLog).where(EDITransactionLog.integration_id == integration.integration_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(logs) == 4

    by_type = {row.document_type: row for row in logs}
    assert {"846", "850", "856", "810"}.issubset(by_type.keys())
    assert by_type["846"].parsed_records >= 1
    assert by_type["856"].parsed_records >= 1
    assert by_type["810"].parsed_records >= 1
    assert by_type["850"].parsed_records >= 1
    assert all(row.status == "processed" for row in logs)

    sync_logs = (
        (
            await test_db.execute(
                select(IntegrationSyncLog).where(
                    IntegrationSyncLog.customer_id == seeded_db["customer_id"],
                    IntegrationSyncLog.integration_type == "EDI",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(sync_logs) == 4
    assert {log.integration_name for log in sync_logs} == {"EDI 846", "EDI 850", "EDI 856", "EDI 810"}
