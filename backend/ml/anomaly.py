"""
Anomaly Detection — ML-powered outlier detection using Isolation Forest.

Detects:
  - Demand spikes/drops (sales anomalies)
  - Inventory discrepancies (stock anomalies)
  - Price anomalies
  - Seasonal pattern violations

Uses:
  - Isolation Forest (sklearn) with contamination=0.05 (5% outliers expected)
  - SHAP for explainability ("Anomalous because sales_7d is 3.2σ above normal")
  - Z-score severity classification (warning: 2-3σ, critical: >3σ)
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Anomaly, InventoryLevel, Product, Store, Transaction

logger = structlog.get_logger()


# ── Feature Engineering ─────────────────────────────────────────────────────


async def build_anomaly_features(
    db: AsyncSession,
    customer_id: uuid.UUID,
    lookback_days: int = 30,
) -> pd.DataFrame:
    """
    Build feature matrix for anomaly detection.

    Features (per product-store):
      - sales_7d: Total sales last 7 days
      - sales_trend_7d: % change from previous 7-day window
      - quantity_on_hand: Current inventory level
      - price: Current product price
      - day_of_week: 0-6 (Monday=0)
      - is_holiday: Boolean (from RetailCalendar)
      - stock_turnover: sales_7d / quantity_on_hand (velocity metric)
      - price_vs_avg: % deviation from category average
    """
    from retail.calendar import RetailCalendar

    calendar = RetailCalendar()
    now = datetime.utcnow()
    today = now.date()
    is_holiday = calendar.is_holiday(today)

    # Get recent transactions (last 30 days)
    cutoff = now - timedelta(days=lookback_days)
    txn_result = await db.execute(
        select(
            Transaction.store_id,
            Transaction.product_id,
            Transaction.quantity,
            Transaction.timestamp,
        ).where(
            Transaction.customer_id == customer_id,
            Transaction.timestamp >= cutoff,
        )
    )
    transactions = txn_result.all()

    # Get current inventory
    inv_result = await db.execute(
        select(
            InventoryLevel.store_id,
            InventoryLevel.product_id,
            InventoryLevel.quantity_on_hand,
            InventoryLevel.timestamp,
        ).where(InventoryLevel.customer_id == customer_id)
    )
    inventory = {(row.store_id, row.product_id): row.quantity_on_hand for row in inv_result.all()}

    # Get products (for price, category)
    prod_result = await db.execute(
        select(Product.product_id, Product.unit_price, Product.category).where(Product.customer_id == customer_id)
    )
    products = {row.product_id: {"unit_price": row.unit_price, "category": row.category} for row in prod_result.all()}

    # Build DataFrame
    if not transactions:
        logger.warning("anomaly.no_transactions", customer_id=str(customer_id))
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            {
                "store_id": str(txn.store_id),
                "product_id": str(txn.product_id),
                "quantity": txn.quantity,
                "date": txn.timestamp,
            }
            for txn in transactions
        ]
    )

    # Calculate sales_7d (last 7 days)
    recent_cutoff = now - timedelta(days=7)
    df_7d = df[df["date"] >= recent_cutoff]
    sales_7d = df_7d.groupby(["store_id", "product_id"])["quantity"].sum().reset_index()
    sales_7d.rename(columns={"quantity": "sales_7d"}, inplace=True)

    # Calculate sales_prev_7d (days 8-14 ago)
    prev_start = now - timedelta(days=14)
    prev_end = recent_cutoff
    df_prev = df[(df["date"] >= prev_start) & (df["date"] < prev_end)]
    sales_prev = df_prev.groupby(["store_id", "product_id"])["quantity"].sum().reset_index()
    sales_prev.rename(columns={"quantity": "sales_prev_7d"}, inplace=True)

    # Merge
    features_df = sales_7d.merge(sales_prev, on=["store_id", "product_id"], how="left")
    features_df["sales_prev_7d"] = features_df["sales_prev_7d"].fillna(0)

    # Calculate trend
    features_df["sales_trend_7d"] = (
        (features_df["sales_7d"] - features_df["sales_prev_7d"]) / (features_df["sales_prev_7d"] + 1)
    ) * 100

    # Add current stock
    features_df["quantity_on_hand"] = features_df.apply(
        lambda row: inventory.get((uuid.UUID(row["store_id"]), uuid.UUID(row["product_id"])), 0),
        axis=1,
    )

    # Add product features
    features_df["unit_price"] = features_df["product_id"].apply(
        lambda pid: products.get(uuid.UUID(pid), {}).get("unit_price", 0)
    )
    features_df["category"] = features_df["product_id"].apply(
        lambda pid: products.get(uuid.UUID(pid), {}).get("category", "Unknown")
    )

    # Add temporal features
    features_df["day_of_week"] = today.weekday()
    features_df["is_holiday"] = int(is_holiday)

    # Calculate stock turnover (velocity)
    features_df["stock_turnover"] = features_df["sales_7d"] / (features_df["quantity_on_hand"] + 1)

    # Calculate price vs category average
    category_avg_price = features_df.groupby("category")["unit_price"].mean().to_dict()
    features_df["price_vs_avg"] = features_df.apply(
        lambda row: (
            (row["unit_price"] - category_avg_price.get(row["category"], row["unit_price"]))
            / (category_avg_price.get(row["category"], row["unit_price"]) + 1)
        )
        * 100,
        axis=1,
    )

    return features_df


# ── Anomaly Detection ───────────────────────────────────────────────────────


async def detect_anomalies_ml(
    db: AsyncSession,
    customer_id: uuid.UUID,
    contamination: float = 0.05,
    severity_threshold: float = 2.0,
) -> dict[str, Any]:
    """
    Detect anomalies using Isolation Forest.

    Args:
        db: Database session
        customer_id: Customer UUID
        contamination: Expected % of outliers (default 5%)
        severity_threshold: Z-score threshold for severity (2σ=warning, 3σ=critical)

    Returns:
        {
            "anomalies_detected": 12,
            "critical_count": 3,
            "warning_count": 9,
            "top_anomalies": [...],
        }
    """
    from ml.experiment import ExperimentTracker

    logger.info("anomaly.detect_start", customer_id=str(customer_id))

    # Build feature matrix
    features_df = await build_anomaly_features(db, customer_id)

    if features_df.empty:
        logger.warning("anomaly.no_data", customer_id=str(customer_id))
        return {
            "anomalies_detected": 0,
            "critical_count": 0,
            "warning_count": 0,
            "top_anomalies": [],
        }

    # Select numerical features for Isolation Forest
    feature_cols = [
        "sales_7d",
        "sales_trend_7d",
        "quantity_on_hand",
        "unit_price",
        "day_of_week",
        "is_holiday",
        "stock_turnover",
        "price_vs_avg",
    ]

    X = features_df[feature_cols].fillna(0)

    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train Isolation Forest with MLflow tracking
    with ExperimentTracker(model_name="anomaly_detector") as tracker:
        tracker.log_params(
            {
                "contamination": contamination,
                "n_estimators": 100,
                "n_features": len(feature_cols),
                "n_samples": len(X),
                "severity_threshold": severity_threshold,
                "customer_id": str(customer_id),
            }
        )
        tracker.log_tags(
            {
                "model_type": "isolation_forest",
                "trigger": "scheduled",
            }
        )

        iso_forest = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100,
        )
        predictions = iso_forest.fit_predict(X_scaled)
        anomaly_scores = iso_forest.score_samples(X_scaled)

        # Log detection metrics
        n_anomalies = int((predictions == -1).sum())
        tracker.log_metrics(
            {
                "n_anomalies": n_anomalies,
                "anomaly_rate": round(n_anomalies / len(predictions), 4) if len(predictions) > 0 else 0,
                "mean_score": float(anomaly_scores.mean()),
                "min_score": float(anomaly_scores.min()),
            }
        )

        # Log severity distribution after anomalies are classified
        tracker.log_model(iso_forest, "isolation_forest")

    # Add predictions to DataFrame
    features_df["is_anomaly"] = predictions == -1
    features_df["anomaly_score"] = anomaly_scores

    # Calculate z-scores for severity
    mean_score = anomaly_scores.mean()
    std_score = anomaly_scores.std()
    features_df["z_score"] = (anomaly_scores - mean_score) / (std_score + 1e-8)

    # Filter anomalies
    anomalies_df = features_df[features_df["is_anomaly"]].copy()

    if anomalies_df.empty:
        logger.info("anomaly.none_detected", customer_id=str(customer_id))
        return {
            "anomalies_detected": 0,
            "critical_count": 0,
            "warning_count": 0,
            "top_anomalies": [],
        }

    # Classify severity
    anomalies_df["severity"] = anomalies_df["z_score"].apply(
        lambda z: "critical" if abs(z) > 3.0 else "warning" if abs(z) > 2.0 else "info"
    )

    # Generate explanations (simplified SHAP-like logic)
    anomalies_df["description"] = anomalies_df.apply(_explain_anomaly, axis=1)

    # Store anomalies in database
    critical_count = 0
    warning_count = 0

    for _, row in anomalies_df.iterrows():
        anomaly = Anomaly(
            anomaly_id=uuid.uuid4(),
            customer_id=customer_id,
            store_id=uuid.UUID(row["store_id"]),
            product_id=uuid.UUID(row["product_id"]),
            anomaly_type="ml_detected",
            severity=row["severity"],
            description=row["description"],
            anomaly_metadata={
                "sales_7d": float(row["sales_7d"]),
                "sales_trend_7d": float(row["sales_trend_7d"]),
                "quantity_on_hand": float(row["quantity_on_hand"]),
                "unit_price": float(row["unit_price"]),
                "z_score": float(row["z_score"]),
                "anomaly_score": float(row["anomaly_score"]),
            },
            detected_at=datetime.utcnow(),
        )
        db.add(anomaly)

        if row["severity"] == "critical":
            critical_count += 1
        elif row["severity"] == "warning":
            warning_count += 1

    await db.commit()

    logger.info(
        "anomaly.detect_complete",
        customer_id=str(customer_id),
        anomalies_detected=len(anomalies_df),
        critical=critical_count,
        warning=warning_count,
    )

    # Return top anomalies (sorted by severity)
    top_anomalies = (
        anomalies_df.sort_values("z_score", ascending=False)
        .head(10)[["store_id", "product_id", "severity", "description", "z_score"]]
        .to_dict("records")
    )

    return {
        "anomalies_detected": len(anomalies_df),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "top_anomalies": top_anomalies,
    }


def _explain_anomaly(row: pd.Series) -> str:
    """
    Generate human-readable explanation for anomaly.

    Simplified SHAP-like logic: identify feature with largest deviation.
    """
    reasons = []

    # Sales spike/drop
    if abs(row["sales_trend_7d"]) > 50:
        if row["sales_trend_7d"] > 0:
            reasons.append(f"Sales spiked {row['sales_trend_7d']:.0f}% vs last week")
        else:
            reasons.append(f"Sales dropped {abs(row['sales_trend_7d']):.0f}% vs last week")

    # Stock anomaly
    if row["quantity_on_hand"] > row["sales_7d"] * 10:
        reasons.append(
            f"Overstock detected ({row['quantity_on_hand']:.0f} units vs {row['sales_7d']:.0f} weekly sales)"
        )
    elif row["quantity_on_hand"] < row["sales_7d"] * 0.5:
        reasons.append(f"Low stock ({row['quantity_on_hand']:.0f} units vs {row['sales_7d']:.0f} weekly sales)")

    # Price anomaly
    if abs(row["price_vs_avg"]) > 30:
        if row["price_vs_avg"] > 0:
            reasons.append(f"Price {row['price_vs_avg']:.0f}% above category average")
        else:
            reasons.append(f"Price {abs(row['price_vs_avg']):.0f}% below category average")

    # Velocity anomaly
    if row["stock_turnover"] > 5:
        reasons.append(f"High velocity ({row['stock_turnover']:.1f}x turnover)")
    elif row["stock_turnover"] < 0.1 and row["quantity_on_hand"] > 0:
        reasons.append(f"Slow-moving ({row['stock_turnover']:.2f}x turnover)")

    if not reasons:
        reasons.append(f"Anomaly detected (z-score: {row['z_score']:.2f})")

    return " | ".join(reasons)
