"""
ML Enhancements — Store clustering, category-aware forecasts, integration sync log.

Revision ID: 006
Revises: 005
Create Date: 2026-02-14

Changes:
  - stores: Add cluster_tier column for K-Means store segmentation
  - demand_forecasts: Add category_tier column for category-specific models
  - integration_sync_log: Track data ingestion from POS/EDI/SFTP/Kafka sources
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── Store Clustering ──────────────────────────────────────────────────
    op.add_column(
        "stores",
        sa.Column("cluster_tier", sa.Integer(), server_default="1", nullable=True),
    )

    # ─── Category-Aware Forecasts ──────────────────────────────────────────
    op.add_column(
        "demand_forecasts",
        sa.Column("category_tier", sa.String(50), nullable=True),
    )

    # ─── Integration Sync Log ──────────────────────────────────────────────
    op.create_table(
        "integration_sync_log",
        sa.Column("sync_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.customer_id"),
            nullable=False,
        ),
        sa.Column("integration_type", sa.String(20), nullable=False),  # POS, EDI, SFTP, Kafka
        sa.Column("integration_name", sa.String(100), nullable=False),  # Square POS, EDI 846, etc.
        sa.Column("sync_type", sa.String(50), nullable=False),  # transactions, inventory, products
        sa.Column("records_synced", sa.Integer(), nullable=False),
        sa.Column(
            "sync_status",
            sa.String(20),
            nullable=False,
            server_default="success",
        ),  # success, failed, partial
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sync_metadata", postgresql.JSONB(), nullable=True),
    )

    op.create_index(
        "ix_sync_log_customer_type",
        "integration_sync_log",
        ["customer_id", "integration_type"],
    )
    op.create_index(
        "ix_sync_log_started_at",
        "integration_sync_log",
        ["started_at"],
    )

    # ─── RLS for integration_sync_log ──────────────────────────────────────
    op.execute("ALTER TABLE integration_sync_log ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY integration_sync_log_tenant_isolation ON integration_sync_log
        FOR ALL USING (customer_id = current_setting('app.current_customer_id')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS integration_sync_log_tenant_isolation ON integration_sync_log")
    op.drop_table("integration_sync_log")
    op.drop_column("demand_forecasts", "category_tier")
    op.drop_column("stores", "cluster_tier")
