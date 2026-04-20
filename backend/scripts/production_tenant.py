from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Action,
    Alert,
    Anomaly,
    BacktestResult,
    Customer,
    DemandForecast,
    ForecastAccuracy,
    Integration,
    IntegrationSyncLog,
    MLAlert,
    ModelExperiment,
    ModelRetrainingLog,
    ModelVersion,
    OpportunityCostLog,
    PODecision,
    Product,
    PromotionResult,
    PurchaseOrder,
    RecommendationOutcome,
    ReplenishmentRecommendation,
    ReceivingDiscrepancy,
    ReorderHistory,
    ReorderPoint,
    Store,
    Supplier,
    Transaction,
    InventoryLevel,
)

PRODUCTION_CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def ensure_production_tenant(db: AsyncSession, *, wipe_synthetic: bool = True) -> dict[str, Any]:
    """Ensure the production tenant exists and optionally wipe seeded data."""
    cid = PRODUCTION_CUSTOMER_ID
    wiped: dict[str, int] = {}

    if wipe_synthetic:
        for model_cls, label in [
            (OpportunityCostLog, "opportunity_cost_logs"),
            (BacktestResult, "backtest_results"),
            (ForecastAccuracy, "forecast_accuracy"),
            (DemandForecast, "demand_forecasts"),
            (RecommendationOutcome, "recommendation_outcomes"),
            (ReplenishmentRecommendation, "replenishment_recommendations"),
            (ModelExperiment, "model_experiments"),
            (ModelRetrainingLog, "model_retraining_logs"),
            (MLAlert, "ml_alerts"),
            (ModelVersion, "model_versions"),
            (IntegrationSyncLog, "integration_sync_logs"),
            (PODecision, "po_decisions"),
            (ReceivingDiscrepancy, "receiving_discrepancies"),
            (PurchaseOrder, "purchase_orders"),
            (Action, "actions"),
            (Alert, "alerts"),
            (Anomaly, "anomalies"),
            (PromotionResult, "promotion_results"),
            (ReorderHistory, "reorder_history"),
            (Transaction, "transactions"),
            (ReorderPoint, "reorder_points"),
            (InventoryLevel, "inventory_levels"),
            (Integration, "integrations"),
            (Product, "products"),
            (Store, "stores"),
            (Supplier, "suppliers"),
        ]:
            result = await db.execute(delete(model_cls).where(model_cls.customer_id == cid))
            wiped[label] = result.rowcount  # type: ignore[union-attr]

    customer = await db.get(Customer, cid)
    if customer is None:
        customer = Customer(
            customer_id=cid,
            name="Production Pilot",
            email="admin@shelfops.io",
            plan="enterprise",
            status="active",
            is_demo=False,
        )
        db.add(customer)
        await db.flush()
    else:
        customer.name = "Production Pilot"
        customer.is_demo = False
        customer.status = "active"

    return {"customer_id": str(cid), "name": customer.name, "wiped": wiped}
