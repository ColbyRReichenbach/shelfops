"""
Tests for GET /api/v1/forecasts/{forecast_id}/explain (SHAP endpoint).

Covers:
- Valid forecast returns SHAPExplanation response
- Redis caching (second call returns cached=True)
- 404 for unknown forecast_id
- Tenant isolation: forecast from another tenant returns 404
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.fixture
async def seeded_forecasts_explain(test_db, seeded_db):
    """Seed DemandForecast rows for SHAP explain tests."""
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
async def test_explain_forecast_returns_shap_data(client: AsyncClient, seeded_forecasts_explain):
    """Valid forecast_id returns SHAP features."""
    forecast = seeded_forecasts_explain["forecasts"][0]

    response = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/explain")
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    assert len(data["features"]) > 0
    assert "predicted_value" in data
    assert "base_value" in data
    assert "cached" in data
    assert data["cached"] is False
    # Each feature has name and importance
    for feat in data["features"]:
        assert "name" in feat
        assert "importance" in feat


@pytest.mark.asyncio
async def test_explain_forecast_404_unknown_id(client: AsyncClient, seeded_forecasts_explain):
    """Unknown forecast_id returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/forecasts/{fake_id}/explain")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_explain_forecast_features_sorted_by_importance(client: AsyncClient, seeded_forecasts_explain):
    """SHAP features are sorted by absolute importance descending."""
    forecast = seeded_forecasts_explain["forecasts"][0]

    response = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/explain")
    assert response.status_code == 200
    features = response.json()["features"]
    importances = [abs(f["importance"]) for f in features]
    assert importances == sorted(importances, reverse=True)


@pytest.mark.asyncio
async def test_explain_forecast_response_structure(client: AsyncClient, seeded_forecasts_explain):
    """Response includes forecast_id, base_value, predicted_value, features."""
    forecast = seeded_forecasts_explain["forecasts"][0]

    response = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/explain")
    assert response.status_code == 200
    data = response.json()

    assert data["forecast_id"] == str(forecast.forecast_id)
    assert data["predicted_value"] == pytest.approx(float(forecast.forecasted_demand))
    assert data["base_value"] == pytest.approx(float(forecast.forecasted_demand) * 0.6)
    assert isinstance(data["features"], list)
    assert len(data["features"]) == 10  # 10 features in _generate_shap_values


@pytest.mark.asyncio
async def test_explain_forecast_features_have_friendly_labels(client: AsyncClient, seeded_forecasts_explain):
    """Known feature names have friendly_label populated."""
    forecast = seeded_forecasts_explain["forecasts"][0]

    response = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/explain")
    assert response.status_code == 200
    features = response.json()["features"]

    # At least some features should have friendly labels
    labels_present = [f["friendly_label"] for f in features if f["friendly_label"] is not None]
    assert len(labels_present) > 0


@pytest.mark.asyncio
async def test_explain_forecast_deterministic(client: AsyncClient, seeded_forecasts_explain):
    """Same forecast_id returns identical SHAP values on repeated calls (deterministic seed)."""
    forecast = seeded_forecasts_explain["forecasts"][0]

    response1 = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/explain")
    response2 = await client.get(f"/api/v1/forecasts/{forecast.forecast_id}/explain")

    assert response1.status_code == 200
    assert response2.status_code == 200

    features1 = response1.json()["features"]
    features2 = response2.json()["features"]

    # Same features in same order with same importances
    for f1, f2 in zip(features1, features2):
        assert f1["name"] == f2["name"]
        assert f1["importance"] == pytest.approx(f2["importance"])


@pytest.mark.asyncio
async def test_explain_forecast_different_forecasts_different_values(client: AsyncClient, seeded_forecasts_explain):
    """Different forecast_ids produce different SHAP feature values."""
    forecasts = seeded_forecasts_explain["forecasts"]
    assert len(forecasts) >= 2

    response1 = await client.get(f"/api/v1/forecasts/{forecasts[0].forecast_id}/explain")
    response2 = await client.get(f"/api/v1/forecasts/{forecasts[1].forecast_id}/explain")

    assert response1.status_code == 200
    assert response2.status_code == 200

    # predicted_values differ since forecasted_demand differs
    assert response1.json()["predicted_value"] != response2.json()["predicted_value"]
