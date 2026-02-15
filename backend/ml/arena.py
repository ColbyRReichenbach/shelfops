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
from typing import Any, Literal

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Type aliases
ModelStatus = Literal["champion", "challenger", "shadow", "archived"]
RoutingStrategy = Literal["champion", "shadow", "canary", "store_segment"]


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


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
    Compare candidate against champion using DS + business guardrails.

    Promotion rules:
      1. MAE non-regression (<= 2% degradation max)
      2. MAPE non-regression (<= 2% degradation max)
      3. Coverage non-regression (candidate >= champion)
      4. Stockout miss-rate non-regression (if both present, <= +0.5pp)
      5. Overstock-rate non-regression (if both present, <= +0.5pp)
      6. Overstock dollars improves >=1%, OR within +0.5% when stockout improves

    Args:
        db: Database session
        customer_id: Tenant ID
        model_name: Model type ('demand_forecast', etc.)
        candidate_version: New model version to evaluate
        candidate_metrics: Includes DS/business metrics.
        improvement_threshold: Legacy parameter, retained for backward compatibility.

    Returns:
        dict with promotion decision and gate check details.
    """
    from db.models import ModelVersion

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

    champion_metrics = champion.get("metrics") or {}

    champion_mae = _as_float(champion_metrics.get("mae"))
    champion_mape = _as_float(champion_metrics.get("mape"))
    champion_coverage = _as_float(champion_metrics.get("coverage"))
    champion_stockout = _as_float(champion_metrics.get("stockout_miss_rate"))
    champion_overstock_rate = _as_float(champion_metrics.get("overstock_rate"))
    champion_overstock_dollars = _as_float(champion_metrics.get("overstock_dollars"))

    candidate_mae = _as_float(candidate_metrics.get("mae"))
    candidate_mape = _as_float(candidate_metrics.get("mape"))
    candidate_coverage = _as_float(candidate_metrics.get("coverage"))
    candidate_stockout = _as_float(candidate_metrics.get("stockout_miss_rate"))
    candidate_overstock_rate = _as_float(candidate_metrics.get("overstock_rate"))
    candidate_overstock_dollars = _as_float(candidate_metrics.get("overstock_dollars"))

    # DS gates (strict)
    mae_gate = candidate_mae is not None and champion_mae is not None and candidate_mae <= champion_mae * 1.02
    mape_gate = candidate_mape is not None and champion_mape is not None and candidate_mape <= champion_mape * 1.02
    coverage_gate = (
        candidate_coverage is not None and champion_coverage is not None and candidate_coverage >= champion_coverage
    )

    # Business gates (fail closed if required inputs are missing).
    stockout_gate = (
        candidate_stockout is not None
        and champion_stockout is not None
        and candidate_stockout <= champion_stockout + 0.005
    )

    overstock_rate_gate = (
        candidate_overstock_rate is not None
        and champion_overstock_rate is not None
        and candidate_overstock_rate <= champion_overstock_rate + 0.005
    )

    if candidate_overstock_dollars is not None and champion_overstock_dollars is not None:
        improved = candidate_overstock_dollars <= champion_overstock_dollars * 0.99
        near_flat_with_stockout_gain = (
            candidate_overstock_dollars <= champion_overstock_dollars * 1.005
            and candidate_stockout is not None
            and champion_stockout is not None
            and candidate_stockout < champion_stockout
        )
        overstock_dollars_gate = improved or near_flat_with_stockout_gain
    else:
        overstock_dollars_gate = False

    should_promote = all(
        [
            mae_gate,
            mape_gate,
            coverage_gate,
            stockout_gate,
            overstock_rate_gate,
            overstock_dollars_gate,
        ]
    )

    gate_checks = {
        "mae_gate": mae_gate,
        "mape_gate": mape_gate,
        "coverage_gate": coverage_gate,
        "stockout_miss_gate": stockout_gate,
        "overstock_rate_gate": overstock_rate_gate,
        "overstock_dollars_gate": overstock_dollars_gate,
    }

    decision = {
        "gates": gate_checks,
        "champion_metrics": {
            "mae": champion_mae,
            "mape": champion_mape,
            "coverage": champion_coverage,
            "stockout_miss_rate": champion_stockout,
            "overstock_rate": champion_overstock_rate,
            "overstock_dollars": champion_overstock_dollars,
        },
        "candidate_metrics": {
            "mae": candidate_mae,
            "mape": candidate_mape,
            "coverage": candidate_coverage,
            "stockout_miss_rate": candidate_stockout,
            "overstock_rate": candidate_overstock_rate,
            "overstock_dollars": candidate_overstock_dollars,
        },
        "thresholds": {
            "max_mae_regression_pct": 2.0,
            "max_mape_regression_pct": 2.0,
            "max_stockout_miss_pp": 0.5,
            "max_overstock_rate_pp": 0.5,
            "overstock_dollars_improvement_pct": 1.0,
            "overstock_dollars_tolerance_pct": 0.5,
        },
    }

    # Persist decision context with candidate metrics for reproducibility.
    enriched_metrics = dict(candidate_metrics)
    enriched_metrics["promotion_decision"] = decision
    await db.execute(
        update(ModelVersion)
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == model_name,
            ModelVersion.version == candidate_version,
        )
        .values(metrics=enriched_metrics)
    )
    await db.commit()

    fail_reasons = [name for name, passed in gate_checks.items() if not passed]
    decision_reason = (
        "passed_business_and_ds_gates"
        if should_promote
        else ("failed_gates:" + ",".join(fail_reasons) if fail_reasons else "failed_unknown_gate")
    )

    # Persist to model experiment log for reproducible decision trace.
    from db.models import ModelExperiment

    experiment = ModelExperiment(
        customer_id=customer_id,
        experiment_name=f"promotion_eval_{model_name}_{candidate_version}",
        hypothesis="Candidate meets business + DS promotion gates.",
        experiment_type="model_architecture",
        model_name=model_name,
        baseline_version=champion["version"],
        experimental_version=candidate_version,
        status="completed",
        proposed_by="system:auto_promotion",
        approved_by="system:auto_promotion",
        results={
            "promoted": should_promote,
            "reason": decision_reason,
            "decision": decision,
        },
        decision_rationale=decision_reason,
        completed_at=datetime.utcnow(),
    )
    db.add(experiment)
    await db.commit()

    if should_promote:
        await promote_to_champion(db, customer_id, model_name, candidate_version)
        logger.info(
            "arena.auto_promoted",
            customer_id=str(customer_id),
            model_name=model_name,
            new_champion=candidate_version,
            old_champion=champion["version"],
            candidate_mae=round(candidate_mae or 0, 2),
            champion_mae=round(champion_mae or 0, 2),
            gate_checks=gate_checks,
        )
        return {
            "promoted": True,
            "reason": decision_reason,
            "gate_checks": gate_checks,
            "champion_mae": champion_mae,
            "candidate_mae": candidate_mae,
            "decision": decision,
        }
    else:
        # Not promoted → set as challenger for shadow testing
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
            reason="failed_business_or_ds_gates",
            candidate_mae=round(candidate_mae or 0, 2),
            champion_mae=round(champion_mae or 0, 2),
            gate_checks=gate_checks,
        )
        return {
            "promoted": False,
            "reason": decision_reason,
            "gate_checks": gate_checks,
            "champion_mae": champion_mae,
            "candidate_mae": candidate_mae,
            "decision": decision,
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
    from sqlalchemy import update

    from db.models import ModelVersion

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
