"""
Forecast Runtime Workers — Generate operational forecasts from registered models.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workers.celery_app import celery_app

logger = structlog.get_logger()


def _coerce_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _apply_future_temporal_columns(df: pd.DataFrame, target_date: date, day_offset: int) -> pd.DataFrame:
    out = df.copy()
    ts = pd.Timestamp(target_date)
    out["date"] = ts
    out["day_of_week"] = int(ts.dayofweek)
    out["month"] = int(ts.month)
    out["quarter"] = int(ts.quarter)
    out["is_weekend"] = int(ts.dayofweek >= 5)
    out["week_of_year"] = int(ts.isocalendar().week)
    out["day_of_month"] = int(ts.day)
    out["is_month_start"] = int(ts.is_month_start)
    out["is_month_end"] = int(ts.is_month_end)
    if "days_since_last_sale" in out.columns:
        out["days_since_last_sale"] = pd.to_numeric(out["days_since_last_sale"], errors="coerce").fillna(0) + day_offset
    return out


async def _resolve_model_version(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    model_name: str,
    explicit_version: str | None,
) -> str | None:
    if explicit_version:
        return explicit_version

    from db.models import ModelVersion

    champion = await db.execute(
        select(ModelVersion.version)
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == model_name,
            ModelVersion.status == "champion",
        )
        .order_by(ModelVersion.promoted_at.desc())
        .limit(1)
    )
    row = champion.one_or_none()
    if row:
        return str(row.version)

    champion_json = Path("backend/models/champion.json")
    if champion_json.exists():
        try:
            payload = json.loads(champion_json.read_text(encoding="utf-8"))
            version = payload.get("version")
            if isinstance(version, str) and version:
                return version
        except json.JSONDecodeError:
            return None
    return None


@celery_app.task(
    name="workers.forecast.generate_forecasts",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    acks_late=True,
)
def generate_forecasts(
    self,
    customer_id: str,
    horizon_days: int | None = None,
    model_version: str | None = None,
    model_name: str = "demand_forecast",
):
    """
    Generate forward demand forecasts and persist them to demand_forecasts.
    """
    from core.config import get_settings
    from db.models import DemandForecast
    from ml.features import create_features
    from ml.predict import load_models, predict_demand
    from workers.retrain import _load_db_data

    settings = get_settings()
    run_id = self.request.id or "manual"
    forecast_horizon = int(horizon_days or settings.ml_forecast_horizon_days)
    logger.info(
        "forecast_generation.started",
        customer_id=customer_id,
        run_id=run_id,
        horizon_days=forecast_horizon,
        model_version=model_version,
    )

    async def _run():
        engine = create_async_engine(settings.database_url)
        created = 0
        skipped = 0
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)
            async with async_session() as db:
                customer_uuid = uuid.UUID(customer_id)
                try:
                    await db.execute(
                        text("SELECT set_config('app.current_customer_id', :customer_id, false)"),
                        {"customer_id": customer_id},
                    )
                except Exception:
                    pass

                resolved_version = await _resolve_model_version(
                    db,
                    customer_id=customer_uuid,
                    model_name=model_name,
                    explicit_version=model_version,
                )
                if not resolved_version:
                    return {"status": "skipped", "reason": "no_model_version_available"}

                try:
                    transactions_df = _load_db_data(customer_id, min_rows=1)
                except ValueError as exc:
                    return {"status": "skipped", "reason": str(exc)}
                if transactions_df.empty:
                    return {"status": "skipped", "reason": "no_transactions_available"}

                features_df = create_features(transactions_df=transactions_df, force_tier="cold_start")
                if features_df.empty:
                    return {"status": "skipped", "reason": "feature_generation_empty"}

                latest_features = (
                    features_df.sort_values("date")
                    .groupby(["store_id", "product_id"], as_index=False)
                    .tail(1)
                    .reset_index(drop=True)
                )
                if latest_features.empty:
                    return {"status": "skipped", "reason": "no_store_product_pairs"}

                try:
                    models = load_models(resolved_version)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "forecast_generation.model_load_failed",
                        customer_id=customer_id,
                        version=resolved_version,
                        error=str(exc),
                    )
                    return {"status": "failed", "reason": "model_load_failed", "error": str(exc)}

                start_date = date.today() + timedelta(days=1)
                forecast_dates = [start_date + timedelta(days=i) for i in range(forecast_horizon)]

                # Ensure deterministic re-runs for the same model/version/day horizon.
                await db.execute(
                    delete(DemandForecast).where(
                        DemandForecast.customer_id == customer_uuid,
                        DemandForecast.model_version == resolved_version,
                        DemandForecast.forecast_date >= forecast_dates[0],
                        DemandForecast.forecast_date <= forecast_dates[-1],
                    )
                )

                for offset, forecast_date in enumerate(forecast_dates, start=1):
                    feature_batch = _apply_future_temporal_columns(latest_features, forecast_date, day_offset=offset)
                    preds = predict_demand(feature_batch, models=models, confidence_level=0.90)

                    for row in preds.itertuples(index=False):
                        store_uuid = _coerce_uuid(row.store_id)
                        product_uuid = _coerce_uuid(row.product_id)
                        if not store_uuid or not product_uuid:
                            skipped += 1
                            continue
                        db.add(
                            DemandForecast(
                                customer_id=customer_uuid,
                                store_id=store_uuid,
                                product_id=product_uuid,
                                forecast_date=forecast_date,
                                forecasted_demand=float(max(row.forecasted_demand, 0.0)),
                                lower_bound=float(max((row.lower_bound or 0.0), 0.0))
                                if row.lower_bound is not None
                                else None,
                                upper_bound=float(max((row.upper_bound or 0.0), 0.0))
                                if row.upper_bound is not None
                                else None,
                                confidence=float(row.confidence) if row.confidence is not None else None,
                                model_version=resolved_version,
                            )
                        )
                        created += 1

                await db.commit()
                return {
                    "status": "success",
                    "customer_id": customer_id,
                    "model_version": resolved_version,
                    "horizon_days": forecast_horizon,
                    "forecast_rows_created": created,
                    "rows_skipped_invalid_ids": skipped,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    try:
        summary = asyncio.run(_run())
        logger.info("forecast_generation.completed", **summary)
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.error("forecast_generation.failed", customer_id=customer_id, error=str(exc), exc_info=True)
        raise self.retry(exc=exc)
