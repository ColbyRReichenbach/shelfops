from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_tenant_db
from recommendations.schemas import RecommendationResponse
from recommendations.service import RecommendationService
from workers.monitoring import summarize_recommendation_impact

router = APIRouter(prefix="/api/v1/replenishment", tags=["replenishment"])


class RecommendationAcceptRequest(BaseModel):
    reason_code: str | None = None
    notes: str | None = None


class RecommendationEditRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    reason_code: str
    notes: str | None = None


class RecommendationRejectRequest(BaseModel):
    reason_code: str
    notes: str | None = None


class QueueGenerationRequest(BaseModel):
    horizon_days: int = Field(default=7, ge=1, le=30)
    model_version: str | None = None


class QueueGenerationResponse(BaseModel):
    as_of_date: str
    horizon_days: int
    model_version: str | None = None
    candidate_pairs: int
    generated_count: int
    skipped_count: int
    skipped_reasons: dict[str, int]
    open_queue_count: int


class ForecastCloseoutResponse(BaseModel):
    measurement_basis: str
    average_forecast_error_abs: float | None = None
    average_forecast_error_abs_confidence: str
    stockout_events: int
    stockout_events_confidence: str
    overstock_events: int
    overstock_events_confidence: str


class RecommendationPolicyResponse(BaseModel):
    measurement_basis: str
    decision_quantity_basis: str
    evaluated_decisions: int
    evaluated_decisions_confidence: str
    net_policy_value: float | None = None
    net_policy_value_confidence: str
    avoided_stockout_value: float | None = None
    avoided_stockout_value_confidence: str
    incremental_overstock_cost: float | None = None
    incremental_overstock_cost_confidence: str


class RecommendationImpactResponse(BaseModel):
    as_of_date: str
    total_recommendations: int
    accepted_count: int
    edited_count: int
    rejected_count: int
    closed_outcomes: int
    closed_outcomes_confidence: str
    provisional_outcomes: int
    provisional_outcomes_confidence: str
    forecast_closeout: ForecastCloseoutResponse
    recommendation_policy: RecommendationPolicyResponse


@router.get("/queue", response_model=list[RecommendationResponse])
async def list_replenishment_queue(
    status: str = Query("open"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    service = RecommendationService(db)
    return await service.list_queue(
        customer_id=UUID(str(user["customer_id"])),
        status=status,
        limit=limit,
    )


@router.post("/generate", response_model=QueueGenerationResponse)
async def generate_replenishment_queue(
    body: QueueGenerationRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    service = RecommendationService(db)
    return await service.generate_queue(
        customer_id=UUID(str(user["customer_id"])),
        horizon_days=body.horizon_days,
        model_version=body.model_version,
    )


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation_detail(
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    service = RecommendationService(db)
    try:
        return await service.get_recommendation(
            customer_id=UUID(str(user["customer_id"])),
            recommendation_id=recommendation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/recommendations/{recommendation_id}/accept", response_model=RecommendationResponse)
async def accept_recommendation(
    recommendation_id: UUID,
    body: RecommendationAcceptRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    service = RecommendationService(db)
    try:
        return await service.accept_recommendation(
            customer_id=UUID(str(user["customer_id"])),
            recommendation_id=recommendation_id,
            actor=user.get("email") or user.get("sub") or "unknown",
            reason_code=body.reason_code,
            notes=body.notes,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc


@router.get("/impact", response_model=RecommendationImpactResponse)
async def get_replenishment_impact(
    as_of_date: date | None = None,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    return await summarize_recommendation_impact(
        db,
        customer_id=UUID(str(user["customer_id"])),
        as_of_date=as_of_date,
    )


@router.post("/recommendations/{recommendation_id}/edit", response_model=RecommendationResponse)
async def edit_recommendation(
    recommendation_id: UUID,
    body: RecommendationEditRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    service = RecommendationService(db)
    try:
        return await service.edit_recommendation(
            customer_id=UUID(str(user["customer_id"])),
            recommendation_id=recommendation_id,
            quantity=body.quantity,
            actor=user.get("email") or user.get("sub") or "unknown",
            reason_code=body.reason_code,
            notes=body.notes,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc


@router.post("/recommendations/{recommendation_id}/reject", response_model=RecommendationResponse)
async def reject_recommendation(
    recommendation_id: UUID,
    body: RecommendationRejectRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    service = RecommendationService(db)
    try:
        return await service.reject_recommendation(
            customer_id=UUID(str(user["customer_id"])),
            recommendation_id=recommendation_id,
            actor=user.get("email") or user.get("sub") or "unknown",
            reason_code=body.reason_code,
            notes=body.notes,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc
