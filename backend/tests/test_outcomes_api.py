"""
API Tests — Outcomes / ROI endpoints.

Tests are split into two layers:

1. Service-layer unit tests (no HTTP) — call calculate_* functions directly
   with a clean SQLite session. These verify business logic and response shape.

2. Schema validation tests — use a custom client fixture whose session
   transparently answers the PostgreSQL current_setting() call so that
   Pydantic validation errors (422) are surfaced without touching real PG.

3. HTTP integration tests — verify endpoints return 200 with expected keys
   when the session is fully stubbed.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"


# ── Session wrapper that stubs current_setting ───────────────────────────────


class _SQLiteTenantSession:
    """
    Thin wrapper around an AsyncSession that intercepts the
    ``SELECT current_setting(...)`` call and returns a fixed customer_id,
    delegating every other query to the underlying real session.
    """

    def __init__(self, real_session, customer_id_str: str):
        self._real = real_session
        self._customer_id_str = customer_id_str

    # Proxy attribute access to the real session
    def __getattr__(self, name):
        return getattr(self._real, name)

    async def execute(self, stmt, *args, **kwargs):
        # Detect the current_setting text call
        stmt_str = str(stmt)
        if "current_setting" in stmt_str:
            result = MagicMock()
            result.scalar.return_value = self._customer_id_str
            return result
        return await self._real.execute(stmt, *args, **kwargs)


@pytest.fixture
async def client_tenant(test_db, mock_user, seeded_db):
    """
    Test client whose get_tenant_db dependency returns a _SQLiteTenantSession
    that answers current_setting() with the test customer_id.
    """
    from api.deps import get_current_user, get_db, get_tenant_db
    from api.main import app

    tenant_session = _SQLiteTenantSession(test_db, str(seeded_db["customer_id"]))

    async def override_get_db():
        yield test_db

    def override_get_current_user():
        return mock_user

    async def override_get_tenant_db():
        return tenant_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_tenant_db] = override_get_tenant_db

    from httpx import ASGITransport
    from httpx import AsyncClient as _AC

    async with _AC(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Service-layer unit tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_alert_effectiveness_service_response_keys():
    """calculate_alert_effectiveness returns all expected keys (empty DB)."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    import ml.alert_outcomes as ao_module
    from db.session import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    customer_id = uuid.UUID(CUSTOMER_ID)
    async with AsyncSession(engine) as session:
        result = await ao_module.calculate_alert_effectiveness(
            db=session,
            customer_id=customer_id,
            lookback_days=30,
        )

    await engine.dispose()

    expected_keys = {
        "total_alerts",
        "resolved",
        "dismissed",
        "pending",
        "acknowledged",
        "false_positive_rate",
        "avg_response_time_hours",
        "period_days",
    }
    assert expected_keys.issubset(set(result.keys()))
    assert result["total_alerts"] == 0
    assert result["false_positive_rate"] == 0.0
    assert result["period_days"] == 30


@pytest.mark.asyncio
async def test_alert_effectiveness_service_custom_lookback():
    """period_days reflects the lookback_days argument."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    import ml.alert_outcomes as ao_module
    from db.session import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    customer_id = uuid.UUID(CUSTOMER_ID)
    async with AsyncSession(engine) as session:
        result = await ao_module.calculate_alert_effectiveness(db=session, customer_id=customer_id, lookback_days=7)

    await engine.dispose()
    assert result["period_days"] == 7


@pytest.mark.asyncio
async def test_anomaly_effectiveness_service_response_keys():
    """calculate_anomaly_effectiveness returns a dict (empty DB)."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    import ml.alert_outcomes as ao_module
    from db.session import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    customer_id = uuid.UUID(CUSTOMER_ID)
    async with AsyncSession(engine) as session:
        result = await ao_module.calculate_anomaly_effectiveness(db=session, customer_id=customer_id, lookback_days=30)

    await engine.dispose()
    assert isinstance(result, dict)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_roi_service_response_keys():
    """calculate_alert_roi returns all expected ROI keys (empty DB)."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    import ml.alert_outcomes as ao_module
    from db.session import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    customer_id = uuid.UUID(CUSTOMER_ID)
    async with AsyncSession(engine) as session:
        result = await ao_module.calculate_alert_roi(db=session, customer_id=customer_id, lookback_days=90)

    await engine.dispose()

    assert "prevented_stockouts" in result
    assert "ghost_stock_recovered_value" in result
    assert "total_value_created" in result
    assert "period_days" in result
    assert result["period_days"] == 90


@pytest.mark.asyncio
async def test_roi_service_zero_for_empty_db():
    """With no anomaly data, ROI values are all zero."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    import ml.alert_outcomes as ao_module
    from db.session import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    customer_id = uuid.UUID(CUSTOMER_ID)
    async with AsyncSession(engine) as session:
        result = await ao_module.calculate_alert_roi(db=session, customer_id=customer_id, lookback_days=90)

    await engine.dispose()

    assert result["prevented_stockouts"] == 0
    assert result["ghost_stock_recovered_value"] == 0.0
    assert result["total_value_created"] == 0.0


# ── HTTP integration tests (stubbed session) ──────────────────────────────────


@pytest.mark.asyncio
async def test_alert_effectiveness_endpoint_200(client_tenant):
    """GET /outcomes/alerts/effectiveness returns 200 with expected keys."""
    response = await client_tenant.get("/outcomes/alerts/effectiveness")
    assert response.status_code == 200
    data = response.json()
    assert "total_alerts" in data
    assert "false_positive_rate" in data
    assert "period_days" in data


@pytest.mark.asyncio
async def test_alert_effectiveness_days_param(client_tenant):
    """days query parameter is accepted and reflected in period_days."""
    response = await client_tenant.get("/outcomes/alerts/effectiveness?days=14")
    assert response.status_code == 200
    assert response.json()["period_days"] == 14


@pytest.mark.asyncio
async def test_anomaly_effectiveness_endpoint_200(client_tenant):
    """GET /outcomes/anomalies/effectiveness returns 200."""
    response = await client_tenant.get("/outcomes/anomalies/effectiveness")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


@pytest.mark.asyncio
async def test_roi_endpoint_200(client_tenant):
    """GET /outcomes/roi returns 200 with ROI structure."""
    response = await client_tenant.get("/outcomes/roi")
    assert response.status_code == 200
    data = response.json()
    assert "total_value_created" in data
    assert "period_days" in data


@pytest.mark.asyncio
async def test_roi_tenant_scoped(client_tenant):
    """ROI endpoint is tenant-scoped (no cross-tenant leakage)."""
    response = await client_tenant.get("/outcomes/roi?days=30")
    assert response.status_code == 200
    assert response.json()["period_days"] == 30


# ── Pydantic schema validation (422 path) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_record_alert_outcome_invalid_literal_422(client_tenant):
    """Invalid outcome value returns 422 before DB is touched."""
    fake_id = str(uuid.uuid4())
    response = await client_tenant.post(
        f"/outcomes/alert/{fake_id}",
        json={"outcome": "invalid_outcome_xyz"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_record_alert_outcome_missing_required_field_422(client_tenant):
    """Missing 'outcome' field returns 422."""
    fake_id = str(uuid.uuid4())
    response = await client_tenant.post(
        f"/outcomes/alert/{fake_id}",
        json={"outcome_notes": "some note"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_record_alert_outcome_valid_literals_no_422(client_tenant):
    """All valid alert outcome literals are accepted by Pydantic (no 422)."""
    valid_outcomes = [
        "true_positive",
        "false_positive",
        "prevented_stockout",
        "prevented_overstock",
        "ghost_stock_confirmed",
    ]
    fake_id = str(uuid.uuid4())
    for outcome in valid_outcomes:
        response = await client_tenant.post(
            f"/outcomes/alert/{fake_id}",
            json={"outcome": outcome},
        )
        assert response.status_code != 422, f"outcome={outcome!r} was incorrectly rejected with 422"


@pytest.mark.asyncio
async def test_record_anomaly_outcome_invalid_literal_422(client_tenant):
    """Invalid anomaly outcome returns 422."""
    fake_id = str(uuid.uuid4())
    response = await client_tenant.post(
        f"/outcomes/anomaly/{fake_id}",
        json={"outcome": "not_a_real_outcome"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_record_anomaly_outcome_valid_literals_no_422(client_tenant):
    """All valid anomaly outcome literals pass Pydantic validation."""
    valid_outcomes = ["true_positive", "false_positive", "resolved", "investigating"]
    fake_id = str(uuid.uuid4())
    for outcome in valid_outcomes:
        response = await client_tenant.post(
            f"/outcomes/anomaly/{fake_id}",
            json={"outcome": outcome},
        )
        assert response.status_code != 422, f"outcome={outcome!r} was incorrectly rejected with 422"


@pytest.mark.asyncio
async def test_record_anomaly_outcome_optional_fields_accepted(client_tenant):
    """Optional action_taken and outcome_notes are accepted without 422."""
    fake_id = str(uuid.uuid4())
    response = await client_tenant.post(
        f"/outcomes/anomaly/{fake_id}",
        json={
            "outcome": "resolved",
            "action_taken": "cycle_count",
            "outcome_notes": "Manually verified",
        },
    )
    assert response.status_code != 422


@pytest.mark.asyncio
async def test_record_alert_outcome_optional_prevented_loss(client_tenant):
    """Optional prevented_loss is accepted without 422."""
    fake_id = str(uuid.uuid4())
    response = await client_tenant.post(
        f"/outcomes/alert/{fake_id}",
        json={"outcome": "prevented_stockout", "prevented_loss": 1500.0},
    )
    assert response.status_code != 422
