"""add anomaly feedback loop tables

Revision ID: 016
Revises: 015
Create Date: 2026-04-28

Persists anomaly scoring runs and champion/challenger shadow predictions so
benchmark evidence, shadow traffic, and later cycle-count outcomes have an
auditable home.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anomaly_detection_runs",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(length=50), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("run_type", sa.String(length=30), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=True),
        sa.Column("dataset_snapshot_id", sa.String(length=100), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rows_scored", sa.Integer(), nullable=False),
        sa.Column("anomalies_detected", sa.Integer(), nullable=False),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("recall", sa.Float(), nullable=True),
        sa.Column("f1", sa.Float(), nullable=True),
        sa.Column("false_positive_rate", sa.Float(), nullable=True),
        sa.Column("review_rate", sa.Float(), nullable=True),
        sa.Column("provenance", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("run_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "run_type IN ('scheduled', 'manual', 'benchmark_replay', 'shadow')",
            name="ck_anomaly_run_type",
        ),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_anomaly_run_status"),
        sa.CheckConstraint(
            "provenance IN ('measured', 'estimated', 'simulated', 'benchmark', 'provisional', 'unavailable')",
            name="ck_anomaly_run_provenance",
        ),
        sa.CheckConstraint("rows_scored >= 0", name="ck_anomaly_run_rows_nonnegative"),
        sa.CheckConstraint("anomalies_detected >= 0", name="ck_anomaly_run_detected_nonnegative"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_anomaly_runs_customer_model",
        "anomaly_detection_runs",
        ["customer_id", "model_name", "started_at"],
        unique=False,
    )

    op.create_table(
        "anomaly_shadow_predictions",
        sa.Column("prediction_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("detected_for_date", sa.Date(), nullable=False),
        sa.Column("champion_version", sa.String(length=50), nullable=False),
        sa.Column("challenger_version", sa.String(length=50), nullable=False),
        sa.Column("champion_score", sa.Float(), nullable=False),
        sa.Column("challenger_score", sa.Float(), nullable=False),
        sa.Column("champion_flag", sa.Boolean(), nullable=False),
        sa.Column("challenger_flag", sa.Boolean(), nullable=False),
        sa.Column("actual_outcome", sa.String(length=30), nullable=True),
        sa.Column("outcome_recorded_at", sa.DateTime(), nullable=True),
        sa.Column("prediction_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "actual_outcome IS NULL OR actual_outcome IN ('true_positive', 'false_positive', 'resolved', 'investigating')",
            name="ck_anomaly_shadow_outcome",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["anomaly_detection_runs.run_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.PrimaryKeyConstraint("prediction_id"),
    )
    op.create_index(
        "ix_anomaly_shadow_customer_date",
        "anomaly_shadow_predictions",
        ["customer_id", "detected_for_date"],
        unique=False,
    )
    op.create_index("ix_anomaly_shadow_run", "anomaly_shadow_predictions", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_anomaly_shadow_run", table_name="anomaly_shadow_predictions")
    op.drop_index("ix_anomaly_shadow_customer_date", table_name="anomaly_shadow_predictions")
    op.drop_table("anomaly_shadow_predictions")
    op.drop_index("ix_anomaly_runs_customer_model", table_name="anomaly_detection_runs")
    op.drop_table("anomaly_detection_runs")
