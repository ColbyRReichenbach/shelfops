"""add replenishment recommendations table

Revision ID: 012
Revises: 011
Create Date: 2026-04-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "replenishment_recommendations",
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.supplier_id"), nullable=True),
        sa.Column("linked_po_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_orders.po_id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("forecast_model_version", sa.String(length=50), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("recommended_quantity", sa.Integer(), nullable=False),
        sa.Column("quantity_available", sa.Integer(), nullable=False),
        sa.Column("quantity_on_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inventory_position", sa.Integer(), nullable=False),
        sa.Column("reorder_point", sa.Integer(), nullable=False),
        sa.Column("safety_stock", sa.Integer(), nullable=False),
        sa.Column("economic_order_qty", sa.Integer(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("service_level", sa.Float(), nullable=False),
        sa.Column("estimated_unit_cost", sa.Float(), nullable=True),
        sa.Column("estimated_total_cost", sa.Float(), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("interval_method", sa.String(length=50), nullable=True),
        sa.Column("calibration_status", sa.String(length=50), nullable=True),
        sa.Column("no_order_stockout_risk", sa.String(length=20), nullable=False),
        sa.Column("order_overstock_risk", sa.String(length=20), nullable=False),
        sa.Column(
            "recommendation_rationale",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'accepted', 'edited', 'rejected', 'expired')", name="ck_recommendation_status"
        ),
        sa.CheckConstraint("recommended_quantity >= 0", name="ck_recommendation_qty_non_negative"),
        sa.CheckConstraint("service_level >= 0 AND service_level <= 1", name="ck_recommendation_service_level_range"),
        sa.CheckConstraint(
            "no_order_stockout_risk IN ('low', 'medium', 'high')", name="ck_recommendation_stockout_risk"
        ),
        sa.CheckConstraint(
            "order_overstock_risk IN ('low', 'medium', 'high')", name="ck_recommendation_overstock_risk"
        ),
    )
    op.create_index(
        "ix_recommendations_customer_status",
        "replenishment_recommendations",
        ["customer_id", "status", "created_at"],
    )
    op.create_index(
        "ix_recommendations_store_product",
        "replenishment_recommendations",
        ["store_id", "product_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("replenishment_recommendations")
