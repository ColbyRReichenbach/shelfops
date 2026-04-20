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
    customer_id?: string
    provider: string
    status: 'connected' | 'disconnected' | 'error' | 'pending'
    last_sync_at?: string
    merchant_id?: string
    created_at?: string
    updated_at?: string
}

export interface CsvOnboardingPayload {
    stores_csv?: string | null
    products_csv?: string | null
    transactions_csv?: string | null
    inventory_csv?: string | null
}

export interface CsvValidationIssue {
    file_type: 'stores' | 'products' | 'transactions' | 'inventory'
    severity: 'error' | 'warning'
    message: string
    row_number?: number | null
    field?: string | null
}

export interface CsvValidationSummary {
    rows: number
    columns: string[]
}

export interface CsvValidationResponse {
    valid: boolean
    issues: CsvValidationIssue[]
    summary: Partial<Record<'stores' | 'products' | 'transactions' | 'inventory', CsvValidationSummary>>
}

export interface CsvIngestResponse {
    created: {
        stores: number
        products: number
        transactions: number
        inventory: number
    }
    readiness: DataReadiness
}

export interface SquareMappingPreviewRow {
    external_id: string
    name: string | null
    status: 'mapped' | 'unmapped'
    mapped_store_id?: string | null
    mapped_product_id?: string | null
    timezone?: string | null
    variation_ids?: string[]
}

export interface SquareMappingPreviewResponse {
    integration_id: string
    provider: string
    mapping_confirmed: boolean
    mapping_coverage: {
        locations_total: number
        locations_mapped: number
        catalog_total: number
        catalog_mapped: number
    }
    unmapped_location_ids: string[]
    unmapped_catalog_ids: string[]
    locations: SquareMappingPreviewRow[]
    catalog_items: SquareMappingPreviewRow[]
}

export interface SquareMappingConfirmPayload {
    square_location_to_store: Record<string, string>
    square_catalog_to_product: Record<string, string>
    square_mapping_confirmed: boolean
}

export interface WebhookDeadLetterEvent {
    webhook_event_id: string
    provider: string
    merchant_id: string | null
    event_type: string
    status: string
    delivery_attempts: number
    last_error: string | null
    received_at: string
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

export interface ActiveModelEvidence {
    version: string
    model_name: string | null
    architecture: string | null
    objective: string | null
    promoted_at: string | null
    promotion_reason: string | null
    dataset_id: string | null
    dataset_snapshot_id: string | null
    rows_trained: number | null
    stores: number | null
    products: number | null
    categories: number | null
    series_selected: number | null
    subset_strategy: string | null
    coverage_start: string | null
    coverage_end: string | null
    feature_tier: string | null
    feature_count: number | null
    interval_method: string | null
    calibration_status: string | null
    interval_coverage: number | null
    cv: {
        mae: number | null
        wape: number | null
        mase: number | null
        bias_pct: number | null
    }
    holdout: {
        cutoff: string | null
        mae: number | null
        wape: number | null
        mase: number | null
        bias_pct: number | null
    }
    benchmark_rows: Array<{
        label: string
        source: string
        wape: number
        mase: number
        note: string
    }>
    limitations: string[]
    claim_boundary: string
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

export interface ExperimentResults {
    baseline_mae?: number | null
    experimental_mae?: number | null
    baseline_wape?: number | null
    experimental_wape?: number | null
    baseline_mase?: number | null
    experimental_mase?: number | null
    overstock_dollars_delta?: number | null
    opportunity_cost_stockout_delta?: number | null
    overall_business_safe?: boolean | null
    decision?: string | null
    promotion_comparison?: {
        promoted?: boolean
        reason?: string
        gate_checks?: Record<string, boolean>
    } | null
    [key: string]: unknown
}

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
    results: ExperimentResults | null
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
    rationale?: string
}

export interface RunExperimentPayload {
    experimentId: string
    dataDir?: string
    holdoutDays?: number
    maxRows?: number
    maxChallengers?: number
}

export interface ExperimentRunExecution {
    status: string
    experiment_id: string
    experiment_status: ExperimentStatus
    baseline_version: string | null
    experimental_version: string
    comparison: {
        promoted: boolean
        reason: string
        gate_checks: Record<string, boolean>
        decision?: Record<string, unknown>
        candidate_mae?: number | null
        champion_mae?: number | null
        candidate_wape?: number | null
        champion_wape?: number | null
        candidate_mase?: number | null
        champion_mase?: number | null
    }
    report: {
        baseline: {
            holdout_metrics: Record<string, number | string | boolean | null>
            lineage_metadata: Record<string, unknown>
        }
        challenger: {
            holdout_metrics: Record<string, number | string | boolean | null>
            lineage_metadata: Record<string, unknown>
            segment_summary?: Record<string, unknown> | null
        }
        experiment: {
            experiment_name: string
            hypothesis: string
            experiment_type: ExperimentType
            decision: string
            decision_rationale: string
        }
    }
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
    mapping_confirmed?: boolean
    mapping_coverage?: {
        locations_total?: number
        locations_mapped?: number
        catalog_total?: number
        catalog_mapped?: number
        [key: string]: number | undefined
    }
    unmapped_location_ids?: string[]
    unmapped_catalog_ids?: string[]
}

export interface SyncHealthResponse {
    sources: SyncHealth[]
    overall_health: 'healthy' | 'degraded'
    checked_at: string
}

export interface ReplenishmentRecommendation {
    recommendation_id: string
    customer_id: string
    store_id: string
    product_id: string
    supplier_id: string | null
    linked_po_id: string | null
    status: string
    forecast_model_version: string
    policy_version: string
    horizon_days: number
    forecast_start_date: string
    forecast_end_date: string
    recommended_quantity: number
    quantity_available: number
    quantity_on_order: number
    inventory_position: number
    reorder_point: number
    safety_stock: number
    economic_order_qty: number
    lead_time_days: number
    service_level: number
    estimated_unit_cost: number | null
    estimated_total_cost: number | null
    source_type: string | null
    source_id: string | null
    source_name: string | null
    horizon_demand_mean: number
    horizon_demand_lower: number | null
    horizon_demand_upper: number | null
    lead_time_demand_mean: number
    lead_time_demand_upper: number | null
    interval_method: string | null
    calibration_status: string | null
    interval_coverage: number | null
    no_order_stockout_risk: string
    order_overstock_risk: string
    recommendation_rationale: Record<string, unknown>
    created_at: string
}

export interface RecommendationImpact {
    as_of_date: string
    total_recommendations: number
    accepted_count: number
    edited_count: number
    rejected_count: number
    closed_outcomes: number
    closed_outcomes_confidence: string
    provisional_outcomes: number
    provisional_outcomes_confidence: string
    forecast_closeout: {
        measurement_basis: string
        average_forecast_error_abs: number | null
        average_forecast_error_abs_confidence: string
        stockout_events: number
        stockout_events_confidence: string
        overstock_events: number
        overstock_events_confidence: string
    }
    recommendation_policy: {
        measurement_basis: string
        decision_quantity_basis: string
        evaluated_decisions: number
        evaluated_decisions_confidence: string
        net_policy_value: number | null
        net_policy_value_confidence: string
        avoided_stockout_value: number | null
        avoided_stockout_value_confidence: string
        incremental_overstock_cost: number | null
        incremental_overstock_cost_confidence: string
    }
}

export interface RecommendationQueueGenerationResult {
    as_of_date: string
    horizon_days: number
    model_version: string | null
    candidate_pairs: number
    generated_count: number
    skipped_count: number
    skipped_reasons: Record<string, number>
    open_queue_count: number
}

export interface RecommendationAcceptPayload {
    reason_code?: string
    notes?: string
}

export interface RecommendationEditPayload {
    quantity: number
    reason_code: string
    notes?: string
}

export interface RecommendationRejectPayload {
    reason_code: string
    notes?: string
}

export interface DataReadinessSnapshot {
    history_days?: number
    store_count?: number
    product_count?: number
    candidate_version?: string | null
    champion_version?: string | null
    candidate_accuracy_samples?: number
    champion_accuracy_samples?: number
    thresholds?: {
        min_history_days?: number
        min_store_count?: number
        min_product_count?: number
        min_accuracy_samples?: number
        accuracy_window_days?: number
    }
    [key: string]: unknown
}

export interface DataReadiness {
    state: string
    reason_code: string
    snapshot: DataReadinessSnapshot
}

export interface ReplenishmentSimulationPolicyRow {
    policy_name: string
    stockout_days: number
    lost_sales_units: number
    lost_sales_proxy: number
    overstock_units: number
    overstock_dollars: number
    service_level: number
    po_count: number
    combined_cost_proxy: number
}

export interface ReplenishmentSimulationReport {
    dataset_id: string
    dataset_snapshot_id?: string | null
    simulation_scope: string
    impact_confidence: string
    claim_boundary: string
    stockout_label_boundary: string
    inventory_assumptions_confidence: string
    po_assumptions_confidence: string
    lead_time_assumptions_confidence: string
    cost_assumptions_confidence: string
    model_version?: string | null
    policy_version?: string | null
    policy_versions: string[]
    rows_used: number
    series_used: number
    history_start: string
    history_end: string
    replay_start: string
    replay_end: string
    results: ReplenishmentSimulationPolicyRow[]
}
