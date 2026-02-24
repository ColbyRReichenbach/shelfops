"""add kafka and pubsub to integrations provider constraint

Revision ID: 009
Revises: 008
Create Date: 2026-02-24

Adds 'kafka' and 'pubsub' to the ck_integration_provider CHECK constraint on
the integrations table so that tenants using Kafka or Google Pub/Sub for real-
time event streaming can register a connected Integration row without a DB
constraint violation.

No column changes — purely a constraint update.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers
revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_PROVIDERS = (
    "'square', 'shopify', 'lightspeed', 'clover', "
    "'oracle_retail', 'sap', 'relex', 'manhattan', 'blue_yonder', "
    "'custom_edi', 'custom_sftp'"
)

_NEW_PROVIDERS = (
    "'square', 'shopify', 'lightspeed', 'clover', "
    "'oracle_retail', 'sap', 'relex', 'manhattan', 'blue_yonder', "
    "'custom_edi', 'custom_sftp', 'kafka', 'pubsub'"
)


def upgrade() -> None:
    op.drop_constraint("ck_integration_provider", "integrations", type_="check")
    op.create_check_constraint(
        "ck_integration_provider",
        "integrations",
        f"provider IN ({_NEW_PROVIDERS})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_integration_provider", "integrations", type_="check")
    op.create_check_constraint(
        "ck_integration_provider",
        "integrations",
        f"provider IN ({_OLD_PROVIDERS})",
    )
