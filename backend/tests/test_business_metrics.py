import pandas as pd

from ml.business_metrics import calculate_overstock_dollars


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
