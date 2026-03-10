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

router = APIRouter(prefix="/experiments", tags=["experiments"])


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
            "lineage_metadata": (exp.results or {}).get("lineage_metadata"),
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
        "results": exp.results,
        "lineage_metadata": (exp.results or {}).get("lineage_metadata"),
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
    exp.results = {
        **existing_results,
        "lineage_metadata": lineage_metadata,
        "decision_payload": decision_payload,
    }
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
        "results": exp.results,
        "lineage_metadata": (exp.results or {}).get("lineage_metadata"),
        "decision_rationale": exp.decision_rationale,
        "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
    }
