"""Regression tests for API contracts and outcome/status mapping."""

from datetime import date, datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_ml_backtests_contract_returns_forecast_fields(client, seeded_db, test_db):
    """Backtest API should expose schema fields that exist in BacktestResult."""
    from db.models import BacktestResult, ModelVersion

    customer_id = seeded_db["customer_id"]

    model = ModelVersion(
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v-test",
        status="champion",
        metrics={"mae": 10.2, "mape": 18.3},
        smoke_test_passed=True,
    )
    test_db.add(model)
    await test_db.flush()

    test_db.add(
        BacktestResult(
            customer_id=customer_id,
            model_id=model.model_id,
            forecast_date=date.today() - timedelta(days=1),
            actual_date=date.today(),
            mae=11.4,
            mape=17.8,
            stockout_miss_rate=0.07,
            overstock_rate=0.11,
        )
    )
    await test_db.commit()

    response = await client.get("/api/v1/ml/backtests?days=90")
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1

    entry = payload[0]
    assert "forecast_date" in entry
    assert "backtest_date" not in entry
    assert "coverage" not in entry
    assert "n_predictions" not in entry
    assert entry["model_name"] == "demand_forecast"
    assert entry["model_version"] == "v-test"

    legacy = await client.get("/ml/backtests?days=90")
    assert legacy.status_code == 200
    assert legacy.headers.get("Deprecation") == "true"
    assert legacy.headers.get("X-API-Deprecated") == "Use /api/v1/ml/* endpoints"


@pytest.mark.asyncio
async def test_sync_health_contract_is_enveloped(client, seeded_db, test_db):
    """Sync health endpoint should return envelope + sources array."""
    from db.models import IntegrationSyncLog

    test_db.add(
        IntegrationSyncLog(
            customer_id=seeded_db["customer_id"],
            integration_type="POS",
            integration_name="Square POS",
            sync_type="transactions",
            records_synced=125,
            sync_status="success",
            started_at=datetime.utcnow() - timedelta(minutes=30),
            completed_at=datetime.utcnow() - timedelta(minutes=25),
        )
    )
    await test_db.commit()

    response = await client.get("/api/v1/integrations/sync-health")
    assert response.status_code == 200

    payload = response.json()
    assert "sources" in payload
    assert "overall_health" in payload
    assert "checked_at" in payload
    assert isinstance(payload["sources"], list)
    assert len(payload["sources"]) == 1

    source = payload["sources"][0]
    assert source["integration_name"] == "Square POS"
    assert "last_sync" in source
    assert "syncs_24h" in source
    assert "failures_24h" in source
    assert "sla_status" in source


@pytest.mark.asyncio
async def test_sync_health_marks_stale_source_as_breach(client, seeded_db, test_db):
    """Stale integrations should breach SLA and degrade overall health."""
    from db.models import IntegrationSyncLog

    test_db.add(
        IntegrationSyncLog(
            customer_id=seeded_db["customer_id"],
            integration_type="EDI",
            integration_name="EDI 846 Inventory",
            sync_type="inventory",
            records_synced=10,
            sync_status="success",
            started_at=datetime.utcnow() - timedelta(hours=72),
            completed_at=datetime.utcnow() - timedelta(hours=71, minutes=50),
        )
    )
    await test_db.commit()

    response = await client.get("/api/v1/integrations/sync-health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["overall_health"] == "degraded"
    assert len(payload["sources"]) == 1

    source = payload["sources"][0]
    assert source["integration_name"] == "EDI 846 Inventory"
    assert source["sla_hours"] == 48
    assert source["hours_since_sync"] is not None
    assert source["hours_since_sync"] > 48
    assert source["sla_status"] == "breach"


@pytest.mark.asyncio
async def test_sync_health_sla_policy_handles_unknown_names(client, seeded_db, test_db):
    """Unknown integration names still resolve deterministic SLA defaults."""
    from db.models import IntegrationSyncLog

    test_db.add_all(
        [
            IntegrationSyncLog(
                customer_id=seeded_db["customer_id"],
                integration_type="EDI",
                integration_name="Custom EDI Feed",
                sync_type="inventory",
                records_synced=8,
                sync_status="success",
                started_at=datetime.utcnow() - timedelta(hours=10),
                completed_at=datetime.utcnow() - timedelta(hours=9, minutes=50),
            ),
            IntegrationSyncLog(
                customer_id=seeded_db["customer_id"],
                integration_type="UNKNOWN",
                integration_name="Brand New Connector",
                sync_type="transactions",
                records_synced=2,
                sync_status="success",
                started_at=datetime.utcnow() - timedelta(hours=10),
                completed_at=datetime.utcnow() - timedelta(hours=9, minutes=50),
            ),
        ]
    )
    await test_db.commit()

    response = await client.get("/api/v1/integrations/sync-health")
    assert response.status_code == 200
    payload = response.json()

    sources = {s["integration_name"]: s for s in payload["sources"]}
    assert sources["Custom EDI Feed"]["sla_hours"] == 48
    assert sources["Brand New Connector"]["sla_hours"] == 24


@pytest.mark.asyncio
async def test_record_anomaly_outcome_maps_to_valid_db_status(seeded_db, test_db):
    """Outcome values should map onto anomaly status enum values."""
    from db.models import Anomaly
    from ml.alert_outcomes import record_anomaly_outcome

    anomaly = Anomaly(
        customer_id=seeded_db["customer_id"],
        store_id=seeded_db["store"].store_id,
        product_id=seeded_db["product"].product_id,
        anomaly_type="inventory_discrepancy",
        severity="warning",
        description="Potential ghost stock",
        status="detected",
    )
    test_db.add(anomaly)
    await test_db.commit()

    result = await record_anomaly_outcome(
        db=test_db,
        customer_id=seeded_db["customer_id"],
        anomaly_id=anomaly.anomaly_id,
        outcome="true_positive",
        outcome_notes="Verified during cycle count",
        action_taken="cycle_count",
    )
    assert result["status"] == "success"
    assert anomaly.status == "resolved"
    assert (anomaly.anomaly_metadata or {}).get("outcome") == "true_positive"

    invalid = await record_anomaly_outcome(
        db=test_db,
        customer_id=seeded_db["customer_id"],
        anomaly_id=anomaly.anomaly_id,
        outcome="not_a_real_outcome",
    )
    assert invalid["status"] == "error"


@pytest.mark.asyncio
async def test_legacy_ml_aliases_return_deprecation_headers(client):
    models_resp = await client.get("/models")
    assert models_resp.status_code == 200
    assert models_resp.headers.get("Deprecation") == "true"

    ml_resp = await client.get("/ml/health")
    assert ml_resp.status_code == 200
    assert ml_resp.headers.get("Deprecation") == "true"
