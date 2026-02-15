from datetime import datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_models_health_uses_real_drift_and_data_signals(client, seeded_db, test_db):
    from db.models import MLAlert, ModelRetrainingLog, ModelVersion, Transaction

    customer_id = seeded_db["customer_id"]
    store_id = seeded_db["store"].store_id
    product_id = seeded_db["product"].product_id

    model = ModelVersion(
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v100",
        status="champion",
        metrics={"mae": 10.0, "mape": 0.2},
        smoke_test_passed=True,
        promoted_at=datetime.utcnow() - timedelta(days=2),
    )
    test_db.add(model)

    retrain_started = datetime.utcnow() - timedelta(hours=3)
    test_db.add(
        ModelRetrainingLog(
            customer_id=customer_id,
            model_name="demand_forecast",
            trigger_type="scheduled",
            status="completed",
            started_at=retrain_started,
            completed_at=retrain_started + timedelta(minutes=10),
        )
    )
    test_db.add(
        MLAlert(
            customer_id=customer_id,
            alert_type="drift_detected",
            severity="critical",
            title="Drift detected",
            message="Model drifted",
            status="unread",
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
    )
    test_db.add(
        Transaction(
            customer_id=customer_id,
            store_id=store_id,
            product_id=product_id,
            timestamp=datetime.utcnow() - timedelta(minutes=15),
            quantity=4,
            unit_price=3.99,
            total_amount=15.96,
            transaction_type="sale",
            external_id="evt-1",
        )
    )
    await test_db.commit()

    response = await client.get("/api/v1/ml/models/health")
    assert response.status_code == 200
    payload = response.json()
    triggers = payload["retraining_triggers"]
    assert triggers["drift_detected"] is True
    assert triggers["new_data_available"] is True
    assert triggers["new_data_rows_since_last_retrain"] >= 1


@pytest.mark.asyncio
async def test_manual_promotion_requires_admin_role(client, seeded_db, test_db):
    from db.models import ModelVersion

    customer_id = seeded_db["customer_id"]
    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="demand_forecast",
            version="v201",
            status="candidate",
            metrics={"mae": 9.9, "mape": 0.19},
            smoke_test_passed=True,
        )
    )
    await test_db.commit()

    response = await client.post(
        "/api/v1/ml/models/v201/promote",
        json={"promotion_reason": "Reviewed and approved after stakeholder sign-off."},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_manual_promotion_admin_records_reason(client, mock_user, seeded_db, test_db):
    from sqlalchemy import select

    from db.models import ModelVersion

    mock_user["roles"] = ["admin"]

    customer_id = seeded_db["customer_id"]
    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="demand_forecast",
            version="v202",
            status="candidate",
            metrics={"mae": 9.7, "mape": 0.18},
            smoke_test_passed=True,
        )
    )
    await test_db.commit()

    reason = "Manual override approved after backtest and merchant review."
    response = await client.post("/api/v1/ml/models/v202/promote", json={"promotion_reason": reason})
    assert response.status_code == 200
    payload = response.json()
    assert payload["promotion_reason"] == reason

    result = await test_db.execute(
        select(ModelVersion).where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == "demand_forecast",
            ModelVersion.version == "v202",
        )
    )
    model = result.scalar_one()
    assert model.status == "champion"
    assert (model.metrics or {}).get("last_manual_promotion", {}).get("reason") == reason
