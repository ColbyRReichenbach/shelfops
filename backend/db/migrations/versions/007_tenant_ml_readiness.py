"""
Tenant ML readiness state machine tables.

Revision ID: 007
Revises: 006
Create Date: 2026-02-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_ml_readiness",
        sa.Column("readiness_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.customer_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("state", sa.String(length=40), nullable=False, server_default="cold_start"),
        sa.Column("reason_code", sa.String(length=100), nullable=False, server_default="insufficient_history"),
        sa.Column("gate_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "state IN ('cold_start', 'warming', 'production_tier_candidate', 'production_tier_active')",
            name="ck_tenant_ml_readiness_state",
        ),
    )
    op.create_index(
        "ix_tenant_ml_readiness_customer_state",
        "tenant_ml_readiness",
        ["customer_id", "state"],
    )

    op.create_table(
        "tenant_ml_readiness_audit",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.customer_id"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(length=40), nullable=True),
        sa.Column("to_state", sa.String(length=40), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("gate_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "to_state IN ('cold_start', 'warming', 'production_tier_candidate', 'production_tier_active')",
            name="ck_tenant_ml_readiness_audit_to_state",
        ),
    )
    op.create_index(
        "ix_tenant_ml_readiness_audit_customer",
        "tenant_ml_readiness_audit",
        ["customer_id", "created_at"],
    )

    op.execute("ALTER TABLE tenant_ml_readiness ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_ml_readiness_audit ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_ml_readiness_tenant_isolation ON tenant_ml_readiness
        FOR ALL USING (customer_id = current_setting('app.current_customer_id')::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_ml_readiness_audit_tenant_isolation ON tenant_ml_readiness_audit
        FOR ALL USING (customer_id = current_setting('app.current_customer_id')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_ml_readiness_audit_tenant_isolation ON tenant_ml_readiness_audit")
    op.execute("DROP POLICY IF EXISTS tenant_ml_readiness_tenant_isolation ON tenant_ml_readiness")
    op.drop_index("ix_tenant_ml_readiness_audit_customer", table_name="tenant_ml_readiness_audit")
    op.drop_table("tenant_ml_readiness_audit")
    op.drop_index("ix_tenant_ml_readiness_customer_state", table_name="tenant_ml_readiness")
    op.drop_table("tenant_ml_readiness")
