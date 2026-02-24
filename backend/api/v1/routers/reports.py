"""
Reports Router — Cross-cutting analytical reports for inventory health,
forecast accuracy, stockout risk, and vendor scorecards.

Agent: full-stack-engineer
Skill: fastapi
"""

from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import (
    DemandForecast,
    ForecastAccuracy,
    InventoryLevel,
    Product,
    PurchaseOrder,
    ReorderPoint,
    Store,
    Supplier,
    Transaction,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# ─── Schemas ─────────────────────────────────────────────────────────────────


class InventoryHealthRow(BaseModel):
    store_id: UUID
    product_id: UUID
    store_name: str
    product_name: str
    quantity_on_hand: int
    reorder_point: int
    days_of_supply: float | None
    status: str  # "critical" | "warning" | "ok"

    model_config = {"from_attributes": True}


class ForecastAccuracyWeek(BaseModel):
    week_start: date
    avg_mae: float
    avg_mape: float
    sample_count: int

    model_config = {"from_attributes": True}


class StockoutRiskRow(BaseModel):
    store_id: UUID
    product_id: UUID
    product_name: str
    store_name: str
    quantity_available: int
    total_forecasted_demand: float
    days_until_stockout: int | None
    risk_level: str  # "high" | "medium"

    model_config = {"from_attributes": True}


class VendorScorecardRow(BaseModel):
    supplier_id: UUID
    supplier_name: str
    on_time_rate: float | None
    avg_lead_time_days: float | None
    total_pos: int
    fill_rate: float | None

    model_config = {"from_attributes": True}


# ─── Services ─────────────────────────────────────────────────────────────────


async def _get_inventory_health(db: AsyncSession) -> list[InventoryHealthRow]:
    """
    Return store/product combos that are at or below their reorder point.
    Joins the latest inventory snapshot with reorder_points and computes
    days_of_supply from average daily transaction volume.
    """
    # Subquery: latest snapshot timestamp per (store_id, product_id)
    latest_sub = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            func.max(InventoryLevel.timestamp).label("max_ts"),
        )
        .group_by(InventoryLevel.store_id, InventoryLevel.product_id)
        .subquery()
    )

    # Subquery: average daily sales per (store_id, product_id) over last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    avg_daily_sub = (
        select(
            Transaction.store_id,
            Transaction.product_id,
            (func.sum(Transaction.quantity) / 30.0).label("avg_daily_sales"),
        )
        .where(
            and_(
                Transaction.timestamp >= thirty_days_ago,
                Transaction.quantity > 0,
            )
        )
        .group_by(Transaction.store_id, Transaction.product_id)
        .subquery()
    )

    query = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            Store.name.label("store_name"),
            Product.name.label("product_name"),
            InventoryLevel.quantity_on_hand,
            ReorderPoint.reorder_point,
            avg_daily_sub.c.avg_daily_sales,
        )
        .join(
            latest_sub,
            and_(
                InventoryLevel.store_id == latest_sub.c.store_id,
                InventoryLevel.product_id == latest_sub.c.product_id,
                InventoryLevel.timestamp == latest_sub.c.max_ts,
            ),
        )
        .join(
            ReorderPoint,
            and_(
                ReorderPoint.store_id == InventoryLevel.store_id,
                ReorderPoint.product_id == InventoryLevel.product_id,
            ),
        )
        .join(Store, Store.store_id == InventoryLevel.store_id)
        .join(Product, Product.product_id == InventoryLevel.product_id)
        .outerjoin(
            avg_daily_sub,
            and_(
                avg_daily_sub.c.store_id == InventoryLevel.store_id,
                avg_daily_sub.c.product_id == InventoryLevel.product_id,
            ),
        )
        .where(InventoryLevel.quantity_on_hand <= ReorderPoint.reorder_point)
    )

    result = await db.execute(query)
    rows = result.all()

    output = []
    for row in rows:
        qty = row.quantity_on_hand
        rop = row.reorder_point
        avg_daily = row.avg_daily_sales

        if qty <= rop * 0.5:
            status = "critical"
        elif qty <= rop:
            status = "warning"
        else:
            status = "ok"

        days_of_supply: float | None = None
        if avg_daily is not None and avg_daily > 0:
            days_of_supply = round(qty / avg_daily, 2)

        output.append(
            InventoryHealthRow(
                store_id=row.store_id,
                product_id=row.product_id,
                store_name=row.store_name,
                product_name=row.product_name,
                quantity_on_hand=qty,
                reorder_point=rop,
                days_of_supply=days_of_supply,
                status=status,
            )
        )

    return output


async def _get_forecast_accuracy(db: AsyncSession, days: int) -> list[ForecastAccuracyWeek]:
    """
    Aggregate forecast_accuracy rows over the lookback window, bucketing into
    ISO calendar weeks in Python (avoids date_trunc / strftime dialect split).
    """
    cutoff = date.today() - timedelta(days=days)

    query = select(
        ForecastAccuracy.forecast_date,
        ForecastAccuracy.mae,
        ForecastAccuracy.mape,
    ).where(ForecastAccuracy.forecast_date >= cutoff)

    result = await db.execute(query)
    rows = result.all()

    # Group rows by ISO week start (Monday) in Python
    weekly: dict[date, dict] = {}
    for row in rows:
        fc_date: date = row.forecast_date
        # isocalendar()[2] is the ISO weekday (1=Mon); subtract to get Monday
        week_start = fc_date - timedelta(days=fc_date.isocalendar()[2] - 1)

        if week_start not in weekly:
            weekly[week_start] = {"mae_sum": 0.0, "mape_sum": 0.0, "count": 0}

        bucket = weekly[week_start]
        bucket["count"] += 1
        if row.mae is not None:
            bucket["mae_sum"] += row.mae
        if row.mape is not None:
            bucket["mape_sum"] += row.mape

    output = [
        ForecastAccuracyWeek(
            week_start=week_start,
            avg_mae=round(v["mae_sum"] / v["count"], 4) if v["count"] else 0.0,
            avg_mape=round(v["mape_sum"] / v["count"], 4) if v["count"] else 0.0,
            sample_count=v["count"],
        )
        for week_start, v in sorted(weekly.items())
    ]

    return output


async def _get_stockout_risk(db: AsyncSession, horizon_days: int) -> list[StockoutRiskRow]:
    """
    Find store/product combos where quantity_available < sum of forecasted demand
    for the next horizon_days.  Returns only the at-risk combos.
    """
    today = date.today()
    horizon_end = today + timedelta(days=horizon_days)

    # Latest inventory snapshot per (store_id, product_id)
    latest_sub = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            func.max(InventoryLevel.timestamp).label("max_ts"),
        )
        .group_by(InventoryLevel.store_id, InventoryLevel.product_id)
        .subquery()
    )

    # Summed forecasted demand for the horizon window
    forecast_sub = (
        select(
            DemandForecast.store_id,
            DemandForecast.product_id,
            func.sum(DemandForecast.forecasted_demand).label("total_demand"),
            func.count(DemandForecast.forecast_id).label("forecast_days"),
        )
        .where(
            and_(
                DemandForecast.forecast_date >= today,
                DemandForecast.forecast_date <= horizon_end,
            )
        )
        .group_by(DemandForecast.store_id, DemandForecast.product_id)
        .subquery()
    )

    query = (
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            Product.name.label("product_name"),
            Store.name.label("store_name"),
            InventoryLevel.quantity_available,
            forecast_sub.c.total_demand,
            forecast_sub.c.forecast_days,
        )
        .join(
            latest_sub,
            and_(
                InventoryLevel.store_id == latest_sub.c.store_id,
                InventoryLevel.product_id == latest_sub.c.product_id,
                InventoryLevel.timestamp == latest_sub.c.max_ts,
            ),
        )
        .join(
            forecast_sub,
            and_(
                forecast_sub.c.store_id == InventoryLevel.store_id,
                forecast_sub.c.product_id == InventoryLevel.product_id,
            ),
        )
        .join(Product, Product.product_id == InventoryLevel.product_id)
        .join(Store, Store.store_id == InventoryLevel.store_id)
        .where(InventoryLevel.quantity_available < forecast_sub.c.total_demand)
    )

    result = await db.execute(query)
    rows = result.all()

    output = []
    for row in rows:
        qty = row.quantity_available
        total_demand = float(row.total_demand)

        # Estimate days_until_stockout: if daily demand rate is known, project
        # forward.  Uses the ratio of inventory to per-day average demand.
        days_until_stockout: int | None = None
        if row.forecast_days and row.forecast_days > 0 and total_demand > 0:
            daily_rate = total_demand / row.forecast_days
            if daily_rate > 0:
                days_until_stockout = max(0, int(qty / daily_rate))

        # risk_level: "high" if less than 50% of demand can be met, else "medium"
        risk_level = "high" if (qty / total_demand) < 0.5 else "medium"

        output.append(
            StockoutRiskRow(
                store_id=row.store_id,
                product_id=row.product_id,
                product_name=row.product_name,
                store_name=row.store_name,
                quantity_available=qty,
                total_forecasted_demand=round(total_demand, 2),
                days_until_stockout=days_until_stockout,
                risk_level=risk_level,
            )
        )

    return output


async def _get_vendor_scorecard(db: AsyncSession) -> list[VendorScorecardRow]:
    """
    Compute per-supplier KPIs from purchase_orders data.
    Only considers POs with status='received' (actual_delivery_date present).
    """
    # All POs grouped by supplier — total count
    total_pos_sub = (
        select(
            PurchaseOrder.supplier_id,
            func.count(PurchaseOrder.po_id).label("total_pos"),
        )
        .where(PurchaseOrder.supplier_id.isnot(None))
        .group_by(PurchaseOrder.supplier_id)
        .subquery()
    )

    # Received POs — on-time rate, fill rate, and the raw date columns needed
    # to compute avg_lead_time_days in Python (avoids julianday / dialect split).
    received_sub = (
        select(
            PurchaseOrder.supplier_id,
            func.avg(
                case(
                    (
                        PurchaseOrder.actual_delivery_date <= PurchaseOrder.promised_delivery_date,
                        1.0,
                    ),
                    else_=0.0,
                )
            ).label("on_time_rate"),
            func.avg(PurchaseOrder.received_qty * 1.0 / PurchaseOrder.quantity).label("fill_rate"),
        )
        .where(
            and_(
                PurchaseOrder.supplier_id.isnot(None),
                PurchaseOrder.status == "received",
                PurchaseOrder.actual_delivery_date.isnot(None),
                PurchaseOrder.promised_delivery_date.isnot(None),
                PurchaseOrder.received_qty.isnot(None),
            )
        )
        .group_by(PurchaseOrder.supplier_id)
        .subquery()
    )

    # Fetch raw date columns so lead-time arithmetic stays in Python.
    lead_time_query = select(
        PurchaseOrder.supplier_id,
        PurchaseOrder.actual_delivery_date,
        PurchaseOrder.suggested_at,
    ).where(
        and_(
            PurchaseOrder.supplier_id.isnot(None),
            PurchaseOrder.status == "received",
            PurchaseOrder.actual_delivery_date.isnot(None),
            PurchaseOrder.suggested_at.isnot(None),
        )
    )

    lead_time_result = await db.execute(lead_time_query)
    lead_time_rows = lead_time_result.all()

    # Compute avg lead time per supplier in Python — no SQL dialect dependency.
    lead_time_days_sum: dict[UUID, float] = {}
    lead_time_days_count: dict[UUID, int] = {}
    for lt_row in lead_time_rows:
        # actual_delivery_date is Date; suggested_at is DateTime — normalise both
        # to date before subtracting so the delta is always in whole days.
        delivery_date: date = (
            lt_row.actual_delivery_date
            if isinstance(lt_row.actual_delivery_date, date)
            else lt_row.actual_delivery_date.date()
        )
        suggested_date: date = (
            lt_row.suggested_at
            if isinstance(lt_row.suggested_at, date)
            else lt_row.suggested_at.date()
        )
        delta_days = (delivery_date - suggested_date).days
        sid = lt_row.supplier_id
        lead_time_days_sum[sid] = lead_time_days_sum.get(sid, 0.0) + delta_days
        lead_time_days_count[sid] = lead_time_days_count.get(sid, 0) + 1

    avg_lead_time_by_supplier: dict[UUID, float] = {
        sid: lead_time_days_sum[sid] / lead_time_days_count[sid]
        for sid in lead_time_days_sum
    }

    query = (
        select(
            Supplier.supplier_id,
            Supplier.name.label("supplier_name"),
            received_sub.c.on_time_rate,
            total_pos_sub.c.total_pos,
            received_sub.c.fill_rate,
        )
        .join(
            total_pos_sub,
            total_pos_sub.c.supplier_id == Supplier.supplier_id,
        )
        .outerjoin(
            received_sub,
            received_sub.c.supplier_id == Supplier.supplier_id,
        )
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        VendorScorecardRow(
            supplier_id=row.supplier_id,
            supplier_name=row.supplier_name,
            on_time_rate=(round(float(row.on_time_rate), 4) if row.on_time_rate is not None else None),
            avg_lead_time_days=(
                round(avg_lead_time_by_supplier[row.supplier_id], 2)
                if row.supplier_id in avg_lead_time_by_supplier
                else None
            ),
            total_pos=row.total_pos,
            fill_rate=(round(float(row.fill_rate), 4) if row.fill_rate is not None else None),
        )
        for row in rows
    ]


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/inventory-health", response_model=list[InventoryHealthRow])
async def get_inventory_health(
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    List all store/product combos at or below their reorder point threshold.
    Each row includes status ("critical", "warning", "ok") and estimated
    days_of_supply based on 30-day average daily sales.
    """
    return await _get_inventory_health(db)


@router.get("/forecast-accuracy", response_model=list[ForecastAccuracyWeek])
async def get_forecast_accuracy(
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Return forecast accuracy metrics aggregated by ISO calendar week.
    Sorted ascending by week_start. Covers the last `days` days of data.
    """
    return await _get_forecast_accuracy(db, days)


@router.get("/stockout-risk", response_model=list[StockoutRiskRow])
async def get_stockout_risk(
    horizon_days: int = Query(7, ge=1, le=90, description="Forecast horizon in days"),
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Identify products where current quantity_available is less than the
    sum of forecasted demand over the next horizon_days.
    Returns risk_level ("high" or "medium") and estimated days_until_stockout.
    """
    return await _get_stockout_risk(db, horizon_days)


@router.get("/vendor-scorecard", response_model=list[VendorScorecardRow])
async def get_vendor_scorecard(
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Compute supplier KPIs from received purchase orders:
    on_time_rate, avg_lead_time_days, fill_rate, and total PO count.
    Only suppliers with at least one PO are returned.
    """
    return await _get_vendor_scorecard(db)
