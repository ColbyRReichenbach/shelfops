"""add is_demo boolean to customers table

Revision ID: 010
Revises: 009
Create Date: 2026-03-19

Adds an is_demo boolean column to the customers table so demo tenants
(Summit Outdoor Supply, Favorita Grocery) can be distinguished from
production tenants.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("customers", "is_demo")
