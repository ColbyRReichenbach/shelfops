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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_tenant_db
from db.models import (
    AnomalyDetectionRun,
    ExperimentAgentTrace,
    ExperimentContextPackage,
    ExperimentHypothesis,
    ExperimentSpec,
    ModelExperiment,
)
from ml.lineage import normalize_experiment_type

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])
DEFAULT_FORECAST_DATA_DIR = "data/benchmarks/m5_walmart/subset_20spc"


# ── Request/Response Models ─────────────────────────────────────────────────


class ProposeExperimentRequest(BaseModel):
    experiment_name: str
    hypothesis: str
    experiment_type: str
    model_name: str = "demand_forecast"
    experiment_source: Literal["manual", "ai_assisted", "ai_agent"] = "manual"
    context_package_id: str | None = None
    hypothesis_id: str | None = None
    experiment_spec_id: str | None = None
    spec_template_id: str | None = None
    spec_overrides: dict[str, Any] = Field(default_factory=dict)
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
    data_dir: str = DEFAULT_FORECAST_DATA_DIR
    experiment_spec_id: str | None = None
    validation_mode: Literal["quick_screen", "extended_backtest", "promotion_gate"] = "quick_screen"
    holdout_days: int = Field(default=28, ge=7, le=365)
    calibration_days: int = Field(default=28, ge=7, le=180)
    rolling_window_count: int | None = Field(default=None, ge=0, le=12)
    rolling_window_days: int = Field(default=28, ge=7, le=90)
    rolling_stride_days: int = Field(default=28, ge=7, le=90)
    max_rows: int = Field(default=50_000, ge=10_000, le=250_000)
    max_series: int = Field(default=60, ge=2, le=250)
    max_challengers: int = Field(default=0, ge=0, le=10)


class CreateContextPackageRequest(BaseModel):
    package_name: str | None = None
    model_name: str = "demand_forecast"
    baseline_version: str | None = None
    dataset_id: str | None = None
    package_type: Literal["manual_vs_ai", "manual", "ai_agent", "benchmark"] = "manual_vs_ai"
    allowed_experiment_types: list[str] | None = None
    notes: str | None = None


class CreateHypothesisRequest(BaseModel):
    title: str
    hypothesis: str
    experiment_type: str
    model_name: str = "demand_forecast"
    experiment_source: Literal["manual", "ai_assisted", "ai_agent"] = "manual"
    context_package_id: str | None = None
    experiment_spec_id: str | None = None
    spec_template_id: str | None = None
    spec_overrides: dict[str, Any] = Field(default_factory=dict)
    domain_rationale: str | None = None
    expected_metric_movement: dict[str, Any] = Field(default_factory=dict)
    risk_notes: str | None = None
    hypothesis_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("experiment_type")
    @classmethod
    def validate_experiment_type(cls, value: str) -> str:
        return normalize_experiment_type(value)


class ReviewHypothesisRequest(BaseModel):
    decision: Literal["approve", "reject"]
    rationale: str | None = None
    convert_to_experiment: bool = False


class CreateExperimentSpecRequest(BaseModel):
    template_id: str
    spec_name: str | None = None
    context_package_id: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class CreateAgentTraceRequest(BaseModel):
    agent_name: str
    trace_type: Literal["hypothesis_generation", "experiment_plan", "interpretation", "execution_review"]
    agent_model: str | None = None
    context_package_id: str | None = None
    hypothesis_id: str | None = None
    experiment_id: str | None = None
    prompt_hash: str | None = Field(default=None, max_length=64)
    prompt_preview: str | None = None
    input_context: dict[str, Any] = Field(default_factory=dict)
    tool_allowlist: list[str] = Field(default_factory=list)
    generated_output: dict[str, Any] = Field(default_factory=dict)
    human_decision: Literal["pending", "approved", "rejected", "edited", "not_required"] = "pending"
    human_decision_rationale: str | None = None
    trace_metadata: dict[str, Any] = Field(default_factory=dict)


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

    for metric_name in ("precision", "recall", "f1", "false_positive_rate", "review_rate"):
        baseline_key = f"baseline_{metric_name}"
        experimental_key = f"experimental_{metric_name}"
        normalized[baseline_key] = payload.get(baseline_key)
        if normalized[baseline_key] is None:
            normalized[baseline_key] = _coerce_float(baseline_metrics.get(metric_name))
        normalized[experimental_key] = payload.get(experimental_key)
        if normalized[experimental_key] is None:
            normalized[experimental_key] = _coerce_float(challenger_metrics.get(metric_name))

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


def _parse_uuid(value: str, field_name: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}") from exc


async def _get_context_package(
    db: AsyncSession,
    customer_id: uuid.UUID,
    context_package_id: str | None,
) -> ExperimentContextPackage | None:
    if not context_package_id:
        return None
    package_uuid = _parse_uuid(context_package_id, "context_package_id")
    result = await db.execute(
        select(ExperimentContextPackage).where(
            ExperimentContextPackage.context_package_id == package_uuid,
            ExperimentContextPackage.customer_id == customer_id,
        )
    )
    package = result.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Experiment context package not found")
    return package


async def _get_hypothesis(
    db: AsyncSession,
    customer_id: uuid.UUID,
    hypothesis_id: str | None,
) -> ExperimentHypothesis | None:
    if not hypothesis_id:
        return None
    hypothesis_uuid = _parse_uuid(hypothesis_id, "hypothesis_id")
    result = await db.execute(
        select(ExperimentHypothesis).where(
            ExperimentHypothesis.hypothesis_id == hypothesis_uuid,
            ExperimentHypothesis.customer_id == customer_id,
        )
    )
    hypothesis = result.scalar_one_or_none()
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Experiment hypothesis not found")
    return hypothesis


async def _get_experiment_spec(
    db: AsyncSession,
    customer_id: uuid.UUID,
    experiment_spec_id: str | None,
) -> ExperimentSpec | None:
    if not experiment_spec_id:
        return None
    spec_uuid = _parse_uuid(experiment_spec_id, "experiment_spec_id")
    result = await db.execute(
        select(ExperimentSpec).where(
            ExperimentSpec.experiment_spec_id == spec_uuid,
            ExperimentSpec.customer_id == customer_id,
        )
    )
    spec = result.scalar_one_or_none()
    if not spec:
        raise HTTPException(status_code=404, detail="Experiment spec not found")
    return spec


def _serialize_experiment_spec(spec: ExperimentSpec) -> dict[str, Any]:
    return {
        "experiment_spec_id": str(spec.experiment_spec_id),
        "context_package_id": str(spec.context_package_id) if spec.context_package_id else None,
        "model_name": spec.model_name,
        "dataset_id": spec.dataset_id,
        "template_id": spec.template_id,
        "spec_name": spec.spec_name,
        "spec_version": spec.spec_version,
        "spec_hash": spec.spec_hash,
        "spec": spec.spec,
        "spec_metadata": spec.spec_metadata,
        "created_by": spec.created_by,
        "created_at": spec.created_at.isoformat(),
    }


async def _create_experiment_spec(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    actor: str,
    template_id: str,
    spec_name: str | None = None,
    context_package: ExperimentContextPackage | None = None,
    overrides: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    expected_model_name: str | None = None,
) -> ExperimentSpec:
    from ml.experiment_specs import hash_experiment_spec, materialize_experiment_spec

    try:
        spec_payload = materialize_experiment_spec(
            template_id=template_id,
            spec_name=spec_name,
            overrides=overrides or {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if expected_model_name and spec_payload["model_name"] != expected_model_name:
        raise HTTPException(status_code=400, detail="Experiment spec template does not match experiment model_name")

    spec = ExperimentSpec(
        experiment_spec_id=uuid.uuid4(),
        customer_id=customer_id,
        context_package_id=context_package.context_package_id if context_package else None,
        model_name=str(spec_payload["model_name"]),
        dataset_id=str(spec_payload["dataset_id"]),
        template_id=str(spec_payload["template_id"]),
        spec_name=str(spec_payload["spec_name"]),
        spec_version=str(spec_payload["spec_version"]),
        spec_hash=hash_experiment_spec(spec_payload),
        spec=spec_payload,
        spec_metadata={
            **dict(metadata or {}),
            "metric_provenance_required": True,
            "claim_boundary": spec_payload.get("claim_boundary"),
        },
        created_by=actor,
        created_at=datetime.utcnow(),
    )
    db.add(spec)
    await db.flush()
    return spec


async def _resolve_or_create_experiment_spec(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    actor: str,
    model_name: str,
    experiment_type: str,
    context_package: ExperimentContextPackage | None = None,
    experiment_spec_id: str | None = None,
    spec_template_id: str | None = None,
    spec_name: str | None = None,
    spec_overrides: dict[str, Any] | None = None,
    create_default: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ExperimentSpec | None:
    from ml.experiment_specs import default_template_for_experiment_type

    spec = await _get_experiment_spec(db, customer_id, experiment_spec_id)
    if spec:
        if spec.model_name != model_name:
            raise HTTPException(status_code=400, detail="Experiment spec model_name does not match experiment model_name")
        if context_package and spec.context_package_id and spec.context_package_id != context_package.context_package_id:
            raise HTTPException(status_code=400, detail="Experiment spec does not belong to the provided context package")
        return spec

    template_id = spec_template_id or (
        default_template_for_experiment_type(experiment_type, model_name=model_name) if create_default else None
    )
    if not template_id:
        return None

    return await _create_experiment_spec(
        db,
        customer_id=customer_id,
        actor=actor,
        template_id=template_id,
        spec_name=spec_name,
        context_package=context_package,
        overrides=spec_overrides or {},
        metadata=metadata,
        expected_model_name=model_name,
    )


def _serialize_experiment(exp: ModelExperiment) -> dict[str, Any]:
    results = _normalize_experiment_results(exp.results)
    return {
        "experiment_id": str(exp.experiment_id),
        "experiment_name": exp.experiment_name,
        "hypothesis": exp.hypothesis,
        "experiment_type": exp.experiment_type,
        "model_name": exp.model_name,
        "experiment_source": exp.experiment_source,
        "context_package_id": str(exp.context_package_id) if exp.context_package_id else None,
        "experiment_spec_id": str(exp.experiment_spec_id) if exp.experiment_spec_id else None,
        "status": exp.status,
        "proposed_by": exp.proposed_by,
        "approved_by": exp.approved_by,
        "baseline_version": exp.baseline_version,
        "experimental_version": exp.experimental_version,
        "lineage_metadata": results.get("lineage_metadata"),
        "results": results,
        "decision_rationale": exp.decision_rationale,
        "created_at": exp.created_at.isoformat(),
        "approved_at": exp.approved_at.isoformat() if exp.approved_at else None,
        "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
    }


def _serialize_context_package(package: ExperimentContextPackage) -> dict[str, Any]:
    return {
        "context_package_id": str(package.context_package_id),
        "package_name": package.package_name,
        "model_name": package.model_name,
        "baseline_version": package.baseline_version,
        "dataset_id": package.dataset_id,
        "dataset_snapshot_id": package.dataset_snapshot_id,
        "package_type": package.package_type,
        "artifact_uri": package.artifact_uri,
        "context_metadata": package.context_metadata,
        "allowed_experiment_types": package.allowed_experiment_types,
        "created_by": package.created_by,
        "created_at": package.created_at.isoformat(),
    }


def _serialize_hypothesis(hypothesis: ExperimentHypothesis) -> dict[str, Any]:
    return {
        "hypothesis_id": str(hypothesis.hypothesis_id),
        "customer_id": str(hypothesis.customer_id),
        "context_package_id": str(hypothesis.context_package_id) if hypothesis.context_package_id else None,
        "experiment_spec_id": str(hypothesis.experiment_spec_id) if hypothesis.experiment_spec_id else None,
        "experiment_id": str(hypothesis.experiment_id) if hypothesis.experiment_id else None,
        "model_name": hypothesis.model_name,
        "experiment_source": hypothesis.experiment_source,
        "title": hypothesis.title,
        "hypothesis": hypothesis.hypothesis,
        "experiment_type": hypothesis.experiment_type,
        "domain_rationale": hypothesis.domain_rationale,
        "expected_metric_movement": hypothesis.expected_metric_movement,
        "risk_notes": hypothesis.risk_notes,
        "status": hypothesis.status,
        "generated_by": hypothesis.generated_by,
        "reviewed_by": hypothesis.reviewed_by,
        "reviewed_at": hypothesis.reviewed_at.isoformat() if hypothesis.reviewed_at else None,
        "hypothesis_metadata": hypothesis.hypothesis_metadata,
        "created_at": hypothesis.created_at.isoformat(),
    }


def _serialize_agent_trace(trace: ExperimentAgentTrace) -> dict[str, Any]:
    return {
        "trace_id": str(trace.trace_id),
        "context_package_id": str(trace.context_package_id) if trace.context_package_id else None,
        "hypothesis_id": str(trace.hypothesis_id) if trace.hypothesis_id else None,
        "experiment_id": str(trace.experiment_id) if trace.experiment_id else None,
        "agent_name": trace.agent_name,
        "agent_model": trace.agent_model,
        "trace_type": trace.trace_type,
        "prompt_hash": trace.prompt_hash,
        "prompt_preview": trace.prompt_preview,
        "input_context": trace.input_context,
        "tool_allowlist": trace.tool_allowlist,
        "generated_output": trace.generated_output,
        "human_decision": trace.human_decision,
        "human_decision_by": trace.human_decision_by,
        "human_decision_at": trace.human_decision_at.isoformat() if trace.human_decision_at else None,
        "human_decision_rationale": trace.human_decision_rationale,
        "trace_metadata": trace.trace_metadata,
        "created_at": trace.created_at.isoformat(),
    }


def _summarize_experiment_for_comparison(exp: ModelExperiment) -> dict[str, Any]:
    results = _normalize_experiment_results(exp.results)
    return {
        "experiment_id": str(exp.experiment_id),
        "experiment_name": exp.experiment_name,
        "status": exp.status,
        "experiment_type": exp.experiment_type,
        "baseline_version": exp.baseline_version,
        "experimental_version": exp.experimental_version,
        "created_at": exp.created_at.isoformat(),
        "approved_at": exp.approved_at.isoformat() if exp.approved_at else None,
        "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
        "metrics": {
            "baseline_wape": results.get("baseline_wape"),
            "experimental_wape": results.get("experimental_wape"),
            "baseline_mase": results.get("baseline_mase"),
            "experimental_mase": results.get("experimental_mase"),
            "baseline_precision": results.get("baseline_precision"),
            "experimental_precision": results.get("experimental_precision"),
            "baseline_recall": results.get("baseline_recall"),
            "experimental_recall": results.get("experimental_recall"),
            "baseline_false_positive_rate": results.get("baseline_false_positive_rate"),
            "experimental_false_positive_rate": results.get("experimental_false_positive_rate"),
            "baseline_review_rate": results.get("baseline_review_rate"),
            "experimental_review_rate": results.get("experimental_review_rate"),
            "overstock_dollars_delta": results.get("overstock_dollars_delta"),
            "opportunity_cost_stockout_delta": results.get("opportunity_cost_stockout_delta"),
            "overall_business_safe": results.get("overall_business_safe"),
            "metric_provenance": (results.get("lineage_metadata") or {}).get("provenance") or "benchmark",
        },
        "decision": {
            "rationale": exp.decision_rationale,
            "promotion_comparison": results.get("promotion_comparison"),
        },
    }


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

    return [_serialize_experiment(exp) for exp in experiments]


@router.get("/spec-templates")
async def list_experiment_spec_templates(model_name: str | None = None) -> list[dict[str, Any]]:
    """List executable, curated experiment-spec templates."""
    from ml.experiment_specs import list_experiment_spec_templates

    return list_experiment_spec_templates(model_name=model_name)


@router.post("/specs")
async def create_experiment_spec(
    request: CreateExperimentSpecRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Materialize an immutable experiment spec from a curated template."""
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)
    package = await _get_context_package(db, customer_id, request.context_package_id)
    spec = await _create_experiment_spec(
        db,
        customer_id=customer_id,
        actor=actor,
        template_id=request.template_id,
        spec_name=request.spec_name,
        context_package=package,
        overrides=request.overrides,
        metadata={"created_from": "api"},
    )
    await db.commit()
    await db.refresh(spec)
    return _serialize_experiment_spec(spec)


@router.get("/specs")
async def list_experiment_specs(
    model_name: str | None = None,
    context_package_id: str | None = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """List tenant-scoped executable experiment specs."""
    customer_id = _resolve_customer_id(user)
    package = await _get_context_package(db, customer_id, context_package_id)
    query = select(ExperimentSpec).where(ExperimentSpec.customer_id == customer_id)
    if model_name:
        query = query.where(ExperimentSpec.model_name == model_name)
    if package:
        query = query.where(ExperimentSpec.context_package_id == package.context_package_id)
    query = query.order_by(ExperimentSpec.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [_serialize_experiment_spec(spec) for spec in result.scalars().all()]


@router.get("/specs/{experiment_spec_id}")
async def get_experiment_spec(
    experiment_spec_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Fetch one tenant-scoped executable experiment spec."""
    customer_id = _resolve_customer_id(user)
    spec = await _get_experiment_spec(db, customer_id, experiment_spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Experiment spec not found")
    return _serialize_experiment_spec(spec)


@router.post("/context-packages")
async def create_context_package(
    request: CreateContextPackageRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Create an auditable context bundle for manual-vs-AI experiment work."""
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)

    from ml.arena import get_champion_model
    from ml.experiment_governance import build_context_package_payload, write_context_package_artifacts

    normalized_types = [
        normalize_experiment_type(experiment_type)
        for experiment_type in (request.allowed_experiment_types or [])
    ] or None
    champion = await get_champion_model(db, customer_id, request.model_name)
    baseline_version = request.baseline_version or (champion["version"] if champion else None)
    context_package_id = uuid.uuid4()
    package_name = request.package_name or (
        f"{request.model_name}_manual_vs_ai_context_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    )
    payload = build_context_package_payload(
        context_package_id=context_package_id,
        package_name=package_name,
        model_name=request.model_name,
        baseline_version=baseline_version,
        dataset_id=request.dataset_id,
        actor=actor,
        package_type=request.package_type,
        allowed_experiment_types=normalized_types,
        notes=request.notes,
    )
    artifact_json, artifact_md = write_context_package_artifacts(context_package_id, payload)

    package = ExperimentContextPackage(
        context_package_id=context_package_id,
        customer_id=customer_id,
        package_name=package_name,
        model_name=request.model_name,
        baseline_version=payload.get("baseline_version"),
        dataset_id=payload.get("dataset_id"),
        dataset_snapshot_id=payload.get("dataset_snapshot_id"),
        package_type=request.package_type,
        artifact_uri=artifact_json,
        context_metadata={**payload, "artifact_markdown_uri": artifact_md},
        allowed_experiment_types=payload.get("allowed_experiment_types") or [],
        created_by=actor,
        created_at=datetime.utcnow(),
    )
    db.add(package)
    await db.commit()
    await db.refresh(package)

    logger.info(
        "experiment.context_package.created",
        context_package_id=str(context_package_id),
        model_name=request.model_name,
        created_by=actor,
    )
    return _serialize_context_package(package)


@router.get("/context-packages")
async def list_context_packages(
    model_name: str | None = None,
    limit: int = 25,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """List context packages available to the current tenant."""
    customer_id = _resolve_customer_id(user)
    query = select(ExperimentContextPackage).where(ExperimentContextPackage.customer_id == customer_id)
    if model_name:
        query = query.where(ExperimentContextPackage.model_name == model_name)
    query = query.order_by(ExperimentContextPackage.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [_serialize_context_package(package) for package in result.scalars().all()]


@router.post("/hypotheses")
async def create_hypothesis(
    request: CreateHypothesisRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Create a governed hypothesis backlog entry before an experiment run."""
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)
    package = await _get_context_package(db, customer_id, request.context_package_id)
    if package and package.model_name != request.model_name:
        raise HTTPException(status_code=400, detail="Context package model_name does not match hypothesis model_name")
    spec = await _resolve_or_create_experiment_spec(
        db,
        customer_id=customer_id,
        actor=actor,
        model_name=request.model_name,
        experiment_type=request.experiment_type,
        context_package=package,
        experiment_spec_id=request.experiment_spec_id,
        spec_template_id=request.spec_template_id,
        spec_name=f"{request.title}_spec" if request.spec_template_id else None,
        spec_overrides=request.spec_overrides,
        metadata={"created_from": "hypothesis_backlog", "experiment_source": request.experiment_source},
    )

    hypothesis = ExperimentHypothesis(
        hypothesis_id=uuid.uuid4(),
        customer_id=customer_id,
        context_package_id=package.context_package_id if package else None,
        experiment_spec_id=spec.experiment_spec_id if spec else None,
        model_name=request.model_name,
        experiment_source=request.experiment_source,
        title=request.title,
        hypothesis=request.hypothesis,
        experiment_type=request.experiment_type,
        domain_rationale=request.domain_rationale,
        expected_metric_movement=request.expected_metric_movement,
        risk_notes=request.risk_notes,
        status="proposed",
        generated_by=actor,
        hypothesis_metadata={
            **request.hypothesis_metadata,
            "context_hash": (package.context_metadata or {}).get("context_hash") if package else None,
            "experiment_spec_id": str(spec.experiment_spec_id) if spec else None,
            "experiment_spec_hash": spec.spec_hash if spec else None,
            "spec_template_id": spec.template_id if spec else request.spec_template_id,
            "metric_provenance_required": True,
        },
        created_at=datetime.utcnow(),
    )
    db.add(hypothesis)
    await db.commit()
    await db.refresh(hypothesis)

    logger.info(
        "experiment.hypothesis.created",
        hypothesis_id=str(hypothesis.hypothesis_id),
        source=request.experiment_source,
        model_name=request.model_name,
    )
    return _serialize_hypothesis(hypothesis)


@router.get("/hypotheses")
async def list_hypotheses(
    model_name: str | None = None,
    context_package_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """List governed hypotheses for manual and AI-assisted work."""
    customer_id = _resolve_customer_id(user)
    package = await _get_context_package(db, customer_id, context_package_id)
    query = select(ExperimentHypothesis).where(ExperimentHypothesis.customer_id == customer_id)
    if model_name:
        query = query.where(ExperimentHypothesis.model_name == model_name)
    if package:
        query = query.where(ExperimentHypothesis.context_package_id == package.context_package_id)
    if status:
        query = query.where(ExperimentHypothesis.status == status)
    query = query.order_by(ExperimentHypothesis.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [_serialize_hypothesis(hypothesis) for hypothesis in result.scalars().all()]


@router.patch("/hypotheses/{hypothesis_id}/review")
async def review_hypothesis(
    hypothesis_id: str,
    request: ReviewHypothesisRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Approve or reject a hypothesis, optionally converting it into an approved experiment."""
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)
    hypothesis = await _get_hypothesis(db, customer_id, hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Experiment hypothesis not found")
    if hypothesis.status not in {"proposed", "approved"}:
        raise HTTPException(status_code=400, detail=f"Cannot review hypothesis in status: {hypothesis.status}")

    now = datetime.utcnow()
    hypothesis.reviewed_by = actor
    hypothesis.reviewed_at = now

    experiment = None
    if request.decision == "reject":
        hypothesis.status = "rejected"
        hypothesis.hypothesis_metadata = {
            **dict(hypothesis.hypothesis_metadata or {}),
            "review_rationale": request.rationale,
        }
    elif request.convert_to_experiment:
        from ml.arena import get_champion_model

        champion = await get_champion_model(db, customer_id, hypothesis.model_name)
        package = await _get_context_package(db, customer_id, str(hypothesis.context_package_id)) if hypothesis.context_package_id else None
        baseline_version = (package.baseline_version if package else None) or (champion["version"] if champion else None)
        experiment = ModelExperiment(
            experiment_id=uuid.uuid4(),
            customer_id=customer_id,
            experiment_name=hypothesis.title,
            hypothesis=hypothesis.hypothesis,
            experiment_type=hypothesis.experiment_type,
            model_name=hypothesis.model_name,
            baseline_version=baseline_version,
            experiment_source=hypothesis.experiment_source,
            context_package_id=hypothesis.context_package_id,
            experiment_spec_id=hypothesis.experiment_spec_id,
            status="approved",
            proposed_by=hypothesis.generated_by,
            approved_by=actor,
            approved_at=now,
            decision_rationale=request.rationale or "Hypothesis approved and converted to experiment.",
            results={
                "lineage_metadata": {
                    "hypothesis_id": str(hypothesis.hypothesis_id),
                    "context_package_id": str(hypothesis.context_package_id) if hypothesis.context_package_id else None,
                    "experiment_spec_id": str(hypothesis.experiment_spec_id) if hypothesis.experiment_spec_id else None,
                    "experiment_source": hypothesis.experiment_source,
                    "domain_rationale": hypothesis.domain_rationale,
                    "expected_metric_movement": hypothesis.expected_metric_movement,
                    "risk_notes": hypothesis.risk_notes,
                    "metric_provenance": "benchmark",
                },
                "review": {
                    "reviewed_by": actor,
                    "reviewed_at": now.isoformat(),
                    "review_rationale": request.rationale,
                },
            },
            created_at=now,
        )
        db.add(experiment)
        await db.flush()
        hypothesis.experiment_id = experiment.experiment_id
        hypothesis.status = "converted"
    else:
        hypothesis.status = "approved"
        hypothesis.hypothesis_metadata = {
            **dict(hypothesis.hypothesis_metadata or {}),
            "review_rationale": request.rationale,
        }

    await db.commit()
    await db.refresh(hypothesis)
    if experiment:
        await db.refresh(experiment)

    logger.info(
        "experiment.hypothesis.reviewed",
        hypothesis_id=hypothesis_id,
        decision=request.decision,
        converted=bool(experiment),
        reviewed_by=actor,
    )
    return {
        "hypothesis": _serialize_hypothesis(hypothesis),
        "experiment": _serialize_experiment(experiment) if experiment else None,
    }


@router.post("/agent-traces")
async def create_agent_trace(
    request: CreateAgentTraceRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Persist an auditable trace for an AI-assisted experiment action."""
    customer_id = _resolve_customer_id(user)
    actor = _resolve_actor(user)
    package = await _get_context_package(db, customer_id, request.context_package_id)
    hypothesis = await _get_hypothesis(db, customer_id, request.hypothesis_id)
    experiment_uuid = _parse_uuid(request.experiment_id, "experiment_id") if request.experiment_id else None

    if hypothesis and package and hypothesis.context_package_id != package.context_package_id:
        raise HTTPException(status_code=400, detail="Hypothesis does not belong to the provided context package")
    if experiment_uuid:
        exp_result = await db.execute(
            select(ModelExperiment).where(
                ModelExperiment.experiment_id == experiment_uuid,
                ModelExperiment.customer_id == customer_id,
            )
        )
        if not exp_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Experiment not found")

    decision_actor = actor if request.human_decision != "pending" else None
    trace = ExperimentAgentTrace(
        trace_id=uuid.uuid4(),
        customer_id=customer_id,
        context_package_id=package.context_package_id if package else None,
        hypothesis_id=hypothesis.hypothesis_id if hypothesis else None,
        experiment_id=experiment_uuid,
        agent_name=request.agent_name,
        agent_model=request.agent_model,
        trace_type=request.trace_type,
        prompt_hash=request.prompt_hash,
        prompt_preview=request.prompt_preview,
        input_context=request.input_context,
        tool_allowlist=request.tool_allowlist,
        generated_output=request.generated_output,
        human_decision=request.human_decision,
        human_decision_by=decision_actor,
        human_decision_at=datetime.utcnow() if decision_actor else None,
        human_decision_rationale=request.human_decision_rationale,
        trace_metadata={
            **request.trace_metadata,
            "metric_provenance_required": True,
            "created_by": actor,
        },
        created_at=datetime.utcnow(),
    )
    db.add(trace)
    await db.commit()
    await db.refresh(trace)

    logger.info(
        "experiment.agent_trace.created",
        trace_id=str(trace.trace_id),
        trace_type=request.trace_type,
        human_decision=request.human_decision,
    )
    return _serialize_agent_trace(trace)


@router.get("/agent-traces")
async def list_agent_traces(
    context_package_id: str | None = None,
    hypothesis_id: str | None = None,
    experiment_id: str | None = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """List auditable agent traces with tenant-scoped filters."""
    customer_id = _resolve_customer_id(user)
    query = select(ExperimentAgentTrace).where(ExperimentAgentTrace.customer_id == customer_id)
    if context_package_id:
        query = query.where(ExperimentAgentTrace.context_package_id == _parse_uuid(context_package_id, "context_package_id"))
    if hypothesis_id:
        query = query.where(ExperimentAgentTrace.hypothesis_id == _parse_uuid(hypothesis_id, "hypothesis_id"))
    if experiment_id:
        query = query.where(ExperimentAgentTrace.experiment_id == _parse_uuid(experiment_id, "experiment_id"))
    query = query.order_by(ExperimentAgentTrace.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [_serialize_agent_trace(trace) for trace in result.scalars().all()]


@router.get("/comparison-report")
async def get_comparison_report(
    context_package_id: str | None = None,
    model_name: str = "demand_forecast",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Compare manual, AI-assisted, and agent-proposed experiment work."""
    customer_id = _resolve_customer_id(user)
    package = await _get_context_package(db, customer_id, context_package_id)
    package_uuid = package.context_package_id if package else None
    if package:
        model_name = package.model_name

    exp_query = select(ModelExperiment).where(
        ModelExperiment.customer_id == customer_id,
        ModelExperiment.model_name == model_name,
    )
    hyp_query = select(ExperimentHypothesis).where(
        ExperimentHypothesis.customer_id == customer_id,
        ExperimentHypothesis.model_name == model_name,
    )
    trace_query = select(ExperimentAgentTrace).where(ExperimentAgentTrace.customer_id == customer_id)
    if package_uuid:
        exp_query = exp_query.where(ModelExperiment.context_package_id == package_uuid)
        hyp_query = hyp_query.where(ExperimentHypothesis.context_package_id == package_uuid)
        trace_query = trace_query.where(ExperimentAgentTrace.context_package_id == package_uuid)

    exp_result = await db.execute(exp_query.order_by(ModelExperiment.created_at.desc()).limit(100))
    hyp_result = await db.execute(hyp_query.order_by(ExperimentHypothesis.created_at.desc()).limit(100))
    trace_result = await db.execute(trace_query.order_by(ExperimentAgentTrace.created_at.desc()).limit(100))
    experiments = exp_result.scalars().all()
    hypotheses = hyp_result.scalars().all()
    traces = trace_result.scalars().all()

    lanes: dict[str, dict[str, Any]] = {
        source: {
            "source": source,
            "hypotheses": 0,
            "experiments": 0,
            "agent_traces": 0,
            "status_counts": {},
            "latest_experiments": [],
        }
        for source in ("manual", "ai_assisted", "ai_agent")
    }
    for hypothesis in hypotheses:
        lane = lanes[hypothesis.experiment_source]
        lane["hypotheses"] += 1
        lane["status_counts"][hypothesis.status] = lane["status_counts"].get(hypothesis.status, 0) + 1
    for exp in experiments:
        lane = lanes[exp.experiment_source]
        lane["experiments"] += 1
        lane["status_counts"][exp.status] = lane["status_counts"].get(exp.status, 0) + 1
        if len(lane["latest_experiments"]) < 5:
            lane["latest_experiments"].append(_summarize_experiment_for_comparison(exp))

    trace_counts_by_source: dict[str, int] = {"manual": 0, "ai_assisted": 0, "ai_agent": 0}
    hypothesis_source = {hypothesis.hypothesis_id: hypothesis.experiment_source for hypothesis in hypotheses}
    experiment_source = {experiment.experiment_id: experiment.experiment_source for experiment in experiments}
    for trace in traces:
        source = None
        if trace.hypothesis_id in hypothesis_source:
            source = hypothesis_source[trace.hypothesis_id]
        elif trace.experiment_id in experiment_source:
            source = experiment_source[trace.experiment_id]
        source = source or "ai_agent"
        trace_counts_by_source[source] = trace_counts_by_source.get(source, 0) + 1
    for source, count in trace_counts_by_source.items():
        lanes[source]["agent_traces"] = count

    return {
        "model_name": model_name,
        "context_package_id": str(package_uuid) if package_uuid else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": {
            "provenance": "benchmark",
            "business_impact": "simulated benchmark replay only unless linked to measured pilot outcomes",
            "promotion": "human approval required; no autonomous production promotion from this report",
        },
        "summary": {
            "hypotheses": len(hypotheses),
            "experiments": len(experiments),
            "agent_traces": len(traces),
        },
        "lanes": list(lanes.values()),
        "context_package": _serialize_context_package(package) if package else None,
    }


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

    return _serialize_experiment(exp)


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
    package = await _get_context_package(db, customer_id, request.context_package_id)
    hypothesis = await _get_hypothesis(db, customer_id, request.hypothesis_id)
    if package and package.model_name != request.model_name:
        raise HTTPException(status_code=400, detail="Context package model_name does not match experiment model_name")
    if hypothesis:
        if hypothesis.model_name != request.model_name:
            raise HTTPException(status_code=400, detail="Hypothesis model_name does not match experiment model_name")
        if hypothesis.context_package_id and package and hypothesis.context_package_id != package.context_package_id:
            raise HTTPException(status_code=400, detail="Hypothesis does not belong to the provided context package")
    spec = await _resolve_or_create_experiment_spec(
        db,
        customer_id=customer_id,
        actor=actor,
        model_name=request.model_name,
        experiment_type=request.experiment_type,
        context_package=package,
        experiment_spec_id=request.experiment_spec_id or (str(hypothesis.experiment_spec_id) if hypothesis else None),
        spec_template_id=request.spec_template_id,
        spec_name=f"{request.experiment_name}_spec" if request.spec_template_id else None,
        spec_overrides=request.spec_overrides,
        metadata={"created_from": "experiment_proposal", "experiment_source": request.experiment_source},
    )

    # Get current champion version as baseline
    from ml.arena import get_champion_model

    champion = await get_champion_model(db, customer_id, request.model_name)
    baseline_version = (package.baseline_version if package else None) or (champion["version"] if champion else None)
    lineage_metadata = {
        **dict(request.lineage_metadata or {}),
        "context_package_id": str(package.context_package_id) if package else None,
        "hypothesis_id": str(hypothesis.hypothesis_id) if hypothesis else None,
        "experiment_spec_id": str(spec.experiment_spec_id) if spec else None,
        "experiment_spec_hash": spec.spec_hash if spec else None,
        "spec_template_id": spec.template_id if spec else request.spec_template_id,
        "experiment_source": request.experiment_source,
        "metric_provenance": (request.lineage_metadata or {}).get("metric_provenance", "benchmark"),
    }

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
        experiment_source=request.experiment_source,
        context_package_id=package.context_package_id if package else None,
        experiment_spec_id=spec.experiment_spec_id if spec else None,
        status="proposed",
        proposed_by=actor,
        results={"lineage_metadata": lineage_metadata},
        created_at=datetime.utcnow(),
    )

    db.add(experiment)
    if hypothesis:
        hypothesis.experiment_id = experiment_id
        if spec and not hypothesis.experiment_spec_id:
            hypothesis.experiment_spec_id = spec.experiment_spec_id
        hypothesis.status = "converted"
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
        "experiment_source": request.experiment_source,
        "context_package_id": str(package.context_package_id) if package else None,
        "experiment_spec_id": str(spec.experiment_spec_id) if spec else None,
        "experiment_spec_hash": spec.spec_hash if spec else None,
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
    exp.results = _normalize_experiment_results(
        {
            **existing_results,
            "lineage_metadata": lineage_metadata,
            **decision_payload,
            "decision_payload": decision_payload,
        }
    )
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
      3. Execute the M5-native decision-aware benchmark cycle
      4. Register the candidate in the arena for shadow review
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

    from ml.anomaly_benchmark import (
        DEFAULT_ANOMALY_DATA_DIR,
        AnomalyExperimentConfig,
        run_anomaly_detection_experiment,
    )
    from ml.arena import get_champion_model, register_model_version
    from ml.decision_experiment import DecisionExperimentConfig, run_decision_aware_experiment
    from ml.experiment_specs import anomaly_config_kwargs_from_spec, decision_config_kwargs_from_spec

    champion = await get_champion_model(db, customer_id, exp.model_name)
    fallback_version = "a1" if exp.model_name == "anomaly_detector" else "v3"
    baseline_version = exp.baseline_version or (champion["version"] if champion else fallback_version)
    if exp.baseline_version != baseline_version:
        exp.baseline_version = baseline_version
        await db.commit()

    candidate_version = f"e{experiment_uuid.hex[:10]}"
    _partition_manifest, output_json, output_md = _experiment_artifact_paths(experiment_uuid)

    package = await _get_context_package(db, customer_id, str(exp.context_package_id)) if exp.context_package_id else None
    if request.experiment_spec_id and exp.experiment_spec_id and str(exp.experiment_spec_id) != request.experiment_spec_id:
        raise HTTPException(status_code=400, detail="Run request experiment_spec_id does not match approved experiment")
    spec = await _resolve_or_create_experiment_spec(
        db,
        customer_id=customer_id,
        actor=actor,
        model_name=exp.model_name,
        experiment_type=exp.experiment_type,
        context_package=package,
        experiment_spec_id=request.experiment_spec_id or (str(exp.experiment_spec_id) if exp.experiment_spec_id else None),
        create_default=True,
        metadata={"created_from": "experiment_run_default", "experiment_id": str(exp.experiment_id)},
    )
    if spec is None:
        raise HTTPException(status_code=400, detail="Experiment run requires an executable experiment spec")
    if not exp.experiment_spec_id:
        exp.experiment_spec_id = spec.experiment_spec_id

    if exp.model_name == "anomaly_detector" and (
        request.validation_mode != "quick_screen" or request.rolling_window_count not in {None, 0}
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Anomaly detector experiments use the FreshRetailNet benchmark split. "
                "Temporal forecast validation modes are only supported for demand_forecast experiments."
            ),
        )

    exp.status = "in_progress"
    await db.commit()

    default_rolling_windows = {"quick_screen": 0, "extended_backtest": 3, "promotion_gate": 6}
    rolling_window_count = (
        request.rolling_window_count
        if request.rolling_window_count is not None
        else default_rolling_windows[request.validation_mode]
    )
    lineage_metadata = dict((exp.results or {}).get("lineage_metadata") or {})
    if exp.model_name == "anomaly_detector":
        spec_config_kwargs = anomaly_config_kwargs_from_spec(
            spec.spec,
            experiment_spec_id=str(spec.experiment_spec_id),
            experiment_spec_hash=spec.spec_hash,
        )
        config = AnomalyExperimentConfig(
            **{
                "baseline_version": baseline_version,
                "challenger_version": candidate_version,
                "model_name": exp.model_name,
                "experiment_name": exp.experiment_name,
                "hypothesis": exp.hypothesis,
                "experiment_type": exp.experiment_type,
                **spec_config_kwargs,
                "max_rows": request.max_rows,
            }
        )
        data_dir = DEFAULT_ANOMALY_DATA_DIR if request.data_dir == DEFAULT_FORECAST_DATA_DIR else request.data_dir
        report = run_anomaly_detection_experiment(
            data_dir=data_dir,
            output_json=output_json,
            output_md=output_md,
            config=config,
        )
        challenger_metrics = {
            **dict(report["challenger"]["holdout_metrics"]),
            **dict(report["challenger"]["lineage_metadata"]),
            "feature_tier": report["challenger"]["lineage_metadata"].get("feature_tier", "benchmark"),
            "tier": report["challenger"]["lineage_metadata"].get("feature_tier", "benchmark"),
            "estimated_business_basis": False,
            "business_basis_note": report.get("claim_boundary"),
            "segment_metrics": report["challenger"].get("segment_metrics"),
            "promotion_comparison": report.get("promotion_comparison"),
            "report_artifact": output_json,
        }
    else:
        spec_config_kwargs = decision_config_kwargs_from_spec(
            spec.spec,
            experiment_spec_id=str(spec.experiment_spec_id),
            experiment_spec_hash=spec.spec_hash,
        )
        config = DecisionExperimentConfig(
            **{
                "baseline_version": baseline_version,
                "challenger_version": candidate_version,
                "model_name": exp.model_name,
                "experiment_name": exp.experiment_name,
                "hypothesis": exp.hypothesis,
                "experiment_type": exp.experiment_type,
                **spec_config_kwargs,
                "validation_mode": request.validation_mode,
                "holdout_days": request.holdout_days,
                "calibration_days": request.calibration_days,
                "rolling_window_count": rolling_window_count,
                "rolling_window_days": request.rolling_window_days,
                "rolling_stride_days": request.rolling_stride_days,
                "max_rows": request.max_rows,
                "max_series": request.max_series,
            }
        )
        report = run_decision_aware_experiment(
            data_dir=request.data_dir,
            output_json=output_json,
            output_md=output_md,
            config=config,
        )
        challenger_metrics = {
            **dict(report["challenger"]["holdout_metrics"]),
            **dict(report["challenger"]["lineage_metadata"]),
            "feature_tier": report["challenger"]["lineage_metadata"].get("feature_tier", "cold_start"),
            "tier": report["challenger"]["lineage_metadata"].get("feature_tier", "cold_start"),
            "estimated_business_basis": True,
            "business_basis_note": report.get("claim_boundary"),
            "segment_metrics": report["challenger"].get("segment_metrics"),
            "decision_replay": report["decision_replay"]["results"].get("challenger"),
            "promotion_comparison": report.get("promotion_comparison"),
            "rolling_validation": report.get("rolling_validation"),
            "validation": report.get("validation"),
            "report_artifact": output_json,
        }

    await register_model_version(
        db=db,
        customer_id=customer_id,
        model_name=exp.model_name,
        version=candidate_version,
        metrics=challenger_metrics,
        status="challenger",
        smoke_test_passed=True,
    )
    comparison = dict(report["promotion_comparison"])

    if exp.model_name == "anomaly_detector":
        challenger_holdout = dict(report["challenger"]["holdout_metrics"])
        db.add(
            AnomalyDetectionRun(
                customer_id=customer_id,
                model_name=exp.model_name,
                model_version=candidate_version,
                run_type="shadow",
                dataset_id=challenger_metrics.get("dataset_id"),
                dataset_snapshot_id=challenger_metrics.get("dataset_snapshot_id"),
                threshold=challenger_holdout.get("threshold"),
                status="completed",
                rows_scored=int(challenger_holdout.get("rows") or 0),
                anomalies_detected=int(challenger_holdout.get("predicted_positive") or 0),
                precision=challenger_holdout.get("precision"),
                recall=challenger_holdout.get("recall"),
                f1=challenger_holdout.get("f1"),
                false_positive_rate=challenger_holdout.get("false_positive_rate"),
                review_rate=challenger_holdout.get("review_rate"),
                provenance=challenger_holdout.get("provenance") or "benchmark",
                completed_at=datetime.utcnow(),
                run_metadata={
                    "experiment_id": str(exp.experiment_id),
                    "experiment_spec_id": str(spec.experiment_spec_id),
                    "experiment_spec_hash": spec.spec_hash,
                    "spec_template_id": spec.template_id,
                    "feature_set_id": challenger_metrics.get("feature_set_id"),
                    "promotion_comparison": comparison,
                    "claim_boundary": report.get("claim_boundary"),
                },
            )
        )

    existing_results = _normalize_experiment_results(exp.results)
    run_lineage_metadata = {
        **lineage_metadata,
        **dict(report["challenger"]["lineage_metadata"]),
        "experiment_source": exp.experiment_source,
        "context_package_id": str(exp.context_package_id) if exp.context_package_id else None,
        "experiment_spec_id": str(spec.experiment_spec_id),
        "experiment_spec_hash": spec.spec_hash,
        "spec_template_id": spec.template_id,
        "metric_provenance": dict(report["challenger"]["lineage_metadata"]).get("provenance", "benchmark"),
    }
    existing_results["lineage_metadata"] = run_lineage_metadata
    existing_results["run_report"] = report
    existing_results["arena_breakdown"] = comparison
    existing_results["promotion_comparison"] = comparison
    existing_results["overall_business_safe"] = bool(report.get("overall_business_safe"))
    existing_results["execution"] = {
        "ran_by": actor,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_dir if exp.model_name == "anomaly_detector" else request.data_dir),
        "validation_mode": request.validation_mode,
        "holdout_days": request.holdout_days,
        "calibration_days": request.calibration_days,
        "rolling_window_count": rolling_window_count,
        "rolling_window_days": request.rolling_window_days,
        "rolling_stride_days": request.rolling_stride_days,
        "max_rows": request.max_rows,
        "max_series": request.max_series,
        "max_challengers": request.max_challengers,
        "experiment_source": exp.experiment_source,
        "context_package_id": str(exp.context_package_id) if exp.context_package_id else None,
        "experiment_spec_id": str(spec.experiment_spec_id),
        "experiment_spec_hash": spec.spec_hash,
        "spec_template_id": spec.template_id,
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
    has_forecast_results = any(
        results.get(key) is not None
        for key in ("baseline_mae", "baseline_wape", "baseline_mase", "experimental_mae", "experimental_wape", "experimental_mase")
    )
    has_anomaly_results = any(
        results.get(key) is not None
        for key in (
            "baseline_precision",
            "baseline_recall",
            "experimental_precision",
            "experimental_recall",
            "experimental_false_positive_rate",
            "experimental_review_rate",
        )
    )
    if not has_forecast_results and not has_anomaly_results:
        raise HTTPException(
            status_code=400, detail="Experiment results are incomplete — run or complete the evaluation first."
        )
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

    if exp.model_name == "anomaly_detector" or has_anomaly_results:
        prompt = f"""You are a senior ML engineer at a retail inventory intelligence platform.

Experiment: {exp.experiment_name}
Hypothesis: {exp.hypothesis}
Model: {exp.model_name}
Feature set: {lineage.get("feature_set_id", "N/A")}
Dataset: {lineage.get("dataset_id", "N/A")}

Baseline ({exp.baseline_version or "champion"}) stockout-anomaly metrics:
  precision={_fmt(results.get("baseline_precision"))}  recall={_fmt(results.get("baseline_recall"))}  f1={_fmt(results.get("baseline_f1"))}
  false_positive_rate={_fmt(results.get("baseline_false_positive_rate"))}  review_rate={_fmt(results.get("baseline_review_rate"))}

Challenger ({exp.experimental_version or "candidate"}) stockout-anomaly metrics:
  precision={_fmt(results.get("experimental_precision"))}  recall={_fmt(results.get("experimental_recall"))}  f1={_fmt(results.get("experimental_f1"))}
  false_positive_rate={_fmt(results.get("experimental_false_positive_rate"))}  review_rate={_fmt(results.get("experimental_review_rate"))}

Arena decision: {"PROMOTED" if results.get("overall_business_safe") else "SHADOW ONLY"}
Gates passed ({len(passed)}): {", ".join(passed) if passed else "none"}
Gates failed ({len(failed)}): {", ".join(failed) if failed else "none"}
Decision rationale: {exp.decision_rationale or promo.get("reason") or "N/A"}
Claim boundary: FreshRetailNet benchmark anomaly evidence only; real buyer or cycle-count outcomes are not available unless explicitly recorded.

Respond with exactly three sections separated by "---":
1. RESULTS SUMMARY (2-3 sentences): What the precision, recall, false-positive, and review-rate numbers show.
2. WHY IT WORKED (2-3 sentences): Mechanistic explanation using retail stockout/anomaly context, such as zero-sales gaps, promotion context, holiday/weather stress, and review workload.
3. NEXT HYPOTHESIS (1-2 sentences): The single most promising follow-up experiment to run next, stated as a testable hypothesis.

Be specific, use the actual metric values, and keep each section concise."""
    else:
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
        "experiment_source": exp.experiment_source,
        "context_package_id": str(exp.context_package_id) if exp.context_package_id else None,
        "baseline_version": exp.baseline_version,
        "experimental_version": exp.experimental_version,
        "results": _normalize_experiment_results(exp.results),
        "lineage_metadata": _normalize_experiment_results(exp.results).get("lineage_metadata"),
        "decision_rationale": exp.decision_rationale,
        "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
    }
