"""add structured recommendation decisions

Revision ID: 020
Revises: 019
Create Date: 2026-05-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True)


def _jsonb_type():
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "recommendation_decisions",
        sa.Column("decision_id", _uuid_type(), nullable=False),
        sa.Column("customer_id", _uuid_type(), nullable=False),
        sa.Column("recommendation_id", _uuid_type(), nullable=False),
        sa.Column("store_id", _uuid_type(), nullable=False),
        sa.Column("product_id", _uuid_type(), nullable=False),
        sa.Column("linked_po_id", _uuid_type(), nullable=True),
        sa.Column("decision_type", sa.String(length=20), nullable=False),
        sa.Column("recommended_qty", sa.Integer(), nullable=False),
        sa.Column("final_qty", sa.Integer(), nullable=False),
        sa.Column("override_qty_delta", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("override_pct", sa.Float(), nullable=True),
        sa.Column("reason_code", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.Column("forecast_model_version", sa.String(length=50), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("decision_metadata", _jsonb_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(
            "decision_type IN ('accepted', 'edited', 'rejected')",
            name="ck_recommendation_decision_type",
        ),
        sa.CheckConstraint(
            "recommended_qty >= 0",
            name="ck_recommendation_decision_recommended_qty_non_negative",
        ),
        sa.CheckConstraint("final_qty >= 0", name="ck_recommendation_decision_final_qty_non_negative"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["linked_po_id"], ["purchase_orders.po_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["replenishment_recommendations.recommendation_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint("recommendation_id"),
    )
    op.create_index(
        "ix_recommendation_decisions_customer",
        "recommendation_decisions",
        ["customer_id", "decided_at"],
    )
    op.create_index(
        "ix_recommendation_decisions_store_product",
        "recommendation_decisions",
        ["store_id", "product_id", "decided_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_recommendation_decisions_store_product", table_name="recommendation_decisions")
    op.drop_index("ix_recommendation_decisions_customer", table_name="recommendation_decisions")
    op.drop_table("recommendation_decisions")
