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
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workers.celery_app import celery_app

logger = structlog.get_logger()


async def compute_recommendation_outcomes(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    as_of_date=None,
    recommendation_id: uuid.UUID | None = None,
):
    from db.models import InventoryLevel, Product, RecommendationOutcome, ReplenishmentRecommendation, Transaction
    from recommendations.outcomes import compute_recommendation_outcome

    analysis_date = as_of_date or datetime.utcnow().date()
    query = select(ReplenishmentRecommendation).where(ReplenishmentRecommendation.customer_id == customer_id)
    if recommendation_id is not None:
        query = query.where(ReplenishmentRecommendation.recommendation_id == recommendation_id)
    result = await db.execute(query.order_by(ReplenishmentRecommendation.created_at.asc()))
    recommendations = result.scalars().all()

    outcomes = []
    for recommendation in recommendations:
        rationale = recommendation.recommendation_rationale or {}
        start_date_raw = rationale.get("forecast_start_date")
        end_date_raw = rationale.get("forecast_end_date")
        if not start_date_raw or not end_date_raw:
            continue

        horizon_start_date = datetime.fromisoformat(f"{start_date_raw}T00:00:00").date()
        horizon_end_date = datetime.fromisoformat(f"{end_date_raw}T00:00:00").date()
        effective_end_date = min(horizon_end_date, analysis_date)

        sales_result = await db.execute(
            select(func.coalesce(func.sum(func.abs(Transaction.quantity)), 0)).where(
                Transaction.customer_id == customer_id,
                Transaction.store_id == recommendation.store_id,
                Transaction.product_id == recommendation.product_id,
                Transaction.transaction_type == "sale",
                func.date(Transaction.timestamp) >= horizon_start_date,
                func.date(Transaction.timestamp) <= effective_end_date,
            )
        )
        actual_sales_qty = float(sales_result.scalar() or 0.0)

        inventory_result = await db.execute(
            select(InventoryLevel.quantity_available)
            .where(
                InventoryLevel.customer_id == customer_id,
                InventoryLevel.store_id == recommendation.store_id,
                InventoryLevel.product_id == recommendation.product_id,
                func.date(InventoryLevel.timestamp) <= effective_end_date,
            )
            .order_by(InventoryLevel.timestamp.desc())
            .limit(1)
        )
        ending_inventory_qty = inventory_result.scalar_one_or_none()

        product = await db.get(Product, recommendation.product_id)
        outcome_summary = compute_recommendation_outcome(
            horizon_demand_mean=float(rationale.get("horizon_demand_mean") or 0.0),
            actual_sales_qty=actual_sales_qty,
            ending_inventory_qty=ending_inventory_qty,
            horizon_end_date=horizon_end_date,
            as_of_date=analysis_date,
            recommended_quantity=recommendation.recommended_quantity,
            safety_stock=recommendation.safety_stock,
            unit_cost=float(product.unit_cost) if product and product.unit_cost is not None else recommendation.estimated_unit_cost,
            unit_price=float(product.unit_price) if product and product.unit_price is not None else None,
            holding_cost_per_unit_per_day=(
                float(product.holding_cost_per_unit_per_day)
                if product and product.holding_cost_per_unit_per_day is not None
                else None
            ),
        )

        existing_result = await db.execute(
            select(RecommendationOutcome).where(
                RecommendationOutcome.recommendation_id == recommendation.recommendation_id
            )
        )
        outcome = existing_result.scalar_one_or_none()
        if outcome is None:
            outcome = RecommendationOutcome(
                recommendation_id=recommendation.recommendation_id,
                customer_id=recommendation.customer_id,
                store_id=recommendation.store_id,
                product_id=recommendation.product_id,
            )
            db.add(outcome)

        outcome.horizon_start_date = horizon_start_date
        outcome.horizon_end_date = horizon_end_date
        outcome.actual_sales_qty = outcome_summary.actual_sales_qty
        outcome.actual_demand_qty = outcome_summary.actual_demand_qty
        outcome.ending_inventory_qty = outcome_summary.ending_inventory_qty
        outcome.stockout_event = outcome_summary.stockout_event
        outcome.overstock_event = outcome_summary.overstock_event
        outcome.forecast_error_abs = outcome_summary.forecast_error_abs
        outcome.estimated_stockout_value = outcome_summary.estimated_stockout_value
        outcome.estimated_overstock_cost = outcome_summary.estimated_overstock_cost
        outcome.net_estimated_value = outcome_summary.net_estimated_value
        outcome.demand_confidence = outcome_summary.demand_confidence
        outcome.value_confidence = outcome_summary.value_confidence
        outcome.status = outcome_summary.status
        outcome.computed_at = datetime.utcnow()
        outcomes.append(outcome)

    await db.commit()
    return outcomes


async def summarize_recommendation_impact(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    as_of_date=None,
):
    from db.models import RecommendationOutcome, ReplenishmentRecommendation

    analysis_date = as_of_date or datetime.utcnow().date()
    await compute_recommendation_outcomes(db, customer_id=customer_id, as_of_date=analysis_date)

    recommendations_result = await db.execute(
        select(ReplenishmentRecommendation).where(ReplenishmentRecommendation.customer_id == customer_id)
    )
    recommendations = recommendations_result.scalars().all()

    outcomes_result = await db.execute(
        select(RecommendationOutcome).where(RecommendationOutcome.customer_id == customer_id)
    )
    outcomes = outcomes_result.scalars().all()

    closed_outcomes = [row for row in outcomes if row.status == "closed"]
    provisional_outcomes = [row for row in outcomes if row.status == "provisional"]
    accepted_count = sum(1 for row in recommendations if row.status == "accepted")
    edited_count = sum(1 for row in recommendations if row.status == "edited")
    rejected_count = sum(1 for row in recommendations if row.status == "rejected")

    average_forecast_error = (
        round(sum(row.forecast_error_abs for row in closed_outcomes) / len(closed_outcomes), 4)
        if closed_outcomes
        else None
    )
    net_estimated_value = round(sum(float(row.net_estimated_value or 0.0) for row in closed_outcomes), 4)

    return {
        "as_of_date": analysis_date.isoformat(),
        "total_recommendations": len(recommendations),
        "accepted_count": accepted_count,
        "edited_count": edited_count,
        "rejected_count": rejected_count,
        "closed_outcomes": len(closed_outcomes),
        "closed_outcomes_confidence": "measured" if closed_outcomes else "provisional",
        "provisional_outcomes": len(provisional_outcomes),
        "provisional_outcomes_confidence": "provisional",
        "average_forecast_error_abs": average_forecast_error,
        "average_forecast_error_abs_confidence": "measured" if closed_outcomes else "provisional",
        "net_estimated_value": net_estimated_value if closed_outcomes else None,
        "net_estimated_value_confidence": (
            "estimated" if closed_outcomes else "provisional"
        ),
        "stockout_events": sum(1 for row in closed_outcomes if row.stockout_event),
        "stockout_events_confidence": "measured" if closed_outcomes else "provisional",
        "overstock_events": sum(1 for row in closed_outcomes if row.overstock_event),
        "overstock_events_confidence": "measured" if closed_outcomes else "provisional",
    }


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
        from db.models import Alert, ForecastAccuracy, ModelVersion

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                customer_uuid = uuid.UUID(customer_id)
                champion_row = (
                    await db.execute(
                        select(ModelVersion.version)
                        .where(
                            ModelVersion.customer_id == customer_uuid,
                            ModelVersion.model_name == "demand_forecast",
                            ModelVersion.status == "champion",
                        )
                        .order_by(ModelVersion.promoted_at.desc())
                        .limit(1)
                    )
                ).one_or_none()
                champion_version = str(champion_row.version) if champion_row else None
                if not champion_version:
                    logger.warning("drift.no_champion", customer_id=customer_id)
                    return {"status": "skipped", "reason": "no_champion_model"}

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
                        ForecastAccuracy.customer_id == customer_uuid,
                        ForecastAccuracy.model_version == champion_version,
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
                        ForecastAccuracy.customer_id == customer_uuid,
                        ForecastAccuracy.model_version == champion_version,
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
                                "champion_version": champion_version,
                            },
                        },
                    )

                await db.commit()

                return {
                    "status": "drift_detected" if is_drifting else "healthy",
                    "customer_id": customer_id,
                    "champion_version": champion_version,
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
    name="workers.monitoring.check_feedback_health",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def check_feedback_health(
    self,
    customer_id: str,
    rejection_threshold: float = 0.60,
    min_decisions: int = 5,
    lookback_days: int = 30,
    cooldown_days: int = 7,
):
    """
    Daily job: Check if planners are rejecting POs at high rates.

    If rejection_rate > threshold for any (store, product) with enough
    decisions, triggers a feedback-driven retrain. A cooldown prevents
    retrain storms from the same persistent pattern.
    """
    run_id = self.request.id or "manual"
    logger.info("feedback_health.started", customer_id=customer_id, run_id=run_id)

    async def _check():
        from core.config import get_settings
        from db.models import MLAlert, PODecision, PurchaseOrder

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            async_session = async_sessionmaker(engine, class_=AsyncSession)

            async with async_session() as db:
                customer_uuid = uuid.UUID(customer_id)

                # Cooldown: skip if we already triggered a feedback retrain recently
                cooldown_cutoff = datetime.utcnow() - timedelta(days=cooldown_days)
                recent_alert = (
                    await db.execute(
                        select(MLAlert.ml_alert_id)
                        .where(
                            MLAlert.customer_id == customer_id,
                            MLAlert.alert_type == "feedback_drift",
                            MLAlert.created_at >= cooldown_cutoff,
                        )
                        .limit(1)
                    )
                ).one_or_none()

                if recent_alert:
                    logger.info("feedback_health.cooldown", customer_id=customer_id)
                    return {"status": "skipped", "reason": "feedback_retrain_cooldown"}

                # Aggregate rejection rates per (store, product)
                cutoff = datetime.utcnow() - timedelta(days=lookback_days)
                result = await db.execute(
                    select(
                        PurchaseOrder.store_id,
                        PurchaseOrder.product_id,
                        func.count(PODecision.decision_id).label("total_decisions"),
                        func.count(
                            case(
                                (PODecision.decision_type == "rejected", 1),
                            )
                        ).label("rejections"),
                    )
                    .join(PurchaseOrder, PODecision.po_id == PurchaseOrder.po_id)
                    .where(
                        PurchaseOrder.customer_id == customer_uuid,
                        PODecision.decided_at >= cutoff,
                    )
                    .group_by(PurchaseOrder.store_id, PurchaseOrder.product_id)
                    .having(func.count(PODecision.decision_id) >= min_decisions)
                )
                rows = result.all()

                flagged = []
                for row in rows:
                    total = row.total_decisions or 1
                    rejection_rate = (row.rejections or 0) / total
                    if rejection_rate > rejection_threshold:
                        flagged.append(
                            {
                                "store_id": str(row.store_id),
                                "product_id": str(row.product_id),
                                "rejection_rate": round(rejection_rate, 3),
                                "total_decisions": total,
                            }
                        )

                if flagged:
                    logger.warning(
                        "feedback_health.drift_detected",
                        customer_id=customer_id,
                        flagged_count=len(flagged),
                    )

                    alert = MLAlert(
                        ml_alert_id=uuid.uuid4(),
                        customer_id=customer_id,
                        alert_type="feedback_drift",
                        severity="warning",
                        title=f"Planner Feedback Drift — {len(flagged)} product(s) with >{int(rejection_threshold * 100)}% rejection rate",
                        message=f"Planners are rejecting POs at high rates for {len(flagged)} product(s). Feedback-driven retrain triggered.",
                        alert_metadata={
                            "flagged_products": flagged,
                            "threshold": rejection_threshold,
                            "lookback_days": lookback_days,
                        },
                        status="unread",
                        action_url="/models/review",
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(alert)

                    from workers.retrain import retrain_forecast_model

                    retrain_forecast_model.apply_async(
                        args=[customer_id],
                        kwargs={
                            "trigger": "feedback_drift",
                            "trigger_metadata": {
                                "flagged_products_count": len(flagged),
                                "flagged_products": flagged[:10],  # Cap metadata size
                                "threshold": rejection_threshold,
                            },
                        },
                    )

                await db.commit()

                return {
                    "status": "feedback_drift_detected" if flagged else "healthy",
                    "customer_id": customer_id,
                    "products_checked": len(rows),
                    "flagged_products_count": len(flagged),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_check())
    except Exception as exc:
        logger.error("feedback_health.failed", error=str(exc), exc_info=True)
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
                await db.execute(
                    text("SELECT set_config('app.current_customer_id', :customer_id, false)"),
                    {"customer_id": customer_id},
                )

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
    name="workers.monitoring.compute_forecast_accuracy",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    acks_late=True,
)
def compute_forecast_accuracy(
    self,
    customer_id: str,
    lookback_days: int = 30,
    model_version: str | None = None,
):
    """
    Compute realized forecast accuracy from persisted forecasts vs transaction outcomes.
    """
    run_id = self.request.id or "manual"
    logger.info(
        "accuracy_compute.started",
        customer_id=customer_id,
        run_id=run_id,
        lookback_days=lookback_days,
        model_version=model_version,
    )

    async def _compute():
        import pandas as pd

        from core.config import get_settings
        from db.models import DemandForecast, ForecastAccuracy, ModelVersion, ShadowPrediction, Transaction
        from ml.readiness import ReadinessThresholds, evaluate_and_persist_tenant_readiness

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
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

                end_date = datetime.utcnow().date() - timedelta(days=1)
                start_date = end_date - timedelta(days=max(lookback_days - 1, 0))
                if end_date < start_date:
                    return {"status": "skipped", "reason": "invalid_date_range"}

                forecast_query = select(
                    DemandForecast.store_id,
                    DemandForecast.product_id,
                    DemandForecast.forecast_date,
                    DemandForecast.forecasted_demand,
                    DemandForecast.model_version,
                ).where(
                    DemandForecast.customer_id == customer_uuid,
                    DemandForecast.forecast_date >= start_date,
                    DemandForecast.forecast_date <= end_date,
                )
                if model_version:
                    forecast_query = forecast_query.where(DemandForecast.model_version == model_version)

                forecast_rows = (await db.execute(forecast_query)).all()
                if not forecast_rows:
                    return {
                        "status": "skipped",
                        "reason": "no_forecasts_for_window",
                        "window_start": str(start_date),
                        "window_end": str(end_date),
                    }

                sales_date = func.date(Transaction.timestamp)
                signed_quantity = func.sum(
                    case(
                        (Transaction.transaction_type == "sale", func.abs(Transaction.quantity)),
                        (Transaction.transaction_type == "return", -func.abs(Transaction.quantity)),
                        else_=0,
                    )
                )
                actual_rows = (
                    await db.execute(
                        select(
                            Transaction.store_id,
                            Transaction.product_id,
                            sales_date.label("sale_date"),
                            signed_quantity.label("actual_quantity"),
                        )
                        .where(
                            Transaction.customer_id == customer_uuid,
                            sales_date >= start_date,
                            sales_date <= end_date,
                            Transaction.transaction_type.in_(["sale", "return"]),
                        )
                        .group_by(Transaction.store_id, Transaction.product_id, sales_date)
                    )
                ).all()

                actual_map = {
                    (str(row.store_id), str(row.product_id), str(row.sale_date)): float(row.actual_quantity or 0.0)
                    for row in actual_rows
                }

                delete_query = ForecastAccuracy.__table__.delete().where(
                    ForecastAccuracy.customer_id == customer_uuid,
                    ForecastAccuracy.forecast_date >= start_date,
                    ForecastAccuracy.forecast_date <= end_date,
                )
                if model_version:
                    delete_query = delete_query.where(ForecastAccuracy.model_version == model_version)
                await db.execute(delete_query)

                inserted = 0
                for row in forecast_rows:
                    key = (str(row.store_id), str(row.product_id), str(row.forecast_date))
                    actual = float(actual_map.get(key, 0.0))
                    forecasted = float(row.forecasted_demand or 0.0)
                    mae = abs(forecasted - actual)
                    mape = (mae / abs(actual)) if actual != 0 else 0.0
                    db.add(
                        ForecastAccuracy(
                            customer_id=customer_uuid,
                            store_id=row.store_id,
                            product_id=row.product_id,
                            forecast_date=row.forecast_date,
                            forecasted_demand=forecasted,
                            actual_demand=actual,
                            mae=mae,
                            mape=mape,
                            model_version=row.model_version,
                            evaluated_at=datetime.utcnow(),
                        )
                    )
                    inserted += 1

                shadow_rows = (
                    (
                        await db.execute(
                            select(ShadowPrediction).where(
                                ShadowPrediction.customer_id == customer_uuid,
                                ShadowPrediction.forecast_date >= start_date,
                                ShadowPrediction.forecast_date <= end_date,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                shadow_updated = 0
                for shadow in shadow_rows:
                    key = (str(shadow.store_id), str(shadow.product_id), str(shadow.forecast_date))
                    if key not in actual_map:
                        continue
                    actual = float(actual_map[key])
                    shadow.actual_demand = actual
                    shadow.champion_error = abs(float(shadow.champion_prediction or 0.0) - actual)
                    shadow.challenger_error = abs(float(shadow.challenger_prediction or 0.0) - actual)
                    shadow_updated += 1

                tx_rows = (
                    await db.execute(
                        select(
                            func.date(Transaction.timestamp).label("date"),
                            Transaction.store_id,
                            Transaction.product_id,
                            func.sum(
                                case(
                                    (Transaction.transaction_type == "sale", func.abs(Transaction.quantity)),
                                    (Transaction.transaction_type == "return", -func.abs(Transaction.quantity)),
                                    else_=0,
                                )
                            ).label("quantity"),
                        )
                        .where(
                            Transaction.customer_id == customer_uuid,
                            Transaction.transaction_type.in_(["sale", "return"]),
                        )
                        .group_by(func.date(Transaction.timestamp), Transaction.store_id, Transaction.product_id)
                    )
                ).all()
                tx_df = pd.DataFrame(
                    [
                        {
                            "date": row.date,
                            "store_id": str(row.store_id),
                            "product_id": str(row.product_id),
                            "quantity": float(row.quantity or 0.0),
                        }
                        for row in tx_rows
                    ],
                    columns=["date", "store_id", "product_id", "quantity"],
                )

                challenger_result = await db.execute(
                    select(ModelVersion.version)
                    .where(
                        ModelVersion.customer_id == customer_uuid,
                        ModelVersion.model_name == "demand_forecast",
                        ModelVersion.status.in_(["candidate", "challenger"]),
                    )
                    .order_by(ModelVersion.created_at.desc())
                    .limit(1)
                )
                challenger_row = challenger_result.one_or_none()
                candidate_version = str(challenger_row.version) if challenger_row else model_version

                readiness = await evaluate_and_persist_tenant_readiness(
                    db=db,
                    customer_id=customer_uuid,
                    transactions_df=tx_df,
                    candidate_version=candidate_version,
                    model_name="demand_forecast",
                    thresholds=ReadinessThresholds(
                        min_history_days=settings.ml_cold_start_min_history_days,
                        min_store_count=settings.ml_cold_start_min_store_count,
                        min_product_count=settings.ml_cold_start_min_product_count,
                        min_accuracy_samples=settings.ml_promotion_min_accuracy_samples,
                        accuracy_window_days=settings.ml_promotion_accuracy_window_days,
                    ),
                )

                await db.commit()
                return {
                    "status": "success",
                    "customer_id": customer_id,
                    "window_start": str(start_date),
                    "window_end": str(end_date),
                    "forecasts_evaluated": len(forecast_rows),
                    "accuracy_rows_written": inserted,
                    "shadow_rows_updated": shadow_updated,
                    "readiness": readiness,
                }
        finally:
            await engine.dispose()

    try:
        result = asyncio.run(_compute())
        logger.info("accuracy_compute.completed", **result)
        return result
    except Exception as exc:
        logger.error("accuracy_compute.failed", customer_id=customer_id, error=str(exc), exc_info=True)
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
                await db.execute(
                    text("SELECT set_config('app.current_customer_id', :customer_id, false)"),
                    {"customer_id": customer_id},
                )

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
                await db.execute(
                    text("SELECT set_config('app.current_customer_id', :customer_id, false)"),
                    {"customer_id": customer_id},
                )

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
                await db.execute(
                    text("SELECT set_config('app.current_customer_id', :customer_id, false)"),
                    {"customer_id": customer_id},
                )

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
