"""
Forecasts Router — Demand forecast endpoints.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import DemandForecast, ForecastAccuracy, Transaction

router = APIRouter(prefix="/api/v1/forecasts", tags=["forecasts"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


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


class ModelDriverFeature(BaseModel):
    name: str
    importance: float
    friendly_label: str | None = None


class ForecastDriverEvidence(BaseModel):
    forecast_id: UUID
    forecast_model_version: str
    artifact_model_version: str | None
    driver_scope: str
    evidence_type: str
    source_artifact: str | None
    plain_summary: str
    limitations: list[str]
    features: list[ModelDriverFeature]
    cached: bool


# Friendly label mapping for model-driver evidence
FEATURE_LABELS: dict[str, str] = {
    "sales_7d": "Recent 7-day sales",
    "sales_30d": "30-day sales trend",
    "sales_90d": "90-day sales history",
    "avg_daily_sales_30d": "Average daily sales over 30 days",
    "avg_daily_sales_7d": "Average daily sales over 7 days",
    "sales_trend_30d": "30-day sales momentum",
    "sales_trend_7d": "7-day sales momentum",
    "sales_volatility_7d": "Recent demand volatility",
    "sales_volatility_30d": "30-day demand volatility",
    "month": "Month of year (seasonality)",
    "day_of_week": "Day of week",
    "day_of_month": "Day of month",
    "is_weekend": "Weekend timing",
    "is_promotion_active": "Active promotion",
    "promotion_discount_pct": "Promotion discount",
    "temperature": "Weather (temperature)",
    "precipitation": "Weather (precipitation)",
    "is_holiday": "Holiday effect",
    "week_of_year": "Week of year",
    "stock_velocity": "Inventory depletion rate",
    "days_of_supply": "Days of supply remaining",
    "days_since_last_sale": "Days since last sale",
    "is_seasonal": "Seasonal product",
    "unit_price": "Unit price",
    "quarter": "Quarter of year",
    "is_month_start": "Month start timing",
    "is_month_end": "Month end timing",
    "max_daily_sales_30d": "Peak 30-day daily sales",
    "min_daily_sales_30d": "Lowest 30-day daily sales",
    "category_encoded": "Category encoding",
    "rejection_rate_30d": "Buyer rejection rate",
    "avg_qty_adjustment_pct": "Average quantity adjustment",
    "forecast_trust_score": "Forecast trust score",
    "oil_price": "Commodity price proxy",
}

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


def _normalize_date_value(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"Unsupported date value: {value!r}")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _feature_importance_candidates(model_version: str) -> list[tuple[str | None, Path]]:
    candidates: list[tuple[str | None, Path]] = []
    candidates.append((model_version, MODELS_DIR / model_version / "feature_importance.json"))

    champion = _load_json(MODELS_DIR / "champion.json") or {}
    champion_version = champion.get("version")
    if isinstance(champion_version, str) and champion_version != model_version:
        candidates.append((champion_version, MODELS_DIR / champion_version / "feature_importance.json"))

    return candidates


def _build_driver_summary(features: list[ModelDriverFeature]) -> str:
    if not features:
        return "Global model-driver evidence is unavailable for this forecast."

    labels = [feature.friendly_label or feature.name.replace("_", " ") for feature in features[:2]]
    primary = labels[0] if labels else "feature availability"
    secondary = labels[1] if len(labels) > 1 else None
    if secondary:
        return f"These model-driver weights are global to the active forecast model; {primary} and {secondary} are the strongest overall drivers."
    return f"These model-driver weights are global to the active forecast model; {primary} is the strongest overall driver."


def _load_model_driver_features(model_version: str) -> tuple[str | None, str | None, list[ModelDriverFeature]]:
    for artifact_version, path in _feature_importance_candidates(model_version):
        data = _load_json(path)
        if not isinstance(data, dict):
            continue

        features = [
            ModelDriverFeature(
                name=name,
                importance=float(importance),
                friendly_label=FEATURE_LABELS.get(name),
            )
            for name, importance in sorted(data.items(), key=lambda item: item[1], reverse=True)
            if float(importance) > 0
        ]
        return artifact_version, path.name, features[:12]

    return None, None, []


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/", response_model=list[ForecastResponse])
async def list_forecasts(
    store_id: UUID | None = None,
    product_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
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


@router.get("/{forecast_id}/drivers", response_model=ForecastDriverEvidence)
async def get_forecast_drivers(
    forecast_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
) -> ForecastDriverEvidence:
    """Return artifact-backed global model-driver evidence for a forecast."""
    # 1. Verify the forecast belongs to this tenant
    stmt = select(DemandForecast).where(DemandForecast.forecast_id == forecast_id)
    result = await db.execute(stmt)
    forecast = result.scalar_one_or_none()
    if forecast is None:
        raise HTTPException(status_code=404, detail="Forecast not found")

    # 2. Try Redis cache
    cache_key = f"forecast-drivers:{forecast_id}"
    try:
        import redis as redis_lib

        r = redis_lib.from_url(REDIS_URL, decode_responses=True)
        cached_data = r.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            data["cached"] = True
            return ForecastDriverEvidence(**data)
    except Exception:
        pass  # Redis unavailable — compute fresh

    artifact_model_version, source_artifact, features = _load_model_driver_features(forecast.model_version)
    limitations = [
        "This panel shows global model-driver importance from a saved artifact, not a local explanation for this individual forecast.",
        "Feature importance indicates which inputs matter most to the model overall; it does not prove causality for a single SKU or date.",
    ]
    if artifact_model_version and artifact_model_version != forecast.model_version:
        limitations.append(
            f"No driver artifact was found for forecast model {forecast.model_version}; showing the active champion artifact from {artifact_model_version} instead."
        )
    if not features:
        limitations.append("No feature-importance artifact is currently available for this forecast model.")

    explanation = ForecastDriverEvidence(
        forecast_id=forecast_id,
        forecast_model_version=forecast.model_version,
        artifact_model_version=artifact_model_version,
        driver_scope="global" if features else "unavailable",
        evidence_type="artifact" if features else "unavailable",
        source_artifact=source_artifact,
        plain_summary=_build_driver_summary(features),
        features=features,
        limitations=limitations,
        cached=False,
    )

    # 4. Cache in Redis
    try:
        import redis as redis_lib

        r = redis_lib.from_url(REDIS_URL, decode_responses=True)
        r.setex(cache_key, 3600, explanation.model_dump_json())
    except Exception:
        pass

    return explanation
