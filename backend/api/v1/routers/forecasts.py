"""
Forecasts Router — Demand forecast endpoints.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import DemandForecast, ForecastAccuracy, Transaction

router = APIRouter(prefix="/api/v1/forecasts", tags=["forecasts"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class ForecastResponse(BaseModel):
    forecast_id: UUID
    store_id: UUID
    product_id: UUID
    forecast_date: date
    forecasted_demand: float
    lower_bound: float | None
    upper_bound: float | None
    confidence: float | None
    model_version: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AccuracySummary(BaseModel):
    store_id: UUID
    product_id: UUID
    avg_mae: float
    avg_mape: float
    num_forecasts: int


class AccuracyTrendPoint(BaseModel):
    date: date
    avg_mae: float | None
    total_actual_demand: float


def _normalize_date_value(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"Unsupported date value: {value!r}")


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/", response_model=list[ForecastResponse])
async def list_forecasts(
    store_id: UUID | None = None,
    product_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List demand forecasts with filters."""
    query = select(DemandForecast)
    if store_id:
        query = query.where(DemandForecast.store_id == store_id)
    if product_id:
        query = query.where(DemandForecast.product_id == product_id)
    if start_date:
        query = query.where(DemandForecast.forecast_date >= start_date)
    if end_date:
        query = query.where(DemandForecast.forecast_date <= end_date)
    query = query.order_by(DemandForecast.forecast_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/accuracy", response_model=list[AccuracySummary])
async def get_accuracy_summary(
    store_id: UUID | None = None,
    model_version: str | None = None,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get forecast accuracy summary grouped by store/product."""
    query = select(
        ForecastAccuracy.store_id,
        ForecastAccuracy.product_id,
        func.avg(ForecastAccuracy.mae).label("avg_mae"),
        func.avg(ForecastAccuracy.mape).label("avg_mape"),
        func.count().label("num_forecasts"),
    ).group_by(ForecastAccuracy.store_id, ForecastAccuracy.product_id)

    if store_id:
        query = query.where(ForecastAccuracy.store_id == store_id)
    if model_version:
        query = query.where(ForecastAccuracy.model_version == model_version)

    result = await db.execute(query)
    return [
        AccuracySummary(
            store_id=row.store_id,
            product_id=row.product_id,
            avg_mae=float(row.avg_mae or 0),
            avg_mape=float(row.avg_mape or 0),
            num_forecasts=row.num_forecasts,
        )
        for row in result.all()
    ]


@router.get("/accuracy/trend", response_model=list[AccuracyTrendPoint])
async def get_accuracy_trend(
    store_id: UUID | None = None,
    product_id: UUID | None = None,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get merged MAE and actual demand trend by day."""
    acc_query = select(
        ForecastAccuracy.forecast_date.label("trend_date"),
        func.avg(ForecastAccuracy.mae).label("avg_mae"),
    ).group_by(ForecastAccuracy.forecast_date)

    txn_query = (
        select(
            func.date(Transaction.timestamp).label("trend_date"),
            func.sum(Transaction.quantity).label("total_actual_demand"),
        )
        .where(Transaction.transaction_type == "sale")
        .group_by(func.date(Transaction.timestamp))
    )

    if store_id:
        acc_query = acc_query.where(ForecastAccuracy.store_id == store_id)
        txn_query = txn_query.where(Transaction.store_id == store_id)
    if product_id:
        acc_query = acc_query.where(ForecastAccuracy.product_id == product_id)
        txn_query = txn_query.where(Transaction.product_id == product_id)

    acc_query = acc_query.order_by(ForecastAccuracy.forecast_date.desc()).limit(days)
    txn_query = txn_query.order_by(func.date(Transaction.timestamp).desc()).limit(days)

    acc_rows = (await db.execute(acc_query)).all()
    txn_rows = (await db.execute(txn_query)).all()

    mae_by_date = {
        _normalize_date_value(row.trend_date): float(row.avg_mae) for row in acc_rows if row.avg_mae is not None
    }
    demand_by_date = {_normalize_date_value(row.trend_date): float(row.total_actual_demand or 0) for row in txn_rows}

    merged_dates = set(mae_by_date.keys()) | set(demand_by_date.keys())
    ordered_dates = sorted(merged_dates, reverse=True)

    return [
        AccuracyTrendPoint(
            date=trend_date,
            avg_mae=mae_by_date.get(trend_date),
            total_actual_demand=demand_by_date.get(trend_date, 0.0),
        )
        for trend_date in ordered_dates[:days]
    ]
