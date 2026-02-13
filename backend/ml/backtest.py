"""
Continuous Backtesting — Walk-forward validation on production data.

Real retailers need to answer:
  - "How would this model have performed last month if we'd used it?"
  - "Is our current champion getting worse over time?"
  - "Did that data drift event actually hurt predictions?"

This module implements rolling-window backtesting that runs automatically:
  - Daily: Backtest champion on yesterday's data (T-1 validation)
  - Weekly: Full 90-day backtest after retraining
  - Event-driven: When drift detected, quantify impact

Agent: ml-engineer
Skill: ml-forecasting
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


# ─── Walk-Forward Validation ────────────────────────────────────────────────


async def run_continuous_backtest(
    db: AsyncSession,
    customer_id: uuid.UUID,
    model_id: uuid.UUID,
    model_version: str,
    window_size_days: int = 30,
    step_size_days: int = 7,
    lookback_days: int = 90,
) -> dict:
    """
    Walk-forward validation on production data.

    For each week in the last lookback_days:
      1. Load model state at that date (from registry)
      2. Generate forecasts for next window_size_days
      3. Compare to actual sales (from transactions)
      4. Record MAE, MAPE, stockout_miss_rate, overstock_rate
      5. Store in backtest_results table

    Args:
        db: Database session
        customer_id: Tenant ID
        model_id: Model version UUID
        model_version: Model version string (for logging)
        window_size_days: Forecast horizon (default 30 days)
        step_size_days: Window step (default 7 days)
        lookback_days: How far back to test (default 90 days)

    Returns:
        dict with {windows_tested, avg_mae, avg_mape, results: [...]}
    """
    from db.models import Base, Transaction

    logger.info(
        "backtest.started",
        customer_id=str(customer_id),
        model_version=model_version,
        window_size_days=window_size_days,
        lookback_days=lookback_days,
    )

    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    results = []
    current_date = start_date

    while current_date + timedelta(days=window_size_days) <= end_date:
        forecast_start = current_date
        forecast_end = current_date + timedelta(days=window_size_days)

        # Load actual sales for this window
        actual_sales_query = select(
            Transaction.store_id,
            Transaction.product_id,
            Transaction.date,
            Transaction.quantity,
        ).where(
            Transaction.customer_id == customer_id,
            Transaction.date >= forecast_start,
            Transaction.date <= forecast_end,
        )

        actual_result = await db.execute(actual_sales_query)
        actual_sales = actual_result.all()

        if not actual_sales:
            logger.warning(
                "backtest.no_actual_data",
                forecast_start=str(forecast_start),
                forecast_end=str(forecast_end),
            )
            current_date += timedelta(days=step_size_days)
            continue

        # Convert to DataFrame for easier computation
        actual_df = pd.DataFrame(
            [
                {
                    "store_id": str(row.store_id),
                    "product_id": str(row.product_id),
                    "date": row.date,
                    "actual_quantity": row.quantity,
                }
                for row in actual_sales
            ]
        )

        # Load forecasts for this window (from demand_forecasts table)
        # Note: This assumes forecasts were generated at forecast_start
        from db.models import DemandForecast

        forecast_query = select(
            DemandForecast.store_id,
            DemandForecast.product_id,
            DemandForecast.forecast_date,
            DemandForecast.forecasted_demand,
        ).where(
            DemandForecast.customer_id == customer_id,
            DemandForecast.forecast_date >= forecast_start,
            DemandForecast.forecast_date <= forecast_end,
            DemandForecast.model_version == model_version,
        )

        forecast_result = await db.execute(forecast_query)
        forecasts = forecast_result.all()

        if not forecasts:
            logger.warning(
                "backtest.no_forecasts",
                model_version=model_version,
                forecast_start=str(forecast_start),
                forecast_end=str(forecast_end),
            )
            current_date += timedelta(days=step_size_days)
            continue

        forecast_df = pd.DataFrame(
            [
                {
                    "store_id": str(row.store_id),
                    "product_id": str(row.product_id),
                    "date": row.forecast_date,
                    "forecasted_demand": row.forecasted_demand,
                }
                for row in forecasts
            ]
        )

        # Merge actual vs forecast
        comparison_df = pd.merge(
            actual_df,
            forecast_df,
            on=["store_id", "product_id", "date"],
            how="inner",
        )

        if comparison_df.empty:
            logger.warning(
                "backtest.no_matching_forecasts",
                forecast_start=str(forecast_start),
                forecast_end=str(forecast_end),
            )
            current_date += timedelta(days=step_size_days)
            continue

        # Calculate metrics
        comparison_df["error"] = comparison_df["forecasted_demand"] - comparison_df["actual_quantity"]
        comparison_df["abs_error"] = comparison_df["error"].abs()
        comparison_df["pct_error"] = (
            comparison_df["abs_error"] / comparison_df["actual_quantity"].replace(0, 1)
        ) * 100

        mae = comparison_df["abs_error"].mean()
        mape = comparison_df["pct_error"].mean()

        # Stockout miss rate: % of actual stockouts (qty=0) we didn't predict
        stockouts = comparison_df[comparison_df["actual_quantity"] == 0]
        if len(stockouts) > 0:
            stockout_miss_rate = (stockouts["forecasted_demand"] > 0).sum() / len(stockouts)
        else:
            stockout_miss_rate = 0.0

        # Overstock rate: % of forecasts that were >2x actual demand
        overstock_count = (comparison_df["forecasted_demand"] > comparison_df["actual_quantity"] * 2).sum()
        overstock_rate = overstock_count / len(comparison_df) if len(comparison_df) > 0 else 0.0

        # Store result
        from db.models import BacktestResult

        backtest_result = BacktestResult(
            backtest_id=uuid.uuid4(),
            customer_id=customer_id,
            model_id=model_id,
            forecast_date=forecast_start,
            actual_date=date.today(),
            mae=float(mae),
            mape=float(mape),
            stockout_miss_rate=float(stockout_miss_rate),
            overstock_rate=float(overstock_rate),
            evaluated_at=datetime.utcnow(),
        )
        db.add(backtest_result)

        results.append(
            {
                "forecast_start": str(forecast_start),
                "forecast_end": str(forecast_end),
                "mae": round(float(mae), 2),
                "mape": round(float(mape), 2),
                "stockout_miss_rate": round(float(stockout_miss_rate), 3),
                "overstock_rate": round(float(overstock_rate), 3),
                "samples": len(comparison_df),
            }
        )

        current_date += timedelta(days=step_size_days)

    await db.commit()

    # Summary
    if results:
        avg_mae = sum(r["mae"] for r in results) / len(results)
        avg_mape = sum(r["mape"] for r in results) / len(results)
    else:
        avg_mae = 0.0
        avg_mape = 0.0

    logger.info(
        "backtest.completed",
        customer_id=str(customer_id),
        model_version=model_version,
        windows_tested=len(results),
        avg_mae=round(avg_mae, 2),
        avg_mape=round(avg_mape, 2),
    )

    return {
        "windows_tested": len(results),
        "avg_mae": avg_mae,
        "avg_mape": avg_mape,
        "results": results,
    }


# ─── Daily T-1 Validation ───────────────────────────────────────────────────


async def backtest_yesterday(
    db: AsyncSession,
    customer_id: uuid.UUID,
    model_id: uuid.UUID,
    model_version: str,
) -> dict:
    """
    Backtest champion on yesterday's data (T-1 validation).

    This is the fastest feedback loop: "Did yesterday's forecasts work?"

    Args:
        db: Database session
        customer_id: Tenant ID
        model_id: Model version UUID
        model_version: Model version string

    Returns:
        dict with {mae, mape, samples, date}
    """
    yesterday = date.today() - timedelta(days=1)

    logger.info(
        "backtest.t1_validation.started",
        customer_id=str(customer_id),
        model_version=model_version,
        date=str(yesterday),
    )

    # Run backtest for just yesterday
    result = await run_continuous_backtest(
        db=db,
        customer_id=customer_id,
        model_id=model_id,
        model_version=model_version,
        window_size_days=1,
        step_size_days=1,
        lookback_days=1,
    )

    if result["windows_tested"] == 0:
        logger.warning(
            "backtest.t1_validation.no_data",
            customer_id=str(customer_id),
            date=str(yesterday),
        )
        return {"mae": None, "mape": None, "samples": 0, "date": str(yesterday)}

    window_result = result["results"][0]
    logger.info(
        "backtest.t1_validation.completed",
        customer_id=str(customer_id),
        model_version=model_version,
        mae=window_result["mae"],
        mape=window_result["mape"],
        samples=window_result["samples"],
    )

    return {
        "mae": window_result["mae"],
        "mape": window_result["mape"],
        "samples": window_result["samples"],
        "date": str(yesterday),
    }


# ─── Backtest Results Retrieval ─────────────────────────────────────────────


async def get_backtest_trend(
    db: AsyncSession,
    customer_id: uuid.UUID,
    model_id: uuid.UUID,
    days: int = 90,
) -> list[dict]:
    """
    Get backtest results for a model over the last N days.

    Returns time-series for charting: [{date, mae, mape}, ...]

    Args:
        db: Database session
        customer_id: Tenant ID
        model_id: Model version UUID
        days: Lookback period (default 90)

    Returns:
        List of {forecast_date, mae, mape, stockout_miss_rate, overstock_rate}
    """
    from db.models import BacktestResult

    cutoff = date.today() - timedelta(days=days)

    result = await db.execute(
        select(
            BacktestResult.forecast_date,
            BacktestResult.mae,
            BacktestResult.mape,
            BacktestResult.stockout_miss_rate,
            BacktestResult.overstock_rate,
        )
        .where(
            BacktestResult.customer_id == customer_id,
            BacktestResult.model_id == model_id,
            BacktestResult.forecast_date >= cutoff,
        )
        .order_by(BacktestResult.forecast_date.asc())
    )

    rows = result.all()

    return [
        {
            "forecast_date": str(row.forecast_date),
            "mae": round(row.mae, 2) if row.mae else None,
            "mape": round(row.mape, 2) if row.mape else None,
            "stockout_miss_rate": round(row.stockout_miss_rate, 3) if row.stockout_miss_rate else None,
            "overstock_rate": round(row.overstock_rate, 3) if row.overstock_rate else None,
        }
        for row in rows
    ]
