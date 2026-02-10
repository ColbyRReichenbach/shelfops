/**
 * React Query hooks for ShelfOps API endpoints.
 * Replaces all MOCK_ data with live API calls.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useApi } from '@/lib/api'
import type {
    Product, Store, Alert, AlertSummary,
    Forecast, ForecastAccuracy, Integration,
    InventoryItem, InventorySummary,
} from '@/lib/types'

// ─── Products ──────────────────────────────────────────────────────────────

export function useProducts(category?: string, status?: string) {
    const api = useApi()
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (status) params.set('status', status)
    const qs = params.toString()

    return useQuery({
        queryKey: ['products', category, status],
        queryFn: () => api.get<Product[]>(`/api/v1/products/${qs ? `?${qs}` : ''}`),
    })
}

export function useProduct(productId: string | undefined) {
    const api = useApi()
    return useQuery({
        queryKey: ['product', productId],
        queryFn: () => api.get<Product>(`/api/v1/products/${productId}`),
        enabled: !!productId,
    })
}

// ─── Stores ────────────────────────────────────────────────────────────────

export function useStores(status?: string) {
    const api = useApi()
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    const qs = params.toString()

    return useQuery({
        queryKey: ['stores', status],
        queryFn: () => api.get<Store[]>(`/api/v1/stores/${qs ? `?${qs}` : ''}`),
    })
}

// ─── Alerts ────────────────────────────────────────────────────────────────

export function useAlerts(filters?: {
    status?: string
    severity?: string
    store_id?: string
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.status) params.set('status', filters.status)
    if (filters?.severity) params.set('severity', filters.severity)
    if (filters?.store_id) params.set('store_id', filters.store_id)
    const qs = params.toString()

    return useQuery({
        queryKey: ['alerts', filters],
        queryFn: () => api.get<Alert[]>(`/api/v1/alerts/${qs ? `?${qs}` : ''}`),
    })
}

export function useAlertSummary(storeId?: string) {
    const api = useApi()
    const params = new URLSearchParams()
    if (storeId) params.set('store_id', storeId)
    const qs = params.toString()

    return useQuery({
        queryKey: ['alert-summary', storeId],
        queryFn: () => api.get<AlertSummary>(`/api/v1/alerts/summary${qs ? `?${qs}` : ''}`),
    })
}

export function useAcknowledgeAlert() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (alertId: string) =>
            api.patch<Alert>(`/api/v1/alerts/${alertId}/acknowledge`, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['alerts'] })
            queryClient.invalidateQueries({ queryKey: ['alert-summary'] })
        },
    })
}

export function useResolveAlert() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ alertId, notes }: { alertId: string; notes?: string }) =>
            api.patch<Alert>(`/api/v1/alerts/${alertId}/resolve`, {
                action_type: 'resolved',
                notes,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['alerts'] })
            queryClient.invalidateQueries({ queryKey: ['alert-summary'] })
        },
    })
}

// ─── Forecasts ─────────────────────────────────────────────────────────────

export function useForecasts(filters?: {
    store_id?: string
    product_id?: string
    start_date?: string
    end_date?: string
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.store_id) params.set('store_id', filters.store_id)
    if (filters?.product_id) params.set('product_id', filters.product_id)
    if (filters?.start_date) params.set('start_date', filters.start_date)
    if (filters?.end_date) params.set('end_date', filters.end_date)
    const qs = params.toString()

    return useQuery({
        queryKey: ['forecasts', filters],
        queryFn: () => api.get<Forecast[]>(`/api/v1/forecasts/${qs ? `?${qs}` : ''}`),
    })
}

// ─── Integrations ─────────────────────────────────────────────────────────

export function useIntegrations() {
    const api = useApi()
    return useQuery({
        queryKey: ['integrations'],
        queryFn: () => api.get<Integration[]>('/api/v1/integrations/'),
    })
}

export function useDisconnectIntegration() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (integrationId: string) =>
            api.delete(`/api/v1/integrations/${integrationId}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['integrations'] })
        },
    })
}

// ─── Inventory ────────────────────────────────────────────────────────────

export function useInventory(filters?: {
    store_id?: string
    status?: string
    category?: string
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.store_id) params.set('store_id', filters.store_id)
    if (filters?.status) params.set('status', filters.status)
    if (filters?.category) params.set('category', filters.category)
    const qs = params.toString()

    return useQuery({
        queryKey: ['inventory', filters],
        queryFn: () => api.get<InventoryItem[]>(`/api/v1/inventory/${qs ? `?${qs}` : ''}`),
    })
}

export function useInventorySummary(storeId?: string) {
    const api = useApi()
    const params = new URLSearchParams()
    if (storeId) params.set('store_id', storeId)
    const qs = params.toString()

    return useQuery({
        queryKey: ['inventory-summary', storeId],
        queryFn: () => api.get<InventorySummary>(`/api/v1/inventory/summary${qs ? `?${qs}` : ''}`),
    })
}

// ─── Forecast Accuracy ────────────────────────────────────────────────────

export function useForecastAccuracy(storeId?: string) {
    const api = useApi()
    const params = new URLSearchParams()
    if (storeId) params.set('store_id', storeId)
    const qs = params.toString()

    return useQuery({
        queryKey: ['forecast-accuracy', storeId],
        queryFn: () => api.get<ForecastAccuracy[]>(`/api/v1/forecasts/accuracy${qs ? `?${qs}` : ''}`),
    })
}
