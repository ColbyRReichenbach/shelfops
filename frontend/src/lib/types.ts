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

export interface ProductMutationPayload {
    sku: string
    name: string
    category?: string | null
    subcategory?: string | null
    brand?: string | null
    unit_cost?: number | null
    unit_price?: number | null
    weight?: number | null
    shelf_life_days?: number | null
    is_seasonal?: boolean
    is_perishable?: boolean
    supplier_id?: string | null
    status?: string
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
}

export interface StoreMutationPayload {
    name: string
    address?: string | null
    city?: string | null
    state?: string | null
    zip_code?: string | null
    lat?: number | null
    lon?: number | null
    timezone?: string
    status?: string
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

// ─── ML Ops types ─────────────────────────────────────────────────────────

export interface MLModel {
    model_id: string
    model_name: string
    version: string
    status: 'champion' | 'challenger' | 'archived' | 'candidate'
    metrics: Record<string, unknown> | null
    dataset_id: string | null
    forecast_grain: string | null
    segment_strategy: string | null
    feature_set_id: string | null
    architecture: string | null
    objective: string | null
    tuning_profile: string | null
    trigger_source: string | null
    lineage_label: string | null
    rule_overlay_enabled: boolean | null
    evaluation_window_days: number | null
    promotion_reason: string | null
    promotion_decision: Record<string, unknown> | null
    lifecycle_events: Array<Record<string, unknown>>
    smoke_test_passed: boolean | null
    routing_weight: number | null
    created_at: string | null
    promoted_at: string | null
    archived_at: string | null
}

export interface BacktestEntry {
    backtest_id: string
    model_name: string
    model_version: string
    forecast_date: string | null
    mae: number | null
    mape: number | null
    stockout_miss_rate: number | null
    overstock_rate: number | null
}

export interface ExperimentRun {
    experiment: string
    model_name: string
    timestamp: string | null
    params: Record<string, unknown>
    metrics: Record<string, number>
    tags: Record<string, string>
    mlflow_run_id: string | null
    source_file: string
}

export type ExperimentType =
    | 'architecture'
    | 'feature_set'
    | 'hyperparameter_tuning'
    | 'data_contract'
    | 'data_window'
    | 'segmentation'
    | 'objective_function'
    | 'post_processing'
    | 'promotion_decision'
    | 'rollback'
    | 'baseline_refresh'

export type ExperimentStatus =
    | 'proposed'
    | 'approved'
    | 'in_progress'
    | 'shadow_testing'
    | 'completed'
    | 'rejected'

export interface ExperimentLedgerEntry {
    experiment_id: string
    experiment_name: string
    hypothesis: string
    experiment_type: ExperimentType
    model_name: string
    status: ExperimentStatus
    proposed_by: string
    approved_by: string | null
    baseline_version: string | null
    experimental_version: string | null
    lineage_metadata: Record<string, unknown> | null
    decision_rationale: string | null
    created_at: string
    approved_at: string | null
    completed_at: string | null
}

export interface ProposeExperimentPayload {
    experiment_name: string
    hypothesis: string
    experiment_type: ExperimentType
    model_name: string
    proposed_by: string
    lineage_metadata?: Record<string, unknown>
}

export interface ProposeExperimentResponse {
    status: string
    experiment_id: string
    message: string
    baseline_version: string | null
}

export interface ApproveExperimentPayload {
    experimentId: string
    approved_by: string
    rationale?: string
}

export interface SHAPFeature {
    name: string
    importance: number
}

export interface MLHealth {
    status: string
    model_counts: Record<string, number>
    champions: Array<{
        model_name: string
        version: string
        metrics: Record<string, number> | null
        promoted_at: string | null
    }>
    recent_backtests_7d: number
    registry_exists: boolean
    checked_at: string
    recent_retraining_events?: Array<{
        trigger_type: string
        status: string
        version_produced: string | null
        started_at: string | null
        completed_at: string | null
        trigger_metadata: Record<string, unknown> | null
    }>
}

export interface RuntimeModelHealth {
    champion: {
        version: string
        status: string
        mae_7d: number | null
        mae_30d: number | null
        trend: string
        promoted_at: string | null
        next_retrain: string | null
    } | null
    challenger: {
        version: string
        status: string
        mae_7d: number | null
        routing_weight: number
        promotion_eligible: boolean
        confidence: number | null
    } | null
    retraining_triggers: {
        drift_detected: boolean
        new_data_available: boolean
        new_data_rows_since_last_retrain: number
        last_trigger: string | null
        last_retrain_at: string | null
    }
    recent_retraining_events: Array<{
        trigger_type: string
        status: string
        version_produced: string | null
        started_at: string | null
        completed_at: string | null
        trigger_metadata: Record<string, unknown> | null
    }>
    models_count: number
}

export interface ModelHistoryEntry {
    version: string
    status: string
    mae: number | null
    mape: number | null
    wape: number | null
    mase: number | null
    bias_pct: number | null
    tier: string | null
    dataset_id: string | null
    forecast_grain: string | null
    feature_set_id: string | null
    architecture: string | null
    objective: string | null
    segment_strategy: string | null
    tuning_profile: string | null
    trigger_source: string | null
    lineage_label: string | null
    promotion_block_reason: string | null
    promotion_decision: Record<string, unknown> | null
    lifecycle_events: Array<Record<string, unknown>>
    created_at: string
    promoted_at: string | null
    archived_at: string | null
    smoke_test_passed: boolean | null
}

export interface MLEffectiveness {
    window_days: number
    model_name: string
    status: string
    sample_count: number
    trend: 'improving' | 'stable' | 'degrading' | 'unknown'
    confidence: string
    forecast_grain: string | null
    evaluation_window?: {
        days: number
        sample_count: number
        start_date: string | null
        end_date: string | null
    }
    metrics: {
        mae: number | null
        mape_nonzero: number | null
        wape: number | null
        mase: number | null
        bias_pct: number | null
        coverage: number | null
        stockout_miss_rate: number | null
        overstock_rate: number | null
        overstock_dollars: number | null
        opportunity_cost_stockout: number | null
        opportunity_cost_overstock: number | null
        lost_sales_qty: number | null
    } | null
    by_version: Array<{
        model_version: string
        samples: number
        mae: number | null
        mape_nonzero: number | null
        wape: number | null
        mase: number | null
        bias_pct: number | null
        forecast_grain?: string | null
        dataset_id?: string | null
        segment_strategy?: string | null
        rule_overlay_enabled?: boolean | null
        evaluation_window_days?: number | null
    }>
    segment_breakdowns?: Record<string, {
        available: boolean
        label: string
        reason?: string
        segments: Array<{
            segment: string
            samples: number
            mae: number
            wape: number
            bias_pct: number
            stockout_miss_rate: number
            overstock_rate: number
        }>
    }>
}

export interface SyncHealth {
    integration_type: string
    integration_name: string
    last_sync: string | null
    hours_since_sync: number | null
    sla_hours: number
    sla_status: 'ok' | 'breach'
    failures_24h: number
    syncs_24h: number
    records_24h: number
}

export interface SyncHealthResponse {
    sources: SyncHealth[]
    overall_health: 'healthy' | 'degraded'
    checked_at: string
}
