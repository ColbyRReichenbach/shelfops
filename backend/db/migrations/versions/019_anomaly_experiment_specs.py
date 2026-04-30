"""allow anomaly detector experiment specs

Revision ID: 019
Revises: 018
Create Date: 2026-04-29

Extends experiment_specs beyond demand_forecast so FreshRetailNet anomaly
detector experiments can use the same immutable spec and hash contract.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_experiment_spec_model_name", "experiment_specs", type_="check")
    op.drop_constraint("ck_experiment_spec_dataset_id", "experiment_specs", type_="check")
    op.create_check_constraint(
        "ck_experiment_spec_model_name",
        "experiment_specs",
        "model_name IN ('demand_forecast', 'anomaly_detector')",
    )
    op.create_check_constraint(
        "ck_experiment_spec_dataset_id",
        "experiment_specs",
        "dataset_id IN ('m5_walmart', 'freshretailnet_50k')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_experiment_spec_dataset_id", "experiment_specs", type_="check")
    op.drop_constraint("ck_experiment_spec_model_name", "experiment_specs", type_="check")
    op.create_check_constraint(
        "ck_experiment_spec_model_name",
        "experiment_specs",
        "model_name IN ('demand_forecast')",
    )
    op.create_check_constraint(
        "ck_experiment_spec_dataset_id",
        "experiment_specs",
        "dataset_id IN ('m5_walmart')",
    )
