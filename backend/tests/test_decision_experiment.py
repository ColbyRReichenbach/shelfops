from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ml.decision_experiment import (
    DecisionExperimentConfig,
    render_decision_experiment_markdown,
    run_decision_aware_experiment,
)
from ml.experiment_specs import decision_config_kwargs_from_spec, hash_experiment_spec, materialize_experiment_spec


def _synthetic_m5_frame() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2024-01-01", periods=98, freq="D")
    series = [
        ("CA_1", "FOODS_1_001", "FOODS", 7, 2, 4.25),
        ("CA_1", "HOUSEHOLD_1_001", "HOUSEHOLD", 3, 1, 8.50),
        ("TX_1", "HOBBIES_1_001", "HOBBIES", 2, 4, 3.00),
    ]
    for store_id, product_id, category, base, weekend_bump, price in series:
        for idx, current_date in enumerate(dates):
            promo = int(idx % 17 in {0, 1, 2})
            quantity = base + (weekend_bump if current_date.dayofweek in {4, 5} else 0) + promo
            rows.append(
                {
                    "date": current_date,
                    "store_id": store_id,
                    "product_id": product_id,
                    "quantity": float(quantity),
                    "category": category,
                    "is_promotional": promo,
                    "is_holiday": int(current_date.dayofweek == 6 and idx % 21 == 0),
                    "dataset_id": "m5_walmart",
                    "country_code": "US",
                    "frequency": "daily",
                    "product_grain": "sku_level",
                    "price": price,
                }
            )
    return pd.DataFrame(rows)


def _synthetic_m5_frame_with_price_movement() -> pd.DataFrame:
    frame = _synthetic_m5_frame()
    date_index = frame.groupby(["store_id", "product_id"]).cumcount()
    food_mask = frame["category"] == "FOODS"
    household_mask = frame["category"] == "HOUSEHOLD"

    frame.loc[food_mask & date_index.between(42, 49), "price"] *= 0.90
    frame.loc[food_mask & date_index.between(42, 49), "quantity"] += 2.0
    frame.loc[household_mask & date_index.between(56, 63), "price"] *= 1.08
    frame.loc[household_mask & date_index.between(56, 63), "quantity"] = (
        frame.loc[household_mask & date_index.between(56, 63), "quantity"] - 1.0
    ).clip(lower=0.0)
    frame["is_promotional"] = 0
    return frame


def _synthetic_m5_frame_with_delayed_activation() -> pd.DataFrame:
    frame = _synthetic_m5_frame()
    delayed_mask = (frame["store_id"] == "TX_1") & (frame["product_id"] == "HOBBIES_1_001")
    sorted_dates = sorted(frame.loc[delayed_mask, "date"].unique())
    activation_date = pd.Timestamp(sorted_dates[35])
    pre_activation_mask = delayed_mask & (pd.to_datetime(frame["date"]) < activation_date)
    frame.loc[pre_activation_mask, "quantity"] = 0.0
    frame.loc[pre_activation_mask, "price"] = pd.NA
    return frame


def _synthetic_m5_frame_with_fast_and_slow_delayed_activation() -> pd.DataFrame:
    frame = _synthetic_m5_frame()
    delayed_series = [
        ("CA_1", "FOODS_1_001"),
        ("TX_1", "HOBBIES_1_001"),
    ]
    for store_id, product_id in delayed_series:
        delayed_mask = (frame["store_id"] == store_id) & (frame["product_id"] == product_id)
        sorted_dates = sorted(frame.loc[delayed_mask, "date"].unique())
        activation_date = pd.Timestamp(sorted_dates[35])
        pre_activation_mask = delayed_mask & (pd.to_datetime(frame["date"]) < activation_date)
        frame.loc[pre_activation_mask, "quantity"] = 0.0
        frame.loc[pre_activation_mask, "price"] = pd.NA
    return frame


def test_decision_aware_experiment_returns_forecast_and_decision_evidence(tmp_path: Path):
    data_dir = tmp_path / "m5"
    data_dir.mkdir()
    _synthetic_m5_frame().to_csv(data_dir / "canonical_transactions.csv", index=False)
    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"

    try:
        report = run_decision_aware_experiment(
            data_dir=data_dir,
            config=DecisionExperimentConfig(
                challenger_version="etestdecision1",
                holdout_days=14,
                calibration_days=14,
                max_rows=10_000,
                max_series=3,
            ),
            output_json=output_json,
            output_md=output_md,
            persist_snapshot=False,
        )
    except ModuleNotFoundError as exc:
        if "lightgbm" in str(exc):
            pytest.skip("lightgbm is not installed")
        raise

    assert output_json.exists()
    assert output_md.exists()
    assert report["dataset"]["dataset_id"] == "m5_walmart"
    assert report["dataset"]["provenance"] == "benchmark"
    assert report["baseline"]["holdout_metrics"]["provenance"] == "benchmark"
    assert report["challenger"]["holdout_metrics"]["provenance"] == "benchmark"
    assert report["challenger"]["holdout_metrics"]["coverage"] >= 0.0
    assert report["decision_replay"]["impact_confidence"] == "simulated"
    assert "not measured merchant impact" in report["decision_replay"]["claim_boundary"].lower()
    assert report["promotion_comparison"]["promoted"] is False
    assert report["promotion_comparison"]["gate_checks"]["measured_pilot_outcome_gate"] is False
    assert report["overall_business_safe"] in {True, False}

    markdown = output_md.read_text()
    assert "# Decision-Aware Experiment Report" in markdown
    assert "## Forecast Holdout" in markdown
    assert "## Replenishment Replay" in markdown
    assert render_decision_experiment_markdown(report) + "\n" == markdown


def test_decision_experiment_executes_selected_spec_contract(tmp_path: Path):
    data_dir = tmp_path / "m5_spec"
    data_dir.mkdir()
    _synthetic_m5_frame().to_csv(data_dir / "canonical_transactions.csv", index=False)

    spec = materialize_experiment_spec(
        template_id="m5_price_promo_lag_v1",
        overrides={
            "feature_set_id": "m5_price_promo_smoke_v1",
            "model_config": {"hyperparameters": {"n_estimators": 40, "num_leaves": 15}},
        },
    )

    try:
        report = run_decision_aware_experiment(
            data_dir=data_dir,
            config=DecisionExperimentConfig(
                challenger_version="especsmoke1",
                holdout_days=14,
                calibration_days=14,
                max_rows=10_000,
                max_series=3,
                **decision_config_kwargs_from_spec(
                    spec,
                    experiment_spec_id="spec-smoke",
                    experiment_spec_hash=hash_experiment_spec(spec),
                ),
            ),
            persist_snapshot=False,
        )
    except ModuleNotFoundError as exc:
        if "lightgbm" in str(exc):
            pytest.skip("lightgbm is not installed")
        raise

    lineage = report["challenger"]["lineage_metadata"]
    assert lineage["experiment_spec_id"] == "spec-smoke"
    assert lineage["experiment_spec_hash"] == hash_experiment_spec(spec)
    assert lineage["feature_set_id"] == "m5_price_promo_smoke_v1"
    assert "lag_56" in lineage["feature_columns"]
    assert "price_change_7" in lineage["feature_columns"]
    assert lineage["model_config"]["hyperparameters"]["n_estimators"] == 40


def test_price_movement_proxy_spec_executes_without_promo_features(tmp_path: Path):
    data_dir = tmp_path / "m5_price_movement"
    data_dir.mkdir()
    _synthetic_m5_frame_with_price_movement().to_csv(data_dir / "canonical_transactions.csv", index=False)

    spec = materialize_experiment_spec(
        template_id="m5_price_movement_proxy_v1",
        overrides={
            "model_config": {"hyperparameters": {"n_estimators": 40, "num_leaves": 15}},
        },
    )

    try:
        report = run_decision_aware_experiment(
            data_dir=data_dir,
            config=DecisionExperimentConfig(
                challenger_version="epricemovement1",
                holdout_days=14,
                calibration_days=14,
                max_rows=10_000,
                max_series=3,
                **decision_config_kwargs_from_spec(
                    spec,
                    experiment_spec_id="spec-price-movement",
                    experiment_spec_hash=hash_experiment_spec(spec),
                ),
            ),
            persist_snapshot=False,
        )
    except ModuleNotFoundError as exc:
        if "lightgbm" in str(exc):
            pytest.skip("lightgbm is not installed")
        raise

    lineage = report["challenger"]["lineage_metadata"]
    assert lineage["experiment_spec_id"] == "spec-price-movement"
    assert lineage["feature_set_id"] == "m5_price_movement_proxy_v1"
    assert lineage["feature_config"]["include_price_momentum"] is True
    assert lineage["feature_config"]["include_promotion"] is False
    assert lineage["feature_config"]["include_promo_price_interaction"] is False
    assert "price_change_7" in lineage["feature_columns"]
    assert "price_index_28" in lineage["feature_columns"]
    assert "is_promotional" not in lineage["feature_columns"]
    assert "promo_price_interaction" not in lineage["feature_columns"]


def test_activation_aware_spec_excludes_pre_activation_training_rows_but_keeps_guardrail(tmp_path: Path):
    data_dir = tmp_path / "m5_activation"
    data_dir.mkdir()
    _synthetic_m5_frame_with_delayed_activation().to_csv(data_dir / "canonical_transactions.csv", index=False)

    spec = materialize_experiment_spec(
        template_id="m5_activation_aware_window_v1",
        overrides={
            "model_config": {"hyperparameters": {"n_estimators": 40, "num_leaves": 15}},
        },
    )

    try:
        report = run_decision_aware_experiment(
            data_dir=data_dir,
            config=DecisionExperimentConfig(
                challenger_version="eactivation1",
                holdout_days=14,
                calibration_days=14,
                max_rows=10_000,
                max_series=3,
                **decision_config_kwargs_from_spec(
                    spec,
                    experiment_spec_id="spec-activation",
                    experiment_spec_hash=hash_experiment_spec(spec),
                ),
            ),
            persist_snapshot=False,
        )
    except ModuleNotFoundError as exc:
        if "lightgbm" in str(exc):
            pytest.skip("lightgbm is not installed")
        raise

    activation = report["activation_policy"]
    assert activation["enabled"] is True
    assert activation["training_rows_excluded"] > 0
    assert activation["calibration_rows_excluded"] == 0
    assert activation["evaluation_policy"]["primary_metric_filter"] == "active_holdout_rows"
    assert activation["evaluation_policy"]["guardrail_metric_filter"] == "canonical_holdout"

    assert report["challenger"]["lineage_metadata"]["dataset_config"]["activation_policy"] == "exclude_pre_first_price"
    assert report["challenger"]["holdout_metrics"]["metric_scope"] == "primary_holdout"
    assert report["challenger"]["guardrail_holdout_metrics"]["metric_scope"] == "canonical_holdout_guardrail"
    assert report["evaluation_slices"]["primary_holdout"]["primary"] is True
    assert report["evaluation_slices"]["canonical_holdout_guardrail"]["guardrail"] is True


def test_segment_gated_activation_spec_excludes_only_eligible_pre_activation_rows(tmp_path: Path):
    data_dir = tmp_path / "m5_segment_activation"
    data_dir.mkdir()
    _synthetic_m5_frame_with_fast_and_slow_delayed_activation().to_csv(
        data_dir / "canonical_transactions.csv",
        index=False,
    )

    spec = materialize_experiment_spec(
        template_id="m5_segment_gated_activation_window_v1",
        overrides={
            "model_config": {"hyperparameters": {"n_estimators": 40, "num_leaves": 15}},
        },
    )

    try:
        report = run_decision_aware_experiment(
            data_dir=data_dir,
            config=DecisionExperimentConfig(
                challenger_version="esegmentactivation1",
                holdout_days=14,
                calibration_days=14,
                max_rows=10_000,
                max_series=3,
                **decision_config_kwargs_from_spec(
                    spec,
                    experiment_spec_id="spec-segment-activation",
                    experiment_spec_hash=hash_experiment_spec(spec),
                ),
            ),
            persist_snapshot=False,
        )
    except ModuleNotFoundError as exc:
        if "lightgbm" in str(exc):
            pytest.skip("lightgbm is not installed")
        raise

    activation = report["activation_policy"]
    assert activation["enabled"] is True
    assert activation["segment_gated"] is True
    assert activation["policy_type"] == "segment_gated_pre_first_price"
    assert activation["training_rows_excluded"] > 0
    assert activation["candidate_pre_activation_training_rows"] > activation["training_rows_excluded"]
    assert activation["eligible_pre_activation_training_rows"] == activation["training_rows_excluded"]
    assert activation["protected_pre_activation_training_rows"] > 0
    assert activation["activation_gate_summary"]["eligible_series"] >= 1
    assert activation["activation_gate_summary"]["protected_series"] >= 1
    assert activation["training_policy_by_segment"]["fast"]["protected_pre_activation_rows"] > 0
    assert activation["training_policy_by_segment"]["fast"]["training_rows_excluded"] == 0

    lineage = report["challenger"]["lineage_metadata"]
    assert lineage["architecture"] == "lightgbm_plus_segment_gated_activation_window_plus_calibrated_post_processing"
    assert lineage["dataset_config"]["activation_policy"] == "segment_gated_pre_first_price"
    assert report["challenger"]["guardrail_holdout_metrics"]["metric_scope"] == "canonical_holdout_guardrail"


def test_segment_routed_activation_spec_preserves_protected_segment_forecasts(tmp_path: Path):
    data_dir = tmp_path / "m5_routed_activation"
    data_dir.mkdir()
    _synthetic_m5_frame_with_fast_and_slow_delayed_activation().to_csv(
        data_dir / "canonical_transactions.csv",
        index=False,
    )

    spec = materialize_experiment_spec(
        template_id="m5_segment_routed_activation_window_v1",
        overrides={
            "model_config": {"hyperparameters": {"n_estimators": 40, "num_leaves": 15}},
        },
    )

    try:
        report = run_decision_aware_experiment(
            data_dir=data_dir,
            config=DecisionExperimentConfig(
                challenger_version="eroutedactivation1",
                holdout_days=14,
                calibration_days=14,
                max_rows=10_000,
                max_series=3,
                **decision_config_kwargs_from_spec(
                    spec,
                    experiment_spec_id="spec-routed-activation",
                    experiment_spec_hash=hash_experiment_spec(spec),
                ),
            ),
            persist_snapshot=False,
        )
    except ModuleNotFoundError as exc:
        if "lightgbm" in str(exc):
            pytest.skip("lightgbm is not installed")
        raise

    activation = report["activation_policy"]
    assert activation["enabled"] is True
    assert activation["segment_routed"] is True
    assert activation["policy_type"] == "segment_routed_pre_first_price"
    assert activation["prediction_routing_policy"] == "eligible_activation_else_champion"
    assert activation["calibration_scope"] == "eligible_segments_only"
    assert activation["training_rows_excluded"] > 0
    assert activation["routed_challenger_holdout_rows"] > 0
    assert activation["routed_champion_holdout_rows"] > 0
    assert activation["routing_policy_by_segment"]["fast"]["routed_champion_rows"] > 0
    assert activation["routing_policy_by_segment"]["fast"]["routed_challenger_rows"] == 0

    baseline_fast = report["baseline"]["segment_metrics"]["fast"]["metrics"]
    challenger_fast = report["challenger"]["segment_metrics"]["fast"]["metrics"]
    assert challenger_fast["wape"] == pytest.approx(baseline_fast["wape"])
    assert challenger_fast["bias_pct"] == pytest.approx(baseline_fast["bias_pct"])
    assert challenger_fast["overstock_rate"] == pytest.approx(baseline_fast["overstock_rate"])

    lineage = report["challenger"]["lineage_metadata"]
    assert lineage["architecture"] == "lightgbm_plus_segment_routed_activation_policy_plus_calibrated_post_processing"
    assert lineage["dataset_config"]["activation_policy"] == "segment_routed_pre_first_price"


def test_decision_experiment_extended_backtest_returns_rolling_validation(tmp_path: Path):
    data_dir = tmp_path / "m5_rolling"
    data_dir.mkdir()
    _synthetic_m5_frame().to_csv(data_dir / "canonical_transactions.csv", index=False)

    try:
        report = run_decision_aware_experiment(
            data_dir=data_dir,
            config=DecisionExperimentConfig(
                challenger_version="erolling1",
                validation_mode="extended_backtest",
                holdout_days=14,
                calibration_days=14,
                rolling_window_count=2,
                rolling_window_days=14,
                rolling_stride_days=14,
                max_rows=10_000,
                max_series=3,
            ),
            persist_snapshot=False,
        )
    except ModuleNotFoundError as exc:
        if "lightgbm" in str(exc):
            pytest.skip("lightgbm is not installed")
        raise

    rolling = report["rolling_validation"]
    assert report["validation"]["mode"] == "extended_backtest"
    assert rolling["completed_windows"] == 2
    assert len(rolling["windows"]) == 2
    assert rolling["rolling_window_days"] == 14
    assert "temporal_validation_gate" in rolling["gate_checks"]
    assert "temporal_validation_gate" in report["promotion_comparison"]["gate_checks"]
    assert rolling["summary_metrics"]["baseline_avg_wape"] is not None
