import pytest

from ml.arena import evaluate_for_promotion, register_model_version


@pytest.mark.asyncio
async def test_business_and_ds_gate_promotes_when_non_regressing(test_db, seeded_db):
    customer_id = seeded_db["customer_id"]

    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v1",
        status="champion",
        smoke_test_passed=True,
        metrics={
            "mae": 10.0,
            "mape": 0.20,
            "coverage": 1.0,
            "stockout_miss_rate": 0.08,
            "overstock_rate": 0.12,
            "overstock_dollars": 1000.0,
        },
    )

    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v2",
        status="candidate",
        smoke_test_passed=True,
        metrics={
            "mae": 10.1,
            "mape": 0.202,
            "coverage": 1.0,
            "stockout_miss_rate": 0.079,
            "overstock_rate": 0.118,
            "overstock_dollars": 980.0,
        },
    )

    result = await evaluate_for_promotion(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        candidate_version="v2",
        candidate_metrics={
            "mae": 10.1,
            "mape": 0.202,
            "coverage": 1.0,
            "stockout_miss_rate": 0.079,
            "overstock_rate": 0.118,
            "overstock_dollars": 980.0,
        },
    )

    assert result["promoted"] is True
    assert result["gate_checks"]["mae_gate"] is True


@pytest.mark.asyncio
async def test_business_and_ds_gate_blocks_on_mape_regression(test_db, seeded_db):
    customer_id = seeded_db["customer_id"]

    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v10",
        status="champion",
        smoke_test_passed=True,
        metrics={"mae": 10.0, "mape": 0.20, "coverage": 1.0},
    )

    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v11",
        status="candidate",
        smoke_test_passed=True,
        metrics={"mae": 10.1, "mape": 0.25, "coverage": 1.0},
    )

    result = await evaluate_for_promotion(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        candidate_version="v11",
        candidate_metrics={"mae": 10.1, "mape": 0.25, "coverage": 1.0},
    )

    assert result["promoted"] is False
    assert result["gate_checks"]["mape_gate"] is False
    assert "failed_gates" in result["reason"]


@pytest.mark.asyncio
async def test_promotion_gate_fails_closed_when_business_metrics_missing(test_db, seeded_db):
    customer_id = seeded_db["customer_id"]

    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v20",
        status="champion",
        smoke_test_passed=True,
        metrics={
            "mae": 10.0,
            "mape": 0.20,
            "coverage": 0.9,
            "stockout_miss_rate": 0.08,
            "overstock_rate": 0.12,
            "overstock_dollars": 1000.0,
        },
    )

    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v21",
        status="candidate",
        smoke_test_passed=True,
        metrics={
            "mae": 9.9,
            "mape": 0.19,
            "coverage": 0.92,
            "stockout_miss_rate": 0.07,
            "overstock_rate": 0.11,
        },
    )

    result = await evaluate_for_promotion(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        candidate_version="v21",
        candidate_metrics={
            "mae": 9.9,
            "mape": 0.19,
            "coverage": 0.92,
            "stockout_miss_rate": 0.07,
            "overstock_rate": 0.11,
        },
    )

    assert result["promoted"] is False
    assert result["gate_checks"]["overstock_dollars_gate"] is False
