from datetime import datetime

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
        "/experiments",
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
        f"/experiments/{experiment.experiment_id}/complete",
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

    response = await client.get("/experiments?model_name=demand_forecast")
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["model_name"] == "demand_forecast"
    assert payload[0]["experiment_name"] == "forecast_feature_hypothesis"


@pytest.mark.asyncio
async def test_list_experiments_invalid_type_returns_400(client):
    response = await client.get("/experiments?experiment_type=definitely_not_valid")
    assert response.status_code == 400
    assert "Unsupported experiment_type" in response.json()["detail"]


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
        f"/experiments/{experiment.experiment_id}/approve",
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
        f"/experiments/{experiment.experiment_id}/reject",
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
        f"/experiments/{experiment.experiment_id}/complete",
        json={
            "decision": "reject",
            "decision_rationale": "not ready",
            "results": {"improvement_pct": -1.0},
        },
    )
    assert response.status_code == 400
    assert "Cannot complete experiment in status: proposed" in response.json()["detail"]
