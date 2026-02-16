"""
Forecasts Router — Demand forecast endpoints.
"""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import DemandForecast, ForecastAccuracy, Product, Transaction

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
    forecast_date: date
    forecasted_demand: float
    actual_demand: float | None
    forecasted_revenue: float
    actual_revenue: float | None
    observations: int


class AccuracyCategoryPoint(BaseModel):
    category: str
    forecasted_demand: float
    actual_demand: float | None
    forecasted_revenue: float
    actual_revenue: float | None
    observations: int


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/", response_model=list[ForecastResponse])
async def list_forecasts(
    store_id: UUID | None = None,
    product_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=5000),
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
    category: str | None = None,
    model_version: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get daily forecast-vs-actual trend with demand and revenue totals."""
    query = (
        select(
            ForecastAccuracy.forecast_date.label("forecast_date"),
            func.sum(ForecastAccuracy.forecasted_demand).label("forecasted_demand"),
            func.sum(ForecastAccuracy.actual_demand).label("actual_demand"),
            func.sum(ForecastAccuracy.forecasted_demand * func.coalesce(Product.unit_price, 0.0)).label(
                "forecasted_revenue"
            ),
            func.sum(ForecastAccuracy.actual_demand * func.coalesce(Product.unit_price, 0.0)).label("actual_revenue"),
            func.count().label("observations"),
        )
        .select_from(ForecastAccuracy)
        .join(
            Product,
            and_(
                ForecastAccuracy.product_id == Product.product_id,
                ForecastAccuracy.customer_id == Product.customer_id,
            ),
            isouter=True,
        )
        .group_by(ForecastAccuracy.forecast_date)
        .order_by(ForecastAccuracy.forecast_date.desc())
        .limit(limit)
    )

    if store_id:
        query = query.where(ForecastAccuracy.store_id == store_id)
    if product_id:
        query = query.where(ForecastAccuracy.product_id == product_id)
    if category:
        query = query.where(Product.category == category)
    if model_version:
        query = query.where(ForecastAccuracy.model_version == model_version)
    if start_date:
        query = query.where(ForecastAccuracy.forecast_date >= start_date)
    if end_date:
        query = query.where(ForecastAccuracy.forecast_date <= end_date)

    result = await db.execute(query)
    rows = list(result.all())
    if not rows:
        rows = await _get_accuracy_trend_fallback_rows(
            db=db,
            store_id=store_id,
            product_id=product_id,
            category=category,
            model_version=model_version,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    # Normalize row shape to mutable dicts.
    normalized_rows = [
        {
            "forecast_date": _normalize_date_value(row.forecast_date),
            "forecasted_demand": float(row.forecasted_demand or 0),
            "actual_demand": float(row.actual_demand or 0),
            "forecasted_revenue": float(row.forecasted_revenue or 0),
            "actual_revenue": float(row.actual_revenue or 0),
            "observations": int(row.observations or 0),
        }
        for row in rows
    ]

    # Merge true transaction actuals into trend rows and include transaction-only dates
    # so charts can render historical actuals even when forecast rows are future-heavy.
    txn_date = func.date(Transaction.timestamp)
    actual_query = (
        select(
            txn_date.label("forecast_date"),
            func.sum(Transaction.quantity).label("actual_demand"),
            func.sum(Transaction.total_amount).label("actual_revenue"),
        )
        .select_from(Transaction)
        .join(
            Product,
            and_(
                Transaction.product_id == Product.product_id,
                Transaction.customer_id == Product.customer_id,
            ),
            isouter=True,
        )
        .where(Transaction.transaction_type == "sale")
        .group_by(txn_date)
        .order_by(txn_date.desc())
        .limit(limit)
    )
    if store_id:
        actual_query = actual_query.where(Transaction.store_id == store_id)
    if product_id:
        actual_query = actual_query.where(Transaction.product_id == product_id)
    if category:
        actual_query = actual_query.where(Product.category == category)
    if start_date:
        actual_query = actual_query.where(txn_date >= start_date)
    if end_date:
        actual_query = actual_query.where(txn_date <= end_date)

    actual_result = await db.execute(actual_query)
    actual_by_date = {
        _normalize_date_value(row.forecast_date): (
            float(row.actual_demand or 0),
            float(row.actual_revenue or 0),
        )
        for row in actual_result.all()
    }

    rows_by_date = {
        _normalize_date_value(row["forecast_date"]): row
        for row in normalized_rows
        if _normalize_date_value(row["forecast_date"]) is not None
    }
    merged_dates = set(rows_by_date.keys()) | set(actual_by_date.keys())
    if merged_dates:
        most_recent_dates = sorted(merged_dates, reverse=True)[:limit]
        normalized_rows = []
        for trend_date in sorted(most_recent_dates):
            base_row = rows_by_date.get(
                trend_date,
                {
                    "forecast_date": trend_date,
                    "forecasted_demand": 0.0,
                    "actual_demand": None,
                    "forecasted_revenue": 0.0,
                    "actual_revenue": None,
                    "observations": 0,
                },
            )
            if trend_date in actual_by_date:
                base_row["actual_demand"], base_row["actual_revenue"] = actual_by_date[trend_date]
            normalized_rows.append(base_row)
    else:
        normalized_rows.sort(key=lambda r: r["forecast_date"])

    return [
        AccuracyTrendPoint(
            forecast_date=row["forecast_date"],
            forecasted_demand=float(row["forecasted_demand"] or 0),
            actual_demand=float(row["actual_demand"]) if row["actual_demand"] is not None else None,
            forecasted_revenue=float(row["forecasted_revenue"] or 0),
            actual_revenue=float(row["actual_revenue"]) if row["actual_revenue"] is not None else None,
            observations=int(row["observations"] or 0),
        )
        for row in normalized_rows
    ]


@router.get("/accuracy/by-category", response_model=list[AccuracyCategoryPoint])
async def get_accuracy_by_category(
    store_id: UUID | None = None,
    model_version: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get aggregated forecast-vs-actual metrics by product category."""
    category_expr = func.coalesce(Product.category, "Unknown")
    query = (
        select(
            category_expr.label("category"),
            func.sum(ForecastAccuracy.forecasted_demand).label("forecasted_demand"),
            func.sum(ForecastAccuracy.actual_demand).label("actual_demand"),
            func.sum(ForecastAccuracy.forecasted_demand * func.coalesce(Product.unit_price, 0.0)).label(
                "forecasted_revenue"
            ),
            func.sum(ForecastAccuracy.actual_demand * func.coalesce(Product.unit_price, 0.0)).label("actual_revenue"),
            func.count().label("observations"),
        )
        .select_from(ForecastAccuracy)
        .join(
            Product,
            and_(
                ForecastAccuracy.product_id == Product.product_id,
                ForecastAccuracy.customer_id == Product.customer_id,
            ),
            isouter=True,
        )
        .group_by(category_expr)
        .order_by(func.sum(ForecastAccuracy.forecasted_demand).desc())
        .limit(limit)
    )

    if store_id:
        query = query.where(ForecastAccuracy.store_id == store_id)
    if model_version:
        query = query.where(ForecastAccuracy.model_version == model_version)
    if start_date:
        query = query.where(ForecastAccuracy.forecast_date >= start_date)
    if end_date:
        query = query.where(ForecastAccuracy.forecast_date <= end_date)

    result = await db.execute(query)
    rows = list(result.all())
    if not rows:
        rows = await _get_accuracy_by_category_fallback_rows(
            db=db,
            store_id=store_id,
            model_version=model_version,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    normalized_rows = [
        {
            "category": str(row.category or "Unknown"),
            "forecasted_demand": float(row.forecasted_demand or 0),
            "actual_demand": float(row.actual_demand or 0),
            "forecasted_revenue": float(row.forecasted_revenue or 0),
            "actual_revenue": float(row.actual_revenue or 0),
            "observations": int(row.observations or 0),
        }
        for row in rows
    ]

    # Same principle as trend: actuals should reflect observed transactions.
    categories = {row["category"] for row in normalized_rows}
    if categories:
        txn_category_expr = func.coalesce(Product.category, "Unknown")
        txn_date = func.date(Transaction.timestamp)
        actual_query = (
            select(
                txn_category_expr.label("category"),
                func.sum(Transaction.quantity).label("actual_demand"),
                func.sum(Transaction.total_amount).label("actual_revenue"),
            )
            .select_from(Transaction)
            .join(
                Product,
                and_(
                    Transaction.product_id == Product.product_id,
                    Transaction.customer_id == Product.customer_id,
                ),
                isouter=True,
            )
            .where(
                Transaction.transaction_type == "sale",
                txn_category_expr.in_(list(categories)),
            )
            .group_by(txn_category_expr)
        )
        if store_id:
            actual_query = actual_query.where(Transaction.store_id == store_id)
        if start_date:
            actual_query = actual_query.where(txn_date >= start_date)
        if end_date:
            actual_query = actual_query.where(txn_date <= end_date)

        actual_result = await db.execute(actual_query)
        actual_by_category = {
            str(row.category or "Unknown"): (
                float(row.actual_demand or 0),
                float(row.actual_revenue or 0),
            )
            for row in actual_result.all()
        }
        for row in normalized_rows:
            if row["category"] in actual_by_category:
                row["actual_demand"], row["actual_revenue"] = actual_by_category[row["category"]]

    return [
        AccuracyCategoryPoint(
            category=str(row["category"] or "Unknown"),
            forecasted_demand=float(row["forecasted_demand"] or 0),
            actual_demand=float(row["actual_demand"]) if row["actual_demand"] is not None else None,
            forecasted_revenue=float(row["forecasted_revenue"] or 0),
            actual_revenue=float(row["actual_revenue"]) if row["actual_revenue"] is not None else None,
            observations=int(row["observations"] or 0),
        )
        for row in normalized_rows
    ]


async def _get_accuracy_trend_fallback_rows(
    db: AsyncSession,
    store_id: UUID | None,
    product_id: UUID | None,
    category: str | None,
    model_version: str | None,
    start_date: date | None,
    end_date: date | None,
    limit: int,
):
    """Fallback trend when forecast_accuracy rows are unavailable for current filters."""
    forecast_query = (
        select(
            DemandForecast.forecast_date.label("forecast_date"),
            func.sum(DemandForecast.forecasted_demand).label("forecasted_demand"),
            func.sum(DemandForecast.forecasted_demand * func.coalesce(Product.unit_price, 0.0)).label("forecasted_revenue"),
            func.count().label("observations"),
        )
        .select_from(DemandForecast)
        .join(
            Product,
            and_(
                DemandForecast.product_id == Product.product_id,
                DemandForecast.customer_id == Product.customer_id,
            ),
            isouter=True,
        )
    )
    if store_id:
        forecast_query = forecast_query.where(DemandForecast.store_id == store_id)
    if product_id:
        forecast_query = forecast_query.where(DemandForecast.product_id == product_id)
    if category:
        forecast_query = forecast_query.where(Product.category == category)
    if model_version:
        forecast_query = forecast_query.where(DemandForecast.model_version == model_version)
    if start_date:
        forecast_query = forecast_query.where(DemandForecast.forecast_date >= start_date)
    if end_date:
        forecast_query = forecast_query.where(DemandForecast.forecast_date <= end_date)
    forecast_subq = forecast_query.group_by(DemandForecast.forecast_date).subquery()

    txn_date = func.date(Transaction.timestamp)
    actual_query = (
        select(
            txn_date.label("forecast_date"),
            func.sum(Transaction.quantity).label("actual_demand"),
            func.sum(Transaction.total_amount).label("actual_revenue"),
        )
        .select_from(Transaction)
        .join(
            Product,
            and_(
                Transaction.product_id == Product.product_id,
                Transaction.customer_id == Product.customer_id,
            ),
            isouter=True,
        )
        .where(Transaction.transaction_type == "sale")
    )
    if store_id:
        actual_query = actual_query.where(Transaction.store_id == store_id)
    if product_id:
        actual_query = actual_query.where(Transaction.product_id == product_id)
    if category:
        actual_query = actual_query.where(Product.category == category)
    if start_date:
        actual_query = actual_query.where(txn_date >= start_date)
    if end_date:
        actual_query = actual_query.where(txn_date <= end_date)
    actual_subq = actual_query.group_by(txn_date).subquery()

    date_union = union_all(
        select(forecast_subq.c.forecast_date.label("trend_date")),
        select(actual_subq.c.forecast_date.label("trend_date")),
    ).subquery()

    dates_subq = select(date_union.c.trend_date).group_by(date_union.c.trend_date).subquery()

    joined_query = (
        select(
            dates_subq.c.trend_date.label("forecast_date"),
            func.coalesce(forecast_subq.c.forecasted_demand, 0.0).label("forecasted_demand"),
            func.coalesce(actual_subq.c.actual_demand, 0.0).label("actual_demand"),
            func.coalesce(forecast_subq.c.forecasted_revenue, 0.0).label("forecasted_revenue"),
            func.coalesce(actual_subq.c.actual_revenue, 0.0).label("actual_revenue"),
            func.coalesce(forecast_subq.c.observations, 0).label("observations"),
        )
        .select_from(dates_subq)
        .join(forecast_subq, dates_subq.c.trend_date == forecast_subq.c.forecast_date, isouter=True)
        .join(actual_subq, dates_subq.c.trend_date == actual_subq.c.forecast_date, isouter=True)
        .order_by(dates_subq.c.trend_date.desc())
        .limit(limit)
    )
    result = await db.execute(joined_query)
    return list(result.all())


async def _get_accuracy_by_category_fallback_rows(
    db: AsyncSession,
    store_id: UUID | None,
    model_version: str | None,
    start_date: date | None,
    end_date: date | None,
    limit: int,
):
    """Fallback category aggregates when forecast_accuracy rows are unavailable."""
    category_expr = func.coalesce(Product.category, "Unknown")
    forecast_query = (
        select(
            category_expr.label("category"),
            func.sum(DemandForecast.forecasted_demand).label("forecasted_demand"),
            func.sum(DemandForecast.forecasted_demand * func.coalesce(Product.unit_price, 0.0)).label("forecasted_revenue"),
            func.count().label("observations"),
        )
        .select_from(DemandForecast)
        .join(
            Product,
            and_(
                DemandForecast.product_id == Product.product_id,
                DemandForecast.customer_id == Product.customer_id,
            ),
            isouter=True,
        )
    )
    if store_id:
        forecast_query = forecast_query.where(DemandForecast.store_id == store_id)
    if model_version:
        forecast_query = forecast_query.where(DemandForecast.model_version == model_version)
    if start_date:
        forecast_query = forecast_query.where(DemandForecast.forecast_date >= start_date)
    if end_date:
        forecast_query = forecast_query.where(DemandForecast.forecast_date <= end_date)
    forecast_subq = forecast_query.group_by(category_expr).subquery()

    txn_category_expr = func.coalesce(Product.category, "Unknown")
    txn_date = func.date(Transaction.timestamp)
    actual_query = (
        select(
            txn_category_expr.label("category"),
            func.sum(Transaction.quantity).label("actual_demand"),
            func.sum(Transaction.total_amount).label("actual_revenue"),
        )
        .select_from(Transaction)
        .join(
            Product,
            and_(
                Transaction.product_id == Product.product_id,
                Transaction.customer_id == Product.customer_id,
            ),
            isouter=True,
        )
        .where(Transaction.transaction_type == "sale")
    )
    if store_id:
        actual_query = actual_query.where(Transaction.store_id == store_id)
    if start_date:
        actual_query = actual_query.where(txn_date >= start_date)
    if end_date:
        actual_query = actual_query.where(txn_date <= end_date)
    actual_subq = actual_query.group_by(txn_category_expr).subquery()

    joined_query = (
        select(
            forecast_subq.c.category,
            forecast_subq.c.forecasted_demand,
            func.coalesce(actual_subq.c.actual_demand, 0.0).label("actual_demand"),
            forecast_subq.c.forecasted_revenue,
            func.coalesce(actual_subq.c.actual_revenue, 0.0).label("actual_revenue"),
            forecast_subq.c.observations,
        )
        .select_from(forecast_subq)
        .join(actual_subq, forecast_subq.c.category == actual_subq.c.category, isouter=True)
        .order_by(forecast_subq.c.forecasted_demand.desc())
        .limit(limit)
    )
    result = await db.execute(joined_query)
    return list(result.all())


def _normalize_date_value(value):
    if value is None:
        return None
    if hasattr(value, "date"):
        try:
            # datetime -> date
            return value.date()
        except Exception:
            pass
    return value
