"""Add RLS policies to commercial readiness tables

The 11 tables from migration 002 have customer_id columns but were
missing tenant_isolation RLS policies (migration 001 only covered
the original 14 tables).

Revision ID: 003
Revises: 002
Create Date: 2026-02-12
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COMMERCIAL_TABLES = [
    "distribution_centers",
    "product_sourcing_rules",
    "dc_inventory",
    "store_transfers",
    "shrinkage_rates",
    "planograms",
    "promotion_results",
    "receiving_discrepancies",
    "reorder_history",
    "po_decisions",
    "opportunity_cost_log",
]


def upgrade() -> None:
    for table in COMMERCIAL_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (customer_id::text = current_setting('app.current_customer_id', true))"
        )


def downgrade() -> None:
    for table in COMMERCIAL_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
