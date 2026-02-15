from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from ml.arena import promote_to_champion, register_model_version


@pytest.mark.asyncio
async def test_rollback_drill_can_restore_previous_champion(test_db, seeded_db):
    """
    Drill:
      1) v1 starts as champion.
      2) v2 promoted to champion (v1 archived).
      3) rollback by promoting v1 again (v2 archived, v1 champion).
    """
    from db.models import ModelVersion

    customer_id = seeded_db["customer_id"]

    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v1",
        status="champion",
        smoke_test_passed=True,
        metrics={"mae": 10.0, "mape": 0.20},
    )
    await register_model_version(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v2",
        status="candidate",
        smoke_test_passed=True,
        metrics={"mae": 9.5, "mape": 0.18},
    )

    await promote_to_champion(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v2",
    )

    rows_after_promote = (
        await test_db.execute(
            select(ModelVersion.version, ModelVersion.status).where(
                ModelVersion.customer_id == customer_id,
                ModelVersion.model_name == "demand_forecast",
            )
        )
    ).all()
    status_after_promote = {row.version: row.status for row in rows_after_promote}
    assert status_after_promote["v2"] == "champion"
    assert status_after_promote["v1"] == "archived"

    # Rollback to prior champion.
    await promote_to_champion(
        db=test_db,
        customer_id=customer_id,
        model_name="demand_forecast",
        version="v1",
    )

    rows_after_rollback = (
        await test_db.execute(
            select(ModelVersion.version, ModelVersion.status).where(
                ModelVersion.customer_id == customer_id,
                ModelVersion.model_name == "demand_forecast",
            )
        )
    ).all()
    status_after_rollback = {row.version: row.status for row in rows_after_rollback}
    assert status_after_rollback["v1"] == "champion"
    assert status_after_rollback["v2"] == "archived"
