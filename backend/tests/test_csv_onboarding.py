from __future__ import annotations

from sqlalchemy import func, select

from db.models import Integration, IntegrationSyncLog, InventoryLevel, Product, Store, TenantMLReadiness, Transaction


def _stores_csv() -> str:
    return "name,city,state,zip_code\nDowntown,Minneapolis,MN,55401\n"


def _products_csv() -> str:
    rows = ["sku,name,category,unit_cost,unit_price"]
    for idx in range(5):
        rows.append(f"SKU-{idx:03d},Product {idx},Grocery,2.5,4.5")
    return "\n".join(rows) + "\n"


def _transactions_csv(days: int = 95) -> str:
    rows = ["date,store_name,sku,quantity,unit_price"]
    for day in range(days):
        current = f"2024-01-{(day % 28) + 1:02d}"
        month = 1 + day // 28
        current = f"2024-{month:02d}-{(day % 28) + 1:02d}"
        for idx in range(5):
            rows.append(f"{current},Downtown,SKU-{idx:03d},{idx + 1},4.5")
    return "\n".join(rows) + "\n"


def _inventory_csv() -> str:
    return (
        "timestamp,store_name,sku,quantity_on_hand,quantity_on_order,quantity_reserved\n"
        "2024-04-05T09:00:00,Downtown,SKU-000,25,3,1\n"
    )


async def test_bad_csv_returns_actionable_errors(client):
    response = await client.post(
        "/api/v1/data/csv/validate",
        json={
            "stores_csv": "city,state\nMinneapolis,MN\n",
            "transactions_csv": "date,store_name,sku,quantity\n2024-01-01,Unknown,SKU-999,abc\n",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    messages = [issue["message"] for issue in payload["issues"]]
    assert "missing required column 'name'" in messages
    assert "unknown store_name 'Unknown'" in messages
    assert "unknown sku 'SKU-999'" in messages
    assert "invalid numeric value for 'quantity'" in messages


async def test_good_csv_creates_canonical_records_and_updates_readiness(client, test_db):
    ingest = await client.post(
        "/api/v1/data/csv/ingest",
        json={
            "stores_csv": _stores_csv(),
            "products_csv": _products_csv(),
            "transactions_csv": _transactions_csv(),
            "inventory_csv": _inventory_csv(),
        },
    )

    assert ingest.status_code == 200
    payload = ingest.json()
    assert payload["created"]["transactions"] > 0
    assert payload["readiness"]["state"] == "warming"
    assert payload["readiness"]["reason_code"] == "insufficient_candidate_accuracy_samples"

    store_count = await test_db.scalar(select(func.count(Store.store_id)))
    product_count = await test_db.scalar(select(func.count(Product.product_id)))
    txn_count = await test_db.scalar(select(func.count(Transaction.transaction_id)))
    inv_count = await test_db.scalar(select(func.count(InventoryLevel.id)))
    csv_integration = (
        await test_db.execute(select(Integration).where(Integration.provider == "csv"))
    ).scalar_one()
    sync_log_count = await test_db.scalar(
        select(func.count(IntegrationSyncLog.sync_id)).where(
            IntegrationSyncLog.integration_name == "CSV Onboarding"
        )
    )
    readiness = (await test_db.execute(select(TenantMLReadiness))).scalar_one()

    assert store_count == 1
    assert product_count == 5
    assert txn_count == 95 * 5
    assert inv_count == 1
    assert csv_integration.status == "connected"
    assert csv_integration.last_sync_at is not None
    assert sync_log_count == 4
    assert readiness.state == "warming"

    readiness_response = await client.get("/api/v1/data/readiness")
    assert readiness_response.status_code == 200
    readiness_payload = readiness_response.json()
    assert readiness_payload["state"] == "warming"
    assert readiness_payload["snapshot"]["history_days"] >= 90


async def test_csv_ingest_registers_first_class_integration(client):
    ingest = await client.post(
        "/api/v1/data/csv/ingest",
        json={
            "stores_csv": _stores_csv(),
            "products_csv": _products_csv(),
            "transactions_csv": _transactions_csv(),
            "inventory_csv": _inventory_csv(),
        },
    )
    assert ingest.status_code == 200

    integrations = await client.get("/api/v1/integrations/")
    assert integrations.status_code == 200
    payload = integrations.json()
    assert len(payload) == 1
    assert payload[0]["provider"] == "csv"
    assert payload[0]["status"] == "connected"
