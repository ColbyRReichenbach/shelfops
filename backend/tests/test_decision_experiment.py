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
