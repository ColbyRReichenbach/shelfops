"""
Prepare a deterministic local demo runtime for the live ShelfOps walkthrough.

This script pins the runtime to a known-good state so the frontend, API, and
terminal proof steps all have fresh records to show:
  - connected integrations + recent sync history
  - suggested purchase orders ready for HITL approval/rejection
  - champion/challenger model health with recent backtests
  - recent retraining, drift alerts, and experiment history

Run:
  PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings
from db.models import (
    BacktestResult,
    Customer,
    DemandForecast,
    Integration,
    IntegrationSyncLog,
    InventoryLevel,
    MLAlert,
    ModelExperiment,
    ModelRetrainingLog,
    ModelVersion,
    Product,
    PurchaseOrder,
    ReorderPoint,
    Store,
    Supplier,
    Transaction,
)

DEV_CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
MODEL_NAME = "demand_forecast"
CHAMPION_VERSION = "v_demo_champion"
CHALLENGER_VERSION = "v_demo_challenger"


def _stable_uuid(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"shelfops-demo::{name}")


def _json_default(value: Any) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Unsupported value: {type(value)!r}")


async def _upsert_customer(db: AsyncSession) -> Customer:
    customer = await db.get(Customer, DEV_CUSTOMER_ID)
    if customer is None:
        customer = Customer(
            customer_id=DEV_CUSTOMER_ID,
            name="Midwest Grocers Demo",
            email="admin@midwestgrocers.com",
            plan="professional",
            status="active",
        )
        db.add(customer)
        await db.flush()
    else:
        customer.name = "Midwest Grocers Demo"
        customer.plan = "professional"
        customer.status = "active"
    return customer


async def _upsert_supplier(db: AsyncSession, customer_id: uuid.UUID) -> Supplier:
    supplier_id = _stable_uuid("supplier::heartland")
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        supplier = Supplier(
            supplier_id=supplier_id,
            customer_id=customer_id,
            name="Heartland Distributors",
            contact_email="orders@heartland.example",
            lead_time_days=5,
            reliability_score=0.97,
            status="active",
            min_order_quantity=12,
        )
        db.add(supplier)
        await db.flush()
    else:
        supplier.customer_id = customer_id
        supplier.name = "Heartland Distributors"
        supplier.contact_email = "orders@heartland.example"
        supplier.lead_time_days = 5
        supplier.reliability_score = 0.97
        supplier.status = "active"
        supplier.min_order_quantity = 12
    return supplier


async def _upsert_stores(db: AsyncSession, customer_id: uuid.UUID) -> list[Store]:
    store_specs = [
        {
            "name": "Minneapolis Flagship",
            "city": "Minneapolis",
            "state": "MN",
            "zip_code": "55401",
            "cluster_tier": 0,
        },
        {
            "name": "Chicago Northside",
            "city": "Chicago",
            "state": "IL",
            "zip_code": "60601",
            "cluster_tier": 1,
        },
    ]
    stores: list[Store] = []
    for idx, spec in enumerate(store_specs, start=1):
        store_id = _stable_uuid(f"store::{idx}")
        store = await db.get(Store, store_id)
        if store is None:
            store = Store(
                store_id=store_id,
                customer_id=customer_id,
                status="active",
                timezone="America/Chicago",
                **spec,
            )
            db.add(store)
            await db.flush()
        else:
            store.customer_id = customer_id
            store.name = spec["name"]
            store.city = spec["city"]
            store.state = spec["state"]
            store.zip_code = spec["zip_code"]
            store.cluster_tier = spec["cluster_tier"]
            store.status = "active"
            store.timezone = "America/Chicago"
        stores.append(store)
    return stores


async def _upsert_products(
    db: AsyncSession,
    customer_id: uuid.UUID,
    supplier_id: uuid.UUID,
) -> list[Product]:
    product_specs = [
        {
            "sku": "DEMO-001",
            "name": "FreshFirst Greek Yogurt",
            "category": "Dairy",
            "brand": "FreshFirst",
            "unit_cost": 2.30,
            "unit_price": 4.99,
            "is_perishable": True,
        },
        {
            "sku": "DEMO-002",
            "name": "NatureBest Sparkling Water",
            "category": "Beverages",
            "brand": "NatureBest",
            "unit_cost": 0.85,
            "unit_price": 1.99,
            "is_perishable": False,
        },
        {
            "sku": "DEMO-003",
            "name": "ValuePack Tortilla Chips",
            "category": "Snacks",
            "brand": "ValuePack",
            "unit_cost": 1.75,
            "unit_price": 3.79,
            "is_perishable": False,
        },
        {
            "sku": "DEMO-004",
            "name": "GreenHarvest Romaine Hearts",
            "category": "Produce",
            "brand": "GreenHarvest",
            "unit_cost": 1.55,
            "unit_price": 3.49,
            "is_perishable": True,
        },
    ]

    products: list[Product] = []
    for idx, spec in enumerate(product_specs, start=1):
        product_id = _stable_uuid(f"product::{idx}")
        product = await db.get(Product, product_id)
        if product is None:
            product = Product(
                product_id=product_id,
                customer_id=customer_id,
                supplier_id=supplier_id,
                status="active",
                lifecycle_state="active",
                **spec,
            )
            db.add(product)
            await db.flush()
        else:
            product.customer_id = customer_id
            product.supplier_id = supplier_id
            product.sku = spec["sku"]
            product.name = spec["name"]
            product.category = spec["category"]
            product.brand = spec["brand"]
            product.unit_cost = spec["unit_cost"]
            product.unit_price = spec["unit_price"]
            product.is_perishable = spec["is_perishable"]
            product.status = "active"
            product.lifecycle_state = "active"
        products.append(product)
    return products


async def _upsert_inventory_positions(
    db: AsyncSession,
    customer_id: uuid.UUID,
    stores: list[Store],
    products: list[Product],
    supplier: Supplier,
    now: datetime,
) -> None:
    inventory_targets = {
        products[0].product_id: 14,
        products[1].product_id: 48,
        products[2].product_id: 29,
        products[3].product_id: 11,
    }
    reorder_targets = {
        products[0].product_id: (22, 10, 60),
        products[1].product_id: (30, 12, 72),
        products[2].product_id: (26, 8, 54),
        products[3].product_id: (18, 9, 42),
    }

    for store in stores:
        for product in products:
            inv_id = _stable_uuid(f"inventory::{store.store_id}::{product.product_id}")
            inventory = await db.get(InventoryLevel, inv_id)
            on_hand = inventory_targets[product.product_id]
            if inventory is None:
                inventory = InventoryLevel(
                    id=inv_id,
                    customer_id=customer_id,
                    store_id=store.store_id,
                    product_id=product.product_id,
                    timestamp=now - timedelta(minutes=8),
                    quantity_on_hand=on_hand,
                    quantity_available=on_hand,
                    quantity_on_order=0,
                )
                db.add(inventory)
            else:
                inventory.customer_id = customer_id
                inventory.store_id = store.store_id
                inventory.product_id = product.product_id
                inventory.timestamp = now - timedelta(minutes=8)
                inventory.quantity_on_hand = on_hand
                inventory.quantity_available = on_hand
                inventory.quantity_on_order = 0

            reorder_id = _stable_uuid(f"reorder::{store.store_id}::{product.product_id}")
            reorder_point = await db.get(ReorderPoint, reorder_id)
            rp, safety, eoq = reorder_targets[product.product_id]
            if reorder_point is None:
                reorder_point = ReorderPoint(
                    id=reorder_id,
                    customer_id=customer_id,
                    store_id=store.store_id,
                    product_id=product.product_id,
                    reorder_point=rp,
                    safety_stock=safety,
                    economic_order_qty=eoq,
                    lead_time_days=supplier.lead_time_days,
                )
                db.add(reorder_point)
            else:
                reorder_point.customer_id = customer_id
                reorder_point.store_id = store.store_id
                reorder_point.product_id = product.product_id
                reorder_point.reorder_point = rp
                reorder_point.safety_stock = safety
                reorder_point.economic_order_qty = eoq
                reorder_point.lead_time_days = supplier.lead_time_days


async def _seed_recent_transactions(
    db: AsyncSession,
    customer_id: uuid.UUID,
    stores: list[Store],
    products: list[Product],
    now: datetime,
) -> None:
    await db.execute(
        delete(Transaction).where(
            Transaction.customer_id == customer_id,
            Transaction.external_id.like("demo-runtime-%"),
        )
    )

    offsets = [
        (stores[0], products[0], 2, 55),
        (stores[0], products[1], 4, 45),
        (stores[1], products[2], 3, 32),
        (stores[1], products[3], 5, 18),
    ]
    for idx, (store, product, qty, minutes_ago) in enumerate(offsets, start=1):
        sold_at = now - timedelta(minutes=minutes_ago)
        db.add(
            Transaction(
                transaction_id=_stable_uuid(f"transaction::{idx}"),
                customer_id=customer_id,
                store_id=store.store_id,
                product_id=product.product_id,
                timestamp=sold_at,
                quantity=qty,
                unit_price=float(product.unit_price or 0),
                total_amount=round(float(product.unit_price or 0) * qty, 2),
                transaction_type="sale",
                external_id=f"demo-runtime-{idx}",
            )
        )


async def _seed_forecasts(
    db: AsyncSession,
    customer_id: uuid.UUID,
    stores: list[Store],
    products: list[Product],
    now: datetime,
) -> None:
    await db.execute(
        delete(DemandForecast).where(
            DemandForecast.customer_id == customer_id,
            DemandForecast.model_version.in_([CHAMPION_VERSION, CHALLENGER_VERSION]),
        )
    )

    base_by_product = {
        products[0].product_id: 18.0,
        products[1].product_id: 27.0,
        products[2].product_id: 21.0,
        products[3].product_id: 14.0,
    }

    for version, bias in ((CHAMPION_VERSION, 0.0), (CHALLENGER_VERSION, -0.6)):
        for store_idx, store in enumerate(stores):
            for product_idx, product in enumerate(products):
                base = base_by_product[product.product_id] + store_idx * 2 + product_idx
                for day_offset in range(14):
                    forecast_date = now.date() + timedelta(days=day_offset)
                    demand = base + (day_offset % 4) + bias
                    confidence = max(0.65, 0.94 - (day_offset * 0.02))
                    margin = max(1.5, demand * (1 - confidence))
                    db.add(
                        DemandForecast(
                            forecast_id=_stable_uuid(
                                f"forecast::{version}::{store.store_id}::{product.product_id}::{forecast_date.isoformat()}"
                            ),
                            customer_id=customer_id,
                            store_id=store.store_id,
                            product_id=product.product_id,
                            forecast_date=forecast_date,
                            forecasted_demand=round(demand, 2),
                            lower_bound=round(max(0.0, demand - margin), 2),
                            upper_bound=round(demand + margin, 2),
                            confidence=round(confidence, 2),
                            model_version=version,
                        )
                    )


async def _seed_model_state(
    db: AsyncSession,
    customer_id: uuid.UUID,
    now: datetime,
) -> dict[str, ModelVersion]:
    await db.execute(
        update(ModelVersion)
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == MODEL_NAME,
            ModelVersion.version.notin_([CHAMPION_VERSION, CHALLENGER_VERSION]),
            ModelVersion.status.in_(["champion", "challenger"]),
        )
        .values(status="archived", archived_at=now)
    )

    target_versions = {
        CHAMPION_VERSION: {
            "status": "champion",
            "routing_weight": 1.0,
            "promoted_at": now - timedelta(days=2),
            "metrics": {
                "mae": 11.4,
                "mape": 0.162,
                "coverage": 0.91,
                "stockout_miss_rate": 0.061,
                "overstock_rate": 0.188,
            },
        },
        CHALLENGER_VERSION: {
            "status": "challenger",
            "routing_weight": 0.0,
            "promoted_at": None,
            "metrics": {
                "mae": 11.1,
                "mape": 0.156,
                "coverage": 0.92,
                "stockout_miss_rate": 0.057,
                "overstock_rate": 0.181,
            },
        },
    }

    versions: dict[str, ModelVersion] = {}
    for version_name, spec in target_versions.items():
        model_id = _stable_uuid(f"model::{version_name}")
        version = await db.get(ModelVersion, model_id)
        if version is None:
            version = ModelVersion(
                model_id=model_id,
                customer_id=customer_id,
                model_name=MODEL_NAME,
                version=version_name,
                smoke_test_passed=True,
                created_at=now - timedelta(days=6 if version_name == CHAMPION_VERSION else 1),
                **spec,
            )
            db.add(version)
            await db.flush()
        else:
            version.customer_id = customer_id
            version.model_name = MODEL_NAME
            version.version = version_name
            version.status = spec["status"]
            version.routing_weight = spec["routing_weight"]
            version.promoted_at = spec["promoted_at"]
            version.metrics = spec["metrics"]
            version.smoke_test_passed = True
        versions[version_name] = version

    await db.execute(
        delete(BacktestResult).where(
            BacktestResult.customer_id == customer_id,
            BacktestResult.model_id.in_([versions[CHAMPION_VERSION].model_id, versions[CHALLENGER_VERSION].model_id]),
        )
    )

    champion_curve = [12.8, 12.6, 12.5, 12.2, 12.0, 11.9, 11.8, 11.7, 11.6, 11.4, 11.3, 11.2, 11.1, 11.0]
    challenger_curve = [12.3, 12.1, 11.9, 11.8, 11.6, 11.5, 11.4, 11.2, 11.1, 10.9, 10.8, 10.7, 10.7, 10.6]
    curves = {
        CHAMPION_VERSION: champion_curve,
        CHALLENGER_VERSION: challenger_curve,
    }

    for version_name, curve in curves.items():
        model = versions[version_name]
        for day_index, mae in enumerate(curve):
            forecast_day = now.date() - timedelta(days=len(curve) - day_index)
            db.add(
                BacktestResult(
                    backtest_id=_stable_uuid(f"backtest::{version_name}::{forecast_day.isoformat()}"),
                    customer_id=customer_id,
                    model_id=model.model_id,
                    forecast_date=forecast_day,
                    actual_date=forecast_day + timedelta(days=1),
                    mae=mae,
                    mape=round(mae / 70, 3),
                    stockout_miss_rate=round(0.07 - (day_index * 0.001), 3),
                    overstock_rate=round(0.22 - (day_index * 0.002), 3),
                    evaluated_at=now - timedelta(hours=4),
                )
            )

    retrain_id = _stable_uuid("retrain::latest")
    retrain = await db.get(ModelRetrainingLog, retrain_id)
    retrain_started = now - timedelta(hours=2, minutes=15)
    retrain_completed = now - timedelta(hours=2)
    retrain_metadata = {
        "drift_pct": 0.17,
        "rows_replayed": 12480,
        "business_trigger": "weekly_demo_reset",
    }
    if retrain is None:
        retrain = ModelRetrainingLog(
            retrain_id=retrain_id,
            customer_id=customer_id,
            model_name=MODEL_NAME,
            trigger_type="drift",
            trigger_metadata=retrain_metadata,
            status="completed",
            version_produced=CHALLENGER_VERSION,
            started_at=retrain_started,
            completed_at=retrain_completed,
        )
        db.add(retrain)
    else:
        retrain.customer_id = customer_id
        retrain.model_name = MODEL_NAME
        retrain.trigger_type = "drift"
        retrain.trigger_metadata = retrain_metadata
        retrain.status = "completed"
        retrain.version_produced = CHALLENGER_VERSION
        retrain.started_at = retrain_started
        retrain.completed_at = retrain_completed

    return versions


async def _seed_ml_alerts(db: AsyncSession, customer_id: uuid.UUID, now: datetime) -> list[MLAlert]:
    alert_specs = [
        {
            "id": _stable_uuid("alert::drift"),
            "alert_type": "drift_detected",
            "severity": "critical",
            "title": "Demo drift event requires review",
            "message": "Forecast MAE degraded 17% on the seeded monitoring slice; retrain completed and challenger is ready for review.",
            "action_url": "/mlops/models",
            "alert_metadata": {
                "model_name": MODEL_NAME,
                "drift_pct": 0.17,
                "trigger_type": "drift",
                "version_produced": CHALLENGER_VERSION,
            },
        },
        {
            "id": _stable_uuid("alert::promotion"),
            "alert_type": "promotion_pending",
            "severity": "warning",
            "title": "Demo challenger promotion pending",
            "message": "Shadow evaluation shows non-regression with lower stockout miss rate; operator approval is still required.",
            "action_url": "/mlops/experiments",
            "alert_metadata": {
                "champion_version": CHAMPION_VERSION,
                "challenger_version": CHALLENGER_VERSION,
                "action_required": "review_and_promote",
            },
        },
    ]

    alerts: list[MLAlert] = []
    for idx, spec in enumerate(alert_specs, start=1):
        alert = await db.get(MLAlert, spec["id"])
        created_at = now - timedelta(minutes=idx * 11)
        if alert is None:
            alert = MLAlert(
                ml_alert_id=spec["id"],
                customer_id=customer_id,
                status="unread",
                created_at=created_at,
                **{k: v for k, v in spec.items() if k != "id"},
            )
            db.add(alert)
        else:
            alert.customer_id = customer_id
            alert.alert_type = spec["alert_type"]
            alert.severity = spec["severity"]
            alert.title = spec["title"]
            alert.message = spec["message"]
            alert.action_url = spec["action_url"]
            alert.alert_metadata = spec["alert_metadata"]
            alert.status = "unread"
            alert.created_at = created_at
            alert.read_at = None
            alert.actioned_at = None
        alerts.append(alert)
    return alerts


async def _seed_experiment(db: AsyncSession, customer_id: uuid.UUID, now: datetime) -> ModelExperiment:
    experiment_id = _stable_uuid("experiment::department-segmentation")
    experiment = await db.get(ModelExperiment, experiment_id)
    payload = {
        "experiment_name": "Department segmentation trial",
        "hypothesis": "Category segmentation improves volatile demand fit without increasing overstock.",
        "experiment_type": "segmentation",
        "model_name": MODEL_NAME,
        "baseline_version": CHAMPION_VERSION,
        "experimental_version": CHALLENGER_VERSION,
        "status": "completed",
        "proposed_by": "demo@shelfops.com",
        "approved_by": "ops-manager@shelfops.com",
        "results": {
            "baseline_mae": 11.4,
            "experimental_mae": 11.1,
            "improvement_pct": 2.63,
            "stockout_miss_rate_delta": -0.004,
            "decision": "continue_shadow_review",
        },
        "decision_rationale": "Non-regression is proven, but promotion still requires operator sign-off in the demo governance flow.",
        "created_at": now - timedelta(days=1, hours=2),
        "approved_at": now - timedelta(days=1, hours=1, minutes=15),
        "completed_at": now - timedelta(hours=6),
    }
    if experiment is None:
        experiment = ModelExperiment(experiment_id=experiment_id, customer_id=customer_id, **payload)
        db.add(experiment)
    else:
        experiment.customer_id = customer_id
        for key, value in payload.items():
            setattr(experiment, key, value)
    return experiment


async def _seed_integrations(db: AsyncSession, customer_id: uuid.UUID, now: datetime) -> list[Integration]:
    integration_specs = [
        {
            "id": _stable_uuid("integration::square"),
            "provider": "square",
            "integration_type": "rest_api",
            "merchant_id": "demo-square-merchant",
            "status": "connected",
            "config": {"location_scope": "all", "demo_mode": True},
            "last_sync_at": now - timedelta(minutes=18),
        },
        {
            "id": _stable_uuid("integration::kafka"),
            "provider": "kafka",
            "integration_type": "event_stream",
            "merchant_id": None,
            "status": "connected",
            "config": {
                "broker_type": "kafka",
                "bootstrap_servers": "localhost:9092",
                "topics": {
                    "transactions": "pos.transactions.completed",
                    "inventory": "inventory.adjustments",
                },
                "consumer_group": "shelfops-demo",
            },
            "last_sync_at": now - timedelta(minutes=28),
        },
        {
            "id": _stable_uuid("integration::edi"),
            "provider": "custom_edi",
            "integration_type": "edi",
            "merchant_id": None,
            "status": "connected",
            "config": {"trading_partner": "demo-distributor", "document_types": ["846", "850", "856", "810"]},
            "last_sync_at": now - timedelta(hours=4),
        },
        {
            "id": _stable_uuid("integration::sftp"),
            "provider": "custom_sftp",
            "integration_type": "sftp",
            "merchant_id": None,
            "status": "connected",
            "config": {"path": "/dropbox/catalog", "file_pattern": "catalog_*.csv"},
            "last_sync_at": now - timedelta(hours=9),
        },
    ]

    integrations: list[Integration] = []
    for spec in integration_specs:
        integration = await db.get(Integration, spec["id"])
        if integration is None:
            integration = Integration(
                integration_id=spec["id"],
                customer_id=customer_id,
                provider=spec["provider"],
                integration_type=spec["integration_type"],
                merchant_id=spec["merchant_id"],
                status=spec["status"],
                config=spec["config"],
                last_sync_at=spec["last_sync_at"],
            )
            db.add(integration)
            await db.flush()
        else:
            integration.customer_id = customer_id
            integration.provider = spec["provider"]
            integration.integration_type = spec["integration_type"]
            integration.merchant_id = spec["merchant_id"]
            integration.status = spec["status"]
            integration.config = spec["config"]
            integration.last_sync_at = spec["last_sync_at"]
        integrations.append(integration)
    return integrations


async def _seed_sync_logs(db: AsyncSession, customer_id: uuid.UUID, now: datetime) -> list[IntegrationSyncLog]:
    log_specs = [
        {
            "id": _stable_uuid("sync::square::recent"),
            "integration_type": "POS",
            "integration_name": "Square POS",
            "sync_type": "transactions",
            "records_synced": 1248,
            "sync_status": "success",
            "started_at": now - timedelta(minutes=18),
            "completed_at": now - timedelta(minutes=17, seconds=48),
            "error_message": None,
            "sync_metadata": {"duration_sec": 12.0, "batch_id": "sq-demo-01"},
        },
        {
            "id": _stable_uuid("sync::edi::recent"),
            "integration_type": "EDI",
            "integration_name": "EDI 846 Inventory",
            "sync_type": "inventory",
            "records_synced": 7422,
            "sync_status": "success",
            "started_at": now - timedelta(hours=4),
            "completed_at": now - timedelta(hours=3, minutes=58),
            "error_message": None,
            "sync_metadata": {"duration_sec": 118.0, "batch_id": "edi-demo-01"},
        },
        {
            "id": _stable_uuid("sync::sftp::recent"),
            "integration_type": "SFTP",
            "integration_name": "SFTP Product Catalog",
            "sync_type": "products",
            "records_synced": 428,
            "sync_status": "success",
            "started_at": now - timedelta(hours=9),
            "completed_at": now - timedelta(hours=8, minutes=59, seconds=20),
            "error_message": None,
            "sync_metadata": {"duration_sec": 40.0, "batch_id": "sftp-demo-01"},
        },
        {
            "id": _stable_uuid("sync::kafka::recent"),
            "integration_type": "Kafka",
            "integration_name": "Kafka Store Transfers",
            "sync_type": "transfers",
            "records_synced": 37,
            "sync_status": "success",
            "started_at": now - timedelta(minutes=28),
            "completed_at": now - timedelta(minutes=27, seconds=55),
            "error_message": None,
            "sync_metadata": {"duration_sec": 5.0, "batch_id": "kafka-demo-02"},
        },
        {
            "id": _stable_uuid("sync::kafka::partial"),
            "integration_type": "Kafka",
            "integration_name": "Kafka Store Transfers",
            "sync_type": "transfers",
            "records_synced": 9,
            "sync_status": "partial",
            "started_at": now - timedelta(hours=7),
            "completed_at": now - timedelta(hours=6, minutes=59),
            "error_message": "Kafka consumer lag exceeded threshold (5000 messages)",
            "sync_metadata": {"duration_sec": 11.0, "batch_id": "kafka-demo-01"},
        },
    ]

    logs: list[IntegrationSyncLog] = []
    for spec in log_specs:
        log = await db.get(IntegrationSyncLog, spec["id"])
        if log is None:
            log = IntegrationSyncLog(sync_id=spec["id"], customer_id=customer_id, **{k: v for k, v in spec.items() if k != "id"})
            db.add(log)
        else:
            log.customer_id = customer_id
            for key, value in spec.items():
                if key != "id":
                    setattr(log, key, value)
        logs.append(log)
    return logs


async def _seed_purchase_orders(
    db: AsyncSession,
    customer_id: uuid.UUID,
    stores: list[Store],
    products: list[Product],
    supplier_id: uuid.UUID,
    now: datetime,
) -> list[PurchaseOrder]:
    po_specs = [
        {
            "id": _stable_uuid("po::approve"),
            "label": "approve_path",
            "store": stores[0],
            "product": products[0],
            "quantity": 84,
            "minutes_ago": 6,
        },
        {
            "id": _stable_uuid("po::reject"),
            "label": "reject_path",
            "store": stores[1],
            "product": products[3],
            "quantity": 52,
            "minutes_ago": 5,
        },
        {
            "id": _stable_uuid("po::edit"),
            "label": "edit_path",
            "store": stores[0],
            "product": products[2],
            "quantity": 66,
            "minutes_ago": 4,
        },
    ]

    purchase_orders: list[PurchaseOrder] = []
    for spec in po_specs:
        po = await db.get(PurchaseOrder, spec["id"])
        product = spec["product"]
        estimated_cost = round(float(product.unit_cost or 0) * spec["quantity"], 2)
        if po is None:
            po = PurchaseOrder(
                po_id=spec["id"],
                customer_id=customer_id,
                store_id=spec["store"].store_id,
                product_id=product.product_id,
                supplier_id=supplier_id,
                quantity=spec["quantity"],
                estimated_cost=estimated_cost,
                status="suggested",
                suggested_at=now - timedelta(minutes=spec["minutes_ago"]),
                expected_delivery=(now + timedelta(days=5)).date(),
                source_type="vendor_direct",
                source_id=supplier_id,
                promised_delivery_date=(now + timedelta(days=5)).date(),
                received_qty=None,
            )
            db.add(po)
        else:
            po.customer_id = customer_id
            po.store_id = spec["store"].store_id
            po.product_id = product.product_id
            po.supplier_id = supplier_id
            po.quantity = spec["quantity"]
            po.estimated_cost = estimated_cost
            po.status = "suggested"
            po.suggested_at = now - timedelta(minutes=spec["minutes_ago"])
            po.ordered_at = None
            po.expected_delivery = (now + timedelta(days=5)).date()
            po.received_at = None
            po.source_type = "vendor_direct"
            po.source_id = supplier_id
            po.promised_delivery_date = (now + timedelta(days=5)).date()
            po.actual_delivery_date = None
            po.received_qty = None
            po.total_received_cost = None
            po.receiving_notes = None
        purchase_orders.append(po)
    return purchase_orders


async def build_demo_runtime(
    db: AsyncSession,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = as_of or datetime.utcnow()
    customer = await _upsert_customer(db)
    supplier = await _upsert_supplier(db, customer.customer_id)
    stores = await _upsert_stores(db, customer.customer_id)
    products = await _upsert_products(db, customer.customer_id, supplier.supplier_id)
    await _upsert_inventory_positions(db, customer.customer_id, stores, products, supplier, now)
    await _seed_recent_transactions(db, customer.customer_id, stores, products, now)
    await _seed_forecasts(db, customer.customer_id, stores, products, now)
    model_versions = await _seed_model_state(db, customer.customer_id, now)
    alerts = await _seed_ml_alerts(db, customer.customer_id, now)
    experiment = await _seed_experiment(db, customer.customer_id, now)
    integrations = await _seed_integrations(db, customer.customer_id, now)
    sync_logs = await _seed_sync_logs(db, customer.customer_id, now)
    purchase_orders = await _seed_purchase_orders(
        db,
        customer.customer_id,
        stores,
        products,
        supplier.supplier_id,
        now,
    )
    await db.commit()

    po_targets = {
        "approve_path": str(_stable_uuid("po::approve")),
        "reject_path": str(_stable_uuid("po::reject")),
        "edit_path": str(_stable_uuid("po::edit")),
    }
    summary = {
        "status": "success",
        "prepared_at": now,
        "customer_id": customer.customer_id,
        "customer_name": customer.name,
        "terminal_showcase": {
            "summary_json": "docs/productization_artifacts/demo_runtime/demo_runtime_summary.json",
            "command": "PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py",
        },
        "purchase_orders": {
            "suggested_count": len(purchase_orders),
            "targets": po_targets,
        },
        "mlops": {
            "champion_version": model_versions[CHAMPION_VERSION].version,
            "challenger_version": model_versions[CHALLENGER_VERSION].version,
            "last_retrain_trigger": "drift",
            "alerts_seeded": [alert.alert_type for alert in alerts],
            "experiment_id": str(experiment.experiment_id),
        },
        "integrations": {
            "providers": [integration.provider for integration in integrations],
            "sync_sources": sorted({log.integration_name for log in sync_logs}),
        },
        "recommended_calls": {
            "health": "curl -s http://localhost:8000/health | jq",
            "sync_health": "curl -s http://localhost:8000/api/v1/integrations/sync-health | jq",
            "suggested_pos": "curl -s http://localhost:8000/api/v1/purchase-orders/suggested | jq",
            "model_health": "curl -s http://localhost:8000/api/v1/ml/models/health | jq",
            "ml_alerts": "curl -s 'http://localhost:8000/ml-alerts?limit=5' | jq",
            "approve_po": (
                f"curl -s -X POST http://localhost:8000/api/v1/purchase-orders/{po_targets['approve_path']}/approve "
                "-H 'Content-Type: application/json' -d '{}'"
            ),
            "reject_po": (
                f"curl -s -X POST http://localhost:8000/api/v1/purchase-orders/{po_targets['reject_path']}/reject "
                "-H 'Content-Type: application/json' "
                "-d '{\"reason_code\":\"forecast_disagree\",\"notes\":\"Demo rejection path\"}'"
            ),
            "edit_and_approve_po": (
                f"curl -s -X POST http://localhost:8000/api/v1/purchase-orders/{po_targets['edit_path']}/approve "
                "-H 'Content-Type: application/json' "
                "-d '{\"quantity\":54,\"reason_code\":\"budget_constraint\",\"notes\":\"Demo edited quantity\"}'"
            ),
            "propose_experiment": (
                "curl -s -X POST http://localhost:8000/experiments "
                "-H 'Content-Type: application/json' "
                "-d '{\"experiment_name\":\"Promo uplift feature trial\","
                "\"hypothesis\":\"Promo-aware features reduce demand bias on promoted SKUs\","
                "\"experiment_type\":\"feature_engineering\","
                "\"model_name\":\"demand_forecast\","
                "\"proposed_by\":\"demo@shelfops.com\"}'"
            ),
        },
    }
    return summary


async def prepare_demo_runtime(output_json: Path) -> dict[str, Any]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            payload = await build_demo_runtime(db)
    finally:
        await engine.dispose()

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare deterministic runtime state for the ShelfOps live demo.")
    parser.add_argument(
        "--output-json",
        default="docs/productization_artifacts/demo_runtime/demo_runtime_summary.json",
        help="Where to write the runtime summary JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = asyncio.run(prepare_demo_runtime(Path(args.output_json)))
    print(json.dumps(payload, indent=2, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
