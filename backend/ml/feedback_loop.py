"""
ML Feedback Loop — Transform PO decisions into features for demand forecasting.

When planners approve, reject, or edit suggested purchase orders, their
decisions are captured as reason codes in the po_decisions table. This module
converts those signals into ML features that improve future forecasts.

Key insight: If planners consistently reject forecasts for a product at a store,
the model should learn to adjust its predictions for that combination.

Features produced:
  - rejection_rate_30d: % of POs rejected for (store, product) in last 30 days
  - avg_qty_adjustment_pct: Avg % change when planners modify suggested qty
  - forecast_trust_score: 1.0 = always accept, 0.5 = half rejected, 0.0 = always reject

Agent: ml-engineer
Skill: ml-forecasting
"""

from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PODecision, PurchaseOrder


async def get_feedback_features(
    db: AsyncSession,
    customer_id: str,
    lookback_days: int = 30,
) -> pd.DataFrame:
    """
    Query po_decisions and aggregate into per-(store, product) features.

    Returns DataFrame with columns:
      store_id, product_id, rejection_rate_30d, avg_qty_adjustment_pct, forecast_trust_score
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    result = await db.execute(
        select(
            PurchaseOrder.store_id,
            PurchaseOrder.product_id,
            func.count(PODecision.decision_id).label("total_decisions"),
            func.count(case(
                (PODecision.decision_type == "rejected", 1),
            )).label("rejections"),
            func.avg(
                case(
                    (
                        PODecision.original_qty > 0,
                        (PODecision.final_qty - PODecision.original_qty)
                        * 100.0 / PODecision.original_qty,
                    ),
                    else_=0,
                )
            ).label("avg_qty_adjustment_pct"),
        )
        .join(PurchaseOrder, PODecision.po_id == PurchaseOrder.po_id)
        .where(
            PurchaseOrder.customer_id == customer_id,
            PODecision.decided_at >= cutoff,
        )
        .group_by(PurchaseOrder.store_id, PurchaseOrder.product_id)
    )
    rows = result.all()

    if not rows:
        return pd.DataFrame(columns=[
            "store_id", "product_id",
            "rejection_rate_30d", "avg_qty_adjustment_pct", "forecast_trust_score",
        ])

    records = []
    for row in rows:
        total = row.total_decisions or 1
        rejections = row.rejections or 0

        rejection_rate = rejections / total
        trust_score = 1.0 - rejection_rate  # Simple inverse

        records.append({
            "store_id": str(row.store_id),
            "product_id": str(row.product_id),
            "rejection_rate_30d": round(rejection_rate, 3),
            "avg_qty_adjustment_pct": round(float(row.avg_qty_adjustment_pct or 0), 1),
            "forecast_trust_score": round(trust_score, 3),
        })

    return pd.DataFrame(records)


def enrich_features_with_feedback(
    features_df: pd.DataFrame,
    feedback_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Left-join feedback features onto the main feature DataFrame.

    Products without PO history get neutral defaults:
      rejection_rate_30d = 0.0 (no rejections)
      avg_qty_adjustment_pct = 0.0 (no modifications)
      forecast_trust_score = 1.0 (full trust)
    """
    if feedback_df.empty:
        features_df["rejection_rate_30d"] = 0.0
        features_df["avg_qty_adjustment_pct"] = 0.0
        features_df["forecast_trust_score"] = 1.0
        return features_df

    merged = features_df.merge(
        feedback_df,
        on=["store_id", "product_id"],
        how="left",
    )

    # Fill missing with neutral defaults
    merged["rejection_rate_30d"] = merged["rejection_rate_30d"].fillna(0.0)
    merged["avg_qty_adjustment_pct"] = merged["avg_qty_adjustment_pct"].fillna(0.0)
    merged["forecast_trust_score"] = merged["forecast_trust_score"].fillna(1.0)

    return merged
