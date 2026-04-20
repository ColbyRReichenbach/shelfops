from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd

from scripts.bootstrap_sample_merchant import build_sample_payloads


def _write_seed_fixture(root: Path) -> None:
    seed_root = root / "seed"
    (seed_root / "transactions").mkdir(parents=True)
    (seed_root / "inventory").mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "store_id": "store-1",
                "external_code": "STR-001",
                "name": "Downtown",
                "city": "Minneapolis",
                "state": "MN",
                "zip_code": "55401",
                "lat": 44.98,
                "lon": -93.26,
                "timezone": "US/Central",
                "volume_multiplier": 1.2,
            },
            {
                "store_id": "store-2",
                "external_code": "STR-002",
                "name": "Uptown",
                "city": "Minneapolis",
                "state": "MN",
                "zip_code": "55408",
                "lat": 44.95,
                "lon": -93.29,
                "timezone": "US/Central",
                "volume_multiplier": 0.9,
            },
        ]
    ).to_csv(seed_root / "stores.csv", index=False)

    pd.DataFrame(
        [
            {
                "product_id": "prod-1",
                "sku": "SKU-001",
                "name": "Trail Mix",
                "category": "Snacks",
                "subcategory": "Nuts",
                "brand": "Northstar",
                "unit_cost": 2.15,
                "unit_price": 4.25,
                "weight": 8.0,
                "shelf_life_days": 180,
                "is_seasonal": False,
                "is_perishable": False,
            },
            {
                "product_id": "prod-2",
                "sku": "SKU-002",
                "name": "Greek Yogurt",
                "category": "Dairy",
                "subcategory": "Yogurt",
                "brand": "Fresh Day",
                "unit_cost": 1.05,
                "unit_price": 2.49,
                "weight": 6.0,
                "shelf_life_days": 18,
                "is_seasonal": False,
                "is_perishable": True,
            },
        ]
    ).to_csv(seed_root / "products.csv", index=False)

    for day in ("2026-01-01", "2026-01-02", "2026-01-03"):
        pd.DataFrame(
            [
                {
                    "TRANS_ID": f"{day}-1",
                    "STORE_NBR": "STR-001",
                    "ITEM_NBR": "SKU-001",
                    "UPC": "111",
                    "QTY_SOLD": 4,
                    "UNIT_PRICE": 4.25,
                    "SALE_AMT": 17.0,
                    "TRANS_DATE": day,
                    "TRANS_TIME": "09:00:00",
                    "TRANS_TYPE": "SALE",
                },
                {
                    "TRANS_ID": f"{day}-2",
                    "STORE_NBR": "STR-002",
                    "ITEM_NBR": "SKU-002",
                    "UPC": "222",
                    "QTY_SOLD": 3,
                    "UNIT_PRICE": 2.49,
                    "SALE_AMT": 7.47,
                    "TRANS_DATE": day,
                    "TRANS_TIME": "10:00:00",
                    "TRANS_TYPE": "SALE",
                },
            ]
        ).to_csv(seed_root / "transactions" / f"DAILY_SALES_{day.replace('-', '')}.csv", index=False)

    pd.DataFrame(
        [
            {
                "STORE_NBR": "STR-001",
                "ITEM_NBR": "SKU-001",
                "UPC": "111",
                "GTIN": "111",
                "ON_HAND_QTY": 20,
                "ON_ORDER_QTY": 0,
                "SNAPSHOT_DATE": "2026-01-03",
            },
            {
                "STORE_NBR": "STR-002",
                "ITEM_NBR": "SKU-002",
                "UPC": "222",
                "GTIN": "222",
                "ON_HAND_QTY": 15,
                "ON_ORDER_QTY": 2,
                "SNAPSHOT_DATE": "2026-01-03",
            },
        ]
    ).to_csv(seed_root / "inventory" / "INV_SNAPSHOT_20260103.csv", index=False)


def test_build_sample_payloads_transforms_seed_files_into_onboarding_csv(tmp_path: Path):
    _write_seed_fixture(tmp_path)

    payloads = build_sample_payloads(
        seed_root=tmp_path / "seed",
        store_limit=2,
        product_limit=2,
        history_days=3,
    )

    stores = pd.read_csv(StringIO(payloads.stores_csv))
    products = pd.read_csv(StringIO(payloads.products_csv))
    transactions = pd.read_csv(StringIO(payloads.transactions_csv))
    inventory = pd.read_csv(StringIO(payloads.inventory_csv))

    assert list(stores.columns) == ["name", "city", "state", "zip_code", "lat", "lon", "timezone"]
    assert list(products.columns) == [
        "sku",
        "name",
        "category",
        "subcategory",
        "brand",
        "unit_cost",
        "unit_price",
        "weight",
        "shelf_life_days",
        "is_seasonal",
        "is_perishable",
    ]
    assert list(transactions.columns) == [
        "date",
        "store_name",
        "sku",
        "quantity",
        "unit_price",
        "transaction_type",
        "external_id",
    ]
    assert list(inventory.columns) == [
        "timestamp",
        "store_name",
        "sku",
        "quantity_on_hand",
        "quantity_on_order",
        "quantity_reserved",
        "quantity_available",
        "source",
    ]
    assert payloads.summary["stores"] == 2
    assert payloads.summary["products"] == 2
    assert payloads.summary["transaction_rows"] == 6
    assert payloads.summary["inventory_rows"] == 2
    assert set(transactions["store_name"]) == {"Downtown", "Uptown"}
    assert set(inventory["source"]) == {"sample_bootstrap"}
