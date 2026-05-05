"""add csv to integrations provider constraint

Revision ID: 015
Revises: 014
Create Date: 2026-04-20

Allows CSV onboarding to register a first-class Integration row so product
surfaces can treat uploaded pilot data as an active source rather than a
sync-log-only side channel.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_PROVIDERS = (
    "'square', 'shopify', 'lightspeed', 'clover', "
    "'oracle_retail', 'sap', 'relex', 'manhattan', 'blue_yonder', "
    "'custom_edi', 'custom_sftp', 'kafka', 'pubsub'"
)

_NEW_PROVIDERS = (
    "'csv', 'square', 'shopify', 'lightspeed', 'clover', "
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
