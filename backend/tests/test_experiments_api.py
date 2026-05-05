import sys
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_propose_experiment_accepts_extended_taxonomy(client, seeded_db, test_db):
    from db.models import ModelExperiment, ModelVersion

    customer_id = seeded_db["customer_id"]
    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="demand_forecast",
            version="vbase",
            status="champion",
            metrics={"mae": 10.0},
            smoke_test_passed=True,
            promoted_at=datetime.utcnow(),
        )
    )
    await test_db.commit()

    response = await client.post(
        "/api/v1/experiments",
        json={
            "experiment_name": "favorita_feature_set_promo_interactions",
            "hypothesis": "Promo interactions will reduce overstock on promoted families.",
            "experiment_type": "feature_set",
            "model_name": "demand_forecast",
            "lineage_metadata": {"change_ticket": "EXP-001"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline_version"] == "vbase"

    result = await test_db.execute(select(ModelExperiment))
    experiment = result.scalar_one()
    assert experiment.experiment_type == "feature_set"
    assert experiment.proposed_by == "test@shelfops.com"
    assert (experiment.results or {}).get("lineage_metadata", {}).get("change_ticket") == "EXP-001"


@pytest.mark.asyncio
async def test_complete_experiment_rollback_promotes_baseline(client, seeded_db, test_db):
    from db.models import ModelExperiment, ModelVersion

    customer_id = seeded_db["customer_id"]
    test_db.add_all(
        [
            ModelVersion(
                customer_id=customer_id,
                model_name="demand_forecast",
                version="v1",
                status="archived",
                metrics={"mae": 10.0},
                smoke_test_passed=True,
                archived_at=datetime.utcnow(),
            ),
            ModelVersion(
                customer_id=customer_id,
                model_name="demand_forecast",
                version="v2",
                status="champion",
                metrics={"mae": 12.0},
                smoke_test_passed=True,
                promoted_at=datetime.utcnow(),
            ),
        ]
    )
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="rollback_test",
        hypothesis="Rollback should restore prior champion cleanly.",
        experiment_type="rollback",
        model_name="demand_forecast",
        baseline_version="v1",
        experimental_version="v2",
        status="shadow_testing",
        proposed_by="test@shelfops.com",
        results={"lineage_metadata": {"change_ticket": "RB-1"}},
    )
    test_db.add(experiment)
    await test_db.commit()

    response = await client.post(
        f"/api/v1/experiments/{experiment.experiment_id}/complete",
        json={
            "decision": "rollback",
            "decision_rationale": "Experimental model regressed badly in production shadow.",
            "results": {"improvement_pct": -12.0},
            "rollback_version": "v1",
        },
    )
    assert response.status_code == 200

    rows = (
        await test_db.execute(
            select(ModelVersion.version, ModelVersion.status).where(ModelVersion.customer_id == customer_id)
        )
    ).all()
    status_map = {row.version: row.status for row in rows}
    assert status_map["v1"] == "champion"
    assert status_map["v2"] == "archived"


@pytest.mark.asyncio
async def test_list_experiments_filters_by_model_name(client, seeded_db, test_db):
    from db.models import ModelExperiment

    customer_id = seeded_db["customer_id"]
    test_db.add_all(
        [
            ModelExperiment(
                customer_id=customer_id,
                experiment_name="forecast_feature_hypothesis",
                hypothesis="Forecast feature work",
                experiment_type="feature_set",
                model_name="demand_forecast",
                status="proposed",
                proposed_by="test@shelfops.com",
                results={"lineage_metadata": {"dataset_id": "favorita"}},
            ),
            ModelExperiment(
                customer_id=customer_id,
                experiment_name="promo_lift_tuning",
                hypothesis="Promo lift tuning",
                experiment_type="hyperparameter_tuning",
                model_name="promo_lift",
                status="approved",
                proposed_by="test@shelfops.com",
                results={"lineage_metadata": {"dataset_id": "favorita"}},
            ),
        ]
    )
    await test_db.commit()

    response = await client.get("/api/v1/experiments?model_name=demand_forecast")
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["model_name"] == "demand_forecast"
    assert payload[0]["experiment_name"] == "forecast_feature_hypothesis"


@pytest.mark.asyncio
async def test_list_experiments_invalid_type_returns_400(client):
    response = await client.get("/api/v1/experiments?experiment_type=definitely_not_valid")
    assert response.status_code == 400
    assert "Unsupported experiment_type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_v1_experiments_alias_matches_canonical_route(client, seeded_db, test_db):
    from db.models import ModelExperiment

    customer_id = seeded_db["customer_id"]
    test_db.add(
        ModelExperiment(
            customer_id=customer_id,
            experiment_name="alias_route_test",
            hypothesis="The /api/v1 alias should expose the same experiment ledger.",
            experiment_type="feature_set",
            model_name="demand_forecast",
            status="proposed",
            proposed_by="test@shelfops.com",
            results={"lineage_metadata": {"dataset_id": "favorita"}},
        )
    )
    await test_db.commit()

    canonical = await client.get("/api/v1/experiments?limit=10")
    alias = await client.get("/experiments?limit=10")

    assert canonical.status_code == 200
    assert alias.status_code == 200
    assert alias.json() == canonical.json()


@pytest.mark.asyncio
async def test_approve_experiment_uses_authenticated_actor(client, seeded_db, test_db):
    from db.models import ModelExperiment

    customer_id = seeded_db["customer_id"]
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="approval_actor_test",
        hypothesis="Approval actor should come from auth context.",
        experiment_type="feature_set",
        model_name="demand_forecast",
        status="proposed",
        proposed_by="seed@shelfops.com",
        results={"lineage_metadata": {"dataset_id": "favorita"}},
    )
    test_db.add(experiment)
    await test_db.commit()

    response = await client.patch(
        f"/api/v1/experiments/{experiment.experiment_id}/approve",
        json={"approved_by": "spoofed@shelfops.com", "rationale": "ship it"},
    )
    assert response.status_code == 200
    assert response.json()["approved_by"] == "test@shelfops.com"

    await test_db.refresh(experiment)
    assert experiment.approved_by == "test@shelfops.com"


@pytest.mark.asyncio
async def test_reject_experiment_enforces_state_and_records_actor(client, seeded_db, test_db):
    from db.models import ModelExperiment

    customer_id = seeded_db["customer_id"]
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="reject_state_test",
        hypothesis="Reject should only work from reviewable states.",
        experiment_type="feature_set",
        model_name="demand_forecast",
        status="completed",
        proposed_by="seed@shelfops.com",
        results={"lineage_metadata": {"dataset_id": "favorita"}},
    )
    test_db.add(experiment)
    await test_db.commit()

    response = await client.patch(
        f"/api/v1/experiments/{experiment.experiment_id}/reject",
        json={"rejected_by": "spoofed@shelfops.com", "rationale": "too late"},
    )
    assert response.status_code == 400
    assert "Cannot reject experiment in status: completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_complete_experiment_requires_reviewable_state(client, seeded_db, test_db):
    from db.models import ModelExperiment

    customer_id = seeded_db["customer_id"]
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="complete_state_test",
        hypothesis="Completion should require active review state.",
        experiment_type="feature_set",
        model_name="demand_forecast",
        status="proposed",
        proposed_by="seed@shelfops.com",
        results={"lineage_metadata": {"dataset_id": "favorita"}},
    )
    test_db.add(experiment)
    await test_db.commit()

    response = await client.post(
        f"/api/v1/experiments/{experiment.experiment_id}/complete",
        json={
            "decision": "reject",
            "decision_rationale": "not ready",
            "results": {"improvement_pct": -1.0},
        },
    )
    assert response.status_code == 400
    assert "Cannot complete experiment in status: proposed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_complete_experiment_persists_submitted_metrics(client, seeded_db, test_db):
    from db.models import ModelExperiment

    customer_id = seeded_db["customer_id"]
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="manual_completion_metrics_test",
        hypothesis="External shadow results should remain queryable after completion.",
        experiment_type="feature_set",
        model_name="demand_forecast",
        status="shadow_testing",
        proposed_by="seed@shelfops.com",
        baseline_version="vbase",
        experimental_version="ecandidate",
        results={"lineage_metadata": {"dataset_id": "m5_walmart", "metric_provenance": "benchmark"}},
    )
    test_db.add(experiment)
    await test_db.commit()

    response = await client.post(
        f"/api/v1/experiments/{experiment.experiment_id}/complete",
        json={
            "decision": "reject",
            "decision_rationale": "WAPE improved, but business replay regressed.",
            "results": {
                "baseline_wape": 0.2,
                "experimental_wape": 0.18,
                "baseline_mase": 0.42,
                "experimental_mase": 0.39,
                "overall_business_safe": False,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["results"]
    assert payload["baseline_wape"] == pytest.approx(0.2)
    assert payload["experimental_wape"] == pytest.approx(0.18)
    assert payload["baseline_mase"] == pytest.approx(0.42)
    assert payload["experimental_mase"] == pytest.approx(0.39)
    assert payload["decision_payload"]["decision"] == "reject"


@pytest.mark.asyncio
async def test_run_experiment_requires_approval(client, seeded_db, test_db):
    from db.models import ModelExperiment

    customer_id = seeded_db["customer_id"]
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="approval_required_test",
        hypothesis="Proposed experiments should require explicit approval before running.",
        experiment_type="feature_set",
        model_name="demand_forecast",
        status="proposed",
        proposed_by="test@shelfops.com",
        results={"lineage_metadata": {"dataset_id": "m5_walmart"}},
    )
    test_db.add(experiment)
    await test_db.commit()

    response = await client.post(f"/api/v1/experiments/{experiment.experiment_id}/run", json={})
    assert response.status_code == 400
    assert "Cannot run experiment in status: proposed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_experiment_spec_materializes_and_drives_run_config(client, seeded_db, test_db, monkeypatch):
    from db.models import ModelExperiment, ModelVersion

    spec_response = await client.post(
        "/api/v1/experiments/specs",
        json={
            "template_id": "m5_price_promo_lag_v1",
            "spec_name": "api_price_promo_spec",
            "overrides": {
                "feature_set_id": "m5_api_price_promo_v1",
                "model_config": {"hyperparameters": {"n_estimators": 55, "num_leaves": 17}},
            },
        },
    )
    assert spec_response.status_code == 200
    spec_payload = spec_response.json()
    assert spec_payload["dataset_id"] == "m5_walmart"
    assert spec_payload["spec"]["feature_config"]["lag_days"] == [1, 7, 14, 28, 56]
    assert len(spec_payload["spec_hash"]) == 64

    templates_response = await client.get("/api/v1/experiments/spec-templates?model_name=demand_forecast")
    assert templates_response.status_code == 200
    assert any(row["template_id"] == "m5_price_promo_lag_v1" for row in templates_response.json())

    customer_id = seeded_db["customer_id"]
    champion_metrics = {
        "mae": 10.0,
        "wape": 0.2,
        "mase": 0.4,
        "overstock_dollars": 1000.0,
        "opportunity_cost_stockout": 800.0,
        "provenance": "benchmark",
    }
    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="demand_forecast",
            version="vchamp",
            status="champion",
            metrics=champion_metrics,
            smoke_test_passed=True,
            promoted_at=datetime.utcnow(),
        )
    )
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="api_spec_run",
        hypothesis="Price and promotion lags should improve benchmark demand fit.",
        experiment_type="feature_set",
        model_name="demand_forecast",
        status="approved",
        proposed_by="test@shelfops.com",
        approved_by="reviewer@shelfops.com",
        approved_at=datetime.utcnow(),
        experiment_spec_id=uuid.UUID(spec_payload["experiment_spec_id"]),
        results={"lineage_metadata": {"dataset_id": "m5_walmart"}},
    )
    test_db.add(experiment)
    await test_db.commit()

    captured_config = {}

    def fake_cycle(**kwargs: object) -> dict:
        config = kwargs["config"]
        captured_config["feature_config"] = config.feature_config
        captured_config["model_config"] = config.model_config
        captured_config["experiment_spec_id"] = config.experiment_spec_id
        captured_config["experiment_spec_hash"] = config.experiment_spec_hash
        captured_config["validation_mode"] = config.validation_mode
        captured_config["holdout_days"] = config.holdout_days
        captured_config["calibration_days"] = config.calibration_days
        captured_config["rolling_window_count"] = config.rolling_window_count
        captured_config["rolling_window_days"] = config.rolling_window_days
        captured_config["rolling_stride_days"] = config.rolling_stride_days
        comparison = {
            "promoted": False,
            "benchmark_gates_passed": True,
            "decision": "continue_shadow_review",
            "reason": "benchmark_gates_passed_but_measured_pilot_outcomes_unavailable",
            "gate_checks": {"measured_pilot_outcome_gate": False},
        }
        lineage = {
            "dataset_id": "m5_walmart",
            "experiment_spec_id": config.experiment_spec_id,
            "experiment_spec_hash": config.experiment_spec_hash,
            "spec_template_id": config.spec_template_id,
            "feature_set_id": config.feature_set_id,
            "feature_tier": "benchmark",
            "provenance": "benchmark",
        }
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "data_dir": "data/benchmarks/m5_walmart/subset_20spc",
            "claim_boundary": "M5 benchmark evidence with simulated decision replay.",
            "lineage_metadata": lineage,
            "baseline": {"version": "vchamp", "holdout_metrics": champion_metrics, "lineage_metadata": lineage},
            "challenger": {
                "version": "e1234567890",
                "holdout_metrics": {**champion_metrics, "wape": 0.19, "mase": 0.38},
                "lineage_metadata": lineage,
                "segment_metrics": {},
            },
            "decision_replay": {"results": {"challenger": {"combined_cost_proxy": 1200.0, "service_level": 0.91}}},
            "promotion_comparison": comparison,
            "comparison": comparison,
            "validation": {
                "mode": config.validation_mode,
                "holdout_days": config.holdout_days,
                "calibration_days": config.calibration_days,
                "rolling_window_count": config.rolling_window_count,
                "rolling_window_days": config.rolling_window_days,
                "rolling_stride_days": config.rolling_stride_days,
            },
            "rolling_validation": {
                "mode": config.validation_mode,
                "completed_windows": config.rolling_window_count,
                "requested_windows": config.rolling_window_count,
                "rolling_window_days": config.rolling_window_days,
                "rolling_stride_days": config.rolling_stride_days,
                "summary_metrics": {"baseline_avg_wape": 0.2, "challenger_avg_wape": 0.19},
                "gate_checks": {"temporal_validation_gate": True},
                "windows": [],
            },
            "overall_business_safe": True,
            "experiment": {
                "experiment_name": "api_spec_run",
                "hypothesis": "Price and promotion lags should improve benchmark demand fit.",
                "experiment_type": "feature_set",
                "model_name": "demand_forecast",
                "baseline_version": "vchamp",
                "experimental_version": "e1234567890",
                "decision": "continue_shadow_review",
                "decision_rationale": comparison["reason"],
                "lineage_metadata": lineage,
            },
        }

    monkeypatch.setattr("ml.decision_experiment.run_decision_aware_experiment", fake_cycle)

    response = await client.post(
        f"/api/v1/experiments/{experiment.experiment_id}/run",
        json={
            "experiment_spec_id": spec_payload["experiment_spec_id"],
            "validation_mode": "extended_backtest",
            "holdout_days": 35,
            "calibration_days": 21,
            "rolling_window_count": 4,
            "rolling_window_days": 28,
            "rolling_stride_days": 14,
        },
    )
    assert response.status_code == 200
    assert captured_config["experiment_spec_id"] == spec_payload["experiment_spec_id"]
    assert captured_config["experiment_spec_hash"] == spec_payload["spec_hash"]
    assert captured_config["feature_config"]["lag_days"] == [1, 7, 14, 28, 56]
    assert captured_config["model_config"]["hyperparameters"]["n_estimators"] == 55
    assert captured_config["validation_mode"] == "extended_backtest"
    assert captured_config["holdout_days"] == 35
    assert captured_config["calibration_days"] == 21
    assert captured_config["rolling_window_count"] == 4
    assert captured_config["rolling_window_days"] == 28
    assert captured_config["rolling_stride_days"] == 14

    await test_db.refresh(experiment)
    lineage = (experiment.results or {})["lineage_metadata"]
    assert lineage["experiment_spec_id"] == spec_payload["experiment_spec_id"]
    assert lineage["experiment_spec_hash"] == spec_payload["spec_hash"]
    assert lineage["feature_set_id"] == "m5_api_price_promo_v1"
    assert (experiment.results or {})["execution"]["validation_mode"] == "extended_backtest"
    assert (experiment.results or {})["execution"]["rolling_window_count"] == 4


@pytest.mark.asyncio
async def test_run_experiment_executes_cycle_and_persists_arena_breakdown(client, seeded_db, test_db, monkeypatch):
    from db.models import ModelExperiment, ModelVersion

    customer_id = seeded_db["customer_id"]
    champion_metrics = {
        "mae": 10.0,
        "mape": 0.2,
        "wape": 0.18,
        "mase": 0.31,
        "bias_pct": 0.01,
        "coverage": 0.9,
        "stockout_miss_rate": 0.05,
        "overstock_rate": 0.2,
        "overstock_dollars": 1000.0,
        "overstock_dollars_confidence": "estimated",
        "lost_sales_qty": 120.0,
        "opportunity_cost_stockout": 800.0,
        "opportunity_cost_stockout_confidence": "estimated",
        "opportunity_cost_overstock": 150.0,
        "opportunity_cost_overstock_confidence": "estimated",
    }
    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="demand_forecast",
            version="vchamp",
            status="champion",
            metrics=champion_metrics,
            smoke_test_passed=True,
            promoted_at=datetime.utcnow(),
        )
    )
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="segmented_family_trial",
        hypothesis="Family velocity segmentation should reduce stockout cost.",
        experiment_type="segmentation",
        model_name="demand_forecast",
        status="approved",
        proposed_by="test@shelfops.com",
        approved_by="reviewer@shelfops.com",
        approved_at=datetime.utcnow(),
        results={
            "lineage_metadata": {
                "dataset_id": "m5_walmart",
                "segment_strategy": "store_product_velocity_and_category_bias_calibration",
                "feature_set_id": "m5_lag_price_calendar_v1",
            }
        },
    )
    test_db.add(experiment)
    await test_db.commit()

    def fake_cycle(**_: object) -> dict:
        comparison = {
            "promoted": False,
            "benchmark_gates_passed": False,
            "decision": "continue_shadow_review",
            "reason": "failed_gates:lost_sales_qty_gate,opportunity_cost_stockout_gate",
            "gate_checks": {"lost_sales_qty_gate": False},
        }
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "data_dir": "data/benchmarks/m5_walmart/subset_20spc",
            "claim_boundary": "M5 benchmark evidence with simulated decision replay.",
            "lineage_metadata": {
                "feature_set_id": "m5_lag_price_calendar_v1",
                "segment_strategy": "store_product_velocity_and_category_bias_calibration",
                "dataset_id": "m5_walmart",
                "feature_tier": "benchmark",
            },
            "baseline": {
                "version": "vchamp",
                "holdout_metrics": champion_metrics,
                "lineage_metadata": {"feature_tier": "benchmark"},
            },
            "challenger": {
                "version": "e1234567890",
                "holdout_metrics": {
                    **champion_metrics,
                    "wape": 0.179,
                    "mase": 0.305,
                    "overstock_dollars": 980.0,
                    "lost_sales_qty": 121.0,
                    "opportunity_cost_stockout": 810.0,
                },
                "lineage_metadata": {
                    "feature_tier": "benchmark",
                    "feature_set_id": "m5_lag_price_calendar_v1",
                    "segment_strategy": "store_product_velocity_and_category_bias_calibration",
                    "dataset_id": "m5_walmart",
                },
                "segment_metrics": {"fast": {"sample_rows": 100, "metrics": {"wape": 0.17}}},
            },
            "decision_replay": {
                "results": {
                    "challenger": {
                        "combined_cost_proxy": 1200.0,
                        "service_level": 0.91,
                    }
                }
            },
            "promotion_comparison": comparison,
            "comparison": comparison,
            "overall_business_safe": False,
            "experiment": {
                "experiment_name": "segmented_family_trial",
                "hypothesis": "Family velocity segmentation should reduce stockout cost.",
                "experiment_type": "segmentation",
                "model_name": "demand_forecast",
                "baseline_version": "vchamp",
                "experimental_version": "e1234567890",
                "decision": "continue_shadow_review",
                "decision_rationale": "failed_gates:lost_sales_qty_gate,opportunity_cost_stockout_gate",
                "lineage_metadata": {
                    "feature_set_id": "m5_lag_price_calendar_v1",
                    "segment_strategy": "store_product_velocity_and_category_bias_calibration",
                },
            },
        }

    monkeypatch.setattr(
        "ml.decision_experiment.run_decision_aware_experiment",
        fake_cycle,
    )

    response = await client.post(f"/api/v1/experiments/{experiment.experiment_id}/run", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["experiment_status"] == "shadow_testing"
    assert payload["comparison"]["promoted"] is False

    await test_db.refresh(experiment)
    assert experiment.status == "shadow_testing"
    assert experiment.approved_by == "reviewer@shelfops.com"
    assert experiment.experimental_version is not None
    assert (experiment.results or {}).get("arena_breakdown", {}).get("reason") == payload["comparison"]["reason"]
    assert (experiment.results or {}).get("promotion_comparison", {}).get("reason") == payload["comparison"]["reason"]
    assert (experiment.results or {}).get("baseline_wape") == pytest.approx(champion_metrics["wape"])
    assert (experiment.results or {}).get("experimental_wape") == pytest.approx(0.179)


@pytest.mark.asyncio
async def test_anomaly_experiment_run_uses_spec_and_persists_shadow_evidence(
    client,
    seeded_db,
    test_db,
    monkeypatch,
):
    from db.models import AnomalyDetectionRun, ModelExperiment, ModelVersion

    customer_id = seeded_db["customer_id"]

    templates_response = await client.get("/api/v1/experiments/spec-templates?model_name=anomaly_detector")
    assert templates_response.status_code == 200
    templates = templates_response.json()
    assert {template["dataset_id"] for template in templates} == {"freshretailnet_50k"}

    spec_response = await client.post(
        "/api/v1/experiments/specs",
        json={
            "template_id": "freshretailnet_balanced_context_v1",
            "spec_name": "api_anomaly_spec",
            "overrides": {
                "feature_config": {"lookback_days": 14},
                "model_config": {"threshold": 0.42},
            },
        },
    )
    assert spec_response.status_code == 200
    spec_payload = spec_response.json()
    assert spec_payload["model_name"] == "anomaly_detector"
    assert spec_payload["dataset_id"] == "freshretailnet_50k"

    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="anomaly_detector",
            version="a1",
            status="champion",
            metrics={"precision": 0.55, "recall": 0.1, "provenance": "benchmark"},
            smoke_test_passed=True,
            promoted_at=datetime.utcnow(),
        )
    )
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="anomaly_review_rate_trial",
        hypothesis="A lower stockout threshold should improve recall while keeping review volume bounded.",
        experiment_type="post_processing",
        model_name="anomaly_detector",
        status="approved",
        proposed_by="test@shelfops.com",
        approved_by="reviewer@shelfops.com",
        approved_at=datetime.utcnow(),
        experiment_spec_id=uuid.UUID(spec_payload["experiment_spec_id"]),
        results={"lineage_metadata": {"dataset_id": "freshretailnet_50k"}},
    )
    test_db.add(experiment)
    await test_db.commit()

    captured: dict[str, object] = {}

    def fake_anomaly_cycle(**kwargs: object) -> dict:
        config = kwargs["config"]
        captured["data_dir"] = kwargs["data_dir"]
        captured["threshold"] = config.model_config["threshold"]
        captured["lookback_days"] = config.feature_config["lookback_days"]
        captured["experiment_spec_hash"] = config.experiment_spec_hash
        comparison = {
            "promoted": False,
            "benchmark_gates_passed": True,
            "decision": "continue_shadow_review",
            "reason": "benchmark_gates_passed_but_cycle_count_feedback_unavailable",
            "gate_checks": {
                "precision_gate": True,
                "recall_gate": True,
                "false_positive_rate_gate": True,
                "review_rate_gate": True,
                "measured_cycle_count_feedback_gate": False,
            },
        }
        lineage = {
            "dataset_id": "freshretailnet_50k",
            "dataset_snapshot_id": "freshretailnet_50k_test",
            "experiment_spec_id": str(config.experiment_spec_id),
            "experiment_spec_hash": config.experiment_spec_hash,
            "spec_template_id": config.spec_template_id,
            "feature_set_id": config.feature_set_id,
            "feature_config": config.feature_config,
            "feature_tier": "benchmark",
            "threshold": config.model_config["threshold"],
            "provenance": "benchmark",
        }
        baseline_metrics = {
            "rows": 10000,
            "predicted_positive": 900,
            "precision": 0.55,
            "recall": 0.10,
            "f1": 0.17,
            "false_positive_rate": 0.08,
            "review_rate": 0.09,
            "threshold": 0.55,
            "provenance": "benchmark",
        }
        challenger_metrics = {
            "rows": 10000,
            "predicted_positive": 2400,
            "precision": 0.43,
            "recall": 0.25,
            "f1": 0.32,
            "false_positive_rate": 0.18,
            "review_rate": 0.24,
            "threshold": config.model_config["threshold"],
            "provenance": "benchmark",
        }
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "data_dir": str(kwargs["data_dir"]),
            "claim_boundary": "FreshRetailNet benchmark anomaly evidence only. Buyer outcomes require real cycle-count feedback.",
            "lineage_metadata": lineage,
            "baseline": {
                "version": "a1",
                "holdout_metrics": baseline_metrics,
                "lineage_metadata": {**lineage, "threshold": 0.55},
            },
            "challenger": {
                "version": config.challenger_version,
                "holdout_metrics": challenger_metrics,
                "lineage_metadata": lineage,
                "segment_metrics": {"category:berries": {"sample_rows": 100, "metrics": {"precision": 0.44}}},
            },
            "promotion_comparison": comparison,
            "comparison": comparison,
            "overall_business_safe": True,
            "experiment": {
                "experiment_name": config.experiment_name,
                "hypothesis": config.hypothesis,
                "experiment_type": config.experiment_type,
                "model_name": "anomaly_detector",
                "baseline_version": "a1",
                "experimental_version": config.challenger_version,
                "decision": comparison["decision"],
                "decision_rationale": comparison["reason"],
                "lineage_metadata": lineage,
            },
        }

    monkeypatch.setattr("ml.anomaly_benchmark.run_anomaly_detection_experiment", fake_anomaly_cycle)

    response = await client.post(
        f"/api/v1/experiments/{experiment.experiment_id}/run",
        json={"max_rows": 10000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["experiment_status"] == "shadow_testing"
    assert payload["report"]["experiment"]["model_name"] == "anomaly_detector"
    assert captured["threshold"] == pytest.approx(0.42)
    assert captured["lookback_days"] == 14
    assert captured["experiment_spec_hash"] == spec_payload["spec_hash"]

    await test_db.refresh(experiment)
    assert experiment.experimental_version is not None
    assert (experiment.results or {})["baseline_precision"] == pytest.approx(0.55)
    assert (experiment.results or {})["experimental_recall"] == pytest.approx(0.25)
    assert (experiment.results or {})["lineage_metadata"]["experiment_spec_hash"] == spec_payload["spec_hash"]

    anomaly_run_result = await test_db.execute(
        select(AnomalyDetectionRun).where(AnomalyDetectionRun.customer_id == customer_id)
    )
    anomaly_run = anomaly_run_result.scalar_one()
    assert anomaly_run.model_version == experiment.experimental_version
    assert anomaly_run.dataset_id == "freshretailnet_50k"
    assert anomaly_run.threshold == pytest.approx(0.42)
    assert anomaly_run.rows_scored == 10000
    assert anomaly_run.anomalies_detected == 2400
    assert anomaly_run.provenance == "benchmark"

    model_result = await test_db.execute(
        select(ModelVersion).where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == "anomaly_detector",
            ModelVersion.version == experiment.experimental_version,
        )
    )
    candidate = model_result.scalar_one()
    assert candidate.status == "challenger"
    assert candidate.metrics["precision"] == pytest.approx(0.43)
    assert candidate.metrics["promotion_comparison"]["gate_checks"]["measured_cycle_count_feedback_gate"] is False


@pytest.mark.asyncio
async def test_anomaly_experiment_rejects_forecast_temporal_validation(client, seeded_db, test_db):
    from db.models import ModelExperiment, ModelVersion

    customer_id = seeded_db["customer_id"]
    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="anomaly_detector",
            version="a1",
            status="champion",
            metrics={"precision": 0.55, "recall": 0.1, "provenance": "benchmark"},
            smoke_test_passed=True,
            promoted_at=datetime.utcnow(),
        )
    )
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="anomaly_extended_backtest_reject",
        hypothesis="Forecast temporal validation controls should not run against anomaly specs.",
        experiment_type="post_processing",
        model_name="anomaly_detector",
        status="approved",
        proposed_by="test@shelfops.com",
        approved_by="reviewer@shelfops.com",
        approved_at=datetime.utcnow(),
        results={"lineage_metadata": {"dataset_id": "freshretailnet_50k"}},
    )
    test_db.add(experiment)
    await test_db.commit()

    response = await client.post(
        f"/api/v1/experiments/{experiment.experiment_id}/run",
        json={"validation_mode": "extended_backtest", "rolling_window_count": 3},
    )

    assert response.status_code == 400
    assert "Temporal forecast validation modes" in response.json()["detail"]
    await test_db.refresh(experiment)
    assert experiment.status == "approved"


@pytest.mark.asyncio
async def test_anomaly_experiment_rejects_forecast_spec_template(client, seeded_db):
    response = await client.post(
        "/api/v1/experiments",
        json={
            "experiment_name": "bad_anomaly_spec",
            "hypothesis": "Wrong model family spec should be rejected.",
            "experiment_type": "post_processing",
            "model_name": "anomaly_detector",
            "spec_template_id": "m5_lag_price_calendar_v1",
        },
    )

    assert response.status_code == 400
    assert "model_name" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_experiments_normalizes_nested_run_results(client, seeded_db, test_db):
    from db.models import ModelExperiment

    customer_id = seeded_db["customer_id"]
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="normalized_results_test",
        hypothesis="Nested run results should be flattened for the ledger view.",
        experiment_type="feature_set",
        model_name="demand_forecast",
        status="completed",
        proposed_by="test@shelfops.com",
        baseline_version="vbase",
        experimental_version="ecandidate",
        results={
            "lineage_metadata": {"dataset_id": "m5_walmart"},
            "run_report": {
                "baseline": {"holdout_metrics": {"mae": 10.0, "wape": 0.2, "mase": 0.4}},
                "challenger": {"holdout_metrics": {"mae": 9.4, "wape": 0.18, "mase": 0.37}},
            },
            "arena_breakdown": {"promoted": False, "reason": "shadow_only", "gate_checks": {"mae_gate": True}},
        },
    )
    test_db.add(experiment)
    await test_db.commit()

    response = await client.get("/api/v1/experiments?status=completed")
    assert response.status_code == 200
    payload = response.json()
    row = next(item for item in payload if item["experiment_id"] == str(experiment.experiment_id))
    assert row["results"]["baseline_wape"] == pytest.approx(0.2)
    assert row["results"]["experimental_wape"] == pytest.approx(0.18)
    assert row["results"]["promotion_comparison"]["reason"] == "shadow_only"


@pytest.mark.asyncio
async def test_interpret_experiment_uses_normalized_run_results_and_caches(client, seeded_db, test_db, monkeypatch):
    from db.models import ModelExperiment

    customer_id = seeded_db["customer_id"]
    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name="interpretation_contract_test",
        hypothesis="Interpretation should read canonical nested run results.",
        experiment_type="feature_set",
        model_name="demand_forecast",
        status="completed",
        proposed_by="test@shelfops.com",
        baseline_version="vbase",
        experimental_version="ecandidate",
        decision_rationale="shadow_only",
        results={
            "lineage_metadata": {"dataset_id": "m5_walmart", "feature_set_id": "m5_candidate_v2"},
            "run_report": {
                "baseline": {"holdout_metrics": {"mae": 10.0, "wape": 0.2, "mase": 0.4}},
                "challenger": {"holdout_metrics": {"mae": 9.2, "wape": 0.18, "mase": 0.36}},
            },
            "arena_breakdown": {"promoted": False, "reason": "shadow_only", "gate_checks": {"mae_gate": True}},
        },
    )
    test_db.add(experiment)
    await test_db.commit()

    class _FakeMessages:
        @staticmethod
        def create(**_: object):
            return SimpleNamespace(content=[SimpleNamespace(text="Summary section---Why section---Next section")])

    class _FakeAnthropicClient:
        def __init__(self, api_key=None):
            self.messages = _FakeMessages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=_FakeAnthropicClient))

    response = await client.post(f"/api/v1/experiments/{experiment.experiment_id}/interpret", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is False
    assert payload["results_summary"] == "Summary section"

    await test_db.refresh(experiment)
    assert (experiment.results or {}).get("llm_interpretation", {}).get("why_it_worked") == "Why section"

    cached_response = await client.post(f"/api/v1/experiments/{experiment.experiment_id}/interpret", json={})
    assert cached_response.status_code == 200
    assert cached_response.json()["cached"] is True


@pytest.mark.asyncio
async def test_experiment_governance_context_hypothesis_trace_and_comparison(
    client,
    seeded_db,
    test_db,
    monkeypatch,
):
    from db.models import ExperimentHypothesis, ModelExperiment, ModelVersion

    customer_id = seeded_db["customer_id"]
    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="demand_forecast",
            version="v3",
            status="champion",
            metrics={"wape": 0.7276, "mase": 0.7968, "provenance": "benchmark"},
            smoke_test_passed=True,
            promoted_at=datetime.utcnow(),
        )
    )
    await test_db.commit()

    monkeypatch.setattr(
        "ml.experiment_governance.write_context_package_artifacts",
        lambda context_package_id, payload: (
            f"backend/reports/experiment_context/{context_package_id}.json",
            f"backend/reports/experiment_context/{context_package_id}.md",
        ),
    )

    context_response = await client.post(
        "/api/v1/experiments/context-packages",
        json={
            "package_name": "manual_vs_agent_m5_v1",
            "model_name": "demand_forecast",
            "dataset_id": "m5_walmart",
        },
    )
    assert context_response.status_code == 200
    context = context_response.json()
    assert context["baseline_version"] == "v3"
    assert context["context_metadata"]["controls"]["human_review_required"] is True
    assert context["context_metadata"]["claim_boundary"]["decision_replay"].startswith("Simulated")

    manual_response = await client.post(
        "/api/v1/experiments/hypotheses",
        json={
            "context_package_id": context["context_package_id"],
            "title": "manual_velocity_feature_test",
            "hypothesis": "Manual velocity features should reduce WAPE for fast movers.",
            "experiment_type": "feature_set",
            "model_name": "demand_forecast",
            "experiment_source": "manual",
            "domain_rationale": "Retail buyers separate fast and slow movers before changing order policy.",
            "expected_metric_movement": {"wape": "down", "stockout_cost": "down"},
        },
    )
    assert manual_response.status_code == 200
    assert manual_response.json()["experiment_source"] == "manual"

    agent_response = await client.post(
        "/api/v1/experiments/hypotheses",
        json={
            "context_package_id": context["context_package_id"],
            "title": "agent_segmented_bias_test",
            "hypothesis": "Agent-proposed segment bias calibration should reduce stockout cost without WAPE regression.",
            "experiment_type": "segmentation",
            "model_name": "demand_forecast",
            "experiment_source": "ai_agent",
            "domain_rationale": "The latest benchmark report struggled on slow-moving and high-volume segments.",
            "risk_notes": "May trade lower stockout cost for higher overstock exposure.",
        },
    )
    assert agent_response.status_code == 200
    agent_hypothesis = agent_response.json()

    trace_response = await client.post(
        "/api/v1/experiments/agent-traces",
        json={
            "context_package_id": context["context_package_id"],
            "hypothesis_id": agent_hypothesis["hypothesis_id"],
            "agent_name": "shelfops-ds-agent",
            "agent_model": "gpt-5.5",
            "trace_type": "hypothesis_generation",
            "prompt_hash": "a" * 64,
            "prompt_preview": "Review context package and propose bounded retail DS experiments.",
            "tool_allowlist": ["read_context_package", "propose_hypothesis"],
            "generated_output": {"hypotheses": [agent_hypothesis["title"]]},
        },
    )
    assert trace_response.status_code == 200
    assert trace_response.json()["human_decision"] == "pending"

    review_response = await client.patch(
        f"/api/v1/experiments/hypotheses/{agent_hypothesis['hypothesis_id']}/review",
        json={
            "decision": "approve",
            "rationale": "Safe to run as a shadow benchmark experiment.",
            "convert_to_experiment": True,
        },
    )
    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["hypothesis"]["status"] == "converted"
    assert reviewed["experiment"]["status"] == "approved"
    assert reviewed["experiment"]["experiment_source"] == "ai_agent"
    assert reviewed["experiment"]["context_package_id"] == context["context_package_id"]

    result = await test_db.execute(select(ModelExperiment).where(ModelExperiment.experiment_source == "ai_agent"))
    experiment = result.scalar_one()
    assert experiment.context_package_id is not None
    assert (experiment.results or {})["lineage_metadata"]["metric_provenance"] == "benchmark"

    result = await test_db.execute(select(ExperimentHypothesis).where(ExperimentHypothesis.experiment_source == "manual"))
    manual_hypothesis = result.scalar_one()
    assert manual_hypothesis.status == "proposed"

    ledger_response = await client.get("/api/v1/experiments?model_name=demand_forecast")
    assert ledger_response.status_code == 200
    ledger = ledger_response.json()
    assert any(row["experiment_source"] == "ai_agent" for row in ledger)

    comparison_response = await client.get(
        f"/api/v1/experiments/comparison-report?context_package_id={context['context_package_id']}"
    )
    assert comparison_response.status_code == 200
    comparison = comparison_response.json()
    lanes = {lane["source"]: lane for lane in comparison["lanes"]}
    assert lanes["manual"]["hypotheses"] == 1
    assert lanes["ai_agent"]["hypotheses"] == 1
    assert lanes["ai_agent"]["experiments"] == 1
    assert lanes["ai_agent"]["agent_traces"] == 1
    assert comparison["claim_boundary"]["promotion"].startswith("human approval")
