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
