"""
Tests for GET /api/v1/forecasts/{forecast_id}/drivers.

Covers:
- Valid forecast returns artifact-backed global model-driver evidence
- 404 for unknown forecast_id
- Features are sorted by descending importance
- Friendly labels are populated for known model-driver features
- Forecasts without a matching per-version artifact fall back to the active champion artifact
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.fixture
async def seeded_forecasts_explain(test_db, seeded_db):
    """Seed DemandForecast rows for model-driver tests."""
    from db.models import DemandForecast

    store = seeded_db["store"]
    product = seeded_db["product"]
    customer_id = seeded_db["customer_id"]

    forecasts = []
    for i in range(3):
        fc = DemandForecast(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            forecast_date=date.today() + timedelta(days=i),
            forecasted_demand=100.0 + i * 10,
            lower_bound=80.0 + i * 10,
            upper_bound=120.0 + i * 10,
            confidence=0.90,
            model_version="v1-test",
        )
        test_db.add(fc)
        forecasts.append(fc)

    await test_db.flush()
    await test_db.commit()

    return {"forecasts": forecasts, **seeded_db}


@pytest.mark.asyncio
async def test_forecast_drivers_return_artifact_backed_response(client: AsyncClient, seeded_forecasts_explain):
    """Valid forecast_id returns global model-driver evidence."""
    forecast = seeded_forecasts_explain["forecasts"][0]

    response = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/drivers")
    assert response.status_code == 200
    data = response.json()

    assert data["forecast_id"] == str(forecast.forecast_id)
    assert data["forecast_model_version"] == "v1-test"
    assert data["artifact_model_version"] == "v3"
    assert data["driver_scope"] == "global"
    assert data["evidence_type"] == "artifact"
    assert data["source_artifact"] == "feature_importance.json"
    assert data["cached"] is False
    assert isinstance(data["plain_summary"], str)
    assert "global" in data["plain_summary"].lower()
    assert len(data["features"]) > 0
    assert any("not a local explanation" in item.lower() for item in data["limitations"])


@pytest.mark.asyncio
async def test_forecast_drivers_404_unknown_id(client: AsyncClient, seeded_forecasts_explain):
    """Unknown forecast_id returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/forecasts/{fake_id}/drivers")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_forecast_drivers_sorted_by_importance(client: AsyncClient, seeded_forecasts_explain):
    """Model-driver features are sorted by descending importance."""
    forecast = seeded_forecasts_explain["forecasts"][0]

    response = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/drivers")
    assert response.status_code == 200
    features = response.json()["features"]
    importances = [f["importance"] for f in features]
    assert importances == sorted(importances, reverse=True)


@pytest.mark.asyncio
async def test_forecast_drivers_have_friendly_labels(client: AsyncClient, seeded_forecasts_explain):
    """Known feature names have friendly_label populated."""
    forecast = seeded_forecasts_explain["forecasts"][0]

    response = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/drivers")
    assert response.status_code == 200
    features = response.json()["features"]

    labels_present = [f["friendly_label"] for f in features if f["friendly_label"] is not None]
    assert len(labels_present) > 0


@pytest.mark.asyncio
async def test_forecast_drivers_fall_back_to_champion_artifact(client: AsyncClient, seeded_forecasts_explain):
    """Forecast model versions without local artifacts use the active champion artifact."""
    forecast = seeded_forecasts_explain["forecasts"][0]

    response = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/drivers")
    assert response.status_code == 200
    data = response.json()

    assert data["forecast_model_version"] == "v1-test"
    assert data["artifact_model_version"] == "v3"
    assert any("active champion artifact" in item.lower() for item in data["limitations"])


@pytest.mark.asyncio
async def test_forecast_drivers_same_artifact_yields_same_features(client: AsyncClient, seeded_forecasts_explain):
    """Forecasts that use the same artifact return the same global model-driver list."""
    forecasts = seeded_forecasts_explain["forecasts"]
    response1 = await client.get(f"/api/v1/forecasts/{forecasts[0].forecast_id}/drivers")
    response2 = await client.get(f"/api/v1/forecasts/{forecasts[1].forecast_id}/drivers")

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["features"] == response2.json()["features"]
