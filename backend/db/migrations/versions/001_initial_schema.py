"""
Initial schema - all 15 tables

Revision ID: 001
Revises: None
Create Date: 2026-02-09
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # 1. Customers
    op.create_table(
        "customers",
        sa.Column("customer_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), nullable=False, server_default="starter"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("plan IN ('starter', 'professional', 'enterprise')", name="ck_customer_plan"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'trial', 'churned')", name="ck_customer_status"),
    )

    # 2. Stores
    op.create_table(
        "stores",
        sa.Column("store_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(2)),
        sa.Column("zip_code", sa.String(10)),
        sa.Column("lat", sa.Float),
        sa.Column("lon", sa.Float),
        sa.Column("timezone", sa.String(50), server_default="America/New_York"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'inactive', 'onboarding')", name="ck_store_status"),
    )
    op.create_index("ix_stores_customer", "stores", ["customer_id"])

    # 3. Suppliers
    op.create_table(
        "suppliers",
        sa.Column("supplier_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("lead_time_days", sa.Integer, nullable=False, server_default="7"),
        sa.Column("min_order_quantity", sa.Integer, server_default="1"),
        sa.Column("reliability_score", sa.Float, server_default="0.95"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("lead_time_days > 0", name="ck_supplier_lead_time_positive"),
        sa.CheckConstraint("reliability_score >= 0 AND reliability_score <= 1", name="ck_supplier_reliability_range"),
    )
    op.create_index("ix_suppliers_customer", "suppliers", ["customer_id"])

    # 4. Products
    op.create_table(
        "products",
        sa.Column("product_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("gtin", sa.String(14)),
        sa.Column("upc", sa.String(12)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("subcategory", sa.String(100)),
        sa.Column("brand", sa.String(100)),
        sa.Column("unit_cost", sa.Float),
        sa.Column("unit_price", sa.Float),
        sa.Column("weight", sa.Float),
        sa.Column("shelf_life_days", sa.Integer),
        sa.Column("is_seasonal", sa.Boolean, server_default="false"),
        sa.Column("is_perishable", sa.Boolean, server_default="false"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.supplier_id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("customer_id", "sku", name="uq_product_sku_per_customer"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_product_cost_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_product_price_positive"),
    )
    op.create_index("ix_products_customer", "products", ["customer_id"])
    op.create_index("ix_products_category", "products", ["customer_id", "category"])

    # 5. Transactions (will become hypertable)
    op.create_table(
        "transactions",
        sa.Column("transaction_id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price", sa.Float, nullable=False),
        sa.Column("total_amount", sa.Float, nullable=False),
        sa.Column("discount_amount", sa.Float, server_default="0"),
        sa.Column("transaction_type", sa.String(20), nullable=False, server_default="sale"),
        sa.Column("external_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("transaction_id", "timestamp"),
        sa.CheckConstraint("quantity != 0", name="ck_transaction_quantity_nonzero"),
        sa.CheckConstraint("transaction_type IN ('sale', 'return', 'void', 'adjustment')", name="ck_transaction_type"),
    )
    op.create_index("ix_transactions_store", "transactions", ["store_id"])
    op.create_index("ix_transactions_product", "transactions", ["product_id"])
    op.create_index("ix_transactions_customer_time", "transactions", ["customer_id", "timestamp"])
    op.create_index("ix_transactions_store_product_time", "transactions", ["store_id", "product_id", "timestamp"])

    # Convert to TimescaleDB hypertable
    op.execute("SELECT create_hypertable('transactions', 'timestamp', migrate_data => true)")
    op.execute("SELECT add_retention_policy('transactions', INTERVAL '2 years')")

    # 6. Inventory Levels (will become hypertable)
    op.create_table(
        "inventory_levels",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("quantity_on_hand", sa.Integer, nullable=False),
        sa.Column("quantity_on_order", sa.Integer, server_default="0"),
        sa.Column("quantity_reserved", sa.Integer, server_default="0"),
        sa.Column("quantity_available", sa.Integer, nullable=False),
        sa.Column("source", sa.String(50), server_default="pos_sync"),
        sa.PrimaryKeyConstraint("id", "timestamp"),
        sa.CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_qty_positive"),
    )
    op.create_index("ix_inventory_store_product", "inventory_levels", ["store_id", "product_id", "timestamp"])
    op.create_index("ix_inventory_customer_time", "inventory_levels", ["customer_id", "timestamp"])

    op.execute("SELECT create_hypertable('inventory_levels', 'timestamp', migrate_data => true)")

    # 7. Demand Forecasts
    op.create_table(
        "demand_forecasts",
        sa.Column("forecast_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("forecast_date", sa.Date, nullable=False),
        sa.Column("forecasted_demand", sa.Float, nullable=False),
        sa.Column("lower_bound", sa.Float),
        sa.Column("upper_bound", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "product_id", "forecast_date", "model_version", name="uq_forecast_unique"),
        sa.CheckConstraint("forecasted_demand >= 0", name="ck_forecast_demand_positive"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_forecast_confidence_range"),
    )
    op.create_index("ix_forecast_store_product_date", "demand_forecasts", ["store_id", "product_id", "forecast_date"])

    # 8. Forecast Accuracy
    op.create_table(
        "forecast_accuracy",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("forecast_date", sa.Date, nullable=False),
        sa.Column("forecasted_demand", sa.Float, nullable=False),
        sa.Column("actual_demand", sa.Float, nullable=False),
        sa.Column("mae", sa.Float),
        sa.Column("mape", sa.Float),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("evaluated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_accuracy_store_product", "forecast_accuracy", ["store_id", "product_id"])
    op.create_index("ix_accuracy_model_version", "forecast_accuracy", ["model_version"])

    # 9. Reorder Points
    op.create_table(
        "reorder_points",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("reorder_point", sa.Integer, nullable=False),
        sa.Column("safety_stock", sa.Integer, nullable=False),
        sa.Column("economic_order_qty", sa.Integer, nullable=False),
        sa.Column("lead_time_days", sa.Integer, nullable=False),
        sa.Column("service_level", sa.Float, nullable=False, server_default="0.95"),
        sa.Column("last_calculated", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "product_id", name="uq_reorder_store_product"),
        sa.CheckConstraint("reorder_point >= 0", name="ck_reorder_point_positive"),
        sa.CheckConstraint("safety_stock >= 0", name="ck_safety_stock_positive"),
        sa.CheckConstraint("service_level >= 0 AND service_level <= 1", name="ck_service_level_range"),
    )
    op.create_index("ix_reorder_store_product", "reorder_points", ["store_id", "product_id"])

    # 10. Alerts
    op.create_table(
        "alerts",
        sa.Column("alert_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime),
        sa.Column("resolved_at", sa.DateTime),
        sa.CheckConstraint(
            "alert_type IN ('stockout_predicted', 'anomaly_detected', 'reorder_recommended', 'forecast_accuracy_low')",
            name="ck_alert_type",
        ),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_alert_severity"),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'resolved', 'dismissed')", name="ck_alert_status"),
    )
    op.create_index("ix_alerts_customer_status", "alerts", ["customer_id", "status"])
    op.create_index("ix_alerts_store", "alerts", ["store_id"])
    # Partial index for open alerts
    op.execute("CREATE INDEX ix_alerts_open ON alerts(customer_id, store_id, alert_type) WHERE status = 'open'")

    # 11. Actions
    op.create_table(
        "actions",
        sa.Column("action_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("alert_id", UUID(as_uuid=True), sa.ForeignKey("alerts.alert_id"), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("taken_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "action_type IN ('acknowledged', 'ordered', 'dismissed', 'escalated', 'resolved')",
            name="ck_action_type",
        ),
    )
    op.create_index("ix_actions_alert", "actions", ["alert_id"])

    # 12. Purchase Orders
    op.create_table(
        "purchase_orders",
        sa.Column("po_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.supplier_id"), nullable=True),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("estimated_cost", sa.Float),
        sa.Column("status", sa.String(20), nullable=False, server_default="suggested"),
        sa.Column("suggested_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("ordered_at", sa.DateTime),
        sa.Column("expected_delivery", sa.Date),
        sa.Column("received_at", sa.DateTime),
        sa.CheckConstraint("quantity > 0", name="ck_po_quantity_positive"),
        sa.CheckConstraint(
            "status IN ('suggested', 'approved', 'ordered', 'shipped', 'received', 'cancelled')",
            name="ck_po_status",
        ),
    )
    op.create_index("ix_po_customer_status", "purchase_orders", ["customer_id", "status"])
    op.create_index("ix_po_store", "purchase_orders", ["store_id"])

    # 13. Promotions
    op.create_table(
        "promotions",
        sa.Column("promotion_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("discount_pct", sa.Float, server_default="0"),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("expected_lift", sa.Float, server_default="1.0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("discount_pct >= 0 AND discount_pct <= 1", name="ck_promo_discount_range"),
        sa.CheckConstraint("end_date >= start_date", name="ck_promo_dates_valid"),
        sa.CheckConstraint("expected_lift >= 0", name="ck_promo_lift_positive"),
        sa.CheckConstraint("status IN ('planned', 'active', 'completed', 'cancelled')", name="ck_promo_status"),
    )
    op.create_index("ix_promotions_customer_dates", "promotions", ["customer_id", "start_date", "end_date"])

    # 14. Integrations
    op.create_table(
        "integrations",
        sa.Column("integration_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("integration_type", sa.String(20), nullable=False, server_default="rest_api"),
        sa.Column("access_token_encrypted", sa.Text),
        sa.Column("refresh_token_encrypted", sa.Text),
        sa.Column("token_expires_at", sa.DateTime),
        sa.Column("merchant_id", sa.String(255)),
        sa.Column("partner_id", sa.String(255)),
        sa.Column("webhook_secret", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="connected"),
        sa.Column("last_sync_at", sa.DateTime),
        sa.Column("config", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("customer_id", "provider", name="uq_integration_per_provider"),
        sa.CheckConstraint(
            "provider IN ('square', 'shopify', 'lightspeed', 'clover', "
            "'oracle_retail', 'sap', 'relex', 'manhattan', 'blue_yonder', 'custom_edi', 'custom_sftp')",
            name="ck_integration_provider",
        ),
        sa.CheckConstraint(
            "integration_type IN ('edi', 'sftp', 'event_stream', 'rest_api')",
            name="ck_integration_type",
        ),
        sa.CheckConstraint("status IN ('connected', 'disconnected', 'error', 'pending')", name="ck_integration_status"),
    )
    op.create_index("ix_integrations_customer", "integrations", ["customer_id"])

    # 15. Anomalies
    op.create_table(
        "anomalies",
        sa.Column("anomaly_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.store_id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("anomaly_type", sa.String(50), nullable=False),
        sa.Column("detected_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("expected_value", sa.Float),
        sa.Column("actual_value", sa.Float),
        sa.Column("z_score", sa.Float),
        sa.Column("status", sa.String(20), nullable=False, server_default="detected"),
        sa.CheckConstraint(
            "anomaly_type IN ('demand_spike', 'demand_drop', 'inventory_discrepancy', 'price_anomaly', 'data_quality')",
            name="ck_anomaly_type",
        ),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_anomaly_severity"),
        sa.CheckConstraint(
            "status IN ('detected', 'investigating', 'resolved', 'false_positive')", name="ck_anomaly_status"
        ),
    )
    op.create_index("ix_anomalies_customer_status", "anomalies", ["customer_id", "status"])
    op.create_index("ix_anomalies_store_product", "anomalies", ["store_id", "product_id"])

    # ─── Row Level Security ──────────────────────────────────────────────
    tables_with_rls = [
        "stores",
        "products",
        "suppliers",
        "transactions",
        "inventory_levels",
        "demand_forecasts",
        "forecast_accuracy",
        "reorder_points",
        "alerts",
        "actions",
        "purchase_orders",
        "promotions",
        "integrations",
        "anomalies",
    ]
    for table in tables_with_rls:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (customer_id::text = current_setting('app.current_customer_id', true))"
        )


def downgrade() -> None:
    tables = [
        "anomalies",
        "integrations",
        "promotions",
        "purchase_orders",
        "actions",
        "alerts",
        "reorder_points",
        "forecast_accuracy",
        "demand_forecasts",
        "inventory_levels",
        "transactions",
        "products",
        "suppliers",
        "stores",
        "customers",
    ]
    for table in tables:
        op.drop_table(table)
