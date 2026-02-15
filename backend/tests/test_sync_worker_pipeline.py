from pathlib import Path

import pytest

from integrations.sftp_adapter import SFTPAdapter
from workers.sync import run_sftp_sync_pipeline


def _write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.asyncio
async def test_sftp_worker_pipeline_logs_sync_health(test_db, seeded_db, tmp_path: Path):
    from sqlalchemy import select

    from db.models import IntegrationSyncLog

    staging = tmp_path / "staging"
    archive = tmp_path / "archive"

    _write_csv(
        staging / "stores" / "stores.csv",
        "STORE_NBR,STORE_NAME,CITY,STATE\n100,Main Store,Minneapolis,MN\n",
    )
    _write_csv(
        staging / "products" / "products.csv",
        "ITEM_NBR,PRODUCT_NAME,CATEGORY,UNIT_COST,UNIT_PRICE\nSKU1,Widget,Tools,2.50,5.00\n",
    )
    _write_csv(
        staging / "transactions" / "transactions.csv",
        (
            "TRANS_ID,ITEM_NBR,STORE_NBR,QTY_SOLD,UNIT_PRICE,TOTAL_AMOUNT,TRANS_DATE,TRANS_TYPE\n"
            "T1,SKU1,100,3,5.00,15.00,2026-02-10,sale\n"
        ),
    )
    _write_csv(
        staging / "inventory" / "inventory.csv",
        "ITEM_NBR,STORE_NBR,ON_HAND_QTY,ON_ORDER_QTY,SNAPSHOT_DATE\nSKU1,100,25,10,2026-02-10\n",
    )

    adapter = SFTPAdapter(
        customer_id=str(seeded_db["customer_id"]),
        config={
            "local_staging_dir": str(staging),
            "archive_dir": str(archive),
            "delimiter": ",",
        },
    )

    result = await run_sftp_sync_pipeline(test_db, customer_id=seeded_db["customer_id"], adapter=adapter)
    assert result["status"] == "success"
    assert {"stores", "products", "transactions", "inventory"} == set(result["sources"].keys())
    assert result["sources"]["transactions"]["records_processed"] == 1
    assert result["sources"]["inventory"]["records_processed"] == 1

    sync_logs = (
        (
            await test_db.execute(
                select(IntegrationSyncLog).where(
                    IntegrationSyncLog.customer_id == seeded_db["customer_id"],
                    IntegrationSyncLog.integration_type == "SFTP",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(sync_logs) == 4
    assert {row.sync_type for row in sync_logs} == {"stores", "products", "transactions", "inventory"}
