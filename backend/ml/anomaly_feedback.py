from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Integer, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AnomalyDetectionRun, AnomalyShadowPrediction


async def summarize_anomaly_feedback(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
) -> dict[str, Any]:
    """Summarize persisted anomaly run, shadow, and review feedback evidence."""
    latest_run = (
        await db.execute(
            select(AnomalyDetectionRun)
            .where(
                AnomalyDetectionRun.customer_id == customer_id,
                AnomalyDetectionRun.model_name == "anomaly_detector",
            )
            .order_by(desc(AnomalyDetectionRun.completed_at), desc(AnomalyDetectionRun.started_at))
            .limit(1)
        )
    ).scalar_one_or_none()

    run_count = int(
        (
            await db.scalar(
                select(func.count(AnomalyDetectionRun.run_id)).where(
                    AnomalyDetectionRun.customer_id == customer_id,
                    AnomalyDetectionRun.model_name == "anomaly_detector",
                )
            )
        )
        or 0
    )

    shadow_row = (
        await db.execute(
            select(
                func.count(AnomalyShadowPrediction.prediction_id).label("total"),
                func.sum(func.cast(AnomalyShadowPrediction.champion_flag, type_=Integer)).label("champion_flags"),
                func.sum(func.cast(AnomalyShadowPrediction.challenger_flag, type_=Integer)).label("challenger_flags"),
                func.sum(
                    func.cast(
                        AnomalyShadowPrediction.champion_flag != AnomalyShadowPrediction.challenger_flag,
                        type_=Integer,
                    )
                ).label("disagreements"),
            ).where(AnomalyShadowPrediction.customer_id == customer_id)
        )
    ).one()

    outcome_row = (
        await db.execute(
            select(
                func.count(AnomalyShadowPrediction.prediction_id).label("recorded"),
                func.sum(
                    func.cast(AnomalyShadowPrediction.actual_outcome == "true_positive", type_=Integer)
                ).label("true_positive"),
                func.sum(
                    func.cast(AnomalyShadowPrediction.actual_outcome == "false_positive", type_=Integer)
                ).label("false_positive"),
            ).where(
                AnomalyShadowPrediction.customer_id == customer_id,
                AnomalyShadowPrediction.actual_outcome.isnot(None),
            )
        )
    ).one()

    shadow_total = int(shadow_row.total or 0)
    champion_flags = int(shadow_row.champion_flags or 0)
    challenger_flags = int(shadow_row.challenger_flags or 0)
    disagreements = int(shadow_row.disagreements or 0)
    outcomes_recorded = int(outcome_row.recorded or 0)
    true_positive = int(outcome_row.true_positive or 0)
    false_positive = int(outcome_row.false_positive or 0)
    measured_denominator = true_positive + false_positive
    measured_precision = true_positive / measured_denominator if measured_denominator else None

    latest_run_payload = None
    if latest_run is not None:
        latest_run_payload = {
            "run_id": str(latest_run.run_id),
            "model_version": latest_run.model_version,
            "run_type": latest_run.run_type,
            "dataset_id": latest_run.dataset_id,
            "dataset_snapshot_id": latest_run.dataset_snapshot_id,
            "threshold": latest_run.threshold,
            "status": latest_run.status,
            "rows_scored": latest_run.rows_scored,
            "anomalies_detected": latest_run.anomalies_detected,
            "precision": latest_run.precision,
            "recall": latest_run.recall,
            "f1": latest_run.f1,
            "false_positive_rate": latest_run.false_positive_rate,
            "review_rate": latest_run.review_rate,
            "provenance": latest_run.provenance,
            "started_at": _iso(latest_run.started_at),
            "completed_at": _iso(latest_run.completed_at),
        }

    return {
        "runs_total": run_count,
        "latest_run": latest_run_payload,
        "shadow_predictions": shadow_total,
        "champion_flags": champion_flags,
        "challenger_flags": challenger_flags,
        "disagreements": disagreements,
        "disagreement_rate": round(disagreements / shadow_total, 4) if shadow_total else None,
        "outcomes_recorded": outcomes_recorded,
        "true_positives": true_positive,
        "false_positives": false_positive,
        "measured_precision": round(measured_precision, 4) if measured_precision is not None else None,
        "feedback_provenance": "measured" if outcomes_recorded else "unavailable",
        "shadow_provenance": latest_run.provenance if latest_run is not None else "unavailable",
    }


async def record_shadow_prediction_outcome(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    prediction_id: uuid.UUID,
    outcome: str,
) -> bool:
    prediction = await db.get(AnomalyShadowPrediction, prediction_id)
    if prediction is None or prediction.customer_id != customer_id:
        return False
    prediction.actual_outcome = outcome
    prediction.outcome_recorded_at = datetime.utcnow()
    return True


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
