from datetime import datetime, timedelta

import pandas as pd
import pytest

from ml.readiness import ReadinessThresholds, evaluate_and_persist_tenant_readiness


def _transactions(history_days: int, stores: int, products: int) -> pd.DataFrame:
    rows = []
    start = datetime.utcnow().date() - timedelta(days=history_days)
    for day_idx in range(history_days):
        day = start + timedelta(days=day_idx)
        for store_idx in range(stores):
            for product_idx in range(products):
                rows.append(
                    {
                        "date": day.isoformat(),
                        "store_id": f"S{store_idx}",
                        "product_id": f"P{product_idx}",
                        "quantity": float((day_idx + product_idx) % 7 + 1),
                    }
                )
    return pd.DataFrame(rows)


@pytest.mark.asyncio
async def test_readiness_transitions_from_cold_start_to_warming(test_db, seeded_db):
    from sqlalchemy import select

    from db.models import TenantMLReadiness, TenantMLReadinessAudit

    customer_id = seeded_db["customer_id"]
    thresholds = ReadinessThresholds(
        min_history_days=90,
        min_store_count=1,
        min_product_count=5,
        min_accuracy_samples=20,
        accuracy_window_days=30,
    )

    cold = await evaluate_and_persist_tenant_readiness(
        db=test_db,
        customer_id=customer_id,
        transactions_df=_transactions(history_days=30, stores=1, products=10),
        candidate_version="v2",
        model_name="demand_forecast",
        thresholds=thresholds,
    )
    assert cold["state"] == "cold_start"
    assert cold["reason_code"] == "insufficient_history_days"

    warming = await evaluate_and_persist_tenant_readiness(
        db=test_db,
        customer_id=customer_id,
        transactions_df=_transactions(history_days=120, stores=1, products=10),
        candidate_version="v2",
        model_name="demand_forecast",
        thresholds=thresholds,
    )
    assert warming["state"] == "warming"
    assert warming["reason_code"] == "insufficient_candidate_accuracy_samples"
    await test_db.commit()

    readiness = (
        await test_db.execute(select(TenantMLReadiness).where(TenantMLReadiness.customer_id == customer_id))
    ).scalar_one()
    assert readiness.state == "warming"

    audit_rows = (
        (await test_db.execute(select(TenantMLReadinessAudit).where(TenantMLReadinessAudit.customer_id == customer_id)))
        .scalars()
        .all()
    )
    assert len(audit_rows) >= 2


@pytest.mark.asyncio
async def test_readiness_reaches_production_tier_active_with_accuracy_samples(test_db, seeded_db):
    from db.models import ForecastAccuracy, ModelVersion

    customer_id = seeded_db["customer_id"]
    store_id = seeded_db["store"].store_id
    product_id = seeded_db["product"].product_id

    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="demand_forecast",
            version="v1",
            status="champion",
            metrics={"mae": 1.0},
            smoke_test_passed=True,
            promoted_at=datetime.utcnow() - timedelta(days=5),
        )
    )
    for idx in range(15):
        eval_time = datetime.utcnow() - timedelta(days=idx)
        test_db.add(
            ForecastAccuracy(
                customer_id=customer_id,
                store_id=store_id,
                product_id=product_id,
                forecast_date=(datetime.utcnow() - timedelta(days=idx + 1)).date(),
                forecasted_demand=10.0,
                actual_demand=9.0,
                mae=1.0,
                mape=0.1111,
                model_version="v2",
                evaluated_at=eval_time,
            )
        )
        test_db.add(
            ForecastAccuracy(
                customer_id=customer_id,
                store_id=store_id,
                product_id=product_id,
                forecast_date=(datetime.utcnow() - timedelta(days=idx + 1)).date(),
                forecasted_demand=9.5,
                actual_demand=9.0,
                mae=0.5,
                mape=0.0555,
                model_version="v1",
                evaluated_at=eval_time,
            )
        )
    await test_db.commit()

    readiness = await evaluate_and_persist_tenant_readiness(
        db=test_db,
        customer_id=customer_id,
        transactions_df=_transactions(history_days=120, stores=2, products=8),
        candidate_version="v2",
        model_name="demand_forecast",
        thresholds=ReadinessThresholds(
            min_history_days=90,
            min_store_count=2,
            min_product_count=8,
            min_accuracy_samples=10,
            accuracy_window_days=30,
        ),
    )
    assert readiness["state"] == "production_tier_active"
    assert readiness["reason_code"] == "all_gates_passed"
