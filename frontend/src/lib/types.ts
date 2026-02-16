/**
 * Type definitions matching the backend Pydantic schemas.
 * Updated to align with actual API response shapes.
 */

import type React from 'react'

// ─── Backend response types (match Pydantic schemas) ───────────────────────

export interface Product {
    product_id: string
    customer_id: string
    sku: string
    name: string
    category: string | null
    subcategory: string | null
    brand: string | null
    unit_cost: number | null
    unit_price: number | null
    weight: number | null
    shelf_life_days: number | null
    is_seasonal: boolean
    is_perishable: boolean
    status: string
    supplier_id: string | null
    created_at: string
    updated_at: string
}

export interface Store {
    store_id: string
    customer_id: string
    name: string
    address: string | null
    city: string | null
    state: string | null
    zip_code: string | null
    lat: number | null
    lon: number | null
    timezone: string
    status: string
    created_at: string
    updated_at: string
    // Computed / UI fields (not from API)
    health_score?: number
    last_sync?: string
}

export interface Alert {
    alert_id: string
    customer_id: string
    store_id: string
    product_id: string
    alert_type: string
    severity: string
    message: string
    alert_metadata: Record<string, unknown> | null
    status: string
    created_at: string
    acknowledged_at: string | null
    resolved_at: string | null
}

export interface AlertSummary {
    total: number
    open: number
    acknowledged: number
    resolved: number
    critical: number
    high: number
}

export interface ReorderAlertContext {
    alert_id: string
    avg_sold_per_day_28d: number | null
    avg_sold_per_week_28d: number | null
    days_of_cover_current: number | null
    days_of_cover_after_order: number | null
    is_perishable: boolean | null
    shelf_life_days: number | null
    suggested_qty: number | null
    lookback_days: number
}

export interface PurchaseOrder {
    po_id: string
    customer_id: string
    store_id: string
    product_id: string
    supplier_id: string | null
    quantity: number
    estimated_cost: number | null
    status: 'suggested' | 'approved' | 'ordered' | 'shipped' | 'received' | 'cancelled' | string
    suggested_at: string
    ordered_at: string | null
    expected_delivery: string | null
    received_at: string | null
    source_type: string | null
    source_id: string | null
    promised_delivery_date: string | null
    actual_delivery_date: string | null
    received_qty: number | null
}

export interface PurchaseOrderSummary {
    total: number
    suggested: number
    approved: number
    ordered: number
    shipped: number
    received: number
    cancelled: number
    total_estimated_cost: number
}

export interface PODecision {
    decision_id: string
    po_id: string
    decision_type: 'approved' | 'rejected' | 'edited' | string
    original_qty: number
    final_qty: number
    reason_code: string | null
    notes: string | null
    decided_by: string | null
    decided_at: string
}

export interface OrderFromAlertRequest {
    quantity?: number
    reason_code?: string
    notes?: string
}

export interface OrderFromAlertResponse {
    status: string
    message: string
    po: PurchaseOrder
    alert: Alert
    decision_id: string
}

export interface Forecast {
    forecast_id: string
    store_id: string
    product_id: string
    forecast_date: string
    forecasted_demand: number
    lower_bound: number | null
    upper_bound: number | null
    confidence: number | null
    model_version: string
    created_at: string
}

export interface ForecastAccuracy {
    store_id: string
    product_id: string
    avg_mae: number
    avg_mape: number
    num_forecasts: number
}

export interface ForecastAccuracyTrend {
    forecast_date: string
    forecasted_demand: number
    actual_demand: number | null
    forecasted_revenue: number
    actual_revenue: number | null
    observations: number
}

export interface ForecastAccuracyByCategory {
    category: string
    forecasted_demand: number
    actual_demand: number | null
    forecasted_revenue: number
    actual_revenue: number | null
    observations: number
}

export interface Integration {
    integration_id: string
    provider: 'square' | 'shopify' | 'lightspeed' | 'clover'
    status: 'connected' | 'disconnected' | 'error' | 'pending'
    last_sync_at?: string
    merchant_id?: string
}

export interface InventoryItem {
    store_id: string
    store_name: string
    product_id: string
    product_name: string
    category: string | null
    sku: string
    quantity_on_hand: number
    quantity_available: number
    reorder_point: number | null
    safety_stock: number | null
    status: 'ok' | 'low' | 'critical' | 'out_of_stock'
    last_updated: string
}

export interface InventorySummary {
    total_items: number
    in_stock: number
    low_stock: number
    critical: number
    out_of_stock: number
}

// ─── MLOps types ───────────────────────────────────────────────────────────

export interface ModelHealthChampion {
    version: string
    status: string
    mae_7d: number | null
    mae_30d: number | null
    trend: string
    promoted_at: string | null
    next_retrain: string | null
}

export interface ModelHealthChallenger {
    version: string
    status: string
    mae_7d: number | null
    routing_weight: number | null
    promotion_eligible: boolean
    confidence: number | null
}

export interface ModelRetrainingTriggers {
    drift_detected: boolean
    new_data_available: boolean
    last_trigger: string | null
    last_retrain_at: string | null
}

export interface ModelHealthResponse {
    champion: ModelHealthChampion | null
    challenger: ModelHealthChallenger | null
    retraining_triggers: ModelRetrainingTriggers
    models_count: number
}

export interface ModelHistoryItem {
    version: string
    status: string
    mae: number | null
    mape: number | null
    tier: string | null
    created_at: string
    promoted_at: string | null
    archived_at: string | null
    smoke_test_passed: boolean
}

export interface BacktestPoint {
    forecast_date: string
    mae: number | null
    mape: number | null
    stockout_miss_rate?: number | null
    overstock_rate?: number | null
}

export interface MLAlertItem {
    ml_alert_id: string
    alert_type: string
    severity: 'info' | 'warning' | 'critical' | string
    title: string
    message: string
    alert_metadata: Record<string, unknown> | null
    status: 'unread' | 'read' | 'actioned' | 'dismissed' | string
    action_url: string | null
    created_at: string
    read_at: string | null
    actioned_at: string | null
}

export interface MLAlertStats {
    total_unread: number
    critical_unread: number
    warning_unread: number
    info_unread: number
}

export interface MLAlertActionResponse {
    status: string
    action: 'approve' | 'dismiss'
    message: string
    actioned_at: string | null
}

export interface MLAlertReadResponse {
    status: string
    message: string
    read_at: string
}

export interface ExperimentItem {
    experiment_id: string
    experiment_name: string
    hypothesis: string
    experiment_type: 'feature_engineering' | 'model_architecture' | 'data_source' | 'segmentation' | string
    model_name: string
    status: 'proposed' | 'approved' | 'in_progress' | 'shadow_testing' | 'completed' | 'rejected' | string
    proposed_by: string
    approved_by: string | null
    baseline_version: string | null
    experimental_version: string | null
    created_at: string
    approved_at: string | null
    completed_at: string | null
}

export interface ProposeExperimentRequest {
    experiment_name: string
    hypothesis: string
    experiment_type: 'feature_engineering' | 'model_architecture' | 'data_source' | 'segmentation'
    model_name: string
    proposed_by: string
}

export interface ProposeExperimentResponse {
    status: string
    experiment_id: string
    message: string
    baseline_version: string | null
}

export interface AlertEffectiveness {
    total_alerts: number
    resolved: number
    dismissed: number
    pending: number
    acknowledged: number
    false_positive_rate: number
    avg_response_time_hours: number
    period_days: number
}

export interface AnomalyEffectivenessByType {
    tp: number
    fp: number
    precision: number
}

export interface AnomalyEffectiveness {
    total_anomalies: number
    true_positives: number
    false_positives: number
    investigating: number
    precision: number
    by_type: Record<string, AnomalyEffectivenessByType>
    period_days: number
}

export interface ROIResponse {
    prevented_stockouts: number
    prevented_stockout_value: number
    prevented_overstock_value: number
    ghost_stock_recovered_value: number
    total_value_created: number
    period_days: number
    note?: string
}

export interface AnomalyStats {
    total_anomalies: number
    critical: number
    warning: number
    info: number
    by_type: Record<string, number>
    trend: 'increasing' | 'decreasing' | 'stable' | string
    period_days: number
}

export interface PromoteModelResponse {
    status: string
    message: string
    promoted_at: string
}

// ─── UI-only types ─────────────────────────────────────────────────────────

export interface KpiData {
    label: string
    value: string | number
    change?: number
    trend?: 'up' | 'down' | 'flat'
    icon?: React.ReactNode
    description?: string
}

export interface DashboardStats {
    revenue_at_risk: number
    recovered_revenue: number
    stockout_rate: number
    active_promotions: number
    forecast_accuracy: number
}
