"""add recommendation outcomes

Revision ID: 013
Revises: 012
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True)


def _jsonb_type():
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "recommendation_outcomes",
        sa.Column("outcome_id", _uuid_type(), nullable=False),
        sa.Column("recommendation_id", _uuid_type(), nullable=False),
        sa.Column("customer_id", _uuid_type(), nullable=False),
        sa.Column("store_id", _uuid_type(), nullable=False),
        sa.Column("product_id", _uuid_type(), nullable=False),
        sa.Column("horizon_start_date", sa.Date(), nullable=False),
        sa.Column("horizon_end_date", sa.Date(), nullable=False),
        sa.Column("actual_sales_qty", sa.Float(), nullable=False),
        sa.Column("actual_demand_qty", sa.Float(), nullable=False),
        sa.Column("ending_inventory_qty", sa.Integer(), nullable=True),
        sa.Column("stockout_event", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("overstock_event", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("forecast_error_abs", sa.Float(), nullable=False),
        sa.Column("estimated_stockout_value", sa.Float(), nullable=True),
        sa.Column("estimated_overstock_cost", sa.Float(), nullable=True),
        sa.Column("net_estimated_value", sa.Float(), nullable=True),
        sa.Column("demand_confidence", sa.String(length=20), nullable=False),
        sa.Column("value_confidence", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["replenishment_recommendations.recommendation_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.PrimaryKeyConstraint("outcome_id"),
        sa.UniqueConstraint("recommendation_id"),
        sa.CheckConstraint("actual_sales_qty >= 0", name="ck_recommendation_outcome_sales_non_negative"),
        sa.CheckConstraint("actual_demand_qty >= 0", name="ck_recommendation_outcome_demand_non_negative"),
        sa.CheckConstraint("forecast_error_abs >= 0", name="ck_recommendation_outcome_error_non_negative"),
        sa.CheckConstraint(
            "demand_confidence IN ('measured', 'estimated', 'provisional', 'unavailable')",
            name="ck_recommendation_outcome_demand_confidence",
        ),
        sa.CheckConstraint(
            "value_confidence IN ('measured', 'estimated', 'provisional', 'unavailable')",
            name="ck_recommendation_outcome_value_confidence",
        ),
        sa.CheckConstraint("status IN ('closed', 'provisional')", name="ck_recommendation_outcome_status"),
    )
    op.create_index(
        "ix_recommendation_outcomes_customer",
        "recommendation_outcomes",
        ["customer_id", "computed_at"],
    )
    op.create_index(
        "ix_recommendation_outcomes_store_product",
        "recommendation_outcomes",
        ["store_id", "product_id", "computed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_recommendation_outcomes_store_product", table_name="recommendation_outcomes")
    op.drop_index("ix_recommendation_outcomes_customer", table_name="recommendation_outcomes")
    op.drop_table("recommendation_outcomes")
