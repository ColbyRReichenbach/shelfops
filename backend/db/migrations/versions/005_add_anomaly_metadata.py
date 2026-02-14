"""Add anomaly_metadata JSONB column

Revision ID: 005
Revises: 004
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add anomaly_metadata JSONB column to anomalies table
    op.add_column(
        'anomalies',
        sa.Column('anomaly_metadata', postgresql.JSONB, nullable=True)
    )

    # Update check constraints to include new types and severities
    op.drop_constraint('ck_anomaly_type', 'anomalies')
    op.drop_constraint('ck_anomaly_severity', 'anomalies')

    op.create_check_constraint(
        'ck_anomaly_type',
        'anomalies',
        "anomaly_type IN ('demand_spike', 'demand_drop', 'inventory_discrepancy', 'price_anomaly', 'data_quality', 'ml_detected')"
    )

    op.create_check_constraint(
        'ck_anomaly_severity',
        'anomalies',
        "severity IN ('low', 'medium', 'high', 'critical', 'info', 'warning')"
    )


def downgrade() -> None:
    # Restore original constraints
    op.drop_constraint('ck_anomaly_type', 'anomalies')
    op.drop_constraint('ck_anomaly_severity', 'anomalies')

    op.create_check_constraint(
        'ck_anomaly_type',
        'anomalies',
        "anomaly_type IN ('demand_spike', 'demand_drop', 'inventory_discrepancy', 'price_anomaly', 'data_quality')"
    )

    op.create_check_constraint(
        'ck_anomaly_severity',
        'anomalies',
        "severity IN ('low', 'medium', 'high', 'critical')"
    )

    # Remove anomaly_metadata column
    op.drop_column('anomalies', 'anomaly_metadata')
