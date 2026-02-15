"""Tenant ML readiness state transitions for cold-start and production-tier gating."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ForecastAccuracy, ModelVersion, TenantMLReadiness, TenantMLReadinessAudit


@dataclass(frozen=True)
class ReadinessThresholds:
    min_history_days: int
    min_store_count: int
    min_product_count: int
    min_accuracy_samples: int
    accuracy_window_days: int


def summarize_transactions(df: pd.DataFrame) -> dict[str, int]:
    if df.empty:
        return {"history_days": 0, "store_count": 0, "product_count": 0}
    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dates.empty:
        history_days = 0
    else:
        history_days = int((dates.max().normalize() - dates.min().normalize()).days + 1)
    return {
        "history_days": history_days,
        "store_count": int(df["store_id"].nunique()),
        "product_count": int(df["product_id"].nunique()),
    }


async def _accuracy_sample_count(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    model_version: str | None,
    window_days: int,
) -> int:
    if not model_version:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    result = await db.execute(
        select(func.count(ForecastAccuracy.id)).where(
            ForecastAccuracy.customer_id == customer_id,
            ForecastAccuracy.model_version == model_version,
            ForecastAccuracy.evaluated_at >= cutoff,
        )
    )
    return int(result.scalar() or 0)


async def _current_champion_version(db: AsyncSession, *, customer_id: uuid.UUID, model_name: str) -> str | None:
    result = await db.execute(
        select(ModelVersion.version)
        .where(
            ModelVersion.customer_id == customer_id,
            ModelVersion.model_name == model_name,
            ModelVersion.status == "champion",
        )
        .order_by(ModelVersion.promoted_at.desc())
        .limit(1)
    )
    row = result.one_or_none()
    return str(row.version) if row else None


def _state_and_reason(
    *,
    summary: dict[str, int],
    candidate_accuracy_samples: int,
    champion_accuracy_samples: int,
    champion_exists: bool,
    thresholds: ReadinessThresholds,
) -> tuple[str, str]:
    if summary["history_days"] < thresholds.min_history_days:
        return "cold_start", "insufficient_history_days"
    if summary["store_count"] < thresholds.min_store_count:
        return "cold_start", "insufficient_store_count"
    if summary["product_count"] < thresholds.min_product_count:
        return "cold_start", "insufficient_product_count"
    if candidate_accuracy_samples < thresholds.min_accuracy_samples:
        return "warming", "insufficient_candidate_accuracy_samples"
    if not champion_exists:
        return "production_tier_candidate", "candidate_ready_no_champion"
    if champion_accuracy_samples < thresholds.min_accuracy_samples:
        return "production_tier_candidate", "insufficient_champion_accuracy_samples"
    return "production_tier_active", "all_gates_passed"


async def evaluate_and_persist_tenant_readiness(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    transactions_df: pd.DataFrame,
    candidate_version: str | None,
    model_name: str,
    thresholds: ReadinessThresholds,
) -> dict[str, Any]:
    summary = summarize_transactions(transactions_df)
    champion_version = await _current_champion_version(db, customer_id=customer_id, model_name=model_name)
    candidate_samples = await _accuracy_sample_count(
        db,
        customer_id=customer_id,
        model_version=candidate_version,
        window_days=thresholds.accuracy_window_days,
    )
    champion_samples = await _accuracy_sample_count(
        db,
        customer_id=customer_id,
        model_version=champion_version,
        window_days=thresholds.accuracy_window_days,
    )
    champion_exists = champion_version is not None

    new_state, reason_code = _state_and_reason(
        summary=summary,
        candidate_accuracy_samples=candidate_samples,
        champion_accuracy_samples=champion_samples,
        champion_exists=champion_exists,
        thresholds=thresholds,
    )

    snapshot = {
        **summary,
        "candidate_version": candidate_version,
        "champion_version": champion_version,
        "candidate_accuracy_samples": candidate_samples,
        "champion_accuracy_samples": champion_samples,
        "thresholds": {
            "min_history_days": thresholds.min_history_days,
            "min_store_count": thresholds.min_store_count,
            "min_product_count": thresholds.min_product_count,
            "min_accuracy_samples": thresholds.min_accuracy_samples,
            "accuracy_window_days": thresholds.accuracy_window_days,
        },
    }

    current = await db.execute(
        select(TenantMLReadiness).where(TenantMLReadiness.customer_id == customer_id).limit(1)
    )
    current_row = current.scalar_one_or_none()
    previous_state = current_row.state if current_row else None

    now = datetime.utcnow()
    if current_row is None:
        current_row = TenantMLReadiness(
            customer_id=customer_id,
            state=new_state,
            reason_code=reason_code,
            gate_snapshot=snapshot,
            transitioned_at=now,
            updated_at=now,
        )
        db.add(current_row)
        transitioned = True
    else:
        transitioned = current_row.state != new_state
        current_row.state = new_state
        current_row.reason_code = reason_code
        current_row.gate_snapshot = snapshot
        current_row.updated_at = now
        if transitioned:
            current_row.transitioned_at = now

    if transitioned:
        db.add(
            TenantMLReadinessAudit(
                customer_id=customer_id,
                from_state=previous_state,
                to_state=new_state,
                reason_code=reason_code,
                gate_snapshot=snapshot,
                created_at=now,
            )
        )

    await db.flush()

    return {
        "state": new_state,
        "reason_code": reason_code,
        "transitioned": transitioned,
        "previous_state": previous_state,
        "snapshot": snapshot,
    }
