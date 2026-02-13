"""
Monitoring Workers — Drift detection, data freshness, and opportunity cost.

Safety nets that detect when the system is degrading:
  1. Drift detection: Is model accuracy getting worse?
  2. Data freshness: Has POS data stopped flowing?
  3. Opportunity cost: How much revenue are we losing to stockouts?

Schedule: See celery_app.py beat_schedule
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="workers.monitoring.detect_model_drift",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def detect_model_drift(self, customer_id: str):
    """
    Daily job: Check if forecast accuracy is degrading.

    Compares last 7 days' MAE against the champion model's baseline.
    Alerts if degradation exceeds 15%.
    """
    run_id = self.request.id or "manual"
    logger.info("drift.started", customer_id=customer_id, run_id=run_id)

    async def _detect():
        from core.config import get_settings
        from db.models import Alert, ForecastAccuracy

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                cutoff = datetime.utcnow() - timedelta(days=7)

                # Get recent MAE
                result = await db.execute(
                    select(
                        func.avg(func.abs(ForecastAccuracy.forecasted_demand - ForecastAccuracy.actual_demand)).label(
                            "recent_mae"
                        ),
                        func.avg(ForecastAccuracy.mape).label("recent_mape"),
                        func.count(ForecastAccuracy.id).label("sample_count"),
                    ).where(
                        ForecastAccuracy.customer_id == customer_id,
                        ForecastAccuracy.evaluated_at >= cutoff,
                    )
                )
                row = result.one()
                recent_mae = float(row.recent_mae) if row.recent_mae else None
                sample_count = row.sample_count

                if sample_count == 0 or recent_mae is None:
                    logger.warning("drift.no_data", customer_id=customer_id)
                    return {"status": "skipped", "reason": "no_recent_accuracy_data"}

                # Get baseline MAE (all-time average for comparison)
                baseline_result = await db.execute(
                    select(
                        func.avg(func.abs(ForecastAccuracy.forecasted_demand - ForecastAccuracy.actual_demand)).label(
                            "baseline_mae"
                        ),
                    ).where(
                        ForecastAccuracy.customer_id == customer_id,
                        ForecastAccuracy.evaluated_at < cutoff,
                    )
                )
                baseline_row = baseline_result.one()
                baseline_mae = float(baseline_row.baseline_mae) if baseline_row.baseline_mae else recent_mae

                # Check for drift: >15% degradation
                drift_pct = (recent_mae - baseline_mae) / max(baseline_mae, 0.01)
                is_drifting = drift_pct > 0.15

                if is_drifting:
                    logger.warning(
                        "drift.detected",
                        customer_id=customer_id,
                        recent_mae=round(recent_mae, 2),
                        baseline_mae=round(baseline_mae, 2),
                        drift_pct=round(drift_pct * 100, 1),
                    )

                    # Create ML Alert
                    from db.models import MLAlert

                    alert = MLAlert(
                        ml_alert_id=uuid.uuid4(),
                        customer_id=customer_id,
                        alert_type="drift_detected",
                        severity="critical",
                        title=f"🚨 Model Drift Detected — {round(drift_pct * 100, 1)}% MAE Degradation",
                        message=f"Champion model performance degraded from {round(baseline_mae, 2)} to {round(recent_mae, 2)} MAE. Emergency retrain triggered. Review required.",
                        alert_metadata={
                            "baseline_mae": round(baseline_mae, 2),
                            "recent_mae": round(recent_mae, 2),
                            "drift_pct": round(drift_pct * 100, 1),
                            "sample_count": sample_count,
                        },
                        status="unread",
                        action_url="/models/review",
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(alert)

                    # Trigger emergency retrain
                    from workers.retrain import retrain_forecast_model

                    retrain_forecast_model.apply_async(
                        args=[customer_id],
                        kwargs={
                            "trigger": "drift_detected",
                            "trigger_metadata": {
                                "drift_pct": round(drift_pct * 100, 1),
                                "baseline_mae": round(baseline_mae, 2),
                                "recent_mae": round(recent_mae, 2),
                            },
                        },
                    )

                await db.commit()

            return {
                "status": "drift_detected" if is_drifting else "healthy",
                "customer_id": customer_id,
                "recent_mae": round(recent_mae, 2),
                "baseline_mae": round(baseline_mae, 2),
                "drift_pct": round(drift_pct * 100, 1),
                "sample_count": sample_count,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_detect())
    except Exception as exc:
        logger.error("drift.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="workers.monitoring.check_data_freshness",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def check_data_freshness(self, customer_id: str):
    """
    Hourly job: Ensure data integrations are still flowing.

    Checks:
      1. Integration last_sync_at < threshold (24h for POS, 7d for EDI)
      2. No new transactions for active stores in 24h
    """
    run_id = self.request.id or "manual"
    logger.info("freshness.started", customer_id=customer_id, run_id=run_id)

    async def _check():
        from core.config import get_settings
        from db.models import Integration, Store, Transaction

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            stale_integrations = []
            stale_stores = []

            async with async_session() as db:
                now = datetime.utcnow()

                # Check integrations freshness
                result = await db.execute(
                    select(Integration).where(
                        Integration.customer_id == customer_id,
                        Integration.status == "connected",
                    )
                )
                integrations = result.scalars().all()

                for integ in integrations:
                    threshold_hours = 168 if integ.integration_type == "edi" else 24  # 7 days for EDI
                    if integ.last_sync_at and (now - integ.last_sync_at).total_seconds() > threshold_hours * 3600:
                        stale_integrations.append(
                            {
                                "provider": integ.provider,
                                "last_sync": integ.last_sync_at.isoformat() if integ.last_sync_at else None,
                                "hours_stale": round((now - integ.last_sync_at).total_seconds() / 3600, 1),
                            }
                        )

                # Check for stores with no recent transactions
                result = await db.execute(
                    select(
                        Store.store_id,
                        Store.name,
                        func.max(Transaction.timestamp).label("last_txn"),
                    )
                    .outerjoin(Transaction, Store.store_id == Transaction.store_id)
                    .where(
                        Store.customer_id == customer_id,
                        Store.status == "active",
                    )
                    .group_by(Store.store_id, Store.name)
                )
                stores = result.all()

                for store in stores:
                    if store.last_txn and (now - store.last_txn).total_seconds() > 24 * 3600:
                        stale_stores.append(
                            {
                                "store_id": str(store.store_id),
                                "store_name": store.name,
                                "hours_since_last_txn": round((now - store.last_txn).total_seconds() / 3600, 1),
                            }
                        )
        finally:
            await engine.dispose()

        summary = {
            "status": "warning" if (stale_integrations or stale_stores) else "healthy",
            "customer_id": customer_id,
            "stale_integrations": stale_integrations,
            "stale_stores": stale_stores,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        if stale_integrations or stale_stores:
            logger.warning("freshness.stale_data", **summary)
        else:
            logger.info("freshness.healthy", customer_id=customer_id)

        return summary

    try:
        return asyncio.run(_check())
    except Exception as exc:
        logger.error("freshness.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="workers.monitoring.run_daily_backtest",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    acks_late=True,
)
def run_daily_backtest(self, customer_id: str):
    """
    Daily job: Backtest champion model on yesterday's data (T-1 validation).

    This is the fastest feedback loop: "Did yesterday's forecasts work?"
    Runs at 6:00 AM daily, after opportunity cost analysis completes.
    """
    import uuid

    run_id = self.request.id or "manual"
    logger.info("backtest.daily.started", customer_id=customer_id, run_id=run_id)

    async def _backtest():
        from core.config import get_settings
        from ml.arena import get_champion_model
        from ml.backtest import backtest_yesterday

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                # Set tenant context for RLS
                await db.execute(f"SET app.current_customer_id = '{customer_id}'")

                # Get champion model
                champion = await get_champion_model(
                    db=db,
                    customer_id=uuid.UUID(customer_id),
                    model_name="demand_forecast",
                )

                if not champion:
                    logger.warning("backtest.daily.no_champion", customer_id=customer_id)
                    return {"status": "skipped", "reason": "no_champion_model"}

                # Run T-1 backtest
                result = await backtest_yesterday(
                    db=db,
                    customer_id=uuid.UUID(customer_id),
                    model_id=champion["model_id"],
                    model_version=champion["version"],
                )

                logger.info(
                    "backtest.daily.completed",
                    customer_id=customer_id,
                    model_version=champion["version"],
                    mae=result.get("mae"),
                    mape=result.get("mape"),
                    samples=result.get("samples"),
                )

                return {
                    "status": "success",
                    "customer_id": customer_id,
                    "model_version": champion["version"],
                    "result": result,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_backtest())
    except Exception as exc:
        logger.error("backtest.daily.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="workers.monitoring.run_weekly_backtest",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def run_weekly_backtest(self, customer_id: str, lookback_days: int = 90):
    """
    Weekly job: Full 90-day walk-forward backtest on champion model.

    Runs every Sunday after retraining completes (4:00 AM).
    Provides trend analysis for model health dashboard.
    """
    import uuid

    run_id = self.request.id or "manual"
    logger.info("backtest.weekly.started", customer_id=customer_id, run_id=run_id, lookback_days=lookback_days)

    async def _backtest():
        from core.config import get_settings
        from ml.arena import get_champion_model
        from ml.backtest import run_continuous_backtest

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                # Set tenant context for RLS
                await db.execute(f"SET app.current_customer_id = '{customer_id}'")

                # Get champion model
                champion = await get_champion_model(
                    db=db,
                    customer_id=uuid.UUID(customer_id),
                    model_name="demand_forecast",
                )

                if not champion:
                    logger.warning("backtest.weekly.no_champion", customer_id=customer_id)
                    return {"status": "skipped", "reason": "no_champion_model"}

                # Run full backtest
                result = await run_continuous_backtest(
                    db=db,
                    customer_id=uuid.UUID(customer_id),
                    model_id=champion["model_id"],
                    model_version=champion["version"],
                    window_size_days=30,
                    step_size_days=7,
                    lookback_days=lookback_days,
                )

                logger.info(
                    "backtest.weekly.completed",
                    customer_id=customer_id,
                    model_version=champion["version"],
                    windows_tested=result.get("windows_tested"),
                    avg_mae=result.get("avg_mae"),
                    avg_mape=result.get("avg_mape"),
                )

                return {
                    "status": "success",
                    "customer_id": customer_id,
                    "model_version": champion["version"],
                    "result": result,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_backtest())
    except Exception as exc:
        logger.error("backtest.weekly.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="workers.monitoring.calculate_opportunity_cost",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def calculate_opportunity_cost(self, customer_id: str, date: str | None = None):
    """
    Daily job: Quantify business impact of stockouts and overstock.

    Runs T+1: analyzes yesterday's data after actual sales are synced.
    Logs results to opportunity_cost_log table.
    """
    from datetime import date as date_type

    analysis_date = date_type.fromisoformat(date) if date else (datetime.utcnow() - timedelta(days=1)).date()
    logger.info("opportunity_cost.started", customer_id=customer_id, date=str(analysis_date))

    async def _analyze():
        from core.config import get_settings
        from db.models import (
            DemandForecast,
            InventoryLevel,
            OpportunityCostLog,
            Product,
            Transaction,
        )

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            records_created = 0
            total_stockout_cost = 0.0
            total_overstock_cost = 0.0

            async with async_session() as db:
                # Get forecasts for the analysis date
                forecasts_result = await db.execute(
                    select(DemandForecast).where(
                        DemandForecast.customer_id == customer_id,
                        DemandForecast.forecast_date == analysis_date,
                    )
                )
                forecasts = forecasts_result.scalars().all()

                for forecast in forecasts:
                    # Get actual sales for (store, product) on that date
                    sales_result = await db.execute(
                        select(func.coalesce(func.sum(Transaction.quantity), 0)).where(
                            Transaction.customer_id == customer_id,
                            Transaction.store_id == forecast.store_id,
                            Transaction.product_id == forecast.product_id,
                            func.date(Transaction.timestamp) == analysis_date,
                            Transaction.transaction_type == "sale",
                        )
                    )
                    actual_sales = int(sales_result.scalar())

                    # Get inventory at start of day
                    inv_result = await db.execute(
                        select(InventoryLevel.quantity_available)
                        .where(
                            InventoryLevel.store_id == forecast.store_id,
                            InventoryLevel.product_id == forecast.product_id,
                            func.date(InventoryLevel.timestamp) <= analysis_date,
                        )
                        .order_by(InventoryLevel.timestamp.desc())
                        .limit(1)
                    )
                    actual_stock = inv_result.scalar() or 0

                    # Get product pricing
                    product = await db.get(Product, forecast.product_id)
                    if not product or not product.unit_price:
                        continue

                    margin = (
                        (product.unit_price - product.unit_cost) / product.unit_price
                        if product.unit_cost and product.unit_price > 0
                        else 0.30  # Default 30% margin
                    )

                    forecasted_demand = forecast.forecasted_demand

                    # Detect stockout: forecast > actual sales AND low/zero stock
                    if actual_stock <= 0 and forecasted_demand > actual_sales:
                        lost_qty = max(0, int(forecasted_demand - actual_sales))
                        opp_cost = lost_qty * product.unit_price * margin

                        db.add(
                            OpportunityCostLog(
                                customer_id=customer_id,
                                store_id=forecast.store_id,
                                product_id=forecast.product_id,
                                date=analysis_date,
                                forecasted_demand=forecasted_demand,
                                actual_stock=actual_stock,
                                actual_sales=actual_sales,
                                lost_sales_qty=lost_qty,
                                opportunity_cost=round(opp_cost, 2),
                                cost_type="stockout",
                            )
                        )
                        total_stockout_cost += opp_cost
                        records_created += 1

                    # Detect overstock: inventory > 2x forecast
                    elif actual_stock > forecasted_demand * 2 and forecasted_demand > 0:
                        excess = int(actual_stock - forecasted_demand)
                        holding = (
                            product.holding_cost_per_unit_per_day * excess
                            if product.holding_cost_per_unit_per_day
                            else excess * (product.unit_cost or 1) * 0.25 / 365
                        )

                        db.add(
                            OpportunityCostLog(
                                customer_id=customer_id,
                                store_id=forecast.store_id,
                                product_id=forecast.product_id,
                                date=analysis_date,
                                forecasted_demand=forecasted_demand,
                                actual_stock=actual_stock,
                                actual_sales=actual_sales,
                                lost_sales_qty=0,
                                opportunity_cost=0.0,
                                holding_cost=round(holding, 2),
                                cost_type="overstock",
                            )
                        )
                        total_overstock_cost += holding
                        records_created += 1

                await db.commit()
        finally:
            await engine.dispose()

        summary = {
            "status": "success",
            "customer_id": customer_id,
            "date": str(analysis_date),
            "records_created": records_created,
            "total_stockout_cost": round(total_stockout_cost, 2),
            "total_overstock_cost": round(total_overstock_cost, 2),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("opportunity_cost.completed", **summary)
        return summary

    try:
        return asyncio.run(_analyze())
    except Exception as exc:
        logger.error("opportunity_cost.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="workers.monitoring.detect_anomalies_ml",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    acks_late=True,
)
def detect_anomalies_ml(self, customer_id: str):
    """
    Anomaly Detection Job (ML-powered with Isolation Forest).

    Runs every 6 hours to detect:
      - Demand spikes/drops
      - Inventory discrepancies
      - Price anomalies
      - Velocity anomalies

    Schedule: Every 6 hours (0:00, 6:00, 12:00, 18:00)
    """
    import uuid

    run_id = self.request.id or "manual"
    logger.info("anomaly.ml.started", customer_id=customer_id, run_id=run_id)

    async def _detect():
        from core.config import get_settings
        from ml.anomaly import detect_anomalies_ml as detect_func

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                # Set tenant context for RLS
                await db.execute(f"SET app.current_customer_id = '{customer_id}'")

                # Run anomaly detection
                result = await detect_func(
                    db=db,
                    customer_id=uuid.UUID(customer_id),
                    contamination=0.05,  # 5% outliers expected
                    severity_threshold=2.0,
                )

                logger.info(
                    "anomaly.ml.completed",
                    customer_id=customer_id,
                    anomalies_detected=result["anomalies_detected"],
                    critical=result["critical_count"],
                    warning=result["warning_count"],
                )

                return {
                    "status": "success",
                    "customer_id": customer_id,
                    "result": result,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_detect())
    except Exception as exc:
        logger.error("anomaly.ml.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="workers.monitoring.detect_ghost_stock",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    acks_late=True,
)
def detect_ghost_stock(self, customer_id: str):
    """
    Ghost Stock Detection Job.

    Runs daily after opportunity cost analysis to detect phantom inventory:
      - Products with stock but consistently low sales vs forecast
      - Likely causes: theft, damage, miscounts

    Schedule: Daily 4:30 AM (30 min after opportunity cost)
    """
    import uuid

    run_id = self.request.id or "manual"
    logger.info("ghost_stock.started", customer_id=customer_id, run_id=run_id)

    async def _detect():
        from core.config import get_settings
        from ml.ghost_stock import detect_ghost_stock as detect_func

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                # Set tenant context for RLS
                await db.execute(f"SET app.current_customer_id = '{customer_id}'")

                # Run ghost stock detection
                result = await detect_func(
                    db=db,
                    customer_id=uuid.UUID(customer_id),
                    lookback_days=7,
                    forecast_sales_ratio_threshold=0.3,
                    consecutive_days_threshold=3,
                )

                logger.info(
                    "ghost_stock.completed",
                    customer_id=customer_id,
                    ghost_stock_detected=result["ghost_stock_detected"],
                    total_value=result["total_value"],
                )

                return {
                    "status": "success",
                    "customer_id": customer_id,
                    "result": result,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_detect())
    except Exception as exc:
        logger.error("ghost_stock.failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)
