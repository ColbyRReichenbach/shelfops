import pytest

from ml.experiment_specs import (
    anomaly_config_kwargs_from_spec,
    decision_config_kwargs_from_spec,
    hash_experiment_spec,
    list_experiment_spec_templates,
    materialize_experiment_spec,
)


def test_experiment_spec_templates_are_executable_and_hashed():
    templates = list_experiment_spec_templates(model_name="demand_forecast")

    assert {row["template_id"] for row in templates} >= {
        "m5_lag_price_calendar_v1",
        "m5_price_promo_lag_v1",
        "m5_price_movement_proxy_v1",
        "m5_velocity_segmented_bias_v1",
        "m5_activation_aware_window_v1",
        "m5_segment_gated_activation_window_v1",
        "m5_segment_routed_activation_window_v1",
    }
    for row in templates:
        assert row["dataset_id"] == "m5_walmart"
        assert row["provenance"] == "benchmark"
        assert len(row["spec_hash"]) == 64
        assert hash_experiment_spec(row["spec"]) == row["spec_hash"]


def test_anomaly_experiment_spec_templates_are_executable_and_hashed():
    templates = list_experiment_spec_templates(model_name="anomaly_detector")

    assert {row["template_id"] for row in templates} >= {
        "freshretailnet_stockout_precision_v1",
        "freshretailnet_balanced_context_v1",
        "freshretailnet_high_recall_review_cap_v1",
    }
    for row in templates:
        assert row["dataset_id"] == "freshretailnet_50k"
        assert row["provenance"] == "benchmark"
        assert row["calibration_strategy"].startswith("threshold_")
        assert len(row["spec_hash"]) == 64
        assert hash_experiment_spec(row["spec"]) == row["spec_hash"]


def test_materialized_experiment_spec_overrides_are_bounded_and_change_hash():
    baseline = materialize_experiment_spec(template_id="m5_lag_price_calendar_v1")
    challenger = materialize_experiment_spec(
        template_id="m5_lag_price_calendar_v1",
        spec_name="manual_depth_test",
        overrides={
            "feature_set_id": "m5_manual_depth_test_v1",
            "feature_config": {"lag_days": [1, 7, 21, 42]},
            "model_config": {"hyperparameters": {"num_leaves": 31, "n_estimators": 120}},
        },
    )

    assert challenger["feature_set_id"] == "m5_manual_depth_test_v1"
    assert challenger["feature_config"]["lag_days"] == [1, 7, 21, 42]
    assert challenger["model_config"]["hyperparameters"]["num_leaves"] == 31
    assert hash_experiment_spec(challenger) != hash_experiment_spec(baseline)

    kwargs = decision_config_kwargs_from_spec(challenger)
    assert kwargs["feature_set_id"] == "m5_manual_depth_test_v1"
    assert kwargs["feature_config"]["lag_days"] == [1, 7, 21, 42]


def test_activation_aware_spec_carries_dataset_window_contract():
    spec = materialize_experiment_spec(template_id="m5_activation_aware_window_v1")

    assert spec["experiment_type"] == "data_window"
    assert spec["dataset_config"]["activation_policy"] == "exclude_pre_first_price"
    assert spec["dataset_config"]["activation_marker"] == "first_available_sell_price"
    assert spec["dataset_config"]["primary_metric_filter"] == "active_holdout_rows"
    assert spec["dataset_config"]["guardrail_metric_filter"] == "canonical_holdout"

    kwargs = decision_config_kwargs_from_spec(spec)
    assert kwargs["dataset_config"]["training_policy"] == "exclude_pre_activation_from_train"
    assert kwargs["dataset_config"]["calibration_policy"] == "exclude_pre_activation_from_calibration"


def test_price_movement_proxy_spec_uses_true_m5_price_fields_not_promo_labels():
    spec = materialize_experiment_spec(template_id="m5_price_movement_proxy_v1")

    assert spec["experiment_type"] == "feature_set"
    assert spec["feature_config"]["include_price"] is True
    assert spec["feature_config"]["include_price_momentum"] is True
    assert spec["feature_config"]["include_promotion"] is False
    assert spec["feature_config"]["include_promo_price_interaction"] is False
    assert "explicit promotion/ad exposure labels" in spec["claim_boundary"]

    kwargs = decision_config_kwargs_from_spec(spec)
    assert kwargs["feature_set_id"] == "m5_price_movement_proxy_v1"
    assert kwargs["feature_config"]["include_price_momentum"] is True
    assert kwargs["feature_config"]["include_promotion"] is False


def test_segment_gated_activation_spec_carries_dataset_window_contract():
    spec = materialize_experiment_spec(template_id="m5_segment_gated_activation_window_v1")

    assert spec["experiment_type"] == "data_window"
    assert spec["dataset_config"]["activation_policy"] == "segment_gated_pre_first_price"
    assert spec["dataset_config"]["activation_marker"] == "first_available_sell_price"
    assert spec["dataset_config"]["training_policy"] == "exclude_pre_activation_for_eligible_segments"
    assert spec["dataset_config"]["calibration_policy"] == "exclude_pre_activation_for_eligible_segments"
    assert spec["dataset_config"]["activation_eligible_velocity_segments"] == ["medium", "slow"]
    assert spec["dataset_config"]["activation_protected_velocity_segments"] == ["fast"]
    assert spec["dataset_config"]["activation_include_late_activation"] is True

    kwargs = decision_config_kwargs_from_spec(spec)
    assert kwargs["dataset_config"]["activation_policy"] == "segment_gated_pre_first_price"
    assert kwargs["segmentation_config"]["strategy"] == "segment_gated_activation_category_velocity_bias_calibration"


def test_segment_routed_activation_spec_carries_policy_routing_contract():
    spec = materialize_experiment_spec(template_id="m5_segment_routed_activation_window_v1")

    assert spec["experiment_type"] == "data_window"
    assert spec["dataset_config"]["activation_policy"] == "segment_routed_pre_first_price"
    assert spec["dataset_config"]["training_policy"] == "exclude_pre_activation_for_eligible_segments"
    assert spec["dataset_config"]["prediction_routing_policy"] == "eligible_activation_else_champion"
    assert spec["dataset_config"]["calibration_scope"] == "eligible_segments_only"
    assert spec["dataset_config"]["activation_protected_velocity_segments"] == ["fast"]

    kwargs = decision_config_kwargs_from_spec(spec)
    assert kwargs["dataset_config"]["activation_policy"] == "segment_routed_pre_first_price"
    assert kwargs["segmentation_config"]["strategy"] == "segment_routed_activation_policy_with_eligible_bias_calibration"


def test_materialized_anomaly_spec_overrides_are_bounded_and_change_hash():
    baseline = materialize_experiment_spec(template_id="freshretailnet_balanced_context_v1")
    challenger = materialize_experiment_spec(
        template_id="freshretailnet_balanced_context_v1",
        spec_name="manual_anomaly_threshold_test",
        overrides={
            "feature_set_id": "freshretailnet_manual_anomaly_v1",
            "feature_config": {"lookback_days": 14, "include_weather": False},
            "model_config": {
                "threshold": 0.42,
                "weights": {
                    "sales_gap": 0.70,
                    "zero_sales": 0.20,
                    "promo": 0.10,
                    "holiday": 0.0,
                    "weather_stress": 0.0,
                },
            },
        },
    )

    assert challenger["model_name"] == "anomaly_detector"
    assert challenger["dataset_id"] == "freshretailnet_50k"
    assert challenger["feature_set_id"] == "freshretailnet_manual_anomaly_v1"
    assert challenger["feature_config"]["lookback_days"] == 14
    assert challenger["feature_config"]["include_weather"] is False
    assert challenger["model_config"]["threshold"] == pytest.approx(0.42)
    assert sum(challenger["model_config"]["weights"].values()) == pytest.approx(1.0)
    assert hash_experiment_spec(challenger) != hash_experiment_spec(baseline)

    kwargs = anomaly_config_kwargs_from_spec(challenger)
    assert kwargs["feature_set_id"] == "freshretailnet_manual_anomaly_v1"
    assert kwargs["model_config"]["threshold"] == pytest.approx(0.42)
    assert kwargs["promotion_gates"]["measured_feedback_required_for_promotion"] is True


def test_experiment_spec_rejects_unsupported_freeform_overrides():
    with pytest.raises(ValueError, match="Unsupported experiment spec hyperparameter"):
        materialize_experiment_spec(
            template_id="m5_lag_price_calendar_v1",
            overrides={"model_config": {"hyperparameters": {"dropout": 0.5}}},
        )

    with pytest.raises(ValueError, match="Unsupported experiment spec override path"):
        materialize_experiment_spec(
            template_id="m5_lag_price_calendar_v1",
            overrides={"dataset_id": "synthetic_demo"},
        )

    with pytest.raises(ValueError, match="Unsupported experiment spec anomaly weight"):
        materialize_experiment_spec(
            template_id="freshretailnet_balanced_context_v1",
            overrides={"model_config": {"weights": {"label_leakage": 1.0}}},
        )
