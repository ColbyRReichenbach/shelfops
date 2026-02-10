"""
Forecasts Router — Demand forecast endpoints.
"""

from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from api.deps import get_tenant_db
from db.models import DemandForecast, ForecastAccuracy

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


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ForecastResponse])
async def list_forecasts(
    store_id: UUID | None = None,
    product_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
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
    query = query.order_by(DemandForecast.forecast_date.desc()).limit(limit)
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
