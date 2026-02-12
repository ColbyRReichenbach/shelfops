"""
ShelfOps Database Models

29 tables for the inventory intelligence platform.
Multi-tenant via customer_id on all tables.
TimescaleDB hypertables: transactions, inventory_levels, dc_inventory.

Tables:
  Core (16 — original):
  1. customers             - Tenant organizations
  2. stores                - Physical store locations
  3. products              - Product catalog (+ lifecycle_state, holding_cost)
  4. suppliers             - Product suppliers (+ vendor scorecard fields)
  5. transactions          - Sales transactions (hypertable)
  6. inventory_levels      - Point-in-time inventory snapshots (hypertable)
  7. demand_forecasts      - ML prediction output
  8. forecast_accuracy     - Prediction vs actual tracking
  9. reorder_points        - Dynamic reorder thresholds
  10. alerts               - Stockout/anomaly alerts
  11. actions              - User actions taken on alerts
  12. purchase_orders      - Suggested/placed purchase orders (+ sourcing, receiving)
  13. promotions           - Active promotions affecting demand
  14. integrations         - POS integration credentials
  15. anomalies            - Detected data anomalies
  16. edi_transaction_log  - EDI document audit trail

  Supply Chain (17-20):
  17. distribution_centers   - DC locations in the supply network
  18. product_sourcing_rules - Maps products to source (DC vs vendor)
  19. dc_inventory           - DC-level inventory snapshots (hypertable)
  20. store_transfers        - Cross-store/DC inventory movements

  Retail Business Logic (21-24):
  21. shrinkage_rates        - Category-based shrink rates
  22. planograms             - What SHOULD be on shelf per store
  23. promotion_results      - Actual vs expected promotional lift
  24. receiving_discrepancies - PO receipt vs ordered tracking

  Decision Engine (25-27):
  25. reorder_history        - Audit trail of ROP changes
  26. po_decisions           - Reason codes for PO approve/reject
  27. opportunity_cost_log   - Quantify stockout/overstock impact
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Date,
    ForeignKey, Text, Enum, CheckConstraint, UniqueConstraint,
    Index, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.session import Base


# ─── 1. Customers ──────────────────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    plan = Column(String(50), nullable=False, default="starter")
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("plan IN ('starter', 'professional', 'enterprise')", name="ck_customer_plan"),
        CheckConstraint("status IN ('active', 'inactive', 'trial', 'churned')", name="ck_customer_status"),
    )

    # Relationships
    stores = relationship("Store", back_populates="customer", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="customer", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="customer", cascade="all, delete-orphan")


# ─── 2. Stores ──────────────────────────────────────────────────────────────

class Store(Base):
    __tablename__ = "stores"

    store_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    lat = Column(Float)
    lon = Column(Float)
    timezone = Column(String(50), default="America/New_York")
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_stores_customer", "customer_id"),
        CheckConstraint("status IN ('active', 'inactive', 'onboarding')", name="ck_store_status"),
    )

    customer = relationship("Customer", back_populates="stores")
    transactions = relationship("Transaction", back_populates="store")
    inventory_levels = relationship("InventoryLevel", back_populates="store")
    alerts = relationship("Alert", back_populates="store")


# ─── 3. Products ────────────────────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    product_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    sku = Column(String(100), nullable=False)
    gtin = Column(String(14))            # GS1 Global Trade Item Number
    upc = Column(String(12))             # Universal Product Code
    name = Column(String(255), nullable=False)
    category = Column(String(100))
    subcategory = Column(String(100))
    brand = Column(String(100))
    unit_cost = Column(Float)
    unit_price = Column(Float)
    weight = Column(Float)
    shelf_life_days = Column(Integer)
    is_seasonal = Column(Boolean, default=False)
    is_perishable = Column(Boolean, default=False)
    status = Column(String(20), nullable=False, default="active")
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Lifecycle & cost fields — for planogram management and EOQ optimization
    lifecycle_state = Column(
        String(30), nullable=False, default="active",
    )  # active, seasonal_out, delisted, discontinued, test, pending_activation
    planogram_required = Column(Boolean, default=False)
    holding_cost_per_unit_per_day = Column(Float)  # Inventory carrying cost for EOQ

    __table_args__ = (
        UniqueConstraint("customer_id", "sku", name="uq_product_sku_per_customer"),
        Index("ix_products_customer", "customer_id"),
        Index("ix_products_category", "customer_id", "category"),
        CheckConstraint("unit_cost >= 0", name="ck_product_cost_positive"),
        CheckConstraint("unit_price >= 0", name="ck_product_price_positive"),
        CheckConstraint(
            "lifecycle_state IN ('active', 'seasonal_out', 'delisted', 'discontinued', 'test', 'pending_activation')",
            name="ck_product_lifecycle_state"
        ),
    )

    customer = relationship("Customer", back_populates="products")
    supplier = relationship("Supplier", back_populates="products")
    transactions = relationship("Transaction", back_populates="product")


# ─── 4. Suppliers ───────────────────────────────────────────────────────────

class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255))
    lead_time_days = Column(Integer, nullable=False, default=7)
    min_order_quantity = Column(Integer, default=1)
    reliability_score = Column(Float, default=0.95)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Vendor scorecard fields — populated by workers/vendor_metrics.py
    distance_miles = Column(Float)                  # Distance from primary DC
    cost_per_order = Column(Float)                  # Fixed cost per PO (receiving labor, setup)
    on_time_delivery_rate = Column(Float)           # Rolling 90-day on-time %
    avg_lead_time_actual = Column(Float)            # Rolling avg actual delivery days
    lead_time_variance = Column(Float)              # Std dev of delivery times
    last_delivery_date = Column(Date)               # Most recent receiving event

    __table_args__ = (
        Index("ix_suppliers_customer", "customer_id"),
        CheckConstraint("lead_time_days > 0", name="ck_supplier_lead_time_positive"),
        CheckConstraint("reliability_score >= 0 AND reliability_score <= 1", name="ck_supplier_reliability_range"),
    )

    products = relationship("Product", back_populates="supplier")


# ─── 5. Transactions (hypertable) ──────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0.0)
    transaction_type = Column(String(20), nullable=False, default="sale")
    external_id = Column(String(255))  # POS transaction ID
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_transactions_store", "store_id"),
        Index("ix_transactions_product", "product_id"),
        Index("ix_transactions_customer_time", "customer_id", "timestamp"),
        Index("ix_transactions_store_product_time", "store_id", "product_id", "timestamp"),
        CheckConstraint("quantity != 0", name="ck_transaction_quantity_nonzero"),
        CheckConstraint("transaction_type IN ('sale', 'return', 'void', 'adjustment')", name="ck_transaction_type"),
    )

    store = relationship("Store", back_populates="transactions")
    product = relationship("Product", back_populates="transactions")


# ─── 6. Inventory Levels (hypertable) ──────────────────────────────────────

class InventoryLevel(Base):
    __tablename__ = "inventory_levels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    quantity_on_hand = Column(Integer, nullable=False)
    quantity_on_order = Column(Integer, default=0)
    quantity_reserved = Column(Integer, default=0)
    quantity_available = Column(Integer, nullable=False)
    source = Column(String(50), default="pos_sync")

    __table_args__ = (
        Index("ix_inventory_store_product", "store_id", "product_id", "timestamp"),
        Index("ix_inventory_customer_time", "customer_id", "timestamp"),
        CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_qty_positive"),
    )

    store = relationship("Store", back_populates="inventory_levels")


# ─── 7. Demand Forecasts ───────────────────────────────────────────────────

class DemandForecast(Base):
    __tablename__ = "demand_forecasts"

    forecast_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    forecast_date = Column(Date, nullable=False)
    forecasted_demand = Column(Float, nullable=False)
    lower_bound = Column(Float)
    upper_bound = Column(Float)
    confidence = Column(Float)
    model_version = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("store_id", "product_id", "forecast_date", "model_version", name="uq_forecast_unique"),
        Index("ix_forecast_store_product_date", "store_id", "product_id", "forecast_date"),
        CheckConstraint("forecasted_demand >= 0", name="ck_forecast_demand_positive"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_forecast_confidence_range"),
    )


# ─── 8. Forecast Accuracy ──────────────────────────────────────────────────

class ForecastAccuracy(Base):
    __tablename__ = "forecast_accuracy"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    forecast_date = Column(Date, nullable=False)
    forecasted_demand = Column(Float, nullable=False)
    actual_demand = Column(Float, nullable=False)
    mae = Column(Float)
    mape = Column(Float)
    model_version = Column(String(50), nullable=False)
    evaluated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_accuracy_store_product", "store_id", "product_id"),
        Index("ix_accuracy_model_version", "model_version"),
    )


# ─── 9. Reorder Points ─────────────────────────────────────────────────────

class ReorderPoint(Base):
    __tablename__ = "reorder_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    reorder_point = Column(Integer, nullable=False)
    safety_stock = Column(Integer, nullable=False)
    economic_order_qty = Column(Integer, nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    service_level = Column(Float, nullable=False, default=0.95)
    last_calculated = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("store_id", "product_id", name="uq_reorder_store_product"),
        Index("ix_reorder_store_product", "store_id", "product_id"),
        CheckConstraint("reorder_point >= 0", name="ck_reorder_point_positive"),
        CheckConstraint("safety_stock >= 0", name="ck_safety_stock_positive"),
        CheckConstraint("service_level >= 0 AND service_level <= 1", name="ck_service_level_range"),
    )


# ─── 10. Alerts ─────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    alert_metadata = Column("metadata", JSON, default={})
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)

    __table_args__ = (
        Index("ix_alerts_customer_status", "customer_id", "status"),
        Index("ix_alerts_store", "store_id"),
        Index("ix_alerts_open", "customer_id", "store_id", "alert_type",
              postgresql_where="status = 'open'"),
        CheckConstraint(
            "alert_type IN ("
            "'stockout_predicted', 'anomaly_detected', 'reorder_recommended', "
            "'forecast_accuracy_low', 'model_drift_detected', 'data_stale', "
            "'receiving_discrepancy', 'vendor_reliability_low', 'reorder_point_changed')",
            name="ck_alert_type"
        ),
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_alert_severity"),
        CheckConstraint("status IN ('open', 'acknowledged', 'resolved', 'dismissed')", name="ck_alert_status"),
    )

    store = relationship("Store", back_populates="alerts")
    actions = relationship("Action", back_populates="alert", cascade="all, delete-orphan")


# ─── 11. Actions ────────────────────────────────────────────────────────────

class Action(Base):
    __tablename__ = "actions"

    action_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.alert_id"), nullable=False)
    action_type = Column(String(50), nullable=False)
    notes = Column(Text)
    taken_by = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_actions_alert", "alert_id"),
        CheckConstraint(
            "action_type IN ('acknowledged', 'ordered', 'dismissed', 'escalated', 'resolved')",
            name="ck_action_type"
        ),
    )

    alert = relationship("Alert", back_populates="actions")


# ─── 12. Purchase Orders ───────────────────────────────────────────────────

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.supplier_id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    estimated_cost = Column(Float)
    status = Column(String(20), nullable=False, default="suggested")
    suggested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ordered_at = Column(DateTime)
    expected_delivery = Column(Date)
    received_at = Column(DateTime)

    # Sourcing — where this order will come from
    source_type = Column(String(20))  # vendor_direct, dc, transfer
    source_id = Column(UUID(as_uuid=True))  # supplier_id or dc_id depending on source_type

    # Receiving — track actual vs promised delivery
    promised_delivery_date = Column(Date)       # When vendor said it would arrive
    actual_delivery_date = Column(Date)         # When it actually arrived
    received_qty = Column(Integer)              # May differ from ordered quantity
    total_received_cost = Column(Float)         # Actual cost (may differ from estimated)
    receiving_notes = Column(Text)

    __table_args__ = (
        Index("ix_po_customer_status", "customer_id", "status"),
        Index("ix_po_store", "store_id"),
        CheckConstraint("quantity > 0", name="ck_po_quantity_positive"),
        CheckConstraint(
            "status IN ('suggested', 'approved', 'ordered', 'shipped', 'received', 'cancelled')",
            name="ck_po_status"
        ),
    )

    decisions = relationship("PODecision", back_populates="purchase_order", cascade="all, delete-orphan")


# ─── 13. Promotions ────────────────────────────────────────────────────────

class Promotion(Base):
    __tablename__ = "promotions"

    promotion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=True)
    name = Column(String(255), nullable=False)
    discount_pct = Column(Float, default=0.0)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    expected_lift = Column(Float, default=1.0)
    status = Column(String(20), nullable=False, default="planned")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_promotions_customer_dates", "customer_id", "start_date", "end_date"),
        CheckConstraint("discount_pct >= 0 AND discount_pct <= 1", name="ck_promo_discount_range"),
        CheckConstraint("end_date >= start_date", name="ck_promo_dates_valid"),
        CheckConstraint("expected_lift >= 0", name="ck_promo_lift_positive"),
        CheckConstraint("status IN ('planned', 'active', 'completed', 'cancelled')", name="ck_promo_status"),
    )


# ─── 14. Integrations ──────────────────────────────────────────────────────

class Integration(Base):
    __tablename__ = "integrations"

    integration_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    provider = Column(String(50), nullable=False)
    integration_type = Column(String(20), nullable=False, default="rest_api")
    access_token_encrypted = Column(Text)
    refresh_token_encrypted = Column(Text)
    token_expires_at = Column(DateTime)
    merchant_id = Column(String(255))
    partner_id = Column(String(255))      # EDI trading partner ID
    webhook_secret = Column(String(255))
    status = Column(String(20), nullable=False, default="connected")
    last_sync_at = Column(DateTime)
    config = Column(JSON, default={})     # Adapter-specific config (SFTP creds, Kafka topics, EDI dirs)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("customer_id", "provider", name="uq_integration_per_provider"),
        Index("ix_integrations_customer", "customer_id"),
        CheckConstraint(
            "provider IN ('square', 'shopify', 'lightspeed', 'clover', "
            "'oracle_retail', 'sap', 'relex', 'manhattan', 'blue_yonder', 'custom_edi', 'custom_sftp')",
            name="ck_integration_provider"
        ),
        CheckConstraint(
            "integration_type IN ('edi', 'sftp', 'event_stream', 'rest_api')",
            name="ck_integration_type"
        ),
        CheckConstraint("status IN ('connected', 'disconnected', 'error', 'pending')", name="ck_integration_status"),
    )

    customer = relationship("Customer", back_populates="integrations")


# ─── 15. Anomalies ─────────────────────────────────────────────────────────

class Anomaly(Base):
    __tablename__ = "anomalies"

    anomaly_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    anomaly_type = Column(String(50), nullable=False)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    severity = Column(String(20), nullable=False)
    description = Column(Text)
    expected_value = Column(Float)
    actual_value = Column(Float)
    z_score = Column(Float)
    status = Column(String(20), nullable=False, default="detected")

    __table_args__ = (
        Index("ix_anomalies_customer_status", "customer_id", "status"),
        Index("ix_anomalies_store_product", "store_id", "product_id"),
        CheckConstraint(
            "anomaly_type IN ('demand_spike', 'demand_drop', 'inventory_discrepancy', 'price_anomaly', 'data_quality')",
            name="ck_anomaly_type"
        ),
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_anomaly_severity"),
        CheckConstraint("status IN ('detected', 'investigating', 'resolved', 'false_positive')", name="ck_anomaly_status"),
    )


# ─── 16. EDI Transaction Log ──────────────────────────────────────────────

class EDITransactionLog(Base):
    __tablename__ = "edi_transaction_log"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.integration_id"), nullable=False)
    document_type = Column(String(10), nullable=False)  # 846, 856, 810, 850
    direction = Column(String(10), nullable=False)        # inbound, outbound
    trading_partner_id = Column(String(100))
    filename = Column(String(255))
    raw_content = Column(Text)
    parsed_records = Column(Integer, default=0)
    errors = Column(JSON, default=[])
    status = Column(String(20), nullable=False, default="received")
    processed_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_edi_log_customer", "customer_id"),
        Index("ix_edi_log_integration", "integration_id"),
        Index("ix_edi_log_customer_type", "customer_id", "document_type", "created_at"),
        CheckConstraint(
            "document_type IN ('846', '856', '810', '850', '997')",
            name="ck_edi_document_type"
        ),
        CheckConstraint("direction IN ('inbound', 'outbound')", name="ck_edi_direction"),
        CheckConstraint(
            "status IN ('received', 'parsing', 'processed', 'failed', 'acknowledged')",
            name="ck_edi_status"
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Supply Chain Models (17-20)
# ═══════════════════════════════════════════════════════════════════════════


# ─── 17. Distribution Centers ─────────────────────────────────────────────

class DistributionCenter(Base):
    __tablename__ = "distribution_centers"

    dc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    name = Column(String(255), nullable=False)
    dc_type = Column(String(30), nullable=False, default="regional")  # regional, national, cross_dock
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    lat = Column(Float)
    lon = Column(Float)
    capacity_cubic_feet = Column(Integer)
    operating_costs_per_day = Column(Float)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_dc_customer", "customer_id"),
        CheckConstraint("dc_type IN ('regional', 'national', 'cross_dock')", name="ck_dc_type"),
        CheckConstraint("status IN ('active', 'inactive', 'planned')", name="ck_dc_status"),
    )

    sourcing_rules = relationship("ProductSourcingRule", back_populates="distribution_center", foreign_keys="ProductSourcingRule.source_id")


# ─── 18. Product Sourcing Rules ───────────────────────────────────────────

class ProductSourcingRule(Base):
    """Maps each product to its replenishment source per store.

    A product at a given store may have multiple sourcing rules:
      priority=1: DC (2-day lead, cheaper)
      priority=2: Vendor direct (10-day lead, fallback if DC out of stock)
    """
    __tablename__ = "product_sourcing_rules"

    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=True)  # Null = all stores
    source_type = Column(String(20), nullable=False)  # vendor_direct, dc, regional_dc, transfer
    source_id = Column(UUID(as_uuid=True), nullable=False)  # supplier_id or dc_id
    lead_time_days = Column(Integer, nullable=False)
    lead_time_variance_days = Column(Integer, default=0)   # Historical ± variance
    min_order_qty = Column(Integer, default=1)
    cost_per_order = Column(Float, default=0.0)   # Fixed ordering cost
    priority = Column(Integer, nullable=False, default=1)  # 1=primary, 2=secondary
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_sourcing_product_store", "product_id", "store_id"),
        Index("ix_sourcing_customer", "customer_id"),
        CheckConstraint(
            "source_type IN ('vendor_direct', 'dc', 'regional_dc', 'transfer')",
            name="ck_sourcing_source_type"
        ),
        CheckConstraint("priority >= 1 AND priority <= 5", name="ck_sourcing_priority_range"),
        CheckConstraint("lead_time_days > 0", name="ck_sourcing_lead_time_positive"),
    )

    distribution_center = relationship("DistributionCenter", back_populates="sourcing_rules", foreign_keys=[source_id])


# ─── 19. DC Inventory ─────────────────────────────────────────────────────

class DCInventory(Base):
    """Distribution center inventory snapshots — TimescaleDB hypertable candidate."""
    __tablename__ = "dc_inventory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    dc_id = Column(UUID(as_uuid=True), ForeignKey("distribution_centers.dc_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    quantity_on_hand = Column(Integer, nullable=False)
    quantity_allocated = Column(Integer, default=0)    # Committed to stores
    quantity_in_transit = Column(Integer, default=0)   # Inbound from vendor
    quantity_available = Column(Integer, nullable=False)  # on_hand - allocated

    __table_args__ = (
        Index("ix_dc_inv_dc_product", "dc_id", "product_id", "timestamp"),
        Index("ix_dc_inv_customer_time", "customer_id", "timestamp"),
        CheckConstraint("quantity_on_hand >= 0", name="ck_dc_inv_qty_positive"),
    )


# ─── 20. Store Transfers ─────────────────────────────────────────────────

class StoreTransfer(Base):
    """Cross-store/DC inventory movements for emergency rebalancing."""
    __tablename__ = "store_transfers"

    transfer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    from_location_type = Column(String(10), nullable=False)  # store, dc
    from_location_id = Column(UUID(as_uuid=True), nullable=False)
    to_location_type = Column(String(10), nullable=False)    # store, dc
    to_location_id = Column(UUID(as_uuid=True), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="requested")
    reason_code = Column(String(30))  # stockout_emergency, rebalance, return, damaged
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    approved_at = Column(DateTime)
    shipped_at = Column(DateTime)
    received_at = Column(DateTime)

    __table_args__ = (
        Index("ix_transfers_customer_status", "customer_id", "status"),
        CheckConstraint("quantity > 0", name="ck_transfer_quantity_positive"),
        CheckConstraint(
            "status IN ('requested', 'approved', 'in_transit', 'received', 'cancelled')",
            name="ck_transfer_status"
        ),
        CheckConstraint(
            "from_location_type IN ('store', 'dc')",
            name="ck_transfer_from_type"
        ),
        CheckConstraint(
            "to_location_type IN ('store', 'dc')",
            name="ck_transfer_to_type"
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Retail Business Logic Models (21-24)
# ═══════════════════════════════════════════════════════════════════════════


# ─── 21. Shrinkage Rates ─────────────────────────────────────────────────

class ShrinkageRate(Base):
    """Category-based shrink rates (theft, spoilage, damage).

    Seeded with NRF 2022-24 industry benchmarks.
    Customers can override per store or per category.
    """
    __tablename__ = "shrinkage_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    category = Column(String(100), nullable=False)   # Maps to products.category
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=True)  # Null = default
    shrink_rate_pct = Column(Float, nullable=False)  # 0.048 = 4.8% annual
    shrink_type = Column(String(20), nullable=False, default="combined")  # theft, spoilage, damage, admin_error, combined
    measurement_period_days = Column(Integer, default=365)
    last_calculated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_shrinkage_customer_category", "customer_id", "category"),
        CheckConstraint("shrink_rate_pct >= 0 AND shrink_rate_pct <= 1", name="ck_shrink_rate_range"),
        CheckConstraint(
            "shrink_type IN ('theft', 'spoilage', 'damage', 'admin_error', 'combined')",
            name="ck_shrink_type"
        ),
    )


# ─── 22. Planograms ──────────────────────────────────────────────────────

class Planogram(Base):
    """Defines what products SHOULD be on shelf at each store.

    Controls reorder logic: don't reorder delisted or seasonal-out products.
    """
    __tablename__ = "planograms"

    planogram_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    aisle = Column(String(50))
    bay = Column(String(50))
    shelf = Column(String(50))
    facings = Column(Integer, default=1)               # Number of product facings
    min_presentation_qty = Column(Integer, default=1)  # Min on shelf for display
    max_capacity = Column(Integer)                     # Max shelf capacity
    status = Column(String(30), nullable=False, default="active")
    effective_date = Column(Date, nullable=False)
    end_date = Column(Date)  # Null = indefinite

    __table_args__ = (
        UniqueConstraint("store_id", "product_id", "effective_date", name="uq_planogram_store_product"),
        Index("ix_planograms_customer", "customer_id"),
        Index("ix_planograms_store_product", "store_id", "product_id"),
        CheckConstraint(
            "status IN ('active', 'seasonal_out', 'discontinued', 'pending_reset')",
            name="ck_planogram_status"
        ),
        CheckConstraint("facings > 0", name="ck_planogram_facings_positive"),
    )


# ─── 23. Promotion Results ───────────────────────────────────────────────

class PromotionResult(Base):
    """Tracks actual vs expected promotional lift for feedback into ML."""
    __tablename__ = "promotion_results"

    result_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    promotion_id = Column(UUID(as_uuid=True), ForeignKey("promotions.promotion_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=True)
    baseline_daily_sales = Column(Float, nullable=False)     # Pre-promo 30-day avg
    promo_daily_sales = Column(Float, nullable=False)        # During promo avg
    actual_lift = Column(Float, nullable=False)              # promo / baseline
    incremental_revenue = Column(Float)
    incremental_margin = Column(Float)
    measured_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_promo_results_promotion", "promotion_id"),
        Index("ix_promo_results_customer", "customer_id"),
    )


# ─── 24. Receiving Discrepancies ─────────────────────────────────────────

class ReceivingDiscrepancy(Base):
    """Tracks order-vs-received mismatches for vendor accountability."""
    __tablename__ = "receiving_discrepancies"

    discrepancy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    po_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.po_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    ordered_qty = Column(Integer, nullable=False)
    received_qty = Column(Integer, nullable=False)
    discrepancy_qty = Column(Integer, nullable=False)  # received - ordered
    discrepancy_type = Column(String(20), nullable=False)  # shortage, overage, damaged, wrong_item
    resolution_status = Column(String(20), nullable=False, default="pending")
    resolution_notes = Column(Text)
    reported_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_discrepancies_po", "po_id"),
        Index("ix_discrepancies_customer", "customer_id"),
        CheckConstraint(
            "discrepancy_type IN ('shortage', 'overage', 'damaged', 'wrong_item')",
            name="ck_discrepancy_type"
        ),
        CheckConstraint(
            "resolution_status IN ('pending', 'credited', 'restocked', 'written_off')",
            name="ck_discrepancy_resolution"
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Decision Engine Models (25-27)
# ═══════════════════════════════════════════════════════════════════════════


# ─── 25. Reorder History ─────────────────────────────────────────────────

class ReorderHistory(Base):
    """Audit trail for dynamic reorder point changes.

    Every time the inventory optimizer recalculates a ROP, the old and new
    values are logged here with the rationale (why it changed).
    """
    __tablename__ = "reorder_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    old_reorder_point = Column(Integer, nullable=False)
    new_reorder_point = Column(Integer, nullable=False)
    old_safety_stock = Column(Integer, nullable=False)
    new_safety_stock = Column(Integer, nullable=False)
    old_eoq = Column(Integer)
    new_eoq = Column(Integer)
    calculation_rationale = Column(JSON, nullable=False)  # {source_type, lead_time, demand_avg, ...}
    calculated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_reorder_history_store_product", "store_id", "product_id", "calculated_at"),
        Index("ix_reorder_history_customer", "customer_id"),
    )


# ─── 26. PO Decisions ────────────────────────────────────────────────────

class PODecision(Base):
    """Captures why a human approved, rejected, or edited a purchase order.

    These reason codes feed back into the ML pipeline as features,
    allowing the model to learn from human overrides.
    """
    __tablename__ = "po_decisions"

    decision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    po_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.po_id"), nullable=False)
    decision_type = Column(String(20), nullable=False)  # approved, rejected, edited
    original_qty = Column(Integer, nullable=False)
    final_qty = Column(Integer, nullable=False)
    reason_code = Column(String(50))  # overstock, seasonal_end, budget_constraint, vendor_issue, forecast_disagree, manual_ordered_elsewhere
    notes = Column(Text)
    decided_by = Column(String(255))
    decided_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_po_decisions_po", "po_id"),
        Index("ix_po_decisions_customer", "customer_id"),
        CheckConstraint(
            "decision_type IN ('approved', 'rejected', 'edited')",
            name="ck_decision_type"
        ),
    )

    purchase_order = relationship("PurchaseOrder", back_populates="decisions")


# ─── 27. Opportunity Cost Log ─────────────────────────────────────────────

class OpportunityCostLog(Base):
    """Quantifies the business impact of stockouts and overstock.

    Populated daily by the counterfactual analysis job.
    Used to prove ROI: "ShelfOps prevented $X in lost sales this month."
    """
    __tablename__ = "opportunity_cost_log"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False)
    date = Column(Date, nullable=False)
    forecasted_demand = Column(Float, nullable=False)
    actual_stock = Column(Integer, nullable=False)
    actual_sales = Column(Integer, nullable=False)
    lost_sales_qty = Column(Integer, nullable=False)           # demand we couldn't fulfill
    opportunity_cost = Column(Float, nullable=False)           # lost_sales × margin
    holding_cost = Column(Float, default=0.0)                  # overstock carrying cost
    cost_type = Column(String(20), nullable=False)             # stockout, overstock
    logged_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_opp_cost_customer_date", "customer_id", "date"),
        Index("ix_opp_cost_store_product", "store_id", "product_id", "date"),
        CheckConstraint("cost_type IN ('stockout', 'overstock')", name="ck_opp_cost_type"),
        CheckConstraint("opportunity_cost >= 0", name="ck_opp_cost_positive"),
    )
