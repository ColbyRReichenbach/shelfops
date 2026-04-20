"""add webhook event log

Revision ID: 014
Revises: 013
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "webhook_event_log",
        sa.Column("webhook_event_id", _uuid_type(), nullable=False),
        sa.Column("customer_id", _uuid_type(), nullable=True),
        sa.Column("integration_id", _uuid_type(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("merchant_id", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.integration_id"]),
        sa.PrimaryKeyConstraint("webhook_event_id"),
        sa.CheckConstraint(
            "status IN ('received', 'processed', 'failed', 'replayed', 'dead_letter', 'invalid_signature')",
            name="ck_webhook_event_log_status",
        ),
        sa.CheckConstraint("delivery_attempts >= 0", name="ck_webhook_event_log_attempts_non_negative"),
    )
    op.create_index(
        "ix_webhook_event_log_provider_status",
        "webhook_event_log",
        ["provider", "status", "received_at"],
    )
    op.create_index(
        "ix_webhook_event_log_customer",
        "webhook_event_log",
        ["customer_id", "received_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_event_log_customer", table_name="webhook_event_log")
    op.drop_index("ix_webhook_event_log_provider_status", table_name="webhook_event_log")
    op.drop_table("webhook_event_log")
