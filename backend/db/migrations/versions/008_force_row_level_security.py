"""Force RLS on tenant-scoped tables to prevent owner-bypass in production.

Revision ID: 008
Revises: 007
Create Date: 2026-02-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = [
    "stores",
    "products",
    "suppliers",
    "transactions",
    "inventory_levels",
    "demand_forecasts",
    "forecast_accuracy",
    "reorder_points",
    "alerts",
    "actions",
    "purchase_orders",
    "promotions",
    "integrations",
    "anomalies",
    "edi_transaction_log",
    "distribution_centers",
    "product_sourcing_rules",
    "dc_inventory",
    "store_transfers",
    "shrinkage_rates",
    "planograms",
    "promotion_results",
    "receiving_discrepancies",
    "reorder_history",
    "po_decisions",
    "opportunity_cost_log",
    "model_versions",
    "backtest_results",
    "shadow_predictions",
    "model_retraining_log",
    "tenant_ml_readiness",
    "tenant_ml_readiness_audit",
    "ml_alerts",
    "model_experiments",
    "integration_sync_log",
]


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
