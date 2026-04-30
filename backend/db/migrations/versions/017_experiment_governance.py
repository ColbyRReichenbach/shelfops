"""add experiment governance tables

Revision ID: 017
Revises: 016
Create Date: 2026-04-29

Persists context packages, hypothesis backlog entries, and agent traces so
manual and AI-assisted DS experiment work can be compared with shared inputs,
explicit provenance, and human review.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiment_context_packages",
        sa.Column("context_package_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("package_name", sa.String(length=255), nullable=False),
        sa.Column("model_name", sa.String(length=50), nullable=False),
        sa.Column("baseline_version", sa.String(length=50), nullable=True),
        sa.Column("dataset_id", sa.String(length=100), nullable=True),
        sa.Column("dataset_snapshot_id", sa.String(length=100), nullable=True),
        sa.Column("package_type", sa.String(length=30), nullable=False),
        sa.Column("artifact_uri", sa.String(length=500), nullable=True),
        sa.Column("context_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allowed_experiment_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "package_type IN ('manual_vs_ai', 'manual', 'ai_agent', 'benchmark')",
            name="ck_experiment_context_package_type",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.PrimaryKeyConstraint("context_package_id"),
    )
    op.create_index(
        "ix_experiment_context_customer_model",
        "experiment_context_packages",
        ["customer_id", "model_name", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_experiment_context_customer_created",
        "experiment_context_packages",
        ["customer_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "experiment_hypotheses",
        sa.Column("hypothesis_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("context_package_id", sa.UUID(), nullable=True),
        sa.Column("experiment_id", sa.UUID(), nullable=True),
        sa.Column("model_name", sa.String(length=50), nullable=False),
        sa.Column("experiment_source", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("experiment_type", sa.String(length=50), nullable=False),
        sa.Column("domain_rationale", sa.Text(), nullable=True),
        sa.Column("expected_metric_movement", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("generated_by", sa.String(length=255), nullable=False),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("hypothesis_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "experiment_source IN ('manual', 'ai_assisted', 'ai_agent')",
            name="ck_experiment_hypothesis_source",
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'converted', 'archived')",
            name="ck_experiment_hypothesis_status",
        ),
        sa.ForeignKeyConstraint(["context_package_id"], ["experiment_context_packages.context_package_id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.PrimaryKeyConstraint("hypothesis_id"),
    )
    op.create_index(
        "ix_experiment_hypotheses_customer_model",
        "experiment_hypotheses",
        ["customer_id", "model_name", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_experiment_hypotheses_context",
        "experiment_hypotheses",
        ["context_package_id", "status"],
        unique=False,
    )

    op.create_table(
        "experiment_agent_traces",
        sa.Column("trace_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("context_package_id", sa.UUID(), nullable=True),
        sa.Column("hypothesis_id", sa.UUID(), nullable=True),
        sa.Column("experiment_id", sa.UUID(), nullable=True),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("agent_model", sa.String(length=100), nullable=True),
        sa.Column("trace_type", sa.String(length=30), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("prompt_preview", sa.Text(), nullable=True),
        sa.Column("input_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tool_allowlist", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("human_decision", sa.String(length=30), nullable=False),
        sa.Column("human_decision_by", sa.String(length=255), nullable=True),
        sa.Column("human_decision_at", sa.DateTime(), nullable=True),
        sa.Column("human_decision_rationale", sa.Text(), nullable=True),
        sa.Column("trace_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "trace_type IN ('hypothesis_generation', 'experiment_plan', 'interpretation', 'execution_review')",
            name="ck_experiment_agent_trace_type",
        ),
        sa.CheckConstraint(
            "human_decision IN ('pending', 'approved', 'rejected', 'edited', 'not_required')",
            name="ck_experiment_agent_trace_human_decision",
        ),
        sa.ForeignKeyConstraint(["context_package_id"], ["experiment_context_packages.context_package_id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["experiment_hypotheses.hypothesis_id"]),
        sa.PrimaryKeyConstraint("trace_id"),
    )
    op.create_index(
        "ix_experiment_agent_traces_customer",
        "experiment_agent_traces",
        ["customer_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_experiment_agent_traces_context",
        "experiment_agent_traces",
        ["context_package_id", "trace_type"],
        unique=False,
    )
    op.create_index(
        "ix_experiment_agent_traces_hypothesis",
        "experiment_agent_traces",
        ["hypothesis_id", "trace_type"],
        unique=False,
    )

    op.add_column(
        "model_experiments",
        sa.Column("experiment_source", sa.String(length=20), nullable=False, server_default="manual"),
    )
    op.add_column("model_experiments", sa.Column("context_package_id", sa.UUID(), nullable=True))
    op.create_check_constraint(
        "ck_model_experiments_source",
        "model_experiments",
        "experiment_source IN ('manual', 'ai_assisted', 'ai_agent')",
    )
    op.create_foreign_key(
        "fk_model_experiments_context_package_id",
        "model_experiments",
        "experiment_context_packages",
        ["context_package_id"],
        ["context_package_id"],
    )
    op.create_index(
        "ix_model_experiments_context",
        "model_experiments",
        ["context_package_id", "experiment_source"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_experiment_hypotheses_experiment_id",
        "experiment_hypotheses",
        "model_experiments",
        ["experiment_id"],
        ["experiment_id"],
    )
    op.create_foreign_key(
        "fk_experiment_agent_traces_experiment_id",
        "experiment_agent_traces",
        "model_experiments",
        ["experiment_id"],
        ["experiment_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_experiment_agent_traces_experiment_id", "experiment_agent_traces", type_="foreignkey")
    op.drop_constraint("fk_experiment_hypotheses_experiment_id", "experiment_hypotheses", type_="foreignkey")
    op.drop_index("ix_model_experiments_context", table_name="model_experiments")
    op.drop_constraint("fk_model_experiments_context_package_id", "model_experiments", type_="foreignkey")
    op.drop_constraint("ck_model_experiments_source", "model_experiments", type_="check")
    op.drop_column("model_experiments", "context_package_id")
    op.drop_column("model_experiments", "experiment_source")

    op.drop_index("ix_experiment_agent_traces_hypothesis", table_name="experiment_agent_traces")
    op.drop_index("ix_experiment_agent_traces_context", table_name="experiment_agent_traces")
    op.drop_index("ix_experiment_agent_traces_customer", table_name="experiment_agent_traces")
    op.drop_table("experiment_agent_traces")

    op.drop_index("ix_experiment_hypotheses_context", table_name="experiment_hypotheses")
    op.drop_index("ix_experiment_hypotheses_customer_model", table_name="experiment_hypotheses")
    op.drop_table("experiment_hypotheses")

    op.drop_index("ix_experiment_context_customer_created", table_name="experiment_context_packages")
    op.drop_index("ix_experiment_context_customer_model", table_name="experiment_context_packages")
    op.drop_table("experiment_context_packages")
