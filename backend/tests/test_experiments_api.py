import sys
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
                "dataset_id": "favorita",
                "segment_strategy": "family_velocity_terciles_with_global_fallback",
                "feature_set_id": "favorita_family_segmented_v1",
            }
        },
    )
    test_db.add(experiment)
    await test_db.commit()

    def fake_cycle(**_: object) -> dict:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "data_dir": "data/kaggle/favorita",
            "rows_used": 50000,
            "holdout_days": 14,
            "business_basis_note": "Estimated costs for demo only.",
            "baseline": {
                "version": "vchamp",
                "holdout_metrics": champion_metrics,
                "lineage_metadata": {"feature_tier": "cold_start"},
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
                    "feature_tier": "cold_start",
                    "feature_set_id": "favorita_family_segmented_v1",
                    "segment_strategy": "family_velocity_terciles_with_global_fallback",
                    "dataset_id": "favorita",
                },
                "segment_summary": {
                    "strategy": "family_velocity_terciles",
                    "segments": ["high_velocity", "mid_velocity", "low_velocity"],
                },
            },
            "comparison": {
                "promoted": False,
                "reason": "failed_gates:lost_sales_qty_gate,opportunity_cost_stockout_gate",
            },
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
                    "feature_set_id": "favorita_family_segmented_v1",
                    "segment_strategy": "family_velocity_terciles_with_global_fallback",
                },
            },
        }

    monkeypatch.setattr(
        "scripts.run_legacy_favorita_experiment_cycle.run_legacy_favorita_experiment_cycle",
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
