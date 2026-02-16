#!/usr/bin/env python3
"""
Populate MLOps demo data and promote a selected model to champion.

What this does:
  1. Promotes a chosen registry version in backend/models/{registry,champion}.json
  2. Upserts model_versions rows for champion/challenger
  3. Seeds backtest_results from forecast_accuracy aggregates
  4. Seeds ml_alerts + model_experiments if empty

Usage:
  cd backend
  python3 scripts/populate_mlops_demo.py --champion-version v_subset_xgb_only_01
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add backend root to sys.path for direct script execution.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import get_settings
from db.models import BacktestResult, MLAlert, ModelExperiment, ModelRetrainingLog, ModelVersion

DEFAULT_CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
REGISTRY_PATH = Path(__file__).resolve().parent.parent / "models" / "registry.json"
CHAMPION_PATH = Path(__file__).resolve().parent.parent / "models" / "champion.json"
MODEL_NAME = "demand_forecast"


def _load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Registry not found at {REGISTRY_PATH}")
    return json.loads(REGISTRY_PATH.read_text())


def _save_registry(payload: dict) -> None:
    REGISTRY_PATH.write_text(json.dumps(payload, indent=2, default=str))


def _save_champion(version: str, promoted_at: str) -> None:
    CHAMPION_PATH.write_text(
        json.dumps(
            {
                "version": version,
                "promoted_at": promoted_at,
                "note": "Promoted for MLOps dashboard population.",
            },
            indent=2,
        )
    )


def _pick_challenger(registry_models: list[dict], champion_version: str) -> str | None:
    candidates = [
        m
        for m in registry_models
        if m.get("version") != champion_version and isinstance(m.get("mae"), (int, float))
    ]
    if not candidates:
        return None
    # Prefer a strong recent candidate by lowest MAE then MAPE.
    candidates.sort(key=lambda m: (m.get("mae", float("inf")), m.get("mape", float("inf"))))
    return str(candidates[0]["version"])


def _normalize_registry_statuses(registry_models: list[dict], champion_version: str, challenger_version: str | None) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    for model in registry_models:
        version = model.get("version")
        if version == champion_version:
            model["status"] = "champion"
            model["promoted_at"] = now_iso
        elif version == challenger_version:
            model["status"] = "candidate"
        elif model.get("status") == "champion":
            model["status"] = "archived"
            if not model.get("promoted_at"):
                model["promoted_at"] = None


async def _upsert_model_version(
    db: AsyncSession,
    customer_id: uuid.UUID,
    version: str,
    status: str,
    metrics: dict,
    promoted_at: datetime | None,
    routing_weight: float,
    archived_at: datetime | None = None,
) -> uuid.UUID:
    existing = await db.execute(
        select(ModelVersion).where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == MODEL_NAME,
            ModelVersion.version == version,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = ModelVersion(
            customer_id=customer_id,
            model_name=MODEL_NAME,
            version=version,
            status=status,
            routing_weight=routing_weight,
            promoted_at=promoted_at,
            archived_at=archived_at,
            metrics=metrics,
            smoke_test_passed=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(row)
    else:
        row.status = status
        row.routing_weight = routing_weight
        row.promoted_at = promoted_at
        row.archived_at = archived_at
        row.metrics = metrics
        row.smoke_test_passed = True
    await db.flush()
    return row.model_id


async def _seed_backtest_from_accuracy(db: AsyncSession, customer_id: uuid.UUID, model_id: uuid.UUID) -> int:
    await db.execute(
        delete(BacktestResult).where(
            BacktestResult.customer_id == customer_id,
            BacktestResult.model_id == model_id,
        )
    )
    result = await db.execute(
        text(
            """
            SELECT
              forecast_date,
              AVG(mae) AS mae,
              AVG(mape) AS mape
            FROM forecast_accuracy
            WHERE customer_id = :customer_id
            GROUP BY forecast_date
            ORDER BY forecast_date DESC
            LIMIT 90
            """
        ),
        {"customer_id": str(customer_id)},
    )
    inserted = 0
    for row in result:
        backtest = BacktestResult(
            customer_id=customer_id,
            model_id=model_id,
            forecast_date=row.forecast_date,
            actual_date=row.forecast_date,
            mae=float(row.mae or 0.0),
            mape=float(row.mape or 0.0),
            stockout_miss_rate=0.0,
            overstock_rate=0.0,
            evaluated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(backtest)
        inserted += 1
    return inserted


async def _seed_ml_alerts_if_empty(db: AsyncSession, customer_id: uuid.UUID, challenger_version: str | None) -> int:
    existing = await db.execute(select(func.count()).select_from(MLAlert).where(MLAlert.customer_id == customer_id))
    if (existing.scalar_one() or 0) > 0:
        return 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    alerts = [
        MLAlert(
            customer_id=customer_id,
            alert_type="drift_detected",
            severity="warning",
            title="MAE drift detected",
            message="7-day MAE moved above rolling baseline. Retrain completed and needs review.",
            alert_metadata={"drift_pct": 0.08, "model_name": MODEL_NAME},
            status="unread",
            action_url="/mlops",
            created_at=now,
        ),
        MLAlert(
            customer_id=customer_id,
            alert_type="promotion_pending",
            severity="info",
            title="Challenger available for review",
            message="A challenger model is registered. Review backtest and decide promotion.",
            alert_metadata={"new_version": challenger_version, "model_name": MODEL_NAME},
            status="read",
            action_url="/mlops",
            created_at=now,
            read_at=now,
        ),
    ]
    db.add_all(alerts)
    return len(alerts)


async def _seed_experiments_if_empty(
    db: AsyncSession,
    customer_id: uuid.UUID,
    champion_version: str,
    challenger_version: str | None,
) -> int:
    existing = await db.execute(
        select(func.count()).select_from(ModelExperiment).where(ModelExperiment.customer_id == customer_id)
    )
    if (existing.scalar_one() or 0) > 0:
        return 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    experiments = [
        ModelExperiment(
            customer_id=customer_id,
            experiment_name="XGBoost hyperparameter refinement",
            hypothesis="Tuned tree constraints improve MAE on volatile categories.",
            experiment_type="model_architecture",
            model_name=MODEL_NAME,
            baseline_version=champion_version,
            experimental_version=challenger_version,
            status="approved",
            proposed_by="ml_team@shelfops.com",
            approved_by="ml_manager@shelfops.com",
            created_at=now,
            approved_at=now,
        ),
        ModelExperiment(
            customer_id=customer_id,
            experiment_name="Reorder sensitivity feature trial",
            hypothesis="Adding reorder decision signals reduces overstock error.",
            experiment_type="feature_engineering",
            model_name=MODEL_NAME,
            baseline_version=champion_version,
            experimental_version=None,
            status="proposed",
            proposed_by="ml_team@shelfops.com",
            created_at=now,
        ),
    ]
    db.add_all(experiments)
    return len(experiments)


async def _seed_retrain_log(db: AsyncSession, customer_id: uuid.UUID, champion_version: str) -> None:
    row = ModelRetrainingLog(
        customer_id=customer_id,
        model_name=MODEL_NAME,
        trigger_type="manual",
        trigger_metadata={"source": "populate_mlops_demo"},
        status="completed",
        version_produced=champion_version,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)


async def main(champion_version: str, customer_id: uuid.UUID) -> None:
    registry = _load_registry()
    models = registry.get("models", [])
    versions = {str(m.get("version")) for m in models}
    if champion_version not in versions:
        raise ValueError(f"Champion version '{champion_version}' not found in registry.json")
    if len(champion_version) > 20:
        raise ValueError(
            f"Champion version '{champion_version}' exceeds DB version length limit (20 chars)."
        )

    challenger_version = _pick_challenger(models, champion_version)
    if challenger_version and len(challenger_version) > 20:
        challenger_version = None

    _normalize_registry_statuses(models, champion_version, challenger_version)
    _save_registry(registry)
    promoted_at_iso = datetime.now(timezone.utc).isoformat()
    _save_champion(champion_version, promoted_at_iso)

    # Pull metrics from registry for champion/challenger rows.
    by_version = {str(m.get("version")): m for m in models}
    champion_entry = by_version[champion_version]
    challenger_entry = by_version.get(challenger_version) if challenger_version else None

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            # Archive any existing champion/challenger for this customer/model.
            existing_rows = await db.execute(
                select(ModelVersion).where(
                    ModelVersion.customer_id == customer_id,
                    ModelVersion.model_name == MODEL_NAME,
                )
            )
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for row in existing_rows.scalars().all():
                if row.status in {"champion", "challenger"} and row.version not in {champion_version, challenger_version}:
                    row.status = "archived"
                    row.archived_at = now
                    row.routing_weight = 0.0

            champion_metrics = {
                "mae": champion_entry.get("mae"),
                "mape": champion_entry.get("mape"),
                "tier": champion_entry.get("feature_tier"),
                "dataset": champion_entry.get("dataset"),
                "rows_trained": champion_entry.get("rows_trained"),
            }
            champion_model_id = await _upsert_model_version(
                db=db,
                customer_id=customer_id,
                version=champion_version,
                status="champion",
                metrics=champion_metrics,
                promoted_at=now,
                routing_weight=1.0,
                archived_at=None,
            )

            if challenger_version and challenger_entry:
                challenger_metrics = {
                    "mae": challenger_entry.get("mae"),
                    "mape": challenger_entry.get("mape"),
                    "tier": challenger_entry.get("feature_tier"),
                    "dataset": challenger_entry.get("dataset"),
                    "rows_trained": challenger_entry.get("rows_trained"),
                }
                await _upsert_model_version(
                    db=db,
                    customer_id=customer_id,
                    version=challenger_version,
                    status="challenger",
                    metrics=challenger_metrics,
                    promoted_at=None,
                    routing_weight=0.0,
                    archived_at=None,
                )

            backtests_inserted = await _seed_backtest_from_accuracy(db, customer_id, champion_model_id)
            ml_alerts_inserted = await _seed_ml_alerts_if_empty(db, customer_id, challenger_version)
            experiments_inserted = await _seed_experiments_if_empty(
                db,
                customer_id,
                champion_version,
                challenger_version,
            )
            await _seed_retrain_log(db, customer_id, champion_version)

            await db.commit()

            print("MLOps demo population complete.")
            print(f"  Champion:   {champion_version}")
            print(f"  Challenger: {challenger_version}")
            print(f"  Backtests:  {backtests_inserted}")
            print(f"  ML Alerts:  +{ml_alerts_inserted}")
            print(f"  Experiments:+{experiments_inserted}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate MLOps demo records.")
    parser.add_argument(
        "--champion-version",
        default="v_subset_xgb_only_01",
        help="Registry version to promote as champion (must be <=20 chars for DB model_versions).",
    )
    parser.add_argument(
        "--customer-id",
        default=str(DEFAULT_CUSTOMER_ID),
        help="Customer UUID.",
    )
    args = parser.parse_args()
    asyncio.run(main(champion_version=args.champion_version, customer_id=uuid.UUID(args.customer_id)))
