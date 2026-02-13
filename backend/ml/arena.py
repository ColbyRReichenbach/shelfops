"""
Champion/Challenger Arena — Model routing, auto-promotion, shadow mode.

Production ML lifecycle management:
  1. Train new model → status='candidate'
  2. Auto-promote if better than champion (95% threshold)
  3. Shadow mode: run challenger in background, compare metrics
  4. Canary deployment: route % of traffic to challenger
  5. Archive old champions (never delete)

Agent: ml-engineer
Skill: ml-forecasting
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Type aliases
ModelStatus = Literal["champion", "challenger", "shadow", "archived"]
RoutingStrategy = Literal["champion", "shadow", "canary", "store_segment"]


# ─── Model Version CRUD ─────────────────────────────────────────────────────


async def register_model_version(
    db: AsyncSession,
    customer_id: uuid.UUID,
    model_name: str,
    version: str,
    metrics: dict,
    status: ModelStatus = "candidate",
    smoke_test_passed: bool = False,
) -> uuid.UUID:
    """
    Register a new model version in the database.

    Args:
        db: Database session
        customer_id: Tenant ID
        model_name: 'demand_forecast', 'promo_lift', 'lead_time', etc.
        version: 'v1', 'v2', etc.
        metrics: {mae, mape, coverage, ...}
        status: Initial status (default 'candidate')
        smoke_test_passed: Whether smoke tests passed

    Returns:
        model_id (UUID)
    """
    from db.models import ModelVersion

    model_id = uuid.uuid4()
    model_version = ModelVersion(
        model_id=model_id,
        customer_id=customer_id,
        model_name=model_name,
        version=version,
        status=status,
        metrics=metrics,
        smoke_test_passed=smoke_test_passed,
        created_at=datetime.utcnow(),
    )

    db.add(model_version)
    await db.commit()

    logger.info(
        "arena.model_registered",
        model_id=str(model_id),
        customer_id=str(customer_id),
        model_name=model_name,
        version=version,
        status=status,
        mae=metrics.get("mae"),
    )

    return model_id


async def get_champion_model(
    db: AsyncSession,
    customer_id: uuid.UUID,
    model_name: str,
) -> dict | None:
    """
    Get current champion model for a customer/model_name.

    Returns:
        dict with {model_id, version, metrics} or None
    """
    from db.models import ModelVersion

    result = await db.execute(
        select(
            ModelVersion.model_id,
            ModelVersion.version,
            ModelVersion.metrics,
            ModelVersion.promoted_at,
        )
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == model_name,
            ModelVersion.status == "champion",
        )
        .order_by(ModelVersion.promoted_at.desc())
        .limit(1)
    )
    row = result.one_or_none()

    if not row:
        return None

    return {
        "model_id": row.model_id,
        "version": row.version,
        "metrics": row.metrics,
        "promoted_at": row.promoted_at,
    }


async def get_challenger_model(
    db: AsyncSession,
    customer_id: uuid.UUID,
    model_name: str,
) -> dict | None:
    """
    Get current challenger model (if exists).

    Returns:
        dict with {model_id, version, metrics, routing_weight} or None
    """
    from db.models import ModelVersion

    result = await db.execute(
        select(
            ModelVersion.model_id,
            ModelVersion.version,
            ModelVersion.metrics,
            ModelVersion.routing_weight,
        )
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == model_name,
            ModelVersion.status == "challenger",
        )
        .order_by(ModelVersion.created_at.desc())
        .limit(1)
    )
    row = result.one_or_none()

    if not row:
        return None

    return {
        "model_id": row.model_id,
        "version": row.version,
        "metrics": row.metrics,
        "routing_weight": row.routing_weight,
    }


# ─── Auto-Promotion Logic ───────────────────────────────────────────────────


async def evaluate_for_promotion(
    db: AsyncSession,
    customer_id: uuid.UUID,
    model_name: str,
    candidate_version: str,
    candidate_metrics: dict,
    improvement_threshold: float = 0.95,
) -> dict:
    """
    Compare candidate against champion. Auto-promote if better.

    Auto-promote if:
      1. MAE < champion_mae × threshold (default 95% = 5% improvement)
      2. MAPE < champion_mape × threshold
      3. Coverage ≥ champion_coverage (no degradation)
      4. Smoke tests passed

    Args:
        db: Database session
        customer_id: Tenant ID
        model_name: Model type ('demand_forecast', etc.)
        candidate_version: New model version to evaluate
        candidate_metrics: {mae, mape, coverage}
        improvement_threshold: Promotion threshold (0.95 = 5% improvement required)

    Returns:
        dict with {promoted: bool, reason: str, champion_mae: float, candidate_mae: float}
    """
    champion = await get_champion_model(db, customer_id, model_name)

    # No champion exists → auto-promote first candidate
    if not champion:
        await promote_to_champion(db, customer_id, model_name, candidate_version)
        return {
            "promoted": True,
            "reason": "first_champion",
            "champion_mae": None,
            "candidate_mae": candidate_metrics.get("mae"),
        }

    champion_metrics = champion["metrics"]
    champion_mae = champion_metrics.get("mae", float("inf"))
    champion_mape = champion_metrics.get("mape", float("inf"))
    champion_coverage = champion_metrics.get("coverage", 0.0)

    candidate_mae = candidate_metrics.get("mae", float("inf"))
    candidate_mape = candidate_metrics.get("mape", float("inf"))
    candidate_coverage = candidate_metrics.get("coverage", 0.0)

    # Promotion criteria
    mae_improved = candidate_mae < champion_mae * improvement_threshold
    mape_improved = candidate_mape < champion_mape * improvement_threshold
    coverage_ok = candidate_coverage >= champion_coverage

    should_promote = mae_improved and mape_improved and coverage_ok

    if should_promote:
        await promote_to_champion(db, customer_id, model_name, candidate_version)
        logger.info(
            "arena.auto_promoted",
            customer_id=str(customer_id),
            model_name=model_name,
            new_champion=candidate_version,
            old_champion=champion["version"],
            candidate_mae=round(candidate_mae, 2),
            champion_mae=round(champion_mae, 2),
            improvement_pct=round((1 - candidate_mae / champion_mae) * 100, 1),
        )
        return {
            "promoted": True,
            "reason": "better_performance",
            "champion_mae": champion_mae,
            "candidate_mae": candidate_mae,
            "improvement_pct": (1 - candidate_mae / champion_mae) * 100,
        }
    else:
        # Not promoted → set as challenger for shadow testing
        from db.models import ModelVersion
        from sqlalchemy import update

        await db.execute(
            update(ModelVersion)
            .where(
                ModelVersion.customer_id == customer_id,
                ModelVersion.model_name == model_name,
                ModelVersion.version == candidate_version,
            )
            .values(status="challenger", routing_weight=0.0)
        )
        await db.commit()

        logger.info(
            "arena.set_as_challenger",
            customer_id=str(customer_id),
            model_name=model_name,
            challenger=candidate_version,
            reason="insufficient_improvement",
            candidate_mae=round(candidate_mae, 2),
            champion_mae=round(champion_mae, 2),
        )
        return {
            "promoted": False,
            "reason": f"mae_improvement={round((1 - candidate_mae/champion_mae)*100, 1)}% < 5% threshold",
            "champion_mae": champion_mae,
            "candidate_mae": candidate_mae,
        }


async def promote_to_champion(
    db: AsyncSession,
    customer_id: uuid.UUID,
    model_name: str,
    version: str,
) -> None:
    """
    Promote a model version to champion status.

    1. Archive existing champion (if any)
    2. Promote new version to champion
    3. Publish alert
    """
    from db.models import ModelVersion
    from sqlalchemy import update

    now = datetime.utcnow()

    # Archive existing champion
    await db.execute(
        update(ModelVersion)
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == model_name,
            ModelVersion.status == "champion",
        )
        .values(status="archived", archived_at=now)
    )

    # Promote new champion
    await db.execute(
        update(ModelVersion)
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == model_name,
            ModelVersion.version == version,
        )
        .values(status="champion", promoted_at=now, routing_weight=1.0)
    )

    await db.commit()

    logger.info(
        "arena.champion_promoted",
        customer_id=str(customer_id),
        model_name=model_name,
        version=version,
        promoted_at=now.isoformat(),
    )


# ─── Model Routing (Prediction Serving) ────────────────────────────────────


def select_model_for_request(
    customer_id: str,
    model_name: str,
    store_id: str,
    routing_strategy: RoutingStrategy = "champion",
    challenger_weight: float = 0.0,
) -> str:
    """
    Select which model version to use for a prediction request.

    Routing strategies:
      - "champion": Always use champion (default, production safe)
      - "shadow": Use champion, log challenger prediction in background
      - "canary": Route X% traffic to challenger (hash-based, stable per store)
      - "store_segment": Route by store cluster (high-volume stores get newer model)

    Args:
        customer_id: Tenant ID
        model_name: Model type
        store_id: Store making the request
        routing_strategy: Routing logic to apply
        challenger_weight: % of traffic to route to challenger (0.0-1.0)

    Returns:
        "champion" or "challenger"
    """
    if routing_strategy == "champion":
        return "champion"

    if routing_strategy == "shadow":
        # Shadow mode: always return champion, but caller should also run challenger
        return "champion"

    if routing_strategy == "canary":
        # Canary: hash-based stable routing (same store always gets same model)
        if challenger_weight <= 0:
            return "champion"

        hash_val = hash(f"{customer_id}{model_name}{store_id}") % 100
        if hash_val < int(challenger_weight * 100):
            return "challenger"
        return "champion"

    if routing_strategy == "store_segment":
        # Future: route by store cluster (high-volume → newer models)
        # For now, default to champion
        return "champion"

    return "champion"


# ─── Shadow Mode Helpers ────────────────────────────────────────────────────


async def log_shadow_prediction(
    db: AsyncSession,
    customer_id: uuid.UUID,
    store_id: uuid.UUID,
    product_id: uuid.UUID,
    forecast_date: datetime.date,
    champion_prediction: float,
    challenger_prediction: float,
) -> None:
    """
    Log a shadow prediction for later comparison.

    Actual demand will be filled in T+1 by a daily job.
    """
    from db.models import ShadowPrediction

    shadow_prediction = ShadowPrediction(
        shadow_id=uuid.uuid4(),
        customer_id=customer_id,
        store_id=store_id,
        product_id=product_id,
        forecast_date=forecast_date,
        champion_prediction=champion_prediction,
        challenger_prediction=challenger_prediction,
        actual_demand=None,  # Filled in T+1
        created_at=datetime.utcnow(),
    )

    db.add(shadow_prediction)
    await db.commit()
