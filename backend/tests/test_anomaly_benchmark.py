import pandas as pd
import pytest

from ml.anomaly_benchmark import (
    AnomalyExperimentConfig,
    evaluate_binary_detector,
    prepare_stockout_detection_frame,
    run_anomaly_detection_experiment,
    score_stockout_risk,
)


def test_evaluate_binary_detector_reports_precision_recall_and_review_rate():
    metrics = evaluate_binary_detector([1, 1, 0, 0], [0.9, 0.2, 0.8, 0.1], threshold=0.5)

    assert metrics["true_positive"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["review_rate"] == 0.5


def test_stockout_features_do_not_use_current_stockout_label_for_score():
    raw = pd.DataFrame(
        {
            "store_id": [1, 1, 1, 1],
            "product_id": [10, 10, 10, 10],
            "dt": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "sale_amount": [5.0, 5.0, 5.0, 0.0],
            "stock_hour6_22_cnt": [0, 0, 0, 4],
            "discount": [1.0, 1.0, 1.0, 1.0],
            "holiday_flag": [0, 0, 0, 0],
            "activity_flag": [0, 0, 0, 0],
            "precpt": [0.0, 0.0, 0.0, 0.0],
            "avg_temperature": [10.0, 10.0, 10.0, 10.0],
            "avg_humidity": [50.0, 50.0, 50.0, 50.0],
            "avg_wind_level": [1.0, 1.0, 1.0, 1.0],
            "third_category_id": [3, 3, 3, 3],
        }
    )

    frame = prepare_stockout_detection_frame(raw)
    scores = score_stockout_risk(frame)

    assert frame.loc[3, "stockout_label"] == 1
    assert frame.loc[3, "expected_sales_7d"] == 5.0
    assert scores.iloc[3] > scores.iloc[2]


def test_stockout_feature_lookback_is_configurable():
    raw = pd.DataFrame(
        {
            "store_id": [1, 1, 1, 1, 1, 1],
            "product_id": [10, 10, 10, 10, 10, 10],
            "dt": pd.date_range("2024-01-01", periods=6).astype(str),
            "sale_amount": [2.0, 4.0, 6.0, 8.0, 10.0, 0.0],
            "stock_hour6_22_cnt": [0, 0, 0, 0, 0, 4],
            "discount": [1.0] * 6,
            "holiday_flag": [0] * 6,
            "activity_flag": [0] * 6,
            "precpt": [0.0] * 6,
            "avg_temperature": [10.0] * 6,
            "avg_humidity": [50.0] * 6,
            "avg_wind_level": [1.0] * 6,
            "third_category_id": [3] * 6,
        }
    )

    short = prepare_stockout_detection_frame(raw, lookback_days=3)
    long = prepare_stockout_detection_frame(raw, lookback_days=5)

    assert short.loc[5, "feature_lookback_days"] == 3
    assert long.loc[5, "feature_lookback_days"] == 5
    assert short.loc[5, "expected_sales_7d"] == pytest.approx((6.0 + 8.0 + 10.0) / 3)
    assert long.loc[5, "expected_sales_7d"] == pytest.approx((2.0 + 4.0 + 6.0 + 8.0 + 10.0) / 5)


def test_run_anomaly_detection_experiment_returns_spec_lineage_and_gates(tmp_path):
    rows = []
    for product_id in ("A", "B"):
        for day in range(18):
            is_stockout = day in {8, 13}
            rows.append(
                {
                    "store_id": "S1",
                    "product_id": product_id,
                    "dt": str(pd.Timestamp("2024-01-01") + pd.Timedelta(days=day)),
                    "sale_amount": 0.0 if is_stockout else 8.0 + (day % 3),
                    "stock_hour6_22_cnt": 3 if is_stockout else 0,
                    "discount": 0.9 if day % 6 == 0 else 1.0,
                    "holiday_flag": 1 if day == 10 else 0,
                    "activity_flag": 1 if day % 6 == 0 else 0,
                    "precpt": 4.0 if day in {8, 13} else 0.1,
                    "avg_temperature": 31.0 if day == 13 else 18.0,
                    "avg_humidity": 55.0,
                    "avg_wind_level": 1.0,
                    "first_category_id": "fresh",
                    "second_category_id": "produce",
                    "third_category_id": "berries",
                }
            )
    pd.DataFrame(rows).to_parquet(tmp_path / "eval.parquet", index=False)

    config = AnomalyExperimentConfig(
        baseline_version="a1",
        challenger_version="e_anomaly_test",
        experiment_spec_id="spec-1",
        experiment_spec_hash="hash-1",
        spec_template_id="freshretailnet_balanced_context_v1",
        spec_name="Balanced context",
        feature_set_id="freshretailnet_balanced_context_v1",
        feature_config={"lookback_days": 5, "include_weather": True},
        model_config={
            "threshold": 0.35,
            "weights": {
                "sales_gap": 0.58,
                "zero_sales": 0.18,
                "promo": 0.11,
                "holiday": 0.04,
                "weather_stress": 0.09,
            },
        },
        promotion_gates={
            "precision_min": 0.2,
            "recall_min": 0.2,
            "false_positive_rate_max": 0.5,
            "review_rate_max": 0.5,
            "measured_feedback_required_for_promotion": True,
        },
    )

    report = run_anomaly_detection_experiment(data_dir=tmp_path, config=config)

    assert report["experiment"]["model_name"] == "anomaly_detector"
    assert report["dataset"]["dataset_id"] == "freshretailnet_50k"
    assert report["challenger"]["holdout_metrics"]["provenance"] == "benchmark"
    assert report["challenger"]["lineage_metadata"]["experiment_spec_hash"] == "hash-1"
    assert report["challenger"]["lineage_metadata"]["feature_config"]["lookback_days"] == 5
    assert report["promotion_comparison"]["promoted"] is False
    assert report["promotion_comparison"]["gate_checks"]["measured_cycle_count_feedback_gate"] is False
    assert report["claim_boundary"].startswith("FreshRetailNet benchmark")
