"""
MLOps Infrastructure — Model versioning, backtesting, shadow mode, retraining log.

Revision ID: 004
Revises: 003
Create Date: 2026-02-12

Tables:
  - model_versions: Champion/challenger/shadow model tracking
  - backtest_results: Continuous backtesting results (walk-forward validation)
  - shadow_predictions: Shadow mode A/B comparison
  - model_retraining_log: Event-driven retraining audit trail
  - ml_alerts: In-app ML notifications
  - model_experiments: Human-led hypothesis testing
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── Model Versions (Champion/Challenger Registry) ─────────────────────
    op.create_table(
        "model_versions",
        sa.Column("model_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(50), nullable=False),  # 'demand_forecast', 'promo_lift', etc.
        sa.Column("version", sa.String(20), nullable=False),  # 'v1', 'v2', etc.
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="candidate",
        ),  # 'champion', 'challenger', 'shadow', 'archived'
        sa.Column("routing_weight", sa.Float, server_default="0.0"),  # For canary: 0.05 = 5% traffic
        sa.Column("promoted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metrics", postgresql.JSONB, nullable=True),  # {mae, mape, coverage}
        sa.Column("smoke_test_passed", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_model_versions_customer_status", "model_versions", ["customer_id", "model_name", "status"])
    op.create_index("idx_model_versions_customer_name_version", "model_versions", ["customer_id", "model_name", "version"], unique=True)

    # Enable RLS
    op.execute("ALTER TABLE model_versions ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON model_versions
        USING (customer_id = current_setting('app.current_customer_id', TRUE)::uuid)
        """
    )

    # ─── Backtest Results (Continuous Validation) ──────────────────────────
    op.create_table(
        "backtest_results",
        sa.Column("backtest_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("forecast_date", sa.Date, nullable=False),  # Date forecasted
        sa.Column("actual_date", sa.Date, nullable=False),  # When actual data arrived
        sa.Column("mae", sa.Float, nullable=True),
        sa.Column("mape", sa.Float, nullable=True),
        sa.Column("stockout_miss_rate", sa.Float, nullable=True),  # % of stockouts we failed to predict
        sa.Column("overstock_rate", sa.Float, nullable=True),  # % of forecasts that caused overordering
        sa.Column("evaluated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["model_versions.model_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_backtest_customer_model_date", "backtest_results", ["customer_id", "model_id", "forecast_date"])

    # Enable RLS
    op.execute("ALTER TABLE backtest_results ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON backtest_results
        USING (customer_id = current_setting('app.current_customer_id', TRUE)::uuid)
        """
    )

    # ─── Shadow Predictions (A/B Testing) ───────────────────────────────────
    op.create_table(
        "shadow_predictions",
        sa.Column("shadow_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("forecast_date", sa.Date, nullable=False),
        sa.Column("champion_prediction", sa.Float, nullable=False),
        sa.Column("challenger_prediction", sa.Float, nullable=False),
        sa.Column("actual_demand", sa.Float, nullable=True),  # Filled in T+1
        sa.Column("champion_error", sa.Float, nullable=True),  # |champion - actual|
        sa.Column("challenger_error", sa.Float, nullable=True),  # |challenger - actual|
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_shadow_predictions_customer_date", "shadow_predictions", ["customer_id", "forecast_date"]
    )

    # Enable RLS
    op.execute("ALTER TABLE shadow_predictions ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON shadow_predictions
        USING (customer_id = current_setting('app.current_customer_id', TRUE)::uuid)
        """
    )

    # ─── Model Retraining Log (Event Tracking) ──────────────────────────────
    op.create_table(
        "model_retraining_log",
        sa.Column("retrain_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(50), nullable=False),  # 'demand_forecast', 'promo_lift', etc.
        sa.Column(
            "trigger_type",
            sa.String(50),
            nullable=False,
        ),  # 'scheduled', 'drift', 'new_data', 'manual'
        sa.Column("trigger_metadata", postgresql.JSONB, nullable=True),  # {drift_pct: 0.18, new_products: 73}
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),  # 'running', 'completed', 'failed'
        sa.Column("version_produced", sa.String(20), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_model_retraining_log_customer_model", "model_retraining_log", ["customer_id", "model_name"]
    )

    # Enable RLS
    op.execute("ALTER TABLE model_retraining_log ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON model_retraining_log
        USING (customer_id = current_setting('app.current_customer_id', TRUE)::uuid)
        """
    )

    # ─── ML Alerts (In-App Notifications) ───────────────────────────────────
    op.create_table(
        "ml_alerts",
        sa.Column("ml_alert_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),  # 'drift_detected', 'promotion_pending', 'backtest_degradation', 'experiment_complete'
        sa.Column("severity", sa.String(20), nullable=False),  # 'info', 'warning', 'critical'
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("alert_metadata", postgresql.JSONB, nullable=True),  # {model_version, drift_pct, action_required}
        sa.Column("status", sa.String(20), nullable=False, server_default="unread"),  # 'unread', 'read', 'actioned', 'dismissed'
        sa.Column("action_url", sa.String(500), nullable=True),  # Link to review page
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("actioned_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_ml_alerts_customer_status", "ml_alerts", ["customer_id", "status", "created_at"])

    # Enable RLS
    op.execute("ALTER TABLE ml_alerts ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON ml_alerts
        USING (customer_id = current_setting('app.current_customer_id', TRUE)::uuid)
        """
    )

    # ─── Model Experiments (Human-Led Hypothesis Testing) ───────────────────
    op.create_table(
        "model_experiments",
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experiment_name", sa.String(255), nullable=False),
        sa.Column("hypothesis", sa.Text, nullable=False),  # "Department-tiered models will improve MAE by 10-15%"
        sa.Column("experiment_type", sa.String(50), nullable=False),  # 'feature_engineering', 'model_architecture', 'data_source', 'segmentation'
        sa.Column("model_name", sa.String(50), nullable=False),  # 'demand_forecast', 'promo_lift', etc.
        sa.Column("baseline_version", sa.String(20), nullable=True),  # Champion version at experiment start
        sa.Column("experimental_version", sa.String(20), nullable=True),  # Version produced by experiment
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),  # 'proposed', 'approved', 'in_progress', 'shadow_testing', 'completed', 'rejected', 'rolled_back'
        sa.Column("proposed_by", sa.String(255), nullable=False),  # User ID or email
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("results", postgresql.JSONB, nullable=True),  # {baseline_mae: 12.3, experimental_mae: 10.8, improvement_pct: 12.2, decision: 'promote'}
        sa.Column("decision_rationale", sa.Text, nullable=True),  # Why approved/rejected
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_model_experiments_customer", "model_experiments", ["customer_id", "status", "created_at"])

    # Enable RLS
    op.execute("ALTER TABLE model_experiments ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON model_experiments
        USING (customer_id = current_setting('app.current_customer_id', TRUE)::uuid)
        """
    )


def downgrade() -> None:
    op.drop_table("model_experiments")
    op.drop_table("ml_alerts")
    op.drop_table("model_retraining_log")
    op.drop_table("shadow_predictions")
    op.drop_table("backtest_results")
    op.drop_table("model_versions")
