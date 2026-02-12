"""commercial_readiness — supply chain, retail logic, decision engine

Add 11 new tables + extend 3 existing tables to transform ShelfOps
from a forecasting tool into a retail operating system.

New tables:
  - distribution_centers, product_sourcing_rules, dc_inventory, store_transfers
  - shrinkage_rates, planograms, promotion_results, receiving_discrepancies
  - reorder_history, po_decisions, opportunity_cost_log

Extended tables:
  - suppliers: vendor scorecard fields
  - purchase_orders: sourcing + receiving fields
  - products: lifecycle_state, holding_cost

Revision ID: 002
Revises: ec78d2c05126
Create Date: 2026-02-11
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: str | None = "ec78d2c05126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════════════════
    # Extend existing tables
    # ═══════════════════════════════════════════════════════════════════

    # --- suppliers: vendor scorecard ---
    op.add_column("suppliers", sa.Column("distance_miles", sa.Float(), nullable=True))
    op.add_column("suppliers", sa.Column("cost_per_order", sa.Float(), nullable=True))
    op.add_column("suppliers", sa.Column("on_time_delivery_rate", sa.Float(), nullable=True))
    op.add_column("suppliers", sa.Column("avg_lead_time_actual", sa.Float(), nullable=True))
    op.add_column("suppliers", sa.Column("lead_time_variance", sa.Float(), nullable=True))
    op.add_column("suppliers", sa.Column("last_delivery_date", sa.Date(), nullable=True))

    # --- products: lifecycle + holding cost ---
    op.add_column(
        "products", sa.Column("lifecycle_state", sa.String(length=30), nullable=False, server_default="active")
    )
    op.add_column("products", sa.Column("planogram_required", sa.Boolean(), nullable=True, server_default="false"))
    op.add_column("products", sa.Column("holding_cost_per_unit_per_day", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_product_lifecycle_state",
        "products",
        "lifecycle_state IN ('active', 'seasonal_out', 'delisted', 'discontinued', 'test', 'pending_activation')",
    )

    # --- purchase_orders: sourcing + receiving ---
    op.add_column("purchase_orders", sa.Column("source_type", sa.String(length=20), nullable=True))
    op.add_column("purchase_orders", sa.Column("source_id", UUID(), nullable=True))
    op.add_column("purchase_orders", sa.Column("promised_delivery_date", sa.Date(), nullable=True))
    op.add_column("purchase_orders", sa.Column("actual_delivery_date", sa.Date(), nullable=True))
    op.add_column("purchase_orders", sa.Column("received_qty", sa.Integer(), nullable=True))
    op.add_column("purchase_orders", sa.Column("total_received_cost", sa.Float(), nullable=True))
    op.add_column("purchase_orders", sa.Column("receiving_notes", sa.Text(), nullable=True))

    # --- alerts: expand alert_type enum ---
    op.drop_constraint("ck_alert_type", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alert_type",
        "alerts",
        "alert_type IN ("
        "'stockout_predicted', 'anomaly_detected', 'reorder_recommended', "
        "'forecast_accuracy_low', 'model_drift_detected', 'data_stale', "
        "'receiving_discrepancy', 'vendor_reliability_low', 'reorder_point_changed')",
    )

    # ═══════════════════════════════════════════════════════════════════
    # Supply Chain Tables
    # ═══════════════════════════════════════════════════════════════════

    op.create_table(
        "distribution_centers",
        sa.Column("dc_id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("dc_type", sa.String(length=30), nullable=False, server_default="regional"),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("zip_code", sa.String(length=10), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("capacity_cubic_feet", sa.Integer(), nullable=True),
        sa.Column("operating_costs_per_day", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.PrimaryKeyConstraint("dc_id"),
        sa.CheckConstraint("dc_type IN ('regional', 'national', 'cross_dock')", name="ck_dc_type"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'planned')", name="ck_dc_status"),
    )
    op.create_index("ix_dc_customer", "distribution_centers", ["customer_id"])

    op.create_table(
        "product_sourcing_rules",
        sa.Column("rule_id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("product_id", UUID(), nullable=False),
        sa.Column("store_id", UUID(), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_id", UUID(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("lead_time_variance_days", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("min_order_qty", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("cost_per_order", sa.Float(), nullable=True, server_default="0"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.PrimaryKeyConstraint("rule_id"),
        sa.CheckConstraint(
            "source_type IN ('vendor_direct', 'dc', 'regional_dc', 'transfer')", name="ck_sourcing_source_type"
        ),
        sa.CheckConstraint("priority >= 1 AND priority <= 5", name="ck_sourcing_priority_range"),
        sa.CheckConstraint("lead_time_days > 0", name="ck_sourcing_lead_time_positive"),
    )
    op.create_index("ix_sourcing_product_store", "product_sourcing_rules", ["product_id", "store_id"])
    op.create_index("ix_sourcing_customer", "product_sourcing_rules", ["customer_id"])

    op.create_table(
        "dc_inventory",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("dc_id", UUID(), nullable=False),
        sa.Column("product_id", UUID(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("quantity_on_hand", sa.Integer(), nullable=False),
        sa.Column("quantity_allocated", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("quantity_in_transit", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("quantity_available", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["dc_id"], ["distribution_centers.dc_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity_on_hand >= 0", name="ck_dc_inv_qty_positive"),
    )
    op.create_index("ix_dc_inv_dc_product", "dc_inventory", ["dc_id", "product_id", "timestamp"])
    op.create_index("ix_dc_inv_customer_time", "dc_inventory", ["customer_id", "timestamp"])

    op.create_table(
        "store_transfers",
        sa.Column("transfer_id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("product_id", UUID(), nullable=False),
        sa.Column("from_location_type", sa.String(length=10), nullable=False),
        sa.Column("from_location_id", UUID(), nullable=False),
        sa.Column("to_location_type", sa.String(length=10), nullable=False),
        sa.Column("to_location_id", UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="requested"),
        sa.Column("reason_code", sa.String(length=30), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("shipped_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("transfer_id"),
        sa.CheckConstraint("quantity > 0", name="ck_transfer_quantity_positive"),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'in_transit', 'received', 'cancelled')", name="ck_transfer_status"
        ),
        sa.CheckConstraint("from_location_type IN ('store', 'dc')", name="ck_transfer_from_type"),
        sa.CheckConstraint("to_location_type IN ('store', 'dc')", name="ck_transfer_to_type"),
    )
    op.create_index("ix_transfers_customer_status", "store_transfers", ["customer_id", "status"])

    # ═══════════════════════════════════════════════════════════════════
    # Retail Business Logic Tables
    # ═══════════════════════════════════════════════════════════════════

    op.create_table(
        "shrinkage_rates",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("store_id", UUID(), nullable=True),
        sa.Column("shrink_rate_pct", sa.Float(), nullable=False),
        sa.Column("shrink_type", sa.String(length=20), nullable=False, server_default="combined"),
        sa.Column("measurement_period_days", sa.Integer(), nullable=True, server_default="365"),
        sa.Column("last_calculated", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("shrink_rate_pct >= 0 AND shrink_rate_pct <= 1", name="ck_shrink_rate_range"),
        sa.CheckConstraint(
            "shrink_type IN ('theft', 'spoilage', 'damage', 'admin_error', 'combined')", name="ck_shrink_type"
        ),
    )
    op.create_index("ix_shrinkage_customer_category", "shrinkage_rates", ["customer_id", "category"])

    op.create_table(
        "planograms",
        sa.Column("planogram_id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("store_id", UUID(), nullable=False),
        sa.Column("product_id", UUID(), nullable=False),
        sa.Column("aisle", sa.String(length=50), nullable=True),
        sa.Column("bay", sa.String(length=50), nullable=True),
        sa.Column("shelf", sa.String(length=50), nullable=True),
        sa.Column("facings", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("min_presentation_qty", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("max_capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("planogram_id"),
        sa.UniqueConstraint("store_id", "product_id", "effective_date", name="uq_planogram_store_product"),
        sa.CheckConstraint(
            "status IN ('active', 'seasonal_out', 'discontinued', 'pending_reset')", name="ck_planogram_status"
        ),
        sa.CheckConstraint("facings > 0", name="ck_planogram_facings_positive"),
    )
    op.create_index("ix_planograms_customer", "planograms", ["customer_id"])
    op.create_index("ix_planograms_store_product", "planograms", ["store_id", "product_id"])

    op.create_table(
        "promotion_results",
        sa.Column("result_id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("promotion_id", UUID(), nullable=False),
        sa.Column("store_id", UUID(), nullable=True),
        sa.Column("product_id", UUID(), nullable=True),
        sa.Column("baseline_daily_sales", sa.Float(), nullable=False),
        sa.Column("promo_daily_sales", sa.Float(), nullable=False),
        sa.Column("actual_lift", sa.Float(), nullable=False),
        sa.Column("incremental_revenue", sa.Float(), nullable=True),
        sa.Column("incremental_margin", sa.Float(), nullable=True),
        sa.Column("measured_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["promotion_id"], ["promotions.promotion_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("result_id"),
    )
    op.create_index("ix_promo_results_promotion", "promotion_results", ["promotion_id"])
    op.create_index("ix_promo_results_customer", "promotion_results", ["customer_id"])

    op.create_table(
        "receiving_discrepancies",
        sa.Column("discrepancy_id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("po_id", UUID(), nullable=False),
        sa.Column("product_id", UUID(), nullable=False),
        sa.Column("ordered_qty", sa.Integer(), nullable=False),
        sa.Column("received_qty", sa.Integer(), nullable=False),
        sa.Column("discrepancy_qty", sa.Integer(), nullable=False),
        sa.Column("discrepancy_type", sa.String(length=20), nullable=False),
        sa.Column("resolution_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("reported_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.po_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("discrepancy_id"),
        sa.CheckConstraint(
            "discrepancy_type IN ('shortage', 'overage', 'damaged', 'wrong_item')", name="ck_discrepancy_type"
        ),
        sa.CheckConstraint(
            "resolution_status IN ('pending', 'credited', 'restocked', 'written_off')", name="ck_discrepancy_resolution"
        ),
    )
    op.create_index("ix_discrepancies_po", "receiving_discrepancies", ["po_id"])
    op.create_index("ix_discrepancies_customer", "receiving_discrepancies", ["customer_id"])

    # ═══════════════════════════════════════════════════════════════════
    # Decision Engine Tables
    # ═══════════════════════════════════════════════════════════════════

    op.create_table(
        "reorder_history",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("store_id", UUID(), nullable=False),
        sa.Column("product_id", UUID(), nullable=False),
        sa.Column("old_reorder_point", sa.Integer(), nullable=False),
        sa.Column("new_reorder_point", sa.Integer(), nullable=False),
        sa.Column("old_safety_stock", sa.Integer(), nullable=False),
        sa.Column("new_safety_stock", sa.Integer(), nullable=False),
        sa.Column("old_eoq", sa.Integer(), nullable=True),
        sa.Column("new_eoq", sa.Integer(), nullable=True),
        sa.Column("calculation_rationale", sa.JSON(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reorder_history_store_product", "reorder_history", ["store_id", "product_id", "calculated_at"])
    op.create_index("ix_reorder_history_customer", "reorder_history", ["customer_id"])

    op.create_table(
        "po_decisions",
        sa.Column("decision_id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("po_id", UUID(), nullable=False),
        sa.Column("decision_type", sa.String(length=20), nullable=False),
        sa.Column("original_qty", sa.Integer(), nullable=False),
        sa.Column("final_qty", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.po_id"]),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.CheckConstraint("decision_type IN ('approved', 'rejected', 'edited')", name="ck_decision_type"),
    )
    op.create_index("ix_po_decisions_po", "po_decisions", ["po_id"])
    op.create_index("ix_po_decisions_customer", "po_decisions", ["customer_id"])

    op.create_table(
        "opportunity_cost_log",
        sa.Column("log_id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("store_id", UUID(), nullable=False),
        sa.Column("product_id", UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("forecasted_demand", sa.Float(), nullable=False),
        sa.Column("actual_stock", sa.Integer(), nullable=False),
        sa.Column("actual_sales", sa.Integer(), nullable=False),
        sa.Column("lost_sales_qty", sa.Integer(), nullable=False),
        sa.Column("opportunity_cost", sa.Float(), nullable=False),
        sa.Column("holding_cost", sa.Float(), nullable=True, server_default="0"),
        sa.Column("cost_type", sa.String(length=20), nullable=False),
        sa.Column("logged_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("log_id"),
        sa.CheckConstraint("cost_type IN ('stockout', 'overstock')", name="ck_opp_cost_type"),
        sa.CheckConstraint("opportunity_cost >= 0", name="ck_opp_cost_positive"),
    )
    op.create_index("ix_opp_cost_customer_date", "opportunity_cost_log", ["customer_id", "date"])
    op.create_index("ix_opp_cost_store_product", "opportunity_cost_log", ["store_id", "product_id", "date"])


def downgrade() -> None:
    # Decision engine tables
    op.drop_table("opportunity_cost_log")
    op.drop_table("po_decisions")
    op.drop_table("reorder_history")

    # Retail business logic tables
    op.drop_table("receiving_discrepancies")
    op.drop_table("promotion_results")
    op.drop_table("planograms")
    op.drop_table("shrinkage_rates")

    # Supply chain tables
    op.drop_table("store_transfers")
    op.drop_table("dc_inventory")
    op.drop_table("product_sourcing_rules")
    op.drop_table("distribution_centers")

    # Revert alert_type constraint
    op.drop_constraint("ck_alert_type", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alert_type",
        "alerts",
        "alert_type IN ('stockout_predicted', 'anomaly_detected', 'reorder_recommended', 'forecast_accuracy_low')",
    )

    # Revert purchase_orders extensions
    op.drop_column("purchase_orders", "receiving_notes")
    op.drop_column("purchase_orders", "total_received_cost")
    op.drop_column("purchase_orders", "received_qty")
    op.drop_column("purchase_orders", "actual_delivery_date")
    op.drop_column("purchase_orders", "promised_delivery_date")
    op.drop_column("purchase_orders", "source_id")
    op.drop_column("purchase_orders", "source_type")

    # Revert products extensions
    op.drop_constraint("ck_product_lifecycle_state", "products", type_="check")
    op.drop_column("products", "holding_cost_per_unit_per_day")
    op.drop_column("products", "planogram_required")
    op.drop_column("products", "lifecycle_state")

    # Revert suppliers extensions
    op.drop_column("suppliers", "last_delivery_date")
    op.drop_column("suppliers", "lead_time_variance")
    op.drop_column("suppliers", "avg_lead_time_actual")
    op.drop_column("suppliers", "on_time_delivery_rate")
    op.drop_column("suppliers", "cost_per_order")
    op.drop_column("suppliers", "distance_miles")
