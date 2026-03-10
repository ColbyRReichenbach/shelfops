import asyncio
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.session import Base


def _settings_for_db(db_url: str) -> SimpleNamespace:
    return SimpleNamespace(
        database_url=db_url,
        ml_forecast_horizon_days=1,
        ml_cold_start_min_history_days=1,
        ml_cold_start_min_store_count=1,
        ml_cold_start_min_product_count=1,
        ml_promotion_min_accuracy_samples=1,
        ml_promotion_accuracy_window_days=30,
    )


def _seed_core_entities(db_url: str) -> dict[str, uuid.UUID]:
    from db.models import Customer, Product, Store

    customer_id = uuid.uuid4()
    store_id = uuid.uuid4()
    product_id = uuid.uuid4()

    async def _seed() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                db.add(
                    Customer(
                        customer_id=customer_id,
                        name="Loop Test Customer",
                        email=f"loop-{customer_id}@example.com",
                        plan="professional",
                        status="active",
                    )
                )
                db.add(
                    Store(
                        store_id=store_id,
                        customer_id=customer_id,
                        name="Main Store",
                        city="Minneapolis",
                        state="MN",
                        zip_code="55401",
                    )
                )
                db.add(
                    Product(
                        product_id=product_id,
                        customer_id=customer_id,
                        sku="SKU-LOOP-1",
                        name="Loop Product",
                        category="general",
                        unit_cost=2.0,
                        unit_price=5.0,
                    )
                )
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(_seed())
    return {"customer_id": customer_id, "store_id": store_id, "product_id": product_id}


def test_generate_forecasts_creates_shadow_rows(tmp_path, monkeypatch):
    from db.models import ModelVersion, ShadowPrediction
    from workers.forecast import generate_forecasts

    db_path = tmp_path / "shadow_create.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    ids = _seed_core_entities(db_url)
    customer_id = ids["customer_id"]
    store_id = ids["store_id"]
    product_id = ids["product_id"]

    async def _seed_models() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                db.add_all(
                    [
                        ModelVersion(
                            customer_id=customer_id,
                            model_name="demand_forecast",
                            version="v1",
                            status="champion",
                            routing_weight=1.0,
                            promoted_at=datetime.utcnow(),
                            metrics={"mae": 10.0, "mape": 0.2, "coverage": 0.9},
                            smoke_test_passed=True,
                        ),
                        ModelVersion(
                            customer_id=customer_id,
                            model_name="demand_forecast",
                            version="v2",
                            status="challenger",
                            routing_weight=0.0,
                            metrics={"mae": 9.5, "mape": 0.19, "coverage": 0.91},
                            smoke_test_passed=True,
                        ),
                    ]
                )
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(_seed_models())

    monkeypatch.setattr("core.config.get_settings", lambda: _settings_for_db(db_url))

    def _fake_create_features(transactions_df, **_kwargs):
        return pd.DataFrame(
            {
                "date": [pd.Timestamp(date.today() - timedelta(days=1))],
                "store_id": [str(store_id)],
                "product_id": [str(product_id)],
                "quantity": [10.0],
            }
        )

    def _fake_load_models(version: str):
        return {"version": version}

    def _fake_predict_demand(features_df: pd.DataFrame, models: dict, confidence_level: float = 0.9):
        value = 10.0 if models["version"] == "v1" else 8.0
        out = features_df[["store_id", "product_id", "date"]].copy()
        out["forecasted_demand"] = value
        out["lower_bound"] = value - 1.0
        out["upper_bound"] = value + 1.0
        out["confidence"] = confidence_level
        return out

    async def _fake_txns(*_args, **_kwargs):
        return pd.DataFrame(
            {
                "date": [date.today() - timedelta(days=1)],
                "store_id": [str(store_id)],
                "product_id": [str(product_id)],
                "quantity": [10.0],
            }
        )

    async def _fake_feedback(*_args, **_kwargs):
        return pd.DataFrame()

    monkeypatch.setattr("ml.features.create_features", _fake_create_features)
    monkeypatch.setattr("ml.predict.load_models", _fake_load_models)
    monkeypatch.setattr("ml.predict.predict_demand", _fake_predict_demand)
    monkeypatch.setattr("workers.forecast._load_db_transactions", _fake_txns)
    monkeypatch.setattr("ml.feedback_loop.get_feedback_features", _fake_feedback)

    summary = generate_forecasts.run(customer_id=str(customer_id), horizon_days=1, model_name="demand_forecast")
    assert summary["status"] == "success"
    assert summary["shadow_rows_created"] == 1
    assert summary["challenger_version"] == "v2"
    assert summary["feature_tier_used"] == "cold_start"

    async def _assert_shadow() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                rows = (await db.execute(select(ShadowPrediction))).scalars().all()
                assert len(rows) == 1
                row = rows[0]
                assert row.customer_id == customer_id
                assert row.store_id == store_id
                assert row.product_id == product_id
                assert row.champion_prediction == 10.0
                assert row.challenger_prediction == 8.0
        finally:
            await engine.dispose()

    asyncio.run(_assert_shadow())


def test_generate_forecasts_uses_model_feature_tier_when_runtime_context_exists(tmp_path, monkeypatch):
    from db.models import InventoryLevel, ModelVersion
    from workers.forecast import generate_forecasts

    db_path = tmp_path / "shadow_production.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    ids = _seed_core_entities(db_url)
    customer_id = ids["customer_id"]
    store_id = ids["store_id"]
    product_id = ids["product_id"]

    async def _seed_models_and_inventory() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                db.add(
                    ModelVersion(
                        customer_id=customer_id,
                        model_name="demand_forecast",
                        version="v1",
                        status="champion",
                        routing_weight=1.0,
                        promoted_at=datetime.utcnow(),
                        metrics={"mae": 10.0, "mape": 0.2, "coverage": 0.9},
                        smoke_test_passed=True,
                    )
                )
                db.add(
                    InventoryLevel(
                        customer_id=customer_id,
                        store_id=store_id,
                        product_id=product_id,
                        timestamp=datetime.utcnow(),
                        quantity_on_hand=24,
                        quantity_on_order=6,
                        quantity_available=20,
                    )
                )
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(_seed_models_and_inventory())

    monkeypatch.setattr("core.config.get_settings", lambda: _settings_for_db(db_url))

    captured: dict[str, str | None] = {"force_tier": None}

    def _fake_create_features(transactions_df, **kwargs):
        captured["force_tier"] = kwargs.get("force_tier")
        return pd.DataFrame(
            {
                "date": [pd.Timestamp(date.today() - timedelta(days=1))],
                "store_id": [str(store_id)],
                "product_id": [str(product_id)],
                "quantity": [10.0],
            }
        )

    def _fake_load_models(version: str):
        return {"version": version, "feature_tier": "production"}

    def _fake_predict_demand(features_df: pd.DataFrame, models: dict, confidence_level: float = 0.9):
        out = features_df[["store_id", "product_id", "date"]].copy()
        out["forecasted_demand"] = 9.0
        out["lower_bound"] = 8.0
        out["upper_bound"] = 10.0
        out["confidence"] = confidence_level
        return out

    async def _fake_txns(*_args, **_kwargs):
        return pd.DataFrame(
            {
                "date": [date.today() - timedelta(days=1)],
                "store_id": [str(store_id)],
                "product_id": [str(product_id)],
                "quantity": [10.0],
            }
        )

    async def _fake_feedback(*_args, **_kwargs):
        return pd.DataFrame()

    monkeypatch.setattr("ml.features.create_features", _fake_create_features)
    monkeypatch.setattr("ml.predict.load_models", _fake_load_models)
    monkeypatch.setattr("ml.predict.predict_demand", _fake_predict_demand)
    monkeypatch.setattr("workers.forecast._load_db_transactions", _fake_txns)
    monkeypatch.setattr("ml.feedback_loop.get_feedback_features", _fake_feedback)

    summary = generate_forecasts.run(customer_id=str(customer_id), horizon_days=1, model_name="demand_forecast")
    assert summary["status"] == "success"
    assert summary["feature_tier_used"] == "production"
    assert summary["feature_tier_fallback_reason"] is None
    assert captured["force_tier"] == "production"


def test_compute_forecast_accuracy_reconciles_shadow_actuals(tmp_path, monkeypatch):
    from db.models import DemandForecast, ForecastAccuracy, ModelVersion, ShadowPrediction, Transaction
    from workers.monitoring import compute_forecast_accuracy

    db_path = tmp_path / "shadow_reconcile.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    ids = _seed_core_entities(db_url)
    customer_id = ids["customer_id"]
    store_id = ids["store_id"]
    product_id = ids["product_id"]
    target_day = datetime.utcnow().date() - timedelta(days=1)

    async def _seed() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                db.add(
                    ModelVersion(
                        customer_id=customer_id,
                        model_name="demand_forecast",
                        version="v1",
                        status="champion",
                        routing_weight=1.0,
                        promoted_at=datetime.utcnow(),
                        metrics={"mae": 10.0, "mape": 0.2, "coverage": 0.9},
                        smoke_test_passed=True,
                    )
                )
                db.add(
                    DemandForecast(
                        customer_id=customer_id,
                        store_id=store_id,
                        product_id=product_id,
                        forecast_date=target_day,
                        forecasted_demand=10.0,
                        lower_bound=9.0,
                        upper_bound=11.0,
                        confidence=0.9,
                        model_version="v1",
                    )
                )
                db.add(
                    ShadowPrediction(
                        customer_id=customer_id,
                        store_id=store_id,
                        product_id=product_id,
                        forecast_date=target_day,
                        champion_prediction=10.0,
                        challenger_prediction=8.0,
                    )
                )
                db.add(
                    Transaction(
                        customer_id=customer_id,
                        store_id=store_id,
                        product_id=product_id,
                        timestamp=datetime.combine(target_day, datetime.min.time()) + timedelta(hours=12),
                        quantity=12,
                        unit_price=5.0,
                        total_amount=60.0,
                        transaction_type="sale",
                    )
                )
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(_seed())
    monkeypatch.setattr("core.config.get_settings", lambda: _settings_for_db(db_url))

    summary = compute_forecast_accuracy.run(
        customer_id=str(customer_id),
        lookback_days=1,
        model_version="v1",
    )
    assert summary["status"] == "success"
    assert summary["shadow_rows_updated"] == 1
    assert summary["accuracy_rows_written"] == 1

    async def _assert_rows() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                shadow = (await db.execute(select(ShadowPrediction))).scalar_one()
                assert shadow.actual_demand == 12.0
                assert shadow.champion_error == 2.0
                assert shadow.challenger_error == 4.0

                accuracy = (await db.execute(select(ForecastAccuracy))).scalar_one()
                assert accuracy.actual_demand == 12.0
                assert accuracy.mae == 2.0
        finally:
            await engine.dispose()

    asyncio.run(_assert_rows())


def test_detect_model_drift_scopes_to_champion_version(tmp_path, monkeypatch):
    from db.models import ForecastAccuracy, ModelVersion
    from workers.monitoring import detect_model_drift

    db_path = tmp_path / "drift_scope.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    ids = _seed_core_entities(db_url)
    customer_id = ids["customer_id"]
    store_id = ids["store_id"]
    product_id = ids["product_id"]

    now = datetime.utcnow()
    old_ts = now - timedelta(days=30)
    recent_ts = now - timedelta(days=1)

    async def _seed() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                db.add_all(
                    [
                        ModelVersion(
                            customer_id=customer_id,
                            model_name="demand_forecast",
                            version="v1",
                            status="champion",
                            routing_weight=1.0,
                            promoted_at=now - timedelta(days=10),
                            metrics={"mae": 10.0, "mape": 0.2, "coverage": 0.9},
                            smoke_test_passed=True,
                        ),
                        ModelVersion(
                            customer_id=customer_id,
                            model_name="demand_forecast",
                            version="v2",
                            status="challenger",
                            routing_weight=0.0,
                            metrics={"mae": 9.0, "mape": 0.18, "coverage": 0.91},
                            smoke_test_passed=True,
                        ),
                        # Champion: 10 -> 11 MAE (10% degradation, below 15% threshold)
                        ForecastAccuracy(
                            customer_id=customer_id,
                            store_id=store_id,
                            product_id=product_id,
                            forecast_date=(date.today() - timedelta(days=30)),
                            forecasted_demand=20.0,
                            actual_demand=10.0,
                            mae=10.0,
                            mape=1.0,
                            model_version="v1",
                            evaluated_at=old_ts,
                        ),
                        ForecastAccuracy(
                            customer_id=customer_id,
                            store_id=store_id,
                            product_id=product_id,
                            forecast_date=(date.today() - timedelta(days=1)),
                            forecasted_demand=21.0,
                            actual_demand=10.0,
                            mae=11.0,
                            mape=1.1,
                            model_version="v1",
                            evaluated_at=recent_ts,
                        ),
                        # Challenger: intentionally bad recent MAE (should be ignored by drift detector).
                        ForecastAccuracy(
                            customer_id=customer_id,
                            store_id=store_id,
                            product_id=product_id,
                            forecast_date=(date.today() - timedelta(days=30)),
                            forecasted_demand=20.0,
                            actual_demand=10.0,
                            mae=10.0,
                            mape=1.0,
                            model_version="v2",
                            evaluated_at=old_ts,
                        ),
                        ForecastAccuracy(
                            customer_id=customer_id,
                            store_id=store_id,
                            product_id=product_id,
                            forecast_date=(date.today() - timedelta(days=1)),
                            forecasted_demand=40.0,
                            actual_demand=10.0,
                            mae=30.0,
                            mape=3.0,
                            model_version="v2",
                            evaluated_at=recent_ts,
                        ),
                    ]
                )
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(_seed())
    monkeypatch.setattr("core.config.get_settings", lambda: _settings_for_db(db_url))

    apply_async_calls: list[dict] = []

    def _capture_apply_async(*args, **kwargs):
        apply_async_calls.append({"args": args, "kwargs": kwargs})
        return None

    monkeypatch.setattr("workers.retrain.retrain_forecast_model.apply_async", _capture_apply_async)

    summary = detect_model_drift.run(customer_id=str(customer_id))
    assert summary["status"] == "healthy"
    assert summary["champion_version"] == "v1"
    assert summary["drift_pct"] < 15.0
    assert apply_async_calls == []


def test_feedback_health_triggers_retrain_on_high_rejection(tmp_path, monkeypatch):
    """PO rejections above 60% threshold trigger feedback-driven retrain."""
    from db.models import PODecision, PurchaseOrder
    from workers.monitoring import check_feedback_health

    db_path = tmp_path / "feedback_health.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    ids = _seed_core_entities(db_url)
    customer_id = ids["customer_id"]
    store_id = ids["store_id"]
    product_id = ids["product_id"]

    async def _seed() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                # 6 POs, 4 rejected (67% > 60% threshold)
                for i in range(6):
                    is_rejected = i < 4
                    po = PurchaseOrder(
                        po_id=uuid.uuid4(),
                        customer_id=customer_id,
                        store_id=store_id,
                        product_id=product_id,
                        quantity=100,
                        status="cancelled" if is_rejected else "approved",
                    )
                    db.add(po)
                    await db.flush()

                    db.add(
                        PODecision(
                            decision_id=uuid.uuid4(),
                            customer_id=customer_id,
                            po_id=po.po_id,
                            decision_type="rejected" if is_rejected else "approved",
                            original_qty=100,
                            final_qty=0 if is_rejected else 100,
                            decided_by="planner",
                            decided_at=datetime.utcnow() - timedelta(days=i),
                        )
                    )
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(_seed())
    monkeypatch.setattr("core.config.get_settings", lambda: _settings_for_db(db_url))

    retrain_calls: list[dict] = []

    def _capture_apply_async(*args, **kwargs):
        retrain_calls.append({"args": args, "kwargs": kwargs})
        return None

    monkeypatch.setattr("workers.retrain.retrain_forecast_model.apply_async", _capture_apply_async)

    summary = check_feedback_health.run(customer_id=str(customer_id))
    assert summary["status"] == "feedback_drift_detected"
    assert summary["flagged_products_count"] >= 1
    assert len(retrain_calls) == 1
    assert retrain_calls[0]["kwargs"]["kwargs"]["trigger"] == "feedback_drift"


def test_feedback_health_skips_when_below_threshold(tmp_path, monkeypatch):
    """PO rejections below 60% threshold do not trigger retrain."""
    from db.models import PODecision, PurchaseOrder
    from workers.monitoring import check_feedback_health

    db_path = tmp_path / "feedback_healthy.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    ids = _seed_core_entities(db_url)
    customer_id = ids["customer_id"]
    store_id = ids["store_id"]
    product_id = ids["product_id"]

    async def _seed() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                # 6 POs, only 2 rejected (33% < 60% threshold)
                for i in range(6):
                    is_rejected = i < 2
                    po = PurchaseOrder(
                        po_id=uuid.uuid4(),
                        customer_id=customer_id,
                        store_id=store_id,
                        product_id=product_id,
                        quantity=100,
                        status="cancelled" if is_rejected else "approved",
                    )
                    db.add(po)
                    await db.flush()

                    db.add(
                        PODecision(
                            decision_id=uuid.uuid4(),
                            customer_id=customer_id,
                            po_id=po.po_id,
                            decision_type="rejected" if is_rejected else "approved",
                            original_qty=100,
                            final_qty=0 if is_rejected else 100,
                            decided_by="planner",
                            decided_at=datetime.utcnow() - timedelta(days=i),
                        )
                    )
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(_seed())
    monkeypatch.setattr("core.config.get_settings", lambda: _settings_for_db(db_url))

    retrain_calls: list[dict] = []

    def _capture_apply_async(*args, **kwargs):
        retrain_calls.append({"args": args, "kwargs": kwargs})
        return None

    monkeypatch.setattr("workers.retrain.retrain_forecast_model.apply_async", _capture_apply_async)

    summary = check_feedback_health.run(customer_id=str(customer_id))
    assert summary["status"] == "healthy"
    assert summary["flagged_products_count"] == 0
    assert retrain_calls == []


def test_receiving_discrepancy_features_computed(tmp_path):
    """Receiving discrepancies produce correct shortage_rate and supply_reliability_score."""
    from db.models import PurchaseOrder, ReceivingDiscrepancy
    from ml.feedback_loop import get_receiving_discrepancy_features

    db_path = tmp_path / "receiving_features.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    ids = _seed_core_entities(db_url)
    customer_id = ids["customer_id"]
    store_id = ids["store_id"]
    product_id = ids["product_id"]

    async def _seed_and_check() -> None:
        engine = create_async_engine(db_url, echo=False)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as db:
                # 4 receipts: 3 shortages, 1 overage
                for i in range(4):
                    po = PurchaseOrder(
                        po_id=uuid.uuid4(),
                        customer_id=customer_id,
                        store_id=store_id,
                        product_id=product_id,
                        quantity=100,
                        status="received",
                    )
                    db.add(po)
                    await db.flush()

                    disc_type = "shortage" if i < 3 else "overage"
                    db.add(
                        ReceivingDiscrepancy(
                            discrepancy_id=uuid.uuid4(),
                            customer_id=customer_id,
                            po_id=po.po_id,
                            product_id=product_id,
                            ordered_qty=100,
                            received_qty=90 if disc_type == "shortage" else 110,
                            discrepancy_qty=-10 if disc_type == "shortage" else 10,
                            discrepancy_type=disc_type,
                            reported_at=datetime.utcnow() - timedelta(days=i),
                        )
                    )
                await db.commit()

            # Now query the features
            async with session_factory() as db:
                result = await get_receiving_discrepancy_features(db, customer_id=customer_id, lookback_days=90)

                assert len(result) == 1
                row = result.iloc[0]
                assert row["shortage_rate_90d"] == 0.75  # 3 out of 4
                assert row["supply_reliability_score"] == 0.25  # 1.0 - 0.75
                assert row["avg_receiving_discrepancy_pct"] > 0
        finally:
            await engine.dispose()

    asyncio.run(_seed_and_check())
