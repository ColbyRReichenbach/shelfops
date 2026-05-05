"""add executable experiment specs

Revision ID: 018
Revises: 017
Create Date: 2026-04-29

Persists immutable experiment recipes so UI-selected feature, tuning,
calibration, and decision-policy changes are executable inputs rather than
free-form lineage notes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiment_specs",
        sa.Column("experiment_spec_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("context_package_id", sa.UUID(), nullable=True),
        sa.Column("model_name", sa.String(length=50), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("template_id", sa.String(length=100), nullable=False),
        sa.Column("spec_name", sa.String(length=255), nullable=False),
        sa.Column("spec_version", sa.String(length=40), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column("spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("spec_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("model_name IN ('demand_forecast')", name="ck_experiment_spec_model_name"),
        sa.CheckConstraint("dataset_id IN ('m5_walmart')", name="ck_experiment_spec_dataset_id"),
        sa.ForeignKeyConstraint(["context_package_id"], ["experiment_context_packages.context_package_id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.PrimaryKeyConstraint("experiment_spec_id"),
    )
    op.create_index(
        "ix_experiment_specs_customer_model",
        "experiment_specs",
        ["customer_id", "model_name", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_experiment_specs_context",
        "experiment_specs",
        ["context_package_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_experiment_specs_hash",
        "experiment_specs",
        ["customer_id", "spec_hash"],
        unique=False,
    )

    op.add_column("experiment_hypotheses", sa.Column("experiment_spec_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_experiment_hypotheses_experiment_spec_id",
        "experiment_hypotheses",
        "experiment_specs",
        ["experiment_spec_id"],
        ["experiment_spec_id"],
    )
    op.create_index(
        "ix_experiment_hypotheses_spec",
        "experiment_hypotheses",
        ["experiment_spec_id", "status"],
        unique=False,
    )

    op.add_column("model_experiments", sa.Column("experiment_spec_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_model_experiments_experiment_spec_id",
        "model_experiments",
        "experiment_specs",
        ["experiment_spec_id"],
        ["experiment_spec_id"],
    )
    op.create_index(
        "ix_model_experiments_spec",
        "model_experiments",
        ["experiment_spec_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_model_experiments_spec", table_name="model_experiments")
    op.drop_constraint("fk_model_experiments_experiment_spec_id", "model_experiments", type_="foreignkey")
    op.drop_column("model_experiments", "experiment_spec_id")

    op.drop_index("ix_experiment_hypotheses_spec", table_name="experiment_hypotheses")
    op.drop_constraint(
        "fk_experiment_hypotheses_experiment_spec_id",
        "experiment_hypotheses",
        type_="foreignkey",
    )
    op.drop_column("experiment_hypotheses", "experiment_spec_id")

    op.drop_index("ix_experiment_specs_hash", table_name="experiment_specs")
    op.drop_index("ix_experiment_specs_context", table_name="experiment_specs")
    op.drop_index("ix_experiment_specs_customer_model", table_name="experiment_specs")
    op.drop_table("experiment_specs")
