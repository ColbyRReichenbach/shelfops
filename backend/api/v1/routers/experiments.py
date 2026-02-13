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
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import ModelExperiment

logger = structlog.get_logger()

router = APIRouter(prefix="/experiments", tags=["experiments"])


# ── Request/Response Models ─────────────────────────────────────────────────


class ProposeExperimentRequest(BaseModel):
    experiment_name: str
    hypothesis: str
    experiment_type: Literal["feature_engineering", "model_architecture", "data_source", "segmentation"]
    model_name: str = "demand_forecast"
    proposed_by: str  # User ID or email


class ApproveExperimentRequest(BaseModel):
    approved_by: str
    rationale: str | None = None


class RejectExperimentRequest(BaseModel):
    rejected_by: str
    rationale: str


class CompleteExperimentRequest(BaseModel):
    decision: Literal["adopt", "reject", "partial_adopt", "rollback"]
    decision_rationale: str
    results: dict[str, Any]  # {baseline_mae, experimental_mae, improvement_pct, etc.}
    experimental_version: str | None = None


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("")
async def list_experiments(
    status: str | None = None,
    experiment_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """
    List model experiments with optional filters.

    Query params:
      - status: 'proposed', 'approved', 'in_progress', 'shadow_testing', 'completed', 'rejected'
      - experiment_type: 'feature_engineering', 'model_architecture', etc.
      - limit: Max experiments to return (default 50)
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

    # Build query
    query = select(ModelExperiment).where(ModelExperiment.customer_id == customer_id)

    if status:
        query = query.where(ModelExperiment.status == status)
    if experiment_type:
        query = query.where(ModelExperiment.experiment_type == experiment_type)

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
            "created_at": exp.created_at.isoformat(),
            "approved_at": exp.approved_at.isoformat() if exp.approved_at else None,
            "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
        }
        for exp in experiments
    ]


@router.get("/{experiment_id}")
async def get_experiment_details(
    experiment_id: str,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Get full details for a specific experiment."""
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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
        "decision_rationale": exp.decision_rationale,
        "created_at": exp.created_at.isoformat(),
        "approved_at": exp.approved_at.isoformat() if exp.approved_at else None,
        "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
    }


@router.post("")
async def propose_experiment(
    request: ProposeExperimentRequest,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Propose a new ML experiment.

    Example:
        {
          "experiment_name": "Department-Tiered Forecasting",
          "hypothesis": "Electronics demand differs from Grocery. Dedicated model will improve MAE by 12%",
          "experiment_type": "segmentation",
          "model_name": "demand_forecast",
          "proposed_by": "jane.doe@shelfops.com"
        }
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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
        proposed_by=request.proposed_by,
        created_at=datetime.utcnow(),
    )

    db.add(experiment)
    await db.commit()

    logger.info(
        "experiment.proposed",
        experiment_id=str(experiment_id),
        experiment_name=request.experiment_name,
        proposed_by=request.proposed_by,
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
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Approve an experiment (manager review).

    After approval, DS can begin implementation.
    """
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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
    exp.approved_by = request.approved_by
    exp.approved_at = datetime.utcnow()

    if request.rationale:
        exp.decision_rationale = request.rationale

    await db.commit()

    logger.info(
        "experiment.approved",
        experiment_id=experiment_id,
        experiment_name=exp.experiment_name,
        approved_by=request.approved_by,
    )

    return {
        "status": "success",
        "message": "Experiment approved",
        "approved_by": request.approved_by,
        "approved_at": exp.approved_at.isoformat(),
    }


@router.patch("/{experiment_id}/reject")
async def reject_experiment(
    experiment_id: str,
    request: RejectExperimentRequest,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Reject an experiment (manager review)."""
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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

    # Reject
    exp.status = "rejected"
    exp.decision_rationale = request.rationale
    exp.completed_at = datetime.utcnow()

    await db.commit()

    logger.info(
        "experiment.rejected",
        experiment_id=experiment_id,
        experiment_name=exp.experiment_name,
        rejected_by=request.rejected_by,
        rationale=request.rationale,
    )

    return {
        "status": "success",
        "message": "Experiment rejected",
        "rejected_by": request.rejected_by,
    }


@router.post("/{experiment_id}/complete")
async def complete_experiment(
    experiment_id: str,
    request: CompleteExperimentRequest,
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
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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

    # Update experiment
    exp.status = "completed"
    exp.results = request.results
    exp.decision_rationale = request.decision_rationale
    exp.completed_at = datetime.utcnow()

    if request.experimental_version:
        exp.experimental_version = request.experimental_version

    # If adopted, promote model
    if request.decision == "adopt" and request.experimental_version:
        from ml.arena import promote_to_champion

        await promote_to_champion(
            db=db,
            customer_id=customer_id,
            model_name=exp.model_name,
            version=request.experimental_version,
        )

        logger.info(
            "experiment.adopted",
            experiment_id=experiment_id,
            experimental_version=request.experimental_version,
            improvement_pct=request.results.get("improvement_pct"),
        )

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
        "results": request.results,
    }


@router.get("/{experiment_id}/results")
async def get_experiment_results(
    experiment_id: str,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Get experiment results (after shadow testing complete)."""
    # Get current customer_id
    result = await db.execute(text("SELECT current_setting('app.current_customer_id', TRUE)"))
    customer_id_str = result.scalar()
    if not customer_id_str:
        raise HTTPException(status_code=401, detail="No customer context set")
    customer_id = uuid.UUID(customer_id_str)

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
        "decision_rationale": exp.decision_rationale,
        "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
    }
