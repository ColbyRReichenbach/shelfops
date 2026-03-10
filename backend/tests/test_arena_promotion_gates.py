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
            "lost_sales_qty": 40.0,
            "opportunity_cost_stockout": 240.0,
            "opportunity_cost_stockout_confidence": "measured",
            "opportunity_cost_overstock": 18.0,
            "opportunity_cost_overstock_confidence": "measured",
            "overstock_dollars": 1000.0,
            "overstock_dollars_confidence": "measured",
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
            "lost_sales_qty": 39.8,
            "opportunity_cost_stockout": 238.0,
            "opportunity_cost_stockout_confidence": "measured",
            "opportunity_cost_overstock": 17.9,
            "opportunity_cost_overstock_confidence": "measured",
            "overstock_dollars": 980.0,
            "overstock_dollars_confidence": "measured",
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
            "lost_sales_qty": 39.8,
            "opportunity_cost_stockout": 238.0,
            "opportunity_cost_stockout_confidence": "measured",
            "opportunity_cost_overstock": 17.9,
            "opportunity_cost_overstock_confidence": "measured",
            "overstock_dollars": 980.0,
            "overstock_dollars_confidence": "measured",
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
            "lost_sales_qty": 40.0,
            "opportunity_cost_stockout": 240.0,
            "opportunity_cost_stockout_confidence": "estimated",
            "opportunity_cost_overstock": 18.0,
            "opportunity_cost_overstock_confidence": "estimated",
            "overstock_dollars": 1000.0,
            "overstock_dollars_confidence": "estimated",
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
    assert result["gate_checks"]["opportunity_cost_stockout_gate"] is False
    assert result["gate_checks"]["overstock_dollars_gate"] is False


@pytest.mark.asyncio
async def test_promotion_gate_blocks_on_stockout_economic_regression(test_db, seeded_db):
    customer_id = seeded_db["customer_id"]

    champion_metrics = {
        "mae": 10.0,
        "mape": 0.20,
        "coverage": 1.0,
        "stockout_miss_rate": 0.05,
        "overstock_rate": 0.10,
        "lost_sales_qty": 30.0,
        "opportunity_cost_stockout": 120.0,
        "opportunity_cost_stockout_confidence": "measured",
        "opportunity_cost_overstock": 15.0,
        "opportunity_cost_overstock_confidence": "measured",
        "overstock_dollars": 900.0,
        "overstock_dollars_confidence": "measured",
    }
    candidate_metrics = {
        "mae": 9.7,
        "mape": 0.19,
        "coverage": 1.0,
        "stockout_miss_rate": 0.05,
        "overstock_rate": 0.10,
        "lost_sales_qty": 31.0,
        "opportunity_cost_stockout": 140.0,
        "opportunity_cost_stockout_confidence": "measured",
        "opportunity_cost_overstock": 14.0,
        "opportunity_cost_overstock_confidence": "measured",
        "overstock_dollars": 890.0,
        "overstock_dollars_confidence": "measured",
    }

    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v30",
        status="champion",
        smoke_test_passed=True,
        metrics=champion_metrics,
    )
    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v31",
        status="candidate",
        smoke_test_passed=True,
        metrics=candidate_metrics,
    )

    result = await evaluate_for_promotion(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        candidate_version="v31",
        candidate_metrics=candidate_metrics,
    )

    assert result["promoted"] is False
    assert result["gate_checks"]["mae_gate"] is True
    assert result["gate_checks"]["mape_gate"] is True
    assert result["gate_checks"]["opportunity_cost_stockout_gate"] is False
    assert result["gate_checks"]["lost_sales_qty_gate"] is False
