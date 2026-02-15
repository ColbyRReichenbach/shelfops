from datetime import date, datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_ml_effectiveness_endpoint_returns_rolling_metrics(client, seeded_db, test_db):
    from db.models import DemandForecast, ForecastAccuracy, ModelVersion

    customer_id = seeded_db["customer_id"]
    store_id = seeded_db["store"].store_id
    product_id = seeded_db["product"].product_id

    test_db.add(
        ModelVersion(
            customer_id=customer_id,
            model_name="demand_forecast",
            version="v777",
            status="champion",
            metrics={"mae": 2.0, "mape": 0.1},
            smoke_test_passed=True,
        )
    )

    today = date.today()
    for idx in range(6):
        d = today - timedelta(days=idx + 1)
        test_db.add(
            DemandForecast(
                customer_id=customer_id,
                store_id=store_id,
                product_id=product_id,
                forecast_date=d,
                forecasted_demand=10 + idx,
                lower_bound=8 + idx,
                upper_bound=12 + idx,
                confidence=0.9,
                model_version="v777",
            )
        )
        actual = 9 + idx
        forecasted = 10 + idx
        test_db.add(
            ForecastAccuracy(
                customer_id=customer_id,
                store_id=store_id,
                product_id=product_id,
                forecast_date=d,
                forecasted_demand=float(forecasted),
                actual_demand=float(actual),
                mae=float(abs(forecasted - actual)),
                mape=float(abs(forecasted - actual) / actual),
                model_version="v777",
                evaluated_at=datetime.utcnow() - timedelta(days=idx),
            )
        )
    await test_db.commit()

    response = await client.get("/api/v1/ml/effectiveness?window_days=30&model_name=demand_forecast")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["sample_count"] >= 6
    assert payload["metrics"]["mae"] is not None
    assert payload["metrics"]["mape_nonzero"] is not None
    assert payload["metrics"]["stockout_miss_rate"] is not None
    assert payload["metrics"]["overstock_rate"] is not None
    assert payload["metrics"]["coverage"] is not None
    assert payload["trend"] in {"improving", "stable", "degrading"}
