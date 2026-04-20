from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_sources.csv_onboarding import ingest_csv_batch
from db.models import (
    Alert,
    BacktestResult,
    DemandForecast,
    ForecastAccuracy,
    IntegrationSyncLog,
    InventoryLevel,
    ModelRetrainingLog,
    ModelVersion,
    Product,
    ReorderPoint,
    RecommendationOutcome,
    ReplenishmentRecommendation,
    Store,
    Supplier,
    Transaction,
)
from ml.readiness import ReadinessThresholds, evaluate_and_persist_tenant_readiness
from recommendations.service import RecommendationService
from scripts.production_tenant import PRODUCTION_CUSTOMER_ID, ensure_production_tenant

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_ROOT = REPO_ROOT / "data" / "seed"
DEFAULT_MODEL_VERSION = "v3"


@dataclass(frozen=True)
class CsvPayloadBundle:
    stores_csv: str
    products_csv: str
    transactions_csv: str
    inventory_csv: str
    summary: dict[str, Any]


def _sorted_csv_files(directory: Path, pattern: str) -> list[Path]:
    files = sorted(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No seed CSV files found in {directory} matching {pattern}")
    return files


def _render_csv(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        raise ValueError("Cannot render onboarding CSV from an empty frame")
    return frame.loc[:, columns].to_csv(index=False)


def build_sample_payloads(
    *,
    seed_root: Path = SEED_ROOT,
    store_limit: int = 2,
    product_limit: int = 6,
    history_days: int = 120,
) -> CsvPayloadBundle:
    stores_source = pd.read_csv(seed_root / "stores.csv").head(store_limit).copy()
    products_source = pd.read_csv(seed_root / "products.csv").head(product_limit).copy()

    if stores_source.empty or products_source.empty:
        raise ValueError("Seed source must contain at least one store and one product")

    transaction_files = _sorted_csv_files(seed_root / "transactions", "DAILY_SALES_*.csv")
    inventory_files = _sorted_csv_files(seed_root / "inventory", "INV_SNAPSHOT_*.csv")
    chosen_transaction_files = transaction_files[-min(history_days, len(transaction_files)) :]
    target_dates = pd.date_range(
        end=pd.Timestamp(date.today() - timedelta(days=1)),
        periods=len(chosen_transaction_files),
        freq="D",
    )

    selected_store_codes = set(stores_source["external_code"].astype(str))
    selected_skus = set(products_source["sku"].astype(str))
    store_name_map = dict(zip(stores_source["external_code"], stores_source["name"], strict=False))

    transaction_frames: list[pd.DataFrame] = []
    for csv_path, target_date in zip(chosen_transaction_files, target_dates, strict=False):
        frame = pd.read_csv(csv_path)
        filtered = frame[
            frame["STORE_NBR"].astype(str).isin(selected_store_codes)
            & frame["ITEM_NBR"].astype(str).isin(selected_skus)
            & (frame["TRANS_TYPE"].astype(str).str.upper() == "SALE")
        ].copy()
        if filtered.empty:
            continue

        filtered["date"] = target_date.date().isoformat()
        filtered["store_name"] = filtered["STORE_NBR"].map(store_name_map)
        filtered["sku"] = filtered["ITEM_NBR"].astype(str)
        filtered["quantity"] = filtered["QTY_SOLD"].astype(float)
        filtered["unit_price"] = filtered["UNIT_PRICE"].astype(float)
        filtered["transaction_type"] = "sale"
        filtered["external_id"] = filtered["TRANS_ID"].astype(str)
        transaction_frames.append(filtered)

    if not transaction_frames:
        raise ValueError("No transaction rows matched the selected store and product subset")

    transactions_frame = pd.concat(transaction_frames, ignore_index=True)
    inventory_source = pd.read_csv(inventory_files[-1])
    inventory_frame = inventory_source[
        inventory_source["STORE_NBR"].astype(str).isin(selected_store_codes)
        & inventory_source["ITEM_NBR"].astype(str).isin(selected_skus)
    ].copy()
    if inventory_frame.empty:
        raise ValueError("No inventory rows matched the selected store and product subset")

    inventory_frame["timestamp"] = datetime.utcnow().replace(microsecond=0).isoformat()
    inventory_frame["store_name"] = inventory_frame["STORE_NBR"].map(store_name_map)
    inventory_frame["sku"] = inventory_frame["ITEM_NBR"].astype(str)
    inventory_frame["quantity_on_hand"] = inventory_frame["ON_HAND_QTY"].astype(float)
    inventory_frame["quantity_on_order"] = inventory_frame["ON_ORDER_QTY"].astype(float)
    inventory_frame["quantity_reserved"] = 0
    inventory_frame["quantity_available"] = inventory_frame["ON_HAND_QTY"].astype(float)
    inventory_frame["source"] = "sample_bootstrap"

    summary = {
        "stores": len(stores_source),
        "products": len(products_source),
        "transaction_rows": int(len(transactions_frame)),
        "inventory_rows": int(len(inventory_frame)),
        "history_days": int(transactions_frame["date"].nunique()),
        "store_names": stores_source["name"].tolist(),
        "skus": products_source["sku"].tolist(),
    }

    return CsvPayloadBundle(
        stores_csv=_render_csv(
            stores_source,
            ["name", "city", "state", "zip_code", "lat", "lon", "timezone"],
        ),
        products_csv=_render_csv(
            products_source,
            [
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
            ],
        ),
        transactions_csv=_render_csv(
            transactions_frame,
            ["date", "store_name", "sku", "quantity", "unit_price", "transaction_type", "external_id"],
        ),
        inventory_csv=_render_csv(
            inventory_frame,
            [
                "timestamp",
                "store_name",
                "sku",
                "quantity_on_hand",
                "quantity_on_order",
                "quantity_reserved",
                "quantity_available",
                "source",
            ],
        ),
        summary=summary,
    )


async def _load_daily_sales(db: AsyncSession, *, customer_id) -> pd.DataFrame:
    result = await db.execute(
        select(
            func.date(Transaction.timestamp).label("sales_date"),
            Transaction.store_id,
            Transaction.product_id,
            func.sum(Transaction.quantity).label("quantity"),
        )
        .where(
            Transaction.customer_id == customer_id,
            Transaction.transaction_type == "sale",
        )
        .group_by(func.date(Transaction.timestamp), Transaction.store_id, Transaction.product_id)
        .order_by(func.date(Transaction.timestamp).asc())
    )
    rows = result.all()
    return pd.DataFrame(
        [
            {
                "sales_date": row.sales_date,
                "store_id": row.store_id,
                "product_id": row.product_id,
                "quantity": float(row.quantity or 0.0),
            }
            for row in rows
        ]
    )


def _velocity_summary(daily_sales: pd.DataFrame, *, lookback_days: int = 35) -> dict[tuple[Any, Any], dict[str, float]]:
    if daily_sales.empty:
        return {}

    frame = daily_sales.copy()
    frame["sales_date"] = pd.to_datetime(frame["sales_date"])
    cutoff = frame["sales_date"].max() - pd.Timedelta(days=lookback_days - 1)
    recent = frame[frame["sales_date"] >= cutoff]
    summary: dict[tuple[Any, Any], dict[str, float]] = {}
    for (store_id, product_id), group in recent.groupby(["store_id", "product_id"]):
        actual = group["quantity"].astype(float)
        avg_daily = float(actual.mean()) if len(actual) else 0.0
        std_daily = float(actual.std(ddof=0)) if len(actual) else 0.0
        summary[(store_id, product_id)] = {
            "avg_daily": max(avg_daily, 1.0),
            "std_daily": max(std_daily, 0.8),
        }
    return summary


async def _ensure_supplier(db: AsyncSession, *, customer_id) -> Supplier:
    result = await db.execute(
        select(Supplier).where(
            Supplier.customer_id == customer_id,
            Supplier.name == "Northstar Wholesale",
        )
    )
    supplier = result.scalar_one_or_none()
    if supplier is None:
        supplier = Supplier(
            customer_id=customer_id,
            name="Northstar Wholesale",
            contact_email="orders@northstarwholesale.example",
            lead_time_days=4,
            min_order_quantity=12,
            reliability_score=0.97,
            cost_per_order=26.0,
            lead_time_variance=1.1,
            on_time_delivery_rate=0.96,
            avg_lead_time_actual=4.2,
            status="active",
        )
        db.add(supplier)
        await db.flush()
    return supplier


async def _apply_store_and_product_defaults(db: AsyncSession, *, customer_id, supplier: Supplier) -> None:
    stores = (
        await db.execute(select(Store).where(Store.customer_id == customer_id).order_by(Store.name.asc()))
    ).scalars().all()
    for idx, store in enumerate(stores):
        store.cluster_tier = 0 if idx == 0 else 1
        store.status = "active"

    products = (
        await db.execute(select(Product).where(Product.customer_id == customer_id).order_by(Product.sku.asc()))
    ).scalars().all()
    for idx, product in enumerate(products):
        product.supplier_id = supplier.supplier_id
        product.holding_cost_per_unit_per_day = round(float(product.unit_cost or 1.0) * 0.0025, 4)
        product.lifecycle_state = "active"
        if idx % 4 == 0:
            product.planogram_required = True
    await db.flush()


async def _seed_model_registry(db: AsyncSession, *, customer_id, model_version: str) -> ModelVersion:
    await db.execute(
        delete(ModelVersion).where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == "demand_forecast",
        )
    )
    model = ModelVersion(
        customer_id=customer_id,
        model_name="demand_forecast",
        version=model_version,
        status="champion",
        routing_weight=1.0,
        promoted_at=datetime.utcnow(),
        smoke_test_passed=True,
        metrics={
            "wape": 0.7276,
            "mase": 0.7968,
            "coverage": 0.9,
            "dataset_id": "pilot_sample_csv_v1",
            "forecast_grain": "daily_store_sku",
            "segment_strategy": "store_sku",
            "feature_set_id": "pilot_csv_core_v1",
            "architecture": "lightgbm",
            "objective": "replenishment_forecast",
            "tuning_profile": "pilot_default",
            "lineage_label": "pilot_sample_bootstrap",
            "rule_overlay_enabled": True,
            "evaluation_window_days": 30,
            "promotion_decision": {
                "reason": "Seeded champion for sample-merchant walkthrough",
                "source": "bootstrap_sample_merchant",
            },
            "interval_method": "conformal_calibrated",
            "interval_coverage": 0.9,
            "calibration_status": "calibrated",
        },
    )
    db.add(model)
    await db.flush()
    return model


async def _seed_forecasts_and_accuracy(db: AsyncSession, *, customer_id, model_version: str) -> dict[str, int]:
    await db.execute(delete(DemandForecast).where(DemandForecast.customer_id == customer_id))
    await db.execute(delete(ForecastAccuracy).where(ForecastAccuracy.customer_id == customer_id))
    await db.execute(delete(BacktestResult).where(BacktestResult.customer_id == customer_id))

    daily_sales = await _load_daily_sales(db, customer_id=customer_id)
    if daily_sales.empty:
        return {"forecasts": 0, "accuracy": 0}

    summary = _velocity_summary(daily_sales)
    today = date.today()
    forecast_rows = 0
    accuracy_rows = 0

    for (store_id, product_id), stats in summary.items():
        avg_daily = stats["avg_daily"]
        std_daily = stats["std_daily"]

        for offset in range(30):
            forecast_date = today + timedelta(days=offset)
            day_multiplier = 1.12 if forecast_date.weekday() in {4, 5} else 0.94 if forecast_date.weekday() == 1 else 1.0
            demand = round(avg_daily * day_multiplier, 2)
            spread = max(1.0, std_daily * 1.35)
            db.add(
                DemandForecast(
                    customer_id=customer_id,
                    store_id=store_id,
                    product_id=product_id,
                    forecast_date=forecast_date,
                    forecasted_demand=demand,
                    lower_bound=max(0.0, round(demand - spread, 2)),
                    upper_bound=round(demand + spread, 2),
                    confidence=0.9,
                    model_version=model_version,
                )
            )
            forecast_rows += 1

        recent_actuals = daily_sales[
            (daily_sales["store_id"] == store_id)
            & (daily_sales["product_id"] == product_id)
        ].sort_values("sales_date").tail(30)
        for idx, row in enumerate(recent_actuals.itertuples(index=False)):
            actual = float(row.quantity)
            adjustment = 0.94 + ((idx % 5) * 0.025)
            predicted = round(max(0.0, actual * adjustment), 2)
            mae = abs(predicted - actual)
            mape = (mae / actual) if actual else 0.0
            db.add(
                ForecastAccuracy(
                    customer_id=customer_id,
                    store_id=store_id,
                    product_id=product_id,
                    forecast_date=pd.Timestamp(row.sales_date).date(),
                    forecasted_demand=predicted,
                    actual_demand=actual,
                    mae=round(mae, 4),
                    mape=round(mape, 4),
                    model_version=model_version,
                    evaluated_at=datetime.utcnow() - timedelta(days=max(0, 29 - idx)),
                )
            )
            accuracy_rows += 1

    await db.flush()
    return {"forecasts": forecast_rows, "accuracy": accuracy_rows}


async def _seed_backtests_and_retraining(db: AsyncSession, *, customer_id, model: ModelVersion) -> dict[str, int]:
    for offset in range(7):
        forecast_date = date.today() - timedelta(days=offset + 1)
        db.add(
            BacktestResult(
                customer_id=customer_id,
                model_id=model.model_id,
                forecast_date=forecast_date,
                actual_date=forecast_date + timedelta(days=1),
                mae=round(5.8 + (offset * 0.2), 4),
                mape=round(0.12 + (offset * 0.003), 4),
                stockout_miss_rate=round(0.04 + (offset * 0.002), 4),
                overstock_rate=round(0.08 + (offset * 0.0025), 4),
            )
        )

    db.add(
        ModelRetrainingLog(
            customer_id=customer_id,
            model_name="demand_forecast",
            trigger_type="manual",
            trigger_metadata={"source": "bootstrap_sample_merchant"},
            status="completed",
            version_produced=model.version,
            started_at=datetime.utcnow() - timedelta(days=2, minutes=18),
            completed_at=datetime.utcnow() - timedelta(days=2),
        )
    )
    await db.flush()
    return {"backtests": 7, "retraining_logs": 1}


async def _seed_reorder_points_and_inventory(db: AsyncSession, *, customer_id) -> dict[str, int]:
    await db.execute(delete(ReorderPoint).where(ReorderPoint.customer_id == customer_id))
    await db.execute(delete(Alert).where(Alert.customer_id == customer_id))
    await db.execute(delete(IntegrationSyncLog).where(IntegrationSyncLog.customer_id == customer_id))

    daily_sales = await _load_daily_sales(db, customer_id=customer_id)
    summary = _velocity_summary(daily_sales)
    inventory_rows = (
        await db.execute(
            select(InventoryLevel)
            .where(InventoryLevel.customer_id == customer_id)
            .order_by(InventoryLevel.timestamp.desc())
        )
    ).scalars().all()
    latest_inventory: dict[tuple[Any, Any], InventoryLevel] = {}
    for row in inventory_rows:
        latest_inventory.setdefault((row.store_id, row.product_id), row)

    alert_rows = 0
    for idx, ((store_id, product_id), stats) in enumerate(sorted(summary.items(), key=lambda item: str(item[0]))):
        avg_daily = stats["avg_daily"]
        std_daily = stats["std_daily"]
        lead_time_days = 4
        safety_stock = max(4, round(std_daily * 2.0))
        reorder_point = max(10, round((avg_daily * lead_time_days) + safety_stock))
        eoq = max(24, round(avg_daily * 12))
        db.add(
            ReorderPoint(
                customer_id=customer_id,
                store_id=store_id,
                product_id=product_id,
                reorder_point=reorder_point,
                safety_stock=safety_stock,
                economic_order_qty=eoq,
                lead_time_days=lead_time_days,
                service_level=0.95,
            )
        )

        inventory = latest_inventory.get((store_id, product_id))
        if inventory is not None:
            if idx < 12:
                target_available = max(0, reorder_point - max(3, round(avg_daily * 2)))
                inventory.quantity_on_hand = target_available
                inventory.quantity_available = target_available
                inventory.quantity_reserved = 0
                inventory.quantity_on_order = 0
            if idx < 6:
                db.add(
                    InventoryLevel(
                        customer_id=customer_id,
                        store_id=store_id,
                        product_id=product_id,
                        timestamp=datetime.combine(date.today() - timedelta(days=8), time(hour=8)),
                        quantity_on_hand=max(0, reorder_point - round(avg_daily * 3)),
                        quantity_on_order=0,
                        quantity_reserved=0,
                        quantity_available=max(0, reorder_point - round(avg_daily * 3)),
                        source="sample_bootstrap_history",
                    )
                )

        if idx < 6:
            db.add(
                Alert(
                    customer_id=customer_id,
                    store_id=store_id,
                    product_id=product_id,
                    alert_type="stockout_predicted" if idx % 2 == 0 else "reorder_recommended",
                    severity="high" if idx < 3 else "medium",
                    message="Demand is outpacing available stock. Review this item in the replenishment queue.",
                    status="open" if idx < 4 else "acknowledged",
                )
            )
            alert_rows += 1

    await db.flush()
    sync_log_count = await db.scalar(
        select(func.count(IntegrationSyncLog.sync_id)).where(IntegrationSyncLog.customer_id == customer_id)
    )
    return {"reorder_points": len(summary), "alerts": alert_rows, "sync_logs": int(sync_log_count or 0)}


async def _seed_recommendations(
    db: AsyncSession,
    *,
    customer_id,
    model_version: str,
    open_limit: int = 12,
    historical_limit: int = 6,
) -> dict[str, int]:
    await db.execute(delete(RecommendationOutcome).where(RecommendationOutcome.customer_id == customer_id))
    await db.execute(delete(ReplenishmentRecommendation).where(ReplenishmentRecommendation.customer_id == customer_id))

    stores = (
        await db.execute(select(Store).where(Store.customer_id == customer_id).order_by(Store.name.asc()))
    ).scalars().all()
    products = (
        await db.execute(select(Product).where(Product.customer_id == customer_id).order_by(Product.sku.asc()))
    ).scalars().all()
    reorder_rows = (
        await db.execute(select(ReorderPoint).where(ReorderPoint.customer_id == customer_id))
    ).scalars().all()
    reorder_map = {(row.store_id, row.product_id): row for row in reorder_rows}
    daily_sales = await _load_daily_sales(db, customer_id=customer_id)
    velocity = _velocity_summary(daily_sales)

    service = RecommendationService(db)
    created_open = 0
    combos = [(store, product) for store in stores for product in products]
    for store, product in combos[:open_limit]:
        if (store.store_id, product.product_id) not in reorder_map:
            continue
        await service.create_recommendation(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            horizon_days=7,
            model_version=model_version,
        )
        created_open += 1

    status_cycle = ["accepted", "edited", "rejected", "accepted", "edited", "accepted"]
    created_historical = 0
    for idx, (store, product) in enumerate(combos[:historical_limit]):
        rp = reorder_map.get((store.store_id, product.product_id))
        stats = velocity.get((store.store_id, product.product_id))
        if rp is None or stats is None:
            continue

        start_date = date.today() - timedelta(days=20 - idx)
        end_date = start_date + timedelta(days=6)
        horizon_mean = round(stats["avg_daily"] * 7, 2)
        db.add(
            ReplenishmentRecommendation(
                customer_id=customer_id,
                store_id=store.store_id,
                product_id=product.product_id,
                supplier_id=product.supplier_id,
                status=status_cycle[idx],
                forecast_model_version=model_version,
                policy_version="pilot_policy_v1",
                horizon_days=7,
                recommended_quantity=max(rp.economic_order_qty, rp.reorder_point),
                quantity_available=max(0, rp.reorder_point - 4),
                quantity_on_order=0,
                inventory_position=max(0, rp.reorder_point - 4),
                reorder_point=rp.reorder_point,
                safety_stock=rp.safety_stock or 0,
                economic_order_qty=rp.economic_order_qty or rp.reorder_point,
                lead_time_days=rp.lead_time_days or 4,
                service_level=rp.service_level or 0.95,
                estimated_unit_cost=float(product.unit_cost or 0.0),
                estimated_total_cost=round(float(product.unit_cost or 0.0) * max(rp.economic_order_qty or 0, 1), 2),
                source_type="vendor_direct",
                source_id=product.supplier_id,
                interval_method="conformal_calibrated",
                calibration_status="calibrated",
                no_order_stockout_risk="medium" if idx % 3 else "high",
                order_overstock_risk="low" if idx % 2 else "medium",
                recommendation_rationale={
                    "source_name": "Northstar Wholesale",
                    "forecast_start_date": start_date.isoformat(),
                    "forecast_end_date": end_date.isoformat(),
                    "horizon_demand_mean": horizon_mean,
                    "horizon_demand_lower": round(horizon_mean * 0.84, 2),
                    "horizon_demand_upper": round(horizon_mean * 1.18, 2),
                    "lead_time_demand_mean": round(stats["avg_daily"] * (rp.lead_time_days or 4), 2),
                    "lead_time_demand_upper": round((stats["avg_daily"] + stats["std_daily"]) * (rp.lead_time_days or 4), 2),
                    "interval_coverage": 0.9,
                    "forecast_row_count": 7,
                    "min_order_qty": 12,
                    "cost_per_order": 26.0,
                },
                created_at=datetime.combine(start_date - timedelta(days=1), time(hour=9)),
            )
        )
        created_historical += 1

    await db.commit()
    return {"open_recommendations": created_open, "historical_recommendations": created_historical}


async def _refresh_readiness(db: AsyncSession, *, customer_id, model_version: str) -> dict[str, Any]:
    daily_sales = await _load_daily_sales(db, customer_id=customer_id)
    readiness_frame = daily_sales.rename(columns={"sales_date": "date"})
    result = await evaluate_and_persist_tenant_readiness(
        db,
        customer_id=customer_id,
        transactions_df=readiness_frame,
        candidate_version=model_version,
        model_name="demand_forecast",
        thresholds=ReadinessThresholds(
            min_history_days=90,
            min_store_count=1,
            min_product_count=5,
            min_accuracy_samples=10,
            accuracy_window_days=30,
        ),
    )
    await db.flush()
    return result


async def bootstrap_sample_merchant(
    *,
    history_days: int,
    store_limit: int,
    product_limit: int,
    model_version: str,
    wipe_existing: bool,
) -> dict[str, Any]:
    from core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with factory() as db:
            tenant_result = await ensure_production_tenant(db, wipe_synthetic=wipe_existing)
            payloads = build_sample_payloads(
                store_limit=store_limit,
                product_limit=product_limit,
                history_days=history_days,
            )
            ingest_result = await ingest_csv_batch(
                db,
                customer_id=PRODUCTION_CUSTOMER_ID,
                payloads={
                    "stores": payloads.stores_csv,
                    "products": payloads.products_csv,
                    "transactions": payloads.transactions_csv,
                    "inventory": payloads.inventory_csv,
                },
            )

            supplier = await _ensure_supplier(db, customer_id=PRODUCTION_CUSTOMER_ID)
            await _apply_store_and_product_defaults(db, customer_id=PRODUCTION_CUSTOMER_ID, supplier=supplier)
            model = await _seed_model_registry(db, customer_id=PRODUCTION_CUSTOMER_ID, model_version=model_version)
            forecast_summary = await _seed_forecasts_and_accuracy(
                db,
                customer_id=PRODUCTION_CUSTOMER_ID,
                model_version=model_version,
            )
            health_summary = await _seed_backtests_and_retraining(
                db,
                customer_id=PRODUCTION_CUSTOMER_ID,
                model=model,
            )
            ops_summary = await _seed_reorder_points_and_inventory(db, customer_id=PRODUCTION_CUSTOMER_ID)
            recommendation_summary = await _seed_recommendations(
                db,
                customer_id=PRODUCTION_CUSTOMER_ID,
                model_version=model_version,
            )
            readiness_result = await _refresh_readiness(
                db,
                customer_id=PRODUCTION_CUSTOMER_ID,
                model_version=model_version,
            )

            await db.commit()
            return {
                "tenant": tenant_result,
                "payloads": payloads.summary,
                "ingest": ingest_result["created"],
                "readiness": readiness_result,
                "runtime": {
                    **forecast_summary,
                    **health_summary,
                    **ops_summary,
                    **recommendation_summary,
                },
            }
    finally:
        await engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reset the production pilot tenant and load a deterministic sample merchant walkthrough dataset.",
    )
    parser.add_argument("--history-days", type=int, default=120, help="Number of historical sales days to include.")
    parser.add_argument("--stores", type=int, default=2, help="Number of stores to include.")
    parser.add_argument("--products", type=int, default=6, help="Number of products to include.")
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION, help="Champion model version label to seed.")
    parser.add_argument(
        "--no-wipe",
        action="store_true",
        help="Keep existing tenant data instead of resetting the production pilot tenant first.",
    )
    return parser


def main() -> None:
    import asyncio
    import json

    args = _build_parser().parse_args()
    result = asyncio.run(
        bootstrap_sample_merchant(
            history_days=args.history_days,
            store_limit=args.stores,
            product_limit=args.products,
            model_version=args.model_version,
            wipe_existing=not args.no_wipe,
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
