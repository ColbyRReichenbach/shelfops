import pandas as pd
import pytest

from ml.business_metrics import calculate_business_impact_metrics, calculate_overstock_dollars


def test_overstock_dollars_with_measured_cost():
    df = pd.DataFrame(
        [
            {"predicted_qty": 15, "actual_qty": 10, "unit_cost": 2.0},
            {"predicted_qty": 5, "actual_qty": 7, "unit_cost": 3.0},
        ]
    )
    dollars, confidence = calculate_overstock_dollars(df)
    assert dollars == 10.0
    assert confidence == "measured"


def test_overstock_dollars_with_estimated_category_cost():
    df = pd.DataFrame(
        [
            {"predicted_qty": 15, "actual_qty": 10, "category": "A", "category_median_cost": 1.5},
            {"predicted_qty": 6, "actual_qty": 6, "category": "A", "category_median_cost": 1.5},
        ]
    )
    dollars, confidence = calculate_overstock_dollars(df)
    assert dollars == 7.5
    assert confidence == "estimated"


def test_business_impact_metrics_with_measured_pricing_and_holding_cost():
    df = pd.DataFrame(
        [
            {
                "predicted_qty": 8,
                "actual_qty": 10,
                "unit_price": 5.0,
                "unit_cost": 3.0,
                "holding_cost_per_unit_per_day": 0.2,
            },
            {
                "predicted_qty": 12,
                "actual_qty": 9,
                "unit_price": 4.0,
                "unit_cost": 2.0,
                "holding_cost_per_unit_per_day": 0.1,
            },
        ]
    )
    metrics = calculate_business_impact_metrics(df)
    assert metrics["lost_sales_qty"] == 2.0
    assert metrics["opportunity_cost_stockout"] == pytest.approx(4.0)
    assert metrics["opportunity_cost_stockout_confidence"] == "measured"
    assert metrics["opportunity_cost_overstock"] == pytest.approx(0.3)
    assert metrics["opportunity_cost_overstock_confidence"] == "measured"


def test_business_impact_metrics_with_estimated_pricing():
    df = pd.DataFrame(
        [
            {
                "predicted_qty": 4,
                "actual_qty": 7,
                "category": "A",
                "category_median_cost": 2.0,
            }
        ]
    )
    metrics = calculate_business_impact_metrics(df)
    assert metrics["lost_sales_qty"] == 3.0
    assert metrics["opportunity_cost_stockout"] == pytest.approx(3.0 * (2.0 / 0.7) * 0.30)
    assert metrics["opportunity_cost_stockout_confidence"] == "estimated"
    assert metrics["opportunity_cost_overstock"] == pytest.approx(0.0)
    assert metrics["opportunity_cost_overstock_confidence"] == "estimated"
