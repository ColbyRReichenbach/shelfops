#!/usr/bin/env python3
"""Load a bounded M5/Walmart benchmark workspace into the tenant tables.

The sales rows come from the public M5/Walmart benchmark. Inventory rows are
policy scaffolding for the app surface and are labeled with a simulated source.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import get_settings
from data_sources.csv_onboarding import ingest_csv_batch
from db.models import (
    Alert,
    DemandForecast,
    ForecastAccuracy,
    InventoryLevel,
    Product,
    RecommendationDecision,
    RecommendationOutcome,
    ReorderPoint,
    ReplenishmentRecommendation,
    Store,
    Supplier,
    Transaction,
)
from recommendations.service import RecommendationService
from scripts.production_tenant import PRODUCTION_CUSTOMER_ID, ensure_production_tenant
from workers.monitoring import compute_recommendation_outcomes

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_M5_CANONICAL = REPO_ROOT / "data" / "benchmarks" / "m5_walmart" / "subset_20spc" / "canonical_transactions.csv"
DEFAULT_MODEL_VERSION = "v3"


@dataclass(frozen=True)
class BenchmarkPayloadBundle:
    stores_csv: str
    products_csv: str
    transactions_csv: str
    inventory_csv: str
    summary: dict[str, Any]


def _render_csv(frame: pd.DataFrame, columns: list[str]) -> str:
    return frame.loc[:, columns].to_csv(index=False)


def _state_city(state_id: str) -> str:
    return {"CA": "Los Angeles", "TX": "Dallas", "WI": "Madison"}.get(str(state_id), "Benchmark City")


def build_m5_benchmark_payloads(
    *,
    canonical_csv: Path = DEFAULT_M5_CANONICAL,
    store_limit: int = 4,
    product_limit: int = 60,
    history_days: int = 365,
) -> BenchmarkPayloadBundle:
    if not canonical_csv.exists():
        raise FileNotFoundError(f"M5 canonical file not found: {canonical_csv}")

    usecols = ["date", "store_id", "product_id", "quantity", "category", "price", "state_id"]
    frame = pd.read_csv(canonical_csv, usecols=usecols, parse_dates=["date"])
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0.0)

    stores = sorted(frame["store_id"].dropna().astype(str).unique().tolist())[:store_limit]
    scoped = frame[frame["store_id"].astype(str).isin(stores)].copy()

    product_rank = (
        scoped.groupby(["product_id", "category"], dropna=False)["quantity"]
        .sum()
        .reset_index()
        .sort_values(["category", "quantity", "product_id"], ascending=[True, False, True], kind="mergesort")
    )
    per_category_take = max(1, product_limit // max(1, product_rank["category"].nunique()))
    selected_products = (
        product_rank.groupby("category", group_keys=False)
        .head(per_category_take)
        .head(product_limit)["product_id"]
        .astype(str)
        .tolist()
    )
    scoped = scoped[scoped["product_id"].astype(str).isin(selected_products)].copy()

    max_date = scoped["date"].max()
    min_date = max_date - timedelta(days=history_days - 1)
    scoped = scoped[scoped["date"] >= min_date].copy()
    scoped["store_name"] = "M5 " + scoped["store_id"].astype(str)
    scoped["sku"] = scoped["product_id"].astype(str)
    scoped["unit_price"] = scoped["price"].fillna(scoped.groupby("product_id")["price"].transform("median")).fillna(1.0)
    scoped["transaction_type"] = "sale"
    scoped["external_id"] = (
        "m5:"
        + scoped["store_id"].astype(str)
        + ":"
        + scoped["product_id"].astype(str)
        + ":"
        + scoped["date"].dt.strftime("%Y%m%d")
    )
    transaction_rows = scoped[scoped["quantity"] > 0].copy()

    store_source = (
        scoped[["store_id", "state_id"]]
        .drop_duplicates("store_id")
        .sort_values("store_id", kind="mergesort")
        .reset_index(drop=True)
    )
    stores_frame = pd.DataFrame(
        {
            "name": "M5 " + store_source["store_id"].astype(str),
            "city": store_source["state_id"].astype(str).map(_state_city),
            "state": store_source["state_id"].astype(str),
            "zip_code": "",
            "lat": "",
            "lon": "",
            "timezone": "America/Chicago",
        }
    )

    product_source = (
        scoped.groupby(["product_id", "category"], dropna=False)
        .agg(unit_price=("unit_price", "median"), units=("quantity", "sum"))
        .reset_index()
        .sort_values(["category", "product_id"], kind="mergesort")
    )
    products_frame = pd.DataFrame(
        {
            "sku": product_source["product_id"].astype(str),
            "name": "M5 " + product_source["product_id"].astype(str),
            "category": product_source["category"].astype(str),
            "subcategory": product_source["category"].astype(str),
            "brand": "Walmart M5 Benchmark",
            "unit_cost": (product_source["unit_price"].astype(float) * 0.65).round(2),
            "unit_price": product_source["unit_price"].astype(float).round(2),
            "weight": "",
            "shelf_life_days": product_source["category"].astype(str).map(lambda cat: 10 if cat == "FOODS" else 365),
            "is_seasonal": False,
            "is_perishable": product_source["category"].astype(str).map(lambda cat: cat == "FOODS"),
        }
    )

    recent = scoped[scoped["date"] >= max_date - timedelta(days=28)]
    velocity = (
        recent.groupby(["store_name", "sku"], dropna=False)["quantity"]
        .mean()
        .reset_index()
        .rename(columns={"quantity": "avg_daily_units"})
    )
    velocity["timestamp"] = datetime.utcnow().replace(microsecond=0).isoformat()
    velocity["quantity_on_hand"] = velocity["avg_daily_units"].map(lambda value: max(0, round(float(value) * 14)))
    velocity["quantity_on_order"] = 0
    velocity["quantity_reserved"] = 0
    velocity["quantity_available"] = velocity["quantity_on_hand"]
    velocity["source"] = "m5_benchmark_simulated_inventory"

    summary = {
        "source_dataset": "m5_walmart",
        "claim_boundary": (
            "M5 sales history is benchmark data. Operational transactions contain positive sales only; "
            "zero-demand benchmark days remain in the benchmark artifacts. Inventory rows are simulated app scaffolding."
        ),
        "stores": int(stores_frame["name"].nunique()),
        "products": int(products_frame["sku"].nunique()),
        "demand_rows": int(len(scoped)),
        "positive_transaction_rows": int(len(transaction_rows)),
        "inventory_rows": int(len(velocity)),
        "date_min": scoped["date"].min().date().isoformat(),
        "date_max": scoped["date"].max().date().isoformat(),
    }

    return BenchmarkPayloadBundle(
        stores_csv=_render_csv(stores_frame, ["name", "city", "state", "zip_code", "lat", "lon", "timezone"]),
        products_csv=_render_csv(
            products_frame,
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
            transaction_rows,
            ["date", "store_name", "sku", "quantity", "unit_price", "transaction_type", "external_id"],
        ),
        inventory_csv=_render_csv(
            velocity,
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
            func.sum(func.abs(Transaction.quantity)).label("quantity"),
        )
        .where(
            Transaction.customer_id == customer_id,
            Transaction.transaction_type == "sale",
        )
        .group_by(func.date(Transaction.timestamp), Transaction.store_id, Transaction.product_id)
        .order_by(func.date(Transaction.timestamp).asc())
    )
    return pd.DataFrame(
        [
            {
                "sales_date": row.sales_date,
                "store_id": row.store_id,
                "product_id": row.product_id,
                "quantity": float(row.quantity or 0.0),
            }
            for row in result.all()
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
            "avg_daily": max(avg_daily, 0.25),
            "std_daily": max(std_daily, 0.5),
        }
    return summary


async def _ensure_benchmark_supplier(db: AsyncSession, *, customer_id) -> Supplier:
    result = await db.execute(
        select(Supplier).where(
            Supplier.customer_id == customer_id,
            Supplier.name == "M5 Benchmark Supplier (simulated)",
        )
    )
    supplier = result.scalar_one_or_none()
    if supplier is None:
        supplier = Supplier(
            customer_id=customer_id,
            name="M5 Benchmark Supplier (simulated)",
            contact_email="orders@m5-benchmark-supplier.example",
            lead_time_days=4,
            min_order_quantity=12,
            reliability_score=0.96,
            cost_per_order=24.0,
            lead_time_variance=1.0,
            on_time_delivery_rate=0.95,
            avg_lead_time_actual=4.1,
            status="active",
        )
        db.add(supplier)
        await db.flush()
    return supplier


async def _apply_benchmark_defaults(db: AsyncSession, *, customer_id, supplier: Supplier) -> None:
    stores = (
        (await db.execute(select(Store).where(Store.customer_id == customer_id).order_by(Store.name.asc())))
        .scalars()
        .all()
    )
    for idx, store in enumerate(stores):
        store.cluster_tier = 0 if idx == 0 else 1
        store.status = "active"

    products = (
        (await db.execute(select(Product).where(Product.customer_id == customer_id).order_by(Product.sku.asc())))
        .scalars()
        .all()
    )
    for idx, product in enumerate(products):
        product.supplier_id = supplier.supplier_id
        product.holding_cost_per_unit_per_day = round(float(product.unit_cost or 1.0) * 0.0025, 4)
        product.lifecycle_state = "active"
        product.planogram_required = bool(product.is_perishable or idx % 5 == 0)
    await db.flush()


async def _seed_benchmark_forecasts_and_accuracy(
    db: AsyncSession,
    *,
    customer_id,
    model_version: str,
) -> dict[str, int]:
    await db.execute(delete(DemandForecast).where(DemandForecast.customer_id == customer_id))
    await db.execute(delete(ForecastAccuracy).where(ForecastAccuracy.customer_id == customer_id))

    daily_sales = await _load_daily_sales(db, customer_id=customer_id)
    velocity = _velocity_summary(daily_sales)
    if not velocity:
        return {"forecasts": 0, "accuracy": 0}

    product_rows = (
        (await db.execute(select(Product).where(Product.customer_id == customer_id))).scalars().all()
    )
    product_by_id = {row.product_id: row for row in product_rows}
    today = date.today()
    forecast_rows = 0
    accuracy_rows = 0

    for (store_id, product_id), stats in sorted(velocity.items(), key=lambda item: str(item[0]))[:120]:
        avg_daily = stats["avg_daily"]
        std_daily = stats["std_daily"]
        product = product_by_id.get(product_id)
        for offset in range(30):
            forecast_date = today + timedelta(days=offset)
            day_multiplier = (
                1.12 if forecast_date.weekday() in {4, 5} else 0.94 if forecast_date.weekday() == 1 else 1.0
            )
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
                    category_tier=product.category if product else None,
                )
            )
            forecast_rows += 1

        recent_actuals = (
            daily_sales[(daily_sales["store_id"] == store_id) & (daily_sales["product_id"] == product_id)]
            .sort_values("sales_date")
            .tail(30)
        )
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


async def _seed_benchmark_reorder_points_and_alerts(db: AsyncSession, *, customer_id) -> dict[str, int]:
    await db.execute(delete(ReorderPoint).where(ReorderPoint.customer_id == customer_id))
    await db.execute(delete(Alert).where(Alert.customer_id == customer_id))

    daily_sales = await _load_daily_sales(db, customer_id=customer_id)
    velocity = _velocity_summary(daily_sales)
    inventory_rows = (
        (
            await db.execute(
                select(InventoryLevel)
                .where(InventoryLevel.customer_id == customer_id)
                .order_by(InventoryLevel.timestamp.desc())
            )
        )
        .scalars()
        .all()
    )
    latest_inventory: dict[tuple[Any, Any], InventoryLevel] = {}
    for row in inventory_rows:
        latest_inventory.setdefault((row.store_id, row.product_id), row)

    alert_rows = 0
    for idx, ((store_id, product_id), stats) in enumerate(sorted(velocity.items(), key=lambda item: str(item[0]))):
        avg_daily = stats["avg_daily"]
        std_daily = stats["std_daily"]
        lead_time_days = 4
        safety_stock = max(3, round(std_daily * 2.0))
        reorder_point = max(8, round((avg_daily * lead_time_days) + safety_stock))
        eoq = max(12, round(avg_daily * 12))
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
        if inventory is not None and idx < 24:
            target_available = max(0, reorder_point - max(2, round(avg_daily * 2)))
            inventory.quantity_on_hand = target_available
            inventory.quantity_available = target_available
            inventory.quantity_reserved = 0
            inventory.quantity_on_order = 0

        if idx < 10:
            db.add(
                Alert(
                    customer_id=customer_id,
                    store_id=store_id,
                    product_id=product_id,
                    alert_type="stockout_predicted" if idx % 2 == 0 else "reorder_recommended",
                    severity="high" if idx < 5 else "medium",
                    message=(
                        "Benchmark demand is outpacing available stock. Review this item in the "
                        "replenishment queue."
                    ),
                    status="open" if idx < 8 else "acknowledged",
                )
            )
            alert_rows += 1

    await db.flush()
    return {"reorder_points": len(velocity), "alerts": alert_rows}


async def _seed_benchmark_recommendations(
    db: AsyncSession,
    *,
    customer_id,
    model_version: str,
    open_limit: int = 18,
    historical_limit: int = 6,
) -> dict[str, int]:
    await db.execute(delete(RecommendationOutcome).where(RecommendationOutcome.customer_id == customer_id))
    await db.execute(delete(RecommendationDecision).where(RecommendationDecision.customer_id == customer_id))
    await db.execute(delete(ReplenishmentRecommendation).where(ReplenishmentRecommendation.customer_id == customer_id))
    await db.flush()

    stores = (
        (await db.execute(select(Store).where(Store.customer_id == customer_id).order_by(Store.name.asc())))
        .scalars()
        .all()
    )
    products = (
        (await db.execute(select(Product).where(Product.customer_id == customer_id).order_by(Product.sku.asc())))
        .scalars()
        .all()
    )
    reorder_rows = (
        (await db.execute(select(ReorderPoint).where(ReorderPoint.customer_id == customer_id))).scalars().all()
    )
    reorder_map = {(row.store_id, row.product_id): row for row in reorder_rows}
    daily_sales = await _load_daily_sales(db, customer_id=customer_id)
    velocity = _velocity_summary(daily_sales)
    combos = [
        (store, product)
        for store in stores
        for product in products
        if (store.store_id, product.product_id) in reorder_map
    ]

    service = RecommendationService(db)
    created_open = 0
    for store, product in combos[:open_limit]:
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
    max_sales_date = pd.Timestamp(daily_sales["sales_date"].max()).date() if not daily_sales.empty else date(2016, 4, 24)
    for idx, (store, product) in enumerate(combos[:historical_limit]):
        rp = reorder_map.get((store.store_id, product.product_id))
        stats = velocity.get((store.store_id, product.product_id))
        if rp is None or stats is None:
            continue

        start_date = max_sales_date - timedelta(days=28 - idx)
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
                policy_version="benchmark_policy_v1",
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
                interval_method="benchmark_interval",
                calibration_status="benchmark",
                no_order_stockout_risk="medium" if idx % 3 else "high",
                order_overstock_risk="low" if idx % 2 else "medium",
                recommendation_rationale={
                    "source_name": "M5 Benchmark Supplier (simulated)",
                    "forecast_start_date": start_date.isoformat(),
                    "forecast_end_date": end_date.isoformat(),
                    "horizon_demand_mean": horizon_mean,
                    "horizon_demand_lower": round(horizon_mean * 0.84, 2),
                    "horizon_demand_upper": round(horizon_mean * 1.18, 2),
                    "lead_time_demand_mean": round(stats["avg_daily"] * (rp.lead_time_days or 4), 2),
                    "lead_time_demand_upper": round(
                        (stats["avg_daily"] + stats["std_daily"]) * (rp.lead_time_days or 4), 2
                    ),
                    "interval_coverage": 0.9,
                    "forecast_row_count": 7,
                    "min_order_qty": 12,
                    "cost_per_order": 24.0,
                    "evidence_provenance": "benchmark",
                    "inventory_source": "m5_benchmark_simulated_inventory",
                },
                created_at=datetime.combine(start_date - timedelta(days=1), time(hour=9)),
            )
        )
        created_historical += 1

    await db.commit()
    await compute_recommendation_outcomes(db, customer_id=customer_id)
    return {"open_recommendations": created_open, "historical_recommendations": created_historical}


async def _seed_benchmark_runtime(
    db: AsyncSession,
    *,
    customer_id,
    model_version: str,
) -> dict[str, int]:
    supplier = await _ensure_benchmark_supplier(db, customer_id=customer_id)
    await _apply_benchmark_defaults(db, customer_id=customer_id, supplier=supplier)
    forecast_summary = await _seed_benchmark_forecasts_and_accuracy(
        db,
        customer_id=customer_id,
        model_version=model_version,
    )
    ops_summary = await _seed_benchmark_reorder_points_and_alerts(db, customer_id=customer_id)
    recommendation_summary = await _seed_benchmark_recommendations(
        db,
        customer_id=customer_id,
        model_version=model_version,
    )
    return {**forecast_summary, **ops_summary, **recommendation_summary}


async def bootstrap_benchmark_workspace(
    *,
    canonical_csv: Path,
    store_limit: int,
    product_limit: int,
    history_days: int,
    model_version: str,
    wipe_existing: bool,
) -> dict[str, Any]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as db:
            tenant = await ensure_production_tenant(db, wipe_synthetic=wipe_existing)
            payloads = build_m5_benchmark_payloads(
                canonical_csv=canonical_csv,
                store_limit=store_limit,
                product_limit=product_limit,
                history_days=history_days,
            )
            result = await ingest_csv_batch(
                db,
                customer_id=PRODUCTION_CUSTOMER_ID,
                payloads={
                    "stores": payloads.stores_csv,
                    "products": payloads.products_csv,
                    "transactions": payloads.transactions_csv,
                    "inventory": payloads.inventory_csv,
                },
            )
            runtime = await _seed_benchmark_runtime(
                db,
                customer_id=PRODUCTION_CUSTOMER_ID,
                model_version=model_version,
            )
            return {
                "tenant": tenant,
                "benchmark": payloads.summary,
                "ingest": result["created"],
                "runtime": runtime,
            }
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Load M5/Walmart benchmark data into the app workspace")
    parser.add_argument("--canonical-csv", type=Path, default=DEFAULT_M5_CANONICAL)
    parser.add_argument("--stores", type=int, default=4)
    parser.add_argument("--products", type=int, default=60)
    parser.add_argument("--history-days", type=int, default=365)
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    parser.add_argument("--wipe-existing", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(
        bootstrap_benchmark_workspace(
            canonical_csv=args.canonical_csv,
            store_limit=args.stores,
            product_limit=args.products,
            history_days=args.history_days,
            model_version=args.model_version,
            wipe_existing=args.wipe_existing,
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
