"""
ML Feedback Loop — Transform buyer decisions into auditable model inputs.

When buyers accept, edit, or reject replenishment recommendations, ShelfOps logs
structured recommendation decisions. Purchase-order decisions remain supported
for older workflows, but recommendation decisions are the primary signal because
rejections do not create purchase orders.

Buyer choices are not demand labels by themselves. They are decision-policy
signals that can be joined with realized outcomes once the horizon closes.
Forecast features should use only lagged aggregates.

Features produced:
  - rejection_rate_30d: % of POs rejected for (store, product) in last 30 days
  - avg_qty_adjustment_pct: Avg % change when planners modify suggested qty
  - forecast_trust_score: 1.0 = always accept, 0.5 = half rejected, 0.0 = always reject

Agent: ml-engineer
Skill: ml-forecasting
"""

from datetime import datetime, timedelta
from uuid import UUID

import pandas as pd
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PODecision, PurchaseOrder, ReceivingDiscrepancy, RecommendationDecision, RecommendationOutcome


async def get_feedback_features(
    db: AsyncSession,
    customer_id: str | UUID,
    lookback_days: int = 30,
) -> pd.DataFrame:
    """
    Aggregate lagged buyer-decision feedback into per-(store, product) features.

    Recommendation decisions are primary. Legacy PO decisions are included so
    older PO-only workflows remain usable. Returned features are intentionally
    coarse; detailed outcome labels are built by
    build_recommendation_decision_dataset.

    Returns DataFrame with columns:
      store_id, product_id, rejection_rate_30d, avg_qty_adjustment_pct, forecast_trust_score
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    rows = await _load_decision_events(db, customer_id=customer_id, cutoff=cutoff)

    if not rows:
        return pd.DataFrame(
            columns=[
                "store_id",
                "product_id",
                "rejection_rate_30d",
                "avg_qty_adjustment_pct",
                "forecast_trust_score",
            ]
        )

    grouped: dict[tuple[str, str], list[dict]] = {}
    records = []
    for row in rows:
        grouped.setdefault((row["store_id"], row["product_id"]), []).append(row)

    for (store_id, product_id), events in grouped.items():
        total = len(events)
        rejections = sum(1 for event in events if event["decision_type"] == "rejected")
        adjustments = [event["override_pct"] for event in events if event["override_pct"] is not None]
        rejection_rate = rejections / max(total, 1)
        trust_score = 1.0 - rejection_rate

        records.append(
            {
                "store_id": store_id,
                "product_id": product_id,
                "rejection_rate_30d": round(rejection_rate, 3),
                "avg_qty_adjustment_pct": round(float(sum(adjustments) / len(adjustments)), 1)
                if adjustments
                else 0.0,
                "forecast_trust_score": round(trust_score, 3),
            }
        )

    return pd.DataFrame(records)


async def _load_decision_events(
    db: AsyncSession,
    *,
    customer_id: str | UUID,
    cutoff: datetime,
) -> list[dict]:
    recommendation_rows = await _load_recommendation_decision_events(
        db,
        customer_id=customer_id,
        cutoff=cutoff,
    )
    po_rows = await _load_po_decision_events(db, customer_id=customer_id, cutoff=cutoff)
    seen_recommendation_po_ids = {
        row["linked_po_id"]
        for row in recommendation_rows
        if row.get("linked_po_id") is not None
    }
    deduped_po_rows = [
        row
        for row in po_rows
        if row.get("linked_po_id") not in seen_recommendation_po_ids
    ]
    return recommendation_rows + deduped_po_rows


async def _load_recommendation_decision_events(
    db: AsyncSession,
    *,
    customer_id: str | UUID,
    cutoff: datetime,
) -> list[dict]:
    result = await db.execute(
        select(
            RecommendationDecision.store_id,
            RecommendationDecision.product_id,
            RecommendationDecision.linked_po_id,
            RecommendationDecision.decision_type,
            RecommendationDecision.recommended_qty,
            RecommendationDecision.final_qty,
            RecommendationDecision.override_pct,
        ).where(
            RecommendationDecision.customer_id == customer_id,
            RecommendationDecision.decided_at >= cutoff,
        )
    )
    return [
        {
            "store_id": str(row.store_id),
            "product_id": str(row.product_id),
            "linked_po_id": str(row.linked_po_id) if row.linked_po_id is not None else None,
            "decision_type": row.decision_type,
            "recommended_qty": int(row.recommended_qty or 0),
            "final_qty": int(row.final_qty or 0),
            "override_pct": float(row.override_pct) if row.override_pct is not None else None,
        }
        for row in result.all()
    ]


async def _load_po_decision_events(
    db: AsyncSession,
    *,
    customer_id: str | UUID,
    cutoff: datetime,
) -> list[dict]:
    result = await db.execute(
        select(
            PurchaseOrder.store_id,
            PurchaseOrder.product_id,
            PurchaseOrder.po_id,
            PODecision.decision_type,
            PODecision.original_qty,
            PODecision.final_qty,
        )
        .join(PurchaseOrder, PODecision.po_id == PurchaseOrder.po_id)
        .where(
            PurchaseOrder.customer_id == customer_id,
            PODecision.decided_at >= cutoff,
        )
    )
    rows = []
    for row in result.all():
        original_qty = int(row.original_qty or 0)
        final_qty = int(row.final_qty or 0)
        decision_type = {
            "approved": "accepted",
            "edited": "edited",
            "rejected": "rejected",
        }.get(row.decision_type, row.decision_type)
        rows.append(
            {
                "store_id": str(row.store_id),
                "product_id": str(row.product_id),
                "linked_po_id": str(row.po_id),
                "decision_type": decision_type,
                "recommended_qty": original_qty,
                "final_qty": final_qty,
                "override_pct": _compute_override_pct(original_qty, final_qty),
            }
        )
    return rows


def _compute_override_pct(recommended_qty: int, final_qty: int) -> float | None:
    if recommended_qty <= 0:
        return None
    return (final_qty - recommended_qty) * 100.0 / recommended_qty


async def build_recommendation_decision_dataset(
    db: AsyncSession,
    customer_id: str | UUID,
    lookback_days: int = 180,
    require_closed_outcome: bool = False,
) -> pd.DataFrame:
    """
    Build the auditable decision/outcome dataset for policy training or review.

    One row represents one buyer decision. Outcome columns are populated only
    after the recommendation horizon closes. This dataset is separate from
    demand forecast labels so buyer behavior does not become a proxy target for
    demand.
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    result = await db.execute(
        select(
            RecommendationDecision.decision_id,
            RecommendationDecision.recommendation_id,
            RecommendationDecision.customer_id,
            RecommendationDecision.store_id,
            RecommendationDecision.product_id,
            RecommendationDecision.linked_po_id,
            RecommendationDecision.decision_type,
            RecommendationDecision.recommended_qty,
            RecommendationDecision.final_qty,
            RecommendationDecision.override_qty_delta,
            RecommendationDecision.override_pct,
            RecommendationDecision.reason_code,
            RecommendationDecision.decided_at,
            RecommendationDecision.forecast_model_version,
            RecommendationDecision.policy_version,
            RecommendationOutcome.outcome_id,
            RecommendationOutcome.status.label("outcome_status"),
            RecommendationOutcome.actual_sales_qty,
            RecommendationOutcome.actual_demand_qty,
            RecommendationOutcome.stockout_event,
            RecommendationOutcome.overstock_event,
            RecommendationOutcome.forecast_error_abs,
            RecommendationOutcome.net_estimated_value,
            RecommendationOutcome.demand_confidence,
            RecommendationOutcome.value_confidence,
            RecommendationOutcome.computed_at,
        )
        .outerjoin(
            RecommendationOutcome,
            RecommendationOutcome.recommendation_id == RecommendationDecision.recommendation_id,
        )
        .where(
            RecommendationDecision.customer_id == customer_id,
            RecommendationDecision.decided_at >= cutoff,
        )
        .order_by(RecommendationDecision.decided_at.asc())
    )
    records = []
    for row in result.all():
        label_available = row.outcome_status == "closed"
        if require_closed_outcome and not label_available:
            continue
        records.append(
            {
                "decision_id": str(row.decision_id),
                "recommendation_id": str(row.recommendation_id),
                "customer_id": str(row.customer_id),
                "store_id": str(row.store_id),
                "product_id": str(row.product_id),
                "linked_po_id": str(row.linked_po_id) if row.linked_po_id is not None else None,
                "decision_type": row.decision_type,
                "recommended_qty": row.recommended_qty,
                "final_qty": row.final_qty,
                "override_qty_delta": row.override_qty_delta,
                "override_pct": row.override_pct,
                "reason_code": row.reason_code,
                "decided_at": row.decided_at.isoformat(),
                "forecast_model_version": row.forecast_model_version,
                "policy_version": row.policy_version,
                "outcome_id": str(row.outcome_id) if row.outcome_id is not None else None,
                "outcome_status": row.outcome_status,
                "label_available": label_available,
                "actual_sales_qty": row.actual_sales_qty,
                "actual_demand_qty": row.actual_demand_qty,
                "stockout_event": row.stockout_event,
                "overstock_event": row.overstock_event,
                "forecast_error_abs": row.forecast_error_abs,
                "net_estimated_value": row.net_estimated_value,
                "demand_confidence": row.demand_confidence,
                "value_confidence": row.value_confidence,
                "computed_at": row.computed_at.isoformat() if row.computed_at is not None else None,
            }
        )
    return pd.DataFrame(records)


async def get_receiving_discrepancy_features(
    db: AsyncSession,
    customer_id: str | UUID,
    lookback_days: int = 90,
) -> pd.DataFrame:
    """
    Query receiving_discrepancies and aggregate into per-(store, product) features.

    Returns DataFrame with columns:
      store_id, product_id, shortage_rate_90d, avg_receiving_discrepancy_pct, supply_reliability_score
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    result = await db.execute(
        select(
            PurchaseOrder.store_id,
            ReceivingDiscrepancy.product_id,
            func.count(ReceivingDiscrepancy.discrepancy_id).label("total_receipts"),
            func.count(
                case(
                    (ReceivingDiscrepancy.discrepancy_type == "shortage", 1),
                )
            ).label("shortage_count"),
            func.avg(
                case(
                    (
                        ReceivingDiscrepancy.ordered_qty > 0,
                        func.abs(ReceivingDiscrepancy.discrepancy_qty) * 100.0 / ReceivingDiscrepancy.ordered_qty,
                    ),
                    else_=0,
                )
            ).label("avg_discrepancy_pct"),
        )
        .join(PurchaseOrder, ReceivingDiscrepancy.po_id == PurchaseOrder.po_id)
        .where(
            PurchaseOrder.customer_id == customer_id,
            ReceivingDiscrepancy.reported_at >= cutoff,
        )
        .group_by(PurchaseOrder.store_id, ReceivingDiscrepancy.product_id)
    )
    rows = result.all()

    if not rows:
        return pd.DataFrame(
            columns=[
                "store_id",
                "product_id",
                "shortage_rate_90d",
                "avg_receiving_discrepancy_pct",
                "supply_reliability_score",
            ]
        )

    records = []
    for row in rows:
        total = row.total_receipts or 1
        shortages = row.shortage_count or 0

        shortage_rate = shortages / total
        reliability = 1.0 - shortage_rate

        records.append(
            {
                "store_id": str(row.store_id),
                "product_id": str(row.product_id),
                "shortage_rate_90d": round(shortage_rate, 3),
                "avg_receiving_discrepancy_pct": round(float(row.avg_discrepancy_pct or 0), 1),
                "supply_reliability_score": round(reliability, 3),
            }
        )

    return pd.DataFrame(records)


def enrich_features_with_feedback(
    features_df: pd.DataFrame,
    feedback_df: pd.DataFrame,
    receiving_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Left-join feedback and receiving discrepancy features onto the main feature DataFrame.

    Products without PO history get neutral defaults:
      rejection_rate_30d = 0.0 (no rejections)
      avg_qty_adjustment_pct = 0.0 (no modifications)
      forecast_trust_score = 1.0 (full trust)
      shortage_rate_90d = 0.0 (no shortages)
      avg_receiving_discrepancy_pct = 0.0 (no discrepancies)
      supply_reliability_score = 1.0 (fully reliable)
    """
    if feedback_df.empty:
        features_df["rejection_rate_30d"] = 0.0
        features_df["avg_qty_adjustment_pct"] = 0.0
        features_df["forecast_trust_score"] = 1.0
    else:
        features_df = features_df.merge(
            feedback_df,
            on=["store_id", "product_id"],
            how="left",
        )
        features_df["rejection_rate_30d"] = features_df["rejection_rate_30d"].fillna(0.0)
        features_df["avg_qty_adjustment_pct"] = features_df["avg_qty_adjustment_pct"].fillna(0.0)
        features_df["forecast_trust_score"] = features_df["forecast_trust_score"].fillna(1.0)

    if receiving_df is not None and not receiving_df.empty:
        features_df = features_df.merge(
            receiving_df,
            on=["store_id", "product_id"],
            how="left",
        )
        features_df["shortage_rate_90d"] = features_df["shortage_rate_90d"].fillna(0.0)
        features_df["avg_receiving_discrepancy_pct"] = features_df["avg_receiving_discrepancy_pct"].fillna(0.0)
        features_df["supply_reliability_score"] = features_df["supply_reliability_score"].fillna(1.0)
    else:
        features_df["shortage_rate_90d"] = 0.0
        features_df["avg_receiving_discrepancy_pct"] = 0.0
        features_df["supply_reliability_score"] = 1.0

    return features_df
