/**
 * React Query hooks for ShelfOps API endpoints.
 * Replaces all MOCK_ data with live API calls.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useApi } from '@/lib/api'
import type {
    Product, Store, Alert, AlertSummary, ReorderAlertContext,
    Forecast, ForecastAccuracy, ForecastAccuracyTrend, ForecastAccuracyByCategory, Integration,
    InventoryItem, InventorySummary, ModelHealthResponse,
    ModelHistoryItem, BacktestPoint, MLAlertItem, MLAlertStats,
    MLAlertActionResponse, MLAlertReadResponse, ExperimentItem,
    ProposeExperimentRequest, ProposeExperimentResponse,
    AlertEffectiveness, AnomalyEffectiveness, ROIResponse,
    AnomalyStats,
    PromoteModelResponse,
    PurchaseOrder, PurchaseOrderSummary, PODecision,
    OrderFromAlertRequest, OrderFromAlertResponse,
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

export function useReorderAlertContext(lookbackDays = 28, statuses: string[] = ['open', 'acknowledged']) {
    const api = useApi()
    const params = new URLSearchParams()
    params.set('lookback_days', String(lookbackDays))
    params.set('statuses', statuses.join(','))
    const qs = params.toString()

    return useQuery({
        queryKey: ['alerts', 'reorder-context', lookbackDays, statuses.join(',')],
        queryFn: () => api.get<ReorderAlertContext[]>(`/api/v1/alerts/reorder-context?${qs}`),
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

export function useDismissAlert() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (alertId: string) =>
            api.patch<Alert>(`/api/v1/alerts/${alertId}/dismiss`, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['alerts'] })
            queryClient.invalidateQueries({ queryKey: ['alert-summary'] })
        },
    })
}

export function useOrderFromAlert() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ alertId, payload }: { alertId: string; payload: OrderFromAlertRequest }) =>
            api.post<OrderFromAlertResponse>(`/api/v1/alerts/${alertId}/order`, payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['alerts'] })
            queryClient.invalidateQueries({ queryKey: ['alert-summary'] })
            queryClient.invalidateQueries({ queryKey: ['purchase-orders'] })
        },
    })
}

// ─── Outcomes ──────────────────────────────────────────────────────────────

export function useRecordAlertOutcome() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ alertId, outcome, outcome_notes, prevented_loss }: { alertId: string; outcome: string; outcome_notes?: string; prevented_loss?: number }) =>
            api.post(`/api/v1/outcomes/alert/${alertId}`, {
                outcome,
                outcome_notes,
                prevented_loss,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['alerts'] })
            queryClient.invalidateQueries({ queryKey: ['alert-summary'] })
            queryClient.invalidateQueries({ queryKey: ['mlops', 'outcomes'] })
        },
    })
}

export function useRecordAnomalyOutcome() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ anomalyId, outcome, outcome_notes, action_taken }: { anomalyId: string; outcome: string; outcome_notes?: string; action_taken?: string }) =>
            api.post(`/api/v1/outcomes/anomaly/${anomalyId}`, {
                outcome,
                outcome_notes,
                action_taken,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['alerts'] }) // Anomalies might show up as alerts
            queryClient.invalidateQueries({ queryKey: ['mlops', 'outcomes'] })
        },
    })
}

// ─── Purchase Orders ───────────────────────────────────────────────────────

export function usePurchaseOrders(filters?: {
    status?: string
    store_id?: string
    product_id?: string
    skip?: number
    limit?: number
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.status) params.set('status', filters.status)
    if (filters?.store_id) params.set('store_id', filters.store_id)
    if (filters?.product_id) params.set('product_id', filters.product_id)
    if (filters?.skip != null) params.set('skip', String(filters.skip))
    if (filters?.limit != null) params.set('limit', String(filters.limit))
    const qs = params.toString()

    return useQuery({
        queryKey: ['purchase-orders', filters],
        queryFn: () => api.get<PurchaseOrder[]>(`/api/v1/purchase-orders/${qs ? `?${qs}` : ''}`),
    })
}

export function useSuggestedPurchaseOrders(limit = 50) {
    const api = useApi()
    return useQuery({
        queryKey: ['purchase-orders', 'suggested', limit],
        queryFn: () => api.get<PurchaseOrder[]>(`/api/v1/purchase-orders/suggested?limit=${limit}`),
    })
}

export function usePurchaseOrderSummary() {
    const api = useApi()
    return useQuery({
        queryKey: ['purchase-orders', 'summary'],
        queryFn: () => api.get<PurchaseOrderSummary>('/api/v1/purchase-orders/summary'),
    })
}

export function useApprovePurchaseOrder() {
    const api = useApi()
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({
            poId,
            quantity,
            reason_code,
            notes,
        }: {
            poId: string
            quantity?: number
            reason_code?: string
            notes?: string
        }) => api.post<PurchaseOrder>(`/api/v1/purchase-orders/${poId}/approve`, { quantity, reason_code, notes }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['purchase-orders'] })
        },
    })
}

export function useRejectPurchaseOrder() {
    const api = useApi()
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({
            poId,
            reason_code,
            notes,
        }: {
            poId: string
            reason_code: string
            notes?: string
        }) => api.post<PurchaseOrder>(`/api/v1/purchase-orders/${poId}/reject`, { reason_code, notes }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['purchase-orders'] })
        },
    })
}

export function useReceivePurchaseOrder() {
    const api = useApi()
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({
            poId,
            received_qty,
            received_date,
            total_received_cost,
            notes,
        }: {
            poId: string
            received_qty: number
            received_date?: string
            total_received_cost?: number
            notes?: string
        }) =>
            api.post<PurchaseOrder>(`/api/v1/purchase-orders/${poId}/receive`, {
                received_qty,
                received_date,
                total_received_cost,
                notes,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['purchase-orders'] })
            queryClient.invalidateQueries({ queryKey: ['inventory'] })
        },
    })
}

export function usePoDecisions(poId: string | null | undefined) {
    const api = useApi()
    return useQuery({
        queryKey: ['purchase-orders', 'decisions', poId],
        queryFn: () => api.get<PODecision[]>(`/api/v1/purchase-orders/${poId}/decisions`),
        enabled: !!poId,
    })
}

// ─── Forecasts ─────────────────────────────────────────────────────────────

export function useForecasts(filters?: {
    store_id?: string
    product_id?: string
    start_date?: string
    end_date?: string
    limit?: number
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.store_id) params.set('store_id', filters.store_id)
    if (filters?.product_id) params.set('product_id', filters.product_id)
    if (filters?.start_date) params.set('start_date', filters.start_date)
    if (filters?.end_date) params.set('end_date', filters.end_date)
    if (filters?.limit) params.set('limit', String(filters.limit))
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

export function useForecastAccuracyTrend(filters?: {
    store_id?: string
    product_id?: string
    category?: string
    model_version?: string
    start_date?: string
    end_date?: string
    limit?: number
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.store_id) params.set('store_id', filters.store_id)
    if (filters?.product_id) params.set('product_id', filters.product_id)
    if (filters?.category) params.set('category', filters.category)
    if (filters?.model_version) params.set('model_version', filters.model_version)
    if (filters?.start_date) params.set('start_date', filters.start_date)
    if (filters?.end_date) params.set('end_date', filters.end_date)
    if (filters?.limit) params.set('limit', String(filters.limit))
    const qs = params.toString()

    return useQuery({
        queryKey: ['forecast-accuracy-trend', filters],
        queryFn: () => api.get<ForecastAccuracyTrend[]>(`/api/v1/forecasts/accuracy/trend${qs ? `?${qs}` : ''}`),
    })
}

export function useForecastAccuracyByCategory(filters?: {
    store_id?: string
    model_version?: string
    start_date?: string
    end_date?: string
    limit?: number
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.store_id) params.set('store_id', filters.store_id)
    if (filters?.model_version) params.set('model_version', filters.model_version)
    if (filters?.start_date) params.set('start_date', filters.start_date)
    if (filters?.end_date) params.set('end_date', filters.end_date)
    if (filters?.limit) params.set('limit', String(filters.limit))
    const qs = params.toString()

    return useQuery({
        queryKey: ['forecast-accuracy-by-category', filters],
        queryFn: () => api.get<ForecastAccuracyByCategory[]>(`/api/v1/forecasts/accuracy/by-category${qs ? `?${qs}` : ''}`),
    })
}

// ─── MLOps ─────────────────────────────────────────────────────────────────

export function useModelHealth() {
    const api = useApi()
    return useQuery({
        queryKey: ['mlops', 'health'],
        queryFn: () => api.get<ModelHealthResponse>('/models/health'),
    })
}

export function useModelHistory(limit = 20) {
    const api = useApi()
    return useQuery({
        queryKey: ['mlops', 'history', limit],
        queryFn: () => api.get<ModelHistoryItem[]>(`/models/history?limit=${limit}`),
    })
}

export function useModelBacktest(version: string | null | undefined, days = 90) {
    const api = useApi()
    return useQuery({
        queryKey: ['mlops', 'backtest', version, days],
        queryFn: () => api.get<BacktestPoint[]>(`/models/backtest/${version}?days=${days}`),
        enabled: !!version,
    })
}

export function usePromoteModel() {
    const api = useApi()
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (version: string) =>
            api.post<PromoteModelResponse>(`/models/${version}/promote`, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['mlops', 'health'] })
            queryClient.invalidateQueries({ queryKey: ['mlops', 'history'] })
            queryClient.invalidateQueries({ queryKey: ['mlops', 'alerts'] })
        },
    })
}

export function useMlAlerts(filters?: {
    status?: string
    severity?: string
    alert_type?: string
    limit?: number
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.status) params.set('status', filters.status)
    if (filters?.severity) params.set('severity', filters.severity)
    if (filters?.alert_type) params.set('alert_type', filters.alert_type)
    params.set('limit', String(filters?.limit ?? 50))
    const qs = params.toString()

    return useQuery({
        queryKey: ['mlops', 'alerts', filters],
        queryFn: () => api.get<MLAlertItem[]>(`/ml-alerts?${qs}`),
    })
}

export function useMlAlertStats() {
    const api = useApi()
    return useQuery({
        queryKey: ['mlops', 'alert-stats'],
        queryFn: () => api.get<MLAlertStats>('/ml-alerts/stats'),
    })
}

export function useMarkMlAlertRead() {
    const api = useApi()
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (alertId: string) =>
            api.patch<MLAlertReadResponse>(`/ml-alerts/${alertId}/read`, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['mlops', 'alerts'] })
            queryClient.invalidateQueries({ queryKey: ['mlops', 'alert-stats'] })
        },
    })
}

export function useActOnMlAlert() {
    const api = useApi()
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: ({
            alertId,
            action,
            notes,
        }: {
            alertId: string
            action: 'approve' | 'dismiss'
            notes?: string
        }) =>
            api.patch<MLAlertActionResponse>(`/ml-alerts/${alertId}/action`, { action, notes }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['mlops', 'alerts'] })
            queryClient.invalidateQueries({ queryKey: ['mlops', 'alert-stats'] })
            queryClient.invalidateQueries({ queryKey: ['mlops', 'health'] })
            queryClient.invalidateQueries({ queryKey: ['mlops', 'history'] })
        },
    })
}

export function useExperiments(filters?: {
    status?: string
    experiment_type?: string
    limit?: number
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.status) params.set('status', filters.status)
    if (filters?.experiment_type) params.set('experiment_type', filters.experiment_type)
    params.set('limit', String(filters?.limit ?? 50))
    const qs = params.toString()

    return useQuery({
        queryKey: ['mlops', 'experiments', filters],
        queryFn: () => api.get<ExperimentItem[]>(`/experiments?${qs}`),
    })
}

export function useProposeExperiment() {
    const api = useApi()
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (payload: ProposeExperimentRequest) =>
            api.post<ProposeExperimentResponse>('/experiments', payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['mlops', 'experiments'] })
            queryClient.invalidateQueries({ queryKey: ['mlops', 'alerts'] })
        },
    })
}

export function useAlertEffectiveness(days = 30) {
    const api = useApi()
    return useQuery({
        queryKey: ['mlops', 'outcomes', 'alerts', days],
        queryFn: () => api.get<AlertEffectiveness>(`/outcomes/alerts/effectiveness?days=${days}`),
    })
}

export function useAnomalyEffectiveness(days = 30) {
    const api = useApi()
    return useQuery({
        queryKey: ['mlops', 'outcomes', 'anomalies', days],
        queryFn: () => api.get<AnomalyEffectiveness>(`/outcomes/anomalies/effectiveness?days=${days}`),
    })
}

export function useAlertRoi(days = 90) {
    const api = useApi()
    return useQuery({
        queryKey: ['mlops', 'outcomes', 'roi', days],
        queryFn: () => api.get<ROIResponse>(`/outcomes/roi?days=${days}`),
    })
}

export function useAnomalyStats(days = 7) {
    const api = useApi()
    return useQuery({
        queryKey: ['mlops', 'anomalies', 'stats', days],
        queryFn: () => api.get<AnomalyStats>(`/anomalies/stats?days=${days}`),
    })
}
