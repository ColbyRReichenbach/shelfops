"""add dataset snapshots table

Revision ID: 011
Revises: 010
Create Date: 2026-04-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_snapshots",
        sa.Column("snapshot_id", sa.String(length=32), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=True),
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("store_count", sa.Integer(), nullable=False),
        sa.Column("product_count", sa.Integer(), nullable=False),
        sa.Column("date_min", sa.Date(), nullable=True),
        sa.Column("date_max", sa.Date(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("frequency", sa.String(length=30), nullable=False),
        sa.Column("forecast_grain", sa.String(length=80), nullable=False),
        sa.Column("geography", sa.String(length=50), nullable=False),
        sa.Column("implementation_status", sa.String(length=50), nullable=False),
        sa.Column("claim_boundaries_ref", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dataset_snapshots_dataset_id", "dataset_snapshots", ["dataset_id"])
    op.create_index("ix_dataset_snapshots_hash", "dataset_snapshots", ["content_hash"], unique=True)
    op.create_index("ix_dataset_snapshots_customer", "dataset_snapshots", ["customer_id"])


def downgrade() -> None:
    op.drop_table("dataset_snapshots")
