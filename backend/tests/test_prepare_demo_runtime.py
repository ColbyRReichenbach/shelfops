from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from db.models import Integration, IntegrationSyncLog, MLAlert, ModelVersion, PurchaseOrder
from scripts.prepare_demo_runtime import (
    CHALLENGER_VERSION,
    CHAMPION_VERSION,
    DEV_CUSTOMER_ID,
    build_demo_runtime,
)


@pytest.mark.asyncio
async def test_build_demo_runtime_seeds_deterministic_live_demo_state(test_db):
    payload = await build_demo_runtime(test_db, as_of=datetime(2026, 3, 8, 15, 0, 0))

    assert payload["status"] == "success"
    assert payload["customer_id"] == DEV_CUSTOMER_ID
    assert payload["purchase_orders"]["suggested_count"] == 3
    assert payload["mlops"]["champion_version"] == CHAMPION_VERSION
    assert payload["mlops"]["challenger_version"] == CHALLENGER_VERSION

    po_result = await test_db.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.customer_id == DEV_CUSTOMER_ID,
            PurchaseOrder.status == "suggested",
        )
    )
    purchase_orders = po_result.scalars().all()
    assert len(purchase_orders) == 3

    version_result = await test_db.execute(
        select(ModelVersion).where(ModelVersion.customer_id == DEV_CUSTOMER_ID)
    )
    versions = {row.version: row for row in version_result.scalars().all()}
    assert versions[CHAMPION_VERSION].status == "champion"
    assert versions[CHALLENGER_VERSION].status == "challenger"

    integration_result = await test_db.execute(
        select(Integration).where(Integration.customer_id == DEV_CUSTOMER_ID)
    )
    providers = {row.provider for row in integration_result.scalars().all()}
    assert {"square", "kafka", "custom_edi", "custom_sftp"} <= providers

    alert_result = await test_db.execute(
        select(MLAlert).where(MLAlert.customer_id == DEV_CUSTOMER_ID)
    )
    alert_types = {row.alert_type for row in alert_result.scalars().all()}
    assert {"drift_detected", "promotion_pending"} <= alert_types

    sync_result = await test_db.execute(
        select(IntegrationSyncLog).where(IntegrationSyncLog.customer_id == DEV_CUSTOMER_ID)
    )
    sync_names = {row.integration_name for row in sync_result.scalars().all()}
    assert "Kafka Store Transfers" in sync_names
    assert "Square POS" in sync_names


@pytest.mark.asyncio
async def test_build_demo_runtime_is_idempotent_for_active_demo_records(test_db):
    await build_demo_runtime(test_db, as_of=datetime(2026, 3, 8, 15, 0, 0))
    await build_demo_runtime(test_db, as_of=datetime(2026, 3, 8, 16, 0, 0))

    po_result = await test_db.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.customer_id == DEV_CUSTOMER_ID,
            PurchaseOrder.status == "suggested",
        )
    )
    purchase_orders = po_result.scalars().all()
    assert len(purchase_orders) == 3

    integration_result = await test_db.execute(
        select(Integration).where(Integration.customer_id == DEV_CUSTOMER_ID)
    )
    assert len(integration_result.scalars().all()) == 4
