"""
Model Experiments API — Human-led hypothesis-driven ML experiments.

Workflow:
  1. Propose: POST /experiments (status='proposed')
  2. Approve: PATCH /experiments/{id}/approve (status='approved')
  3. Implement: DS trains model, status → 'in_progress' → 'shadow_testing'
  4. Complete: POST /experiments/{id}/complete (status='completed')

Endpoints:
  GET /experiments — List experiments
  GET /experiments/{id} — Get experiment details
  POST /experiments — Propose new experiment
  PATCH /experiments/{id}/approve — Approve experiment
  PATCH /experiments/{id}/reject — Reject experiment
  POST /experiments/{id}/complete — Complete experiment with results
  GET /experiments/{id}/results — Get experiment results
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_tenant_db
from db.models import ModelExperiment
from ml.lineage import EXPERIMENT_TYPE_CHOICES, normalize_experiment_type

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


# ── Request/Response Models ─────────────────────────────────────────────────


class ProposeExperimentRequest(BaseModel):
    experiment_name: str
    hypothesis: str
    experiment_type: str
    model_name: str = "demand_forecast"
    lineage_metadata: dict[str, Any] | None = None

    @field_validator("experiment_type")
    @classmethod
    def validate_experiment_type(cls, value: str) -> str:
        return normalize_experiment_type(value)


class ApproveExperimentRequest(BaseModel):
    rationale: str | None = None


class RejectExperimentRequest(BaseModel):
    rationale: str


class CompleteExperimentRequest(BaseModel):
    decision: Literal["adopt", "reject", "partial_adopt", "rollback"]
    decision_rationale: str
    results: dict[str, Any]  # {baseline_mae, experimental_mae, improvement_pct, etc.}
    experimental_version: str | None = None
    rollback_version: str | None = None


class RunExperimentRequest(BaseModel):
    data_dir: str = "data/benchmarks/m5_walmart"
    holdout_days: int = Field(default=14, ge=7, le=60)
    max_rows: int = Field(default=50_000, ge=10_000, le=250_000)
    max_challengers: int = Field(default=0, ge=0, le=10)


def _resolve_customer_id(user: dict) -> uuid.UUID:
    raw = user.get("customer_id")
    if not raw:
        raise HTTPException(status_code=401, detail="No customer context set")
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid customer context") from exc


def _resolve_actor(user: dict) -> str:
    actor = user.get("email") or user.get("sub")
    if not actor:
        raise HTTPException(status_code=401, detail="No authenticated actor available")
    return str(actor)


def _experiment_artifact_paths(experiment_id: uuid.UUID) -> tuple[str, str, str]:
    base = Path("backend/reports/experiments") / str(experiment_id)
    base.parent.mkdir(parents=True, exist_ok=True)
    return (
        str(base.with_suffix(".partition.json")),
        str(base.with_suffix(".report.json")),
        str(base.with_suffix(".report.md")),
    )


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_delta(
    baseline_metrics: dict[str, Any],
    challenger_metrics: dict[str, Any],
    metric_name: str,
) -> float | None:
    baseline = _coerce_float(baseline_metrics.get(metric_name))
    challenger = _coerce_float(challenger_metrics.get(metric_name))
    if baseline is None or challenger is None:
        return None
    return round(challenger - baseline, 4)


def _normalize_experiment_results(results: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(results or {})
    run_report = dict(payload.get("run_report") or {})
    arena_breakdown = dict(payload.get("arena_breakdown") or payload.get("promotion_comparison") or {})

    baseline_metrics = dict((run_report.get("baseline") or {}).get("holdout_metrics") or {})
    challenger_metrics = dict((run_report.get("challenger") or {}).get("holdout_metrics") or {})
    challenger_lineage = dict((run_report.get("challenger") or {}).get("lineage_metadata") or {})
    baseline_lineage = dict((run_report.get("baseline") or {}).get("lineage_metadata") or {})

    lineage_metadata = dict(payload.get("lineage_metadata") or challenger_lineage or baseline_lineage)

    normalized = {
        **payload,
        "lineage_metadata": lineage_metadata,
        "promotion_comparison": payload.get("promotion_comparison") or arena_breakdown or None,
    }

    for source_key, target_key in (
        ("mae", "baseline_mae"),
        ("wape", "baseline_wape"),
        ("mase", "baseline_mase"),
    ):
        normalized[target_key] = payload.get(target_key)
        if normalized[target_key] is None:
            normalized[target_key] = _coerce_float(baseline_metrics.get(source_key))

    for source_key, target_key in (
        ("mae", "experimental_mae"),
        ("wape", "experimental_wape"),
        ("mase", "experimental_mase"),
    ):
        normalized[target_key] = payload.get(target_key)
        if normalized[target_key] is None:
            normalized[target_key] = _coerce_float(challenger_metrics.get(source_key))

    if normalized.get("overstock_dollars_delta") is None:
        normalized["overstock_dollars_delta"] = _metric_delta(
            baseline_metrics,
            challenger_metrics,
            "overstock_dollars",
        )
    if normalized.get("opportunity_cost_stockout_delta") is None:
        normalized["opportunity_cost_stockout_delta"] = _metric_delta(
            baseline_metrics,
            challenger_metrics,
            "opportunity_cost_stockout",
        )
    if normalized.get("overall_business_safe") is None and "promoted" in arena_breakdown:
        normalized["overall_business_safe"] = bool(arena_breakdown.get("promoted"))

    return normalized


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("")
async def list_experiments(
    model_name: str | None = None,
    status: str | None = None,
    experiment_type: str | None = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """
    List model experiments with optional filters.

    Query params:
      - status: 'proposed', 'approved', 'in_progress', 'shadow_testing', 'completed', 'rejected'
      - experiment_type: 'feature_engineering', 'model_architecture', etc.
      - limit: Max experiments to return (default 50)
    """
    customer_id = _resolve_customer_id(user)

    # Build query
    query = select(ModelExperiment).where(ModelExperiment.customer_id == customer_id)

    if status:
        query = query.where(ModelExperiment.status == status)
    if model_name:
        query = query.where(ModelExperiment.model_name == model_name)
    if experiment_type:
        try:
            normalized_type = normalize_experiment_type(experiment_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        query = query.where(ModelExperiment.experiment_type == normalized_type)

    query = query.order_by(ModelExperiment.created_at.desc()).limit(limit)

    experiments_result = await db.execute(query)
    experiments = experiments_result.scalars().all()

    return [
        {
            "experiment_id": str(exp.experiment_id),
            "experiment_name": exp.experiment_name,
            "hypothesis": exp.hypothesis,
            "experiment_type": exp.experiment_type,
            "model_name": exp.model_name,
            "status": exp.status,
            "proposed_by": exp.proposed_by,
            "approved_by": exp.approved_by,
            "baseline_version": exp.baseline_version,
            "experimental_version": exp.experimental_version,
            "lineage_metadata": _normalize_experiment_results(exp.results).get("lineage_metadata"),
            "results": _normalize_experiment_results(exp.results),
            "decision_rationale": exp.decision_rationale,
            "created_at": exp.created_at.isoformat(),
            "approved_at": exp.approved_at.isoformat() if exp.approved_at else None,
            "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
        }
        for exp in experiments
    ]


@router.get("/{experiment_id}")
async def get_experiment_details(
    experiment_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Get full details for a specific experiment."""
    customer_id = _resolve_customer_id(user)

    # Get experiment
    exp_result = await db.execute(
        select(ModelExperiment).where(
            ModelExperiment.experiment_id == uuid.UUID(experiment_id),
            ModelExperiment.customer_id == customer_id,
        )
    )
    exp = exp_result.scalar_one_or_none()

    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return {
        "experiment_id": str(exp.experiment_id),
        "experiment_name": exp.experiment_name,
        "hypothesis": exp.hypothesis,
        "experiment_type": exp.experiment_type,
        "model_name": exp.model_name,
        "baseline_version": exp.baseline_version,
        "experimental_version": exp.experimental_version,
        "status": exp.status,
        "proposed_by": exp.proposed_by,
        "approved_by": exp.approved_by,
        "results": _normalize_experiment_results(exp.results),
        "lineage_metadata": _normalize_experiment_results(exp.results).get("lineage_metadata"),
        "decision_rationale": exp.decision_rationale,
        "created_at": exp.created_at.isoformat(),
        "approved_at": exp.approved_at.isoformat() if exp.approved_at else None,
        "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
    }


@router.post("")
async def propose_experiment(
    request: ProposeExperimentRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Propose a new ML experiment.

    Example:
        {
          "experiment_name": "Department-Tiered Forecasting",
          "hypothesis": "Electronics demand differs from Grocery. Dedicated model will improve MAE by 12%",
          "experiment_type": "segmentation",
          "model_name": "demand_forecast"
        }
    """
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)

    # Get current champion version as baseline
    from ml.arena import get_champion_model

    champion = await get_champion_model(db, customer_id, request.model_name)
    baseline_version = champion["version"] if champion else None

    # Create experiment
    experiment_id = uuid.uuid4()
    experiment = ModelExperiment(
        experiment_id=experiment_id,
        customer_id=customer_id,
        experiment_name=request.experiment_name,
        hypothesis=request.hypothesis,
        experiment_type=request.experiment_type,
        model_name=request.model_name,
        baseline_version=baseline_version,
        status="proposed",
        proposed_by=actor,
        results={"lineage_metadata": request.lineage_metadata or {}},
        created_at=datetime.utcnow(),
    )

    db.add(experiment)
    await db.commit()

    logger.info(
        "experiment.proposed",
        experiment_id=str(experiment_id),
        experiment_name=request.experiment_name,
        proposed_by=actor,
    )

    return {
        "status": "success",
        "experiment_id": str(experiment_id),
        "message": "Experiment proposed successfully",
        "baseline_version": baseline_version,
    }


@router.patch("/{experiment_id}/approve")
async def approve_experiment(
    experiment_id: str,
    request: ApproveExperimentRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Approve an experiment (manager review).

    After approval, DS can begin implementation.
    """
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)

    # Get experiment
    exp_result = await db.execute(
        select(ModelExperiment).where(
            ModelExperiment.experiment_id == uuid.UUID(experiment_id),
            ModelExperiment.customer_id == customer_id,
        )
    )
    exp = exp_result.scalar_one_or_none()

    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if exp.status != "proposed":
        raise HTTPException(status_code=400, detail=f"Cannot approve experiment in status: {exp.status}")

    # Approve
    exp.status = "approved"
    exp.approved_by = actor
    exp.approved_at = datetime.utcnow()

    if request.rationale:
        exp.decision_rationale = request.rationale

    await db.commit()

    logger.info(
        "experiment.approved",
        experiment_id=experiment_id,
        experiment_name=exp.experiment_name,
        approved_by=actor,
    )

    return {
        "status": "success",
        "message": "Experiment approved",
        "approved_by": actor,
        "approved_at": exp.approved_at.isoformat(),
    }


@router.patch("/{experiment_id}/reject")
async def reject_experiment(
    experiment_id: str,
    request: RejectExperimentRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Reject an experiment (manager review)."""
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)

    # Get experiment
    exp_result = await db.execute(
        select(ModelExperiment).where(
            ModelExperiment.experiment_id == uuid.UUID(experiment_id),
            ModelExperiment.customer_id == customer_id,
        )
    )
    exp = exp_result.scalar_one_or_none()

    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if exp.status not in {"proposed", "approved"}:
        raise HTTPException(status_code=400, detail=f"Cannot reject experiment in status: {exp.status}")

    # Reject
    exp.status = "rejected"
    exp.decision_rationale = request.rationale
    exp.completed_at = datetime.utcnow()
    exp.results = {
        **dict(exp.results or {}),
        "review": {
            **dict((exp.results or {}).get("review") or {}),
            "rejected_by": actor,
            "rejected_at": exp.completed_at.isoformat(),
        },
    }

    await db.commit()

    logger.info(
        "experiment.rejected",
        experiment_id=experiment_id,
        experiment_name=exp.experiment_name,
        rejected_by=actor,
        rationale=request.rationale,
    )

    return {
        "status": "success",
        "message": "Experiment rejected",
        "rejected_by": actor,
    }


@router.post("/{experiment_id}/complete")
async def complete_experiment(
    experiment_id: str,
    request: CompleteExperimentRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Complete an experiment with results.

    After shadow testing, DS submits results for final decision:
      - 'adopt': Promote experimental model to champion
      - 'reject': Keep champion, archive experimental
      - 'partial_adopt': Adopt for specific segments (e.g., Electronics only)
      - 'rollback': Emergency rollback (experimental model caused issues)
    """
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)

    # Get experiment
    exp_result = await db.execute(
        select(ModelExperiment).where(
            ModelExperiment.experiment_id == uuid.UUID(experiment_id),
            ModelExperiment.customer_id == customer_id,
        )
    )
    exp = exp_result.scalar_one_or_none()

    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if exp.status not in {"approved", "in_progress", "shadow_testing"}:
        raise HTTPException(status_code=400, detail=f"Cannot complete experiment in status: {exp.status}")

    existing_results = dict(exp.results or {})
    lineage_metadata = dict(existing_results.get("lineage_metadata") or {})
    decision_payload = dict(request.results)
    decision_payload["decision"] = request.decision
    decision_payload["decision_rationale"] = request.decision_rationale
    decision_payload["completed_by"] = actor

    # Update experiment
    exp.status = "completed"
    exp.results = _normalize_experiment_results({
        **existing_results,
        "lineage_metadata": lineage_metadata,
        "decision_payload": decision_payload,
    })
    exp.decision_rationale = request.decision_rationale
    exp.completed_at = datetime.utcnow()

    if request.experimental_version:
        exp.experimental_version = request.experimental_version

    registry_sync = None

    # If adopted, promote model
    if request.decision == "adopt" and request.experimental_version:
        from ml.arena import promote_to_champion
        from ml.experiment import sync_registry_with_runtime_state

        await promote_to_champion(
            db=db,
            customer_id=customer_id,
            model_name=exp.model_name,
            version=request.experimental_version,
        )
        registry_sync = {
            "version": request.experimental_version,
            "model_name": exp.model_name,
            "candidate_status": "champion",
            "active_champion_version": request.experimental_version,
            "promotion_reason": "experiment_adopted",
        }

        logger.info(
            "experiment.adopted",
            experiment_id=experiment_id,
            experimental_version=request.experimental_version,
            improvement_pct=request.results.get("improvement_pct"),
        )
        sync_registry_with_runtime_state(**registry_sync)
    elif request.decision == "rollback":
        from ml.arena import promote_to_champion
        from ml.experiment import sync_registry_with_runtime_state

        rollback_version = request.rollback_version or exp.baseline_version or request.experimental_version
        if not rollback_version:
            raise HTTPException(
                status_code=400, detail="Rollback requires rollback_version, baseline_version, or experimental_version"
            )

        await promote_to_champion(
            db=db,
            customer_id=customer_id,
            model_name=exp.model_name,
            version=rollback_version,
        )
        registry_sync = {
            "version": rollback_version,
            "model_name": exp.model_name,
            "candidate_status": "champion",
            "active_champion_version": rollback_version,
            "promotion_reason": "experiment_rollback",
        }
        sync_registry_with_runtime_state(**registry_sync)
        decision_payload["rollback_version"] = rollback_version

    await db.commit()

    # Create ML Alert
    from db.models import MLAlert

    alert = MLAlert(
        ml_alert_id=uuid.uuid4(),
        customer_id=customer_id,
        alert_type="experiment_complete",
        severity="info",
        title=f"✅ Experiment Complete: {exp.experiment_name}",
        message=f"Decision: {request.decision}. {request.decision_rationale}",
        alert_metadata={
            "experiment_id": experiment_id,
            "decision": request.decision,
            "improvement_pct": request.results.get("improvement_pct"),
            "rollback_version": request.rollback_version,
        },
        status="unread",
        action_url=f"/experiments/{experiment_id}/results",
        created_at=datetime.utcnow(),
    )
    db.add(alert)
    await db.commit()

    logger.info(
        "experiment.completed",
        experiment_id=experiment_id,
        experiment_name=exp.experiment_name,
        decision=request.decision,
    )

    return {
        "status": "success",
        "message": f"Experiment completed with decision: {request.decision}",
        "completed_at": exp.completed_at.isoformat(),
        "results": exp.results,
    }


@router.post("/{experiment_id}/run")
async def run_experiment(
    experiment_id: str,
    request: RunExperimentRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Run a bounded experiment cycle from the logged hypothesis.

    This is intended for bounded analyst workflow iteration:
      1. Use the logged hypothesis metadata as run configuration
      2. Require explicit approval before execution
      3. Execute the offline legacy benchmark cycle
      4. Register the candidate in the arena
      5. Persist gate-by-gate pass/fail and resulting status
    """
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)
    experiment_uuid = uuid.UUID(experiment_id)

    exp_result = await db.execute(
        select(ModelExperiment).where(
            ModelExperiment.experiment_id == experiment_uuid,
            ModelExperiment.customer_id == customer_id,
        )
    )
    exp = exp_result.scalar_one_or_none()

    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status != "approved":
        raise HTTPException(status_code=400, detail=f"Cannot run experiment in status: {exp.status}")
    if exp.experimental_version:
        raise HTTPException(
            status_code=400, detail="Experiment already has an experimental version. Create a new hypothesis to rerun."
        )

    exp.status = "in_progress"
    await db.commit()

    from ml.arena import evaluate_for_promotion, get_champion_model, register_model_version
    from scripts.run_legacy_favorita_experiment_cycle import run_legacy_favorita_experiment_cycle

    champion = await get_champion_model(db, customer_id, exp.model_name)
    if champion and not exp.baseline_version:
        exp.baseline_version = champion["version"]
        await db.commit()

    candidate_version = f"e{experiment_uuid.hex[:10]}"
    partition_manifest, output_json, output_md = _experiment_artifact_paths(experiment_uuid)

    lineage_metadata = dict((exp.results or {}).get("lineage_metadata") or {})
    report = run_legacy_favorita_experiment_cycle(
        data_dir=request.data_dir,
        holdout_days=request.holdout_days,
        max_rows=request.max_rows,
        max_challengers=request.max_challengers,
        partition_manifest=partition_manifest,
        output_json=output_json,
        output_md=output_md,
        experiment_context={
            "experiment_name": exp.experiment_name,
            "hypothesis": exp.hypothesis,
            "experiment_type": exp.experiment_type,
            "model_name": exp.model_name,
            "lineage_metadata": lineage_metadata,
            "baseline_version": exp.baseline_version,
            "experimental_version": candidate_version,
        },
        champion_version=exp.baseline_version or None,
        challenger_version=candidate_version,
    )

    challenger_metrics = {
        **dict(report["challenger"]["holdout_metrics"]),
        **dict(report["challenger"]["lineage_metadata"]),
        "feature_tier": report["challenger"]["lineage_metadata"].get("feature_tier", "cold_start"),
        "tier": report["challenger"]["lineage_metadata"].get("feature_tier", "cold_start"),
        "estimated_business_basis": True,
        "business_basis_note": report.get("business_basis_note"),
        "segment_summary": report["challenger"].get("segment_summary"),
        "report_artifact": output_json,
    }

    await register_model_version(
        db=db,
        customer_id=customer_id,
        model_name=exp.model_name,
        version=candidate_version,
        metrics=challenger_metrics,
        status="candidate",
        smoke_test_passed=True,
    )
    comparison = await evaluate_for_promotion(
        db=db,
        customer_id=customer_id,
        model_name=exp.model_name,
        candidate_version=candidate_version,
        candidate_metrics=challenger_metrics,
    )

    existing_results = _normalize_experiment_results(exp.results)
    existing_results["lineage_metadata"] = report["challenger"]["lineage_metadata"]
    existing_results["run_report"] = report
    existing_results["arena_breakdown"] = comparison
    existing_results["execution"] = {
        "ran_by": actor,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": request.data_dir,
        "holdout_days": request.holdout_days,
        "max_rows": request.max_rows,
        "max_challengers": request.max_challengers,
        "artifact_json": output_json,
        "artifact_md": output_md,
    }

    exp.experimental_version = candidate_version
    exp.results = _normalize_experiment_results(existing_results)
    exp.decision_rationale = str(comparison["reason"])
    if comparison["promoted"]:
        exp.status = "completed"
        exp.completed_at = datetime.utcnow()
    else:
        exp.status = "shadow_testing"
        exp.completed_at = None

    await db.commit()

    logger.info(
        "experiment.run_completed",
        experiment_id=experiment_id,
        model_name=exp.model_name,
        promoted=comparison["promoted"],
        candidate_version=candidate_version,
        actor=actor,
    )

    return {
        "status": "success",
        "experiment_id": experiment_id,
        "experiment_status": exp.status,
        "baseline_version": exp.baseline_version,
        "experimental_version": candidate_version,
        "comparison": comparison,
        "report": report,
    }


@router.post("/{experiment_id}/interpret")
async def interpret_experiment(
    experiment_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Use Claude to interpret Arena evaluation results for a completed experiment.

    Returns a 3-part interpretation:
      - results_summary: what happened in plain language
      - why_it_worked: mechanistic explanation of feature contributions
      - next_hypothesis: concrete next experiment to run

    The interpretation is cached in exp.results["llm_interpretation"] to avoid
    redundant API calls on re-fetch.
    """
    from core.config import get_settings

    customer_id = _resolve_customer_id(user)

    exp_result = await db.execute(
        select(ModelExperiment).where(
            ModelExperiment.experiment_id == uuid.UUID(experiment_id),
            ModelExperiment.customer_id == customer_id,
        )
    )
    exp = exp_result.scalar_one_or_none()

    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not exp.results:
        raise HTTPException(status_code=400, detail="Experiment has no results yet — run the evaluation first.")

    # Return cached interpretation if available
    cached = (exp.results or {}).get("llm_interpretation")
    if cached:
        return {"experiment_id": experiment_id, "cached": True, **cached}

    settings = get_settings()
    api_key = settings.anthropic_api_key or None  # SDK reads ANTHROPIC_API_KEY from env if None

    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=api_key) if api_key else _anthropic.Anthropic()
    except Exception:
        raise HTTPException(status_code=503, detail="Anthropic client unavailable — check ANTHROPIC_API_KEY.")

    results = _normalize_experiment_results(exp.results)
    if not any(
        results.get(key) is not None
        for key in (
            "baseline_mae",
            "baseline_wape",
            "baseline_mase",
            "experimental_mae",
            "experimental_wape",
            "experimental_mase",
        )
    ):
        raise HTTPException(status_code=400, detail="Experiment results are incomplete — run or complete the evaluation first.")
    promo = results.get("promotion_comparison") or {}
    gate_checks = promo.get("gate_checks") or {}
    passed = [k for k, v in gate_checks.items() if v]
    failed = [k for k, v in gate_checks.items() if not v]
    lineage = results.get("lineage_metadata") or {}

    def _fmt(v: object) -> str:
        if v is None:
            return "N/A"
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)

    prompt = f"""You are a senior ML engineer at a retail inventory intelligence platform.

Experiment: {exp.experiment_name}
Hypothesis: {exp.hypothesis}
Model: {exp.model_name}
Feature set: {lineage.get("feature_set_id", "N/A")}
Dataset: {lineage.get("dataset_id", "N/A")}

Baseline ({exp.baseline_version or "champion"}) metrics:
  MAE={_fmt(results.get("baseline_mae"))}  WAPE={_fmt(results.get("baseline_wape"))}  MASE={_fmt(results.get("baseline_mase"))}

Challenger ({exp.experimental_version or "candidate"}) metrics:
  MAE={_fmt(results.get("experimental_mae"))}  WAPE={_fmt(results.get("experimental_wape"))}  MASE={_fmt(results.get("experimental_mase"))}

Overstock dollars delta: {_fmt(results.get("overstock_dollars_delta"))}
Opportunity cost (stockout) delta: {_fmt(results.get("opportunity_cost_stockout_delta"))}
Arena decision: {"PROMOTED" if results.get("overall_business_safe") else "SHADOW ONLY"}
Gates passed ({len(passed)}): {", ".join(passed) if passed else "none"}
Gates failed ({len(failed)}): {", ".join(failed) if failed else "none"}
Decision rationale: {exp.decision_rationale or promo.get("reason") or "N/A"}

Respond with exactly three sections separated by "---":
1. RESULTS SUMMARY (2-3 sentences): What the numbers show, whether the hypothesis was confirmed.
2. WHY IT WORKED (2-3 sentences): Mechanistic explanation — what the new features capture and why that improves accuracy for this retailer.
3. NEXT HYPOTHESIS (1-2 sentences): The single most promising follow-up experiment to run next, stated as a testable hypothesis.

Be specific, use the actual metric values, and keep each section concise."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text if message.content else ""
    except Exception as exc:
        logger.error("experiment.interpret.failed", experiment_id=experiment_id, error=str(exc))
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc

    # Parse the three sections
    parts = [p.strip() for p in raw.split("---") if p.strip()]
    interpretation = {
        "results_summary": parts[0] if len(parts) > 0 else raw,
        "why_it_worked": parts[1] if len(parts) > 1 else "",
        "next_hypothesis": parts[2] if len(parts) > 2 else "",
        "model": "claude-haiku-4-5-20251001",
    }

    # Cache in experiment results
    exp.results = _normalize_experiment_results({**results, "llm_interpretation": interpretation})
    await db.commit()

    logger.info("experiment.interpreted", experiment_id=experiment_id, model=interpretation["model"])

    return {"experiment_id": experiment_id, "cached": False, **interpretation}


@router.get("/{experiment_id}/results")
async def get_experiment_results(
    experiment_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Get experiment results (after shadow testing complete)."""
    customer_id = _resolve_customer_id(user)

    # Get experiment
    exp_result = await db.execute(
        select(ModelExperiment).where(
            ModelExperiment.experiment_id == uuid.UUID(experiment_id),
            ModelExperiment.customer_id == customer_id,
        )
    )
    exp = exp_result.scalar_one_or_none()

    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if not exp.results:
        raise HTTPException(status_code=400, detail="Experiment results not yet available")

    return {
        "experiment_id": str(exp.experiment_id),
        "experiment_name": exp.experiment_name,
        "hypothesis": exp.hypothesis,
        "status": exp.status,
        "baseline_version": exp.baseline_version,
        "experimental_version": exp.experimental_version,
        "results": _normalize_experiment_results(exp.results),
        "lineage_metadata": _normalize_experiment_results(exp.results).get("lineage_metadata"),
        "decision_rationale": exp.decision_rationale,
        "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
    }
