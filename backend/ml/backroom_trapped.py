"""
Backroom Trapped Anomaly Detector.

Detects inventory that is in the store but not on the sales floor.
Conditions:
- quantity_on_hand > 0
- sales_trend_7d < -80% (sharp drop)
- High expected velocity or is_promo
"""

import uuid
from datetime import datetime
from typing import Any

import pandas as pd
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Anomaly
from ml.anomaly import build_anomaly_features

logger = structlog.get_logger()

async def detect_backroom_trapped(
    db: AsyncSession,
    customer_id: uuid.UUID,
    sales_drop_threshold: float = -80.0,
) -> dict[str, Any]:
    """
    Identify products likely trapped in the backroom.
    """
    logger.info("backroom_trapped.detect_start", customer_id=str(customer_id))
    
    # Use existing feature builder which gathers sales_trend_7d, quantity_on_hand, etc.
    features_df = await build_anomaly_features(db, customer_id)
    
    if features_df.empty:
        return {"trapped_detected": 0, "flagged_products": []}
        
    trapped_cases = []
    
    # Conditions:
    # 1. quantity_on_hand > 0
    # 2. sales_trend_7d <= -80%
    # 3. Was selling consistently before (sales_prev_7d > 5)
    
    mask = (
        (features_df["quantity_on_hand"] > 0) &
        (features_df["sales_trend_7d"] <= sales_drop_threshold) &
        (features_df["sales_prev_7d"] > 5)
    )
    
    flagged_df = features_df[mask]
    
    for _, row in flagged_df.iterrows():
        store_id = uuid.UUID(row["store_id"])
        product_id = uuid.UUID(row["product_id"])
        qty = row["quantity_on_hand"]
        drop = row["sales_trend_7d"]
        
        trapped_cases.append({
            "store_id": str(store_id),
            "product_id": str(product_id),
            "quantity_on_hand": qty,
            "sales_drop": drop,
            "category": row.get("category", "Unknown"),
            "velocity": row.get("sales_prev_7d", 0)
        })
        
        # Create Anomaly record
        anomaly = Anomaly(
            anomaly_id=uuid.uuid4(),
            customer_id=customer_id,
            store_id=store_id,
            product_id=product_id,
            anomaly_type="backroom_trapped",
            severity="high" if drop <= -90.0 else "medium",
            description=f"Possible backroom trapped inventory: {qty} units. Sales dropped by {abs(drop):.0f}%.",
            anomaly_metadata={
                "quantity_on_hand": float(qty),
                "sales_drop_pct": float(drop),
                "previous_7d_sales": float(row.get("sales_prev_7d", 0)),
                "suggested_action": "restock_shelf"
            },
            detected_at=datetime.utcnow()
        )
        db.add(anomaly)
        
    if trapped_cases:
        await db.commit()
        
    logger.info(
        "backroom_trapped.detect_complete",
        customer_id=str(customer_id),
        trapped_detected=len(trapped_cases)
    )
    
    return {
        "trapped_detected": len(trapped_cases),
        "flagged_products": trapped_cases
    }
