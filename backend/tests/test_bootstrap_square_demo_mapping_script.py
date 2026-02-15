from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Customer, Product, Store
from db.session import Base

CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _seed_minimal_customer(db_url: str) -> tuple[str, str]:
    engine = create_async_engine(db_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as db:
            customer = Customer(
                customer_id=CUSTOMER_ID,
                name="Demo Customer",
                email="demo-customer@shelfops.test",
                plan="professional",
            )
            db.add(customer)
            await db.flush()

            store = Store(
                customer_id=CUSTOMER_ID,
                name="Demo Store",
                city="Minneapolis",
                state="MN",
                zip_code="55401",
            )
            db.add(store)
            await db.flush()

            product = Product(
                customer_id=CUSTOMER_ID,
                sku="DEMO-SKU-001",
                name="Demo Product",
                category="Dairy",
            )
            db.add(product)
            await db.flush()
            await db.commit()
            return str(store.store_id), str(product.product_id)
    finally:
        await engine.dispose()


def _parse_json_output(stdout: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_bootstrap_square_demo_mapping_script_creates_and_is_idempotent(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "backend" / "scripts" / "bootstrap_square_demo_mapping.py"
    db_path = tmp_path / "demo_bootstrap.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    seeded_store_id, seeded_product_id = asyncio.run(_seed_minimal_customer(db_url))

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["APP_ENV"] = "test"

    cmd = [
        sys.executable,
        str(script_path),
        "--customer-id",
        str(CUSTOMER_ID),
        "--seed-demo-mappings",
    ]

    first = subprocess.run(cmd, cwd=str(repo_root), env=env, capture_output=True, text=True, check=True)
    first_payload = _parse_json_output(first.stdout)
    assert first_payload["status"] == "success"
    assert first_payload["created_integration"] is True
    assert first_payload["synthesis_enabled"] is True
    assert first_payload["store_mapping_count"] == 1
    assert first_payload["product_mapping_count"] == 1
    assert set(first_payload["changed_keys"]) == {
        "square_catalog_to_product",
        "square_location_to_store",
        "square_synthesize_demo_mappings",
    }

    second = subprocess.run(cmd, cwd=str(repo_root), env=env, capture_output=True, text=True, check=True)
    second_payload = _parse_json_output(second.stdout)
    assert second_payload["status"] == "success"
    assert second_payload["created_integration"] is False
    assert second_payload["changed_keys"] == []
    assert second_payload["integration_id"] == first_payload["integration_id"]

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT provider, config FROM integrations WHERE customer_id = ?",
            (str(CUSTOMER_ID),),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    provider, raw_config = row
    assert provider == "square"
    config = json.loads(raw_config)
    assert config["square_synthesize_demo_mappings"] is True
    assert set(config["square_location_to_store"].values()) == {seeded_store_id}
    assert set(config["square_catalog_to_product"].values()) == {seeded_product_id}
