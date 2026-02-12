"""
Promotion Effectiveness Tracker — Measure Actual vs Expected Promo Lift.

Called 7 days after a promotion ends to calculate actual lift,
then stores results for ML feedback (future promo forecasts).

Example: Expected 1.5x lift, actual was 1.8x → store this for next
time the model predicts demand during a similar promotion.

Agent: data-engineer + ml-engineer
Skill: postgresql, ml-forecasting
"""

import uuid
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Promotion, PromotionResult, Transaction

logger = structlog.get_logger()


async def measure_promotion_effectiveness(
    db: AsyncSession,
    customer_id: uuid.UUID,
    lookback_days: int = 14,
) -> dict:
    """
    Evaluate recently completed promotions.

    Finds promotions that ended between (now - lookback_days) and (now - 7 days),
    giving 7 days of post-promo data to settle before measuring.

    For each:
    1. Baseline = avg daily sales 30 days BEFORE promo start
    2. Promo sales = avg daily sales DURING promo
    3. Actual lift = promo_avg / baseline_avg
    4. Compare vs promotion.expected_lift
    """
    today = date.today()
    # Promotions that ended 7-14 days ago (settled enough to measure)
    window_end = today - timedelta(days=7)
    window_start = today - timedelta(days=lookback_days)

    promo_result = await db.execute(
        select(Promotion).where(
            Promotion.customer_id == customer_id,
            Promotion.end_date >= window_start,
            Promotion.end_date <= window_end,
        )
    )
    promotions = promo_result.scalars().all()

    measured = 0
    flagged = 0

    for promo in promotions:
        # Check if already measured
        existing = await db.execute(
            select(PromotionResult).where(
                PromotionResult.promotion_id == promo.promotion_id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Get products in this promotion (assume store-wide or specific product)
        promo_store_id = promo.store_id
        promo_product_id = promo.product_id

        if not promo_store_id or not promo_product_id:
            continue

        # Baseline: 30-day avg daily sales BEFORE promo
        baseline_start = promo.start_date - timedelta(days=30)
        baseline_end = promo.start_date - timedelta(days=1)

        baseline_result = await db.execute(
            select(func.avg(Transaction.quantity)).where(
                Transaction.customer_id == customer_id,
                Transaction.store_id == promo_store_id,
                Transaction.product_id == promo_product_id,
                func.date(Transaction.transaction_date) >= baseline_start,
                func.date(Transaction.transaction_date) <= baseline_end,
            )
        )
        baseline_avg = baseline_result.scalar() or 0

        if baseline_avg <= 0:
            continue  # Can't compute lift without baseline

        # Promo period: avg daily sales
        promo_sales_result = await db.execute(
            select(func.avg(Transaction.quantity)).where(
                Transaction.customer_id == customer_id,
                Transaction.store_id == promo_store_id,
                Transaction.product_id == promo_product_id,
                func.date(Transaction.transaction_date) >= promo.start_date,
                func.date(Transaction.transaction_date) <= promo.end_date,
            )
        )
        promo_avg = promo_sales_result.scalar() or 0

        actual_lift = round(float(promo_avg) / float(baseline_avg), 3) if baseline_avg > 0 else 1.0
        expected_lift = promo.expected_lift or 1.0
        variance_pct = round(abs(actual_lift - expected_lift) / max(expected_lift, 0.01) * 100, 1)

        # Flag if variance > 30%
        needs_review = variance_pct > 30

        db.add(
            PromotionResult(
                customer_id=customer_id,
                promotion_id=promo.promotion_id,
                store_id=promo_store_id,
                product_id=promo_product_id,
                baseline_daily_avg=round(float(baseline_avg), 2),
                promo_daily_avg=round(float(promo_avg), 2),
                actual_lift=actual_lift,
                expected_lift=expected_lift,
                variance_pct=variance_pct,
                needs_review=needs_review,
            )
        )

        measured += 1
        if needs_review:
            flagged += 1

    await db.commit()

    summary = {
        "promotions_evaluated": measured,
        "flagged_for_review": flagged,
        "total_candidates": len(promotions),
    }
    logger.info("promo_tracking.completed", **summary)
    return summary
