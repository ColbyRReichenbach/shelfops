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
    ProductMutationPayload, StoreMutationPayload,
    MLModel, BacktestEntry, ExperimentRun,
    ExperimentLedgerEntry, ProposeExperimentPayload, ProposeExperimentResponse, ApproveExperimentPayload,
    RunExperimentPayload, ExperimentRunExecution,
    SHAPFeature, MLHealth, MLEffectiveness, ModelHistoryEntry, RuntimeModelHealth, SyncHealthResponse,
    ReplenishmentRecommendation, RecommendationImpact, RecommendationAcceptPayload, RecommendationEditPayload,
    RecommendationRejectPayload, DataReadiness, ReplenishmentSimulationReport,
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

export function useCreateProduct() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (payload: ProductMutationPayload) =>
            api.post<Product>('/api/v1/products/', payload),
        onSuccess: (product) => {
            queryClient.invalidateQueries({ queryKey: ['products'] })
            queryClient.invalidateQueries({ queryKey: ['product', product.product_id] })
        },
    })
}

export function useUpdateProduct() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ productId, payload }: { productId: string; payload: Partial<ProductMutationPayload> }) =>
            api.patch<Product>(`/api/v1/products/${productId}`, payload),
        onSuccess: (product) => {
            queryClient.invalidateQueries({ queryKey: ['products'] })
            queryClient.invalidateQueries({ queryKey: ['product', product.product_id] })
        },
    })
}

export function useDeleteProduct() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (productId: string) =>
            api.delete<void>(`/api/v1/products/${productId}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['products'] })
        },
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

export function useStore(storeId: string | undefined) {
    const api = useApi()
    return useQuery({
        queryKey: ['store', storeId],
        queryFn: () => api.get<Store>(`/api/v1/stores/${storeId}`),
        enabled: !!storeId,
    })
}

export function useCreateStore() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (payload: StoreMutationPayload) =>
            api.post<Store>('/api/v1/stores/', payload),
        onSuccess: (store) => {
            queryClient.invalidateQueries({ queryKey: ['stores'] })
            queryClient.invalidateQueries({ queryKey: ['store', store.store_id] })
        },
    })
}

export function useUpdateStore() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ storeId, payload }: { storeId: string; payload: Partial<StoreMutationPayload> }) =>
            api.patch<Store>(`/api/v1/stores/${storeId}`, payload),
        onSuccess: (store) => {
            queryClient.invalidateQueries({ queryKey: ['stores'] })
            queryClient.invalidateQueries({ queryKey: ['store', store.store_id] })
        },
    })
}

export function useDeleteStore() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (storeId: string) =>
            api.delete<void>(`/api/v1/stores/${storeId}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['stores'] })
        },
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

// ─── ML Ops ──────────────────────────────────────────────────────────────

export function useMLModels(modelName?: string, status?: string) {
    const api = useApi()
    const params = new URLSearchParams()
    if (modelName) params.set('model_name', modelName)
    if (status) params.set('status', status)
    const qs = params.toString()

    return useQuery({
        queryKey: ['ml-models', modelName, status],
        queryFn: () => api.get<MLModel[]>(`/api/v1/ml/models${qs ? `?${qs}` : ''}`),
    })
}

export function useModelSHAP(version: string) {
    const api = useApi()
    return useQuery({
        queryKey: ['ml-shap', version],
        queryFn: () => api.get<{ version: string; features: SHAPFeature[] }>(`/api/v1/ml/models/${version}/shap`),
        enabled: !!version,
    })
}

export function useBacktests(days = 90, modelName?: string) {
    const api = useApi()
    const params = new URLSearchParams()
    params.set('days', String(days))
    if (modelName) params.set('model_name', modelName)
    const qs = params.toString()

    return useQuery({
        queryKey: ['ml-backtests', days, modelName],
        queryFn: () => api.get<BacktestEntry[]>(`/api/v1/ml/backtests?${qs}`),
    })
}

export function useExperiments(modelName?: string) {
    const api = useApi()
    const params = new URLSearchParams()
    if (modelName) params.set('model_name', modelName)
    const qs = params.toString()

    return useQuery({
        queryKey: ['ml-experiments', modelName],
        queryFn: () => api.get<ExperimentRun[]>(`/api/v1/ml/experiments${qs ? `?${qs}` : ''}`),
    })
}

export function useExperimentLedger(filters?: {
    modelName?: string
    status?: string
    experimentType?: string
    limit?: number
}) {
    const api = useApi()
    const params = new URLSearchParams()
    if (filters?.modelName) params.set('model_name', filters.modelName)
    if (filters?.status) params.set('status', filters.status)
    if (filters?.experimentType) params.set('experiment_type', filters.experimentType)
    if (filters?.limit) params.set('limit', String(filters.limit))
    const qs = params.toString()

    return useQuery({
        queryKey: ['experiment-ledger', filters],
        queryFn: () => api.get<ExperimentLedgerEntry[]>(`/api/v1/experiments${qs ? `?${qs}` : ''}`),
    })
}

export function useProposeExperiment() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (payload: ProposeExperimentPayload) =>
            api.post<ProposeExperimentResponse>('/api/v1/experiments', payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['experiment-ledger'] })
        },
    })
}

export function useApproveExperiment() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ experimentId, rationale }: ApproveExperimentPayload) =>
            api.patch(`/api/v1/experiments/${experimentId}/approve`, { rationale }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['experiment-ledger'] })
        },
    })
}

export function useRunExperiment() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ experimentId, dataDir, holdoutDays, maxRows, maxChallengers }: RunExperimentPayload) =>
            api.post<ExperimentRunExecution>(`/api/v1/experiments/${experimentId}/run`, {
                data_dir: dataDir,
                holdout_days: holdoutDays,
                max_rows: maxRows,
                max_challengers: maxChallengers,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['experiment-ledger'] })
            queryClient.invalidateQueries({ queryKey: ['ml-models'] })
            queryClient.invalidateQueries({ queryKey: ['model-history'] })
            queryClient.invalidateQueries({ queryKey: ['runtime-model-health'] })
            queryClient.invalidateQueries({ queryKey: ['ml-health'] })
        },
    })
}

export function useInterpretExperiment() {
    const api = useApi()
    return useMutation({
        mutationFn: (experimentId: string) =>
            api.post<{
                experiment_id: string
                cached: boolean
                results_summary: string
                why_it_worked: string
                next_hypothesis: string
                model: string
            }>(`/api/v1/experiments/${experimentId}/interpret`, {}),
    })
}

export function useMLHealth() {
    const api = useApi()
    return useQuery({
        queryKey: ['ml-health'],
        queryFn: () => api.get<MLHealth>('/api/v1/ml/health'),
    })
}

export function useModelHistory(limit = 20) {
    const api = useApi()
    const params = new URLSearchParams()
    params.set('limit', String(limit))

    return useQuery({
        queryKey: ['model-history', limit],
        queryFn: () => api.get<ModelHistoryEntry[]>(`/api/v1/ml/models/history?${params.toString()}`),
    })
}

export function useRuntimeModelHealth() {
    const api = useApi()
    return useQuery({
        queryKey: ['runtime-model-health'],
        queryFn: () => api.get<RuntimeModelHealth>('/api/v1/ml/models/health'),
    })
}

export function useMLEffectiveness(windowDays = 30, modelName = 'demand_forecast') {
    const api = useApi()
    const params = new URLSearchParams()
    params.set('window_days', String(windowDays))
    params.set('model_name', modelName)

    return useQuery({
        queryKey: ['ml-effectiveness', windowDays, modelName],
        queryFn: () => api.get<MLEffectiveness>(`/api/v1/ml/effectiveness?${params.toString()}`),
    })
}

export function useSyncHealth() {
    const api = useApi()
    return useQuery({
        queryKey: ['sync-health'],
        queryFn: async () => {
            const response = await api.get<SyncHealthResponse>('/api/v1/integrations/sync-health')
            return response.sources
        },
    })
}

// ─── Replenishment ───────────────────────────────────────────────────────

export function useRecommendationQueue(status = 'open', limit = 50) {
    const api = useApi()
    const params = new URLSearchParams()
    params.set('status', status)
    params.set('limit', String(limit))

    return useQuery({
        queryKey: ['replenishment-queue', status, limit],
        queryFn: () => api.get<ReplenishmentRecommendation[]>(`/api/v1/replenishment/queue?${params.toString()}`),
    })
}

export function useRecommendationDetail(recommendationId: string | undefined) {
    const api = useApi()
    return useQuery({
        queryKey: ['replenishment-recommendation', recommendationId],
        queryFn: () => api.get<ReplenishmentRecommendation>(`/api/v1/replenishment/recommendations/${recommendationId}`),
        enabled: !!recommendationId,
    })
}

export function useRecommendationImpact() {
    const api = useApi()
    return useQuery({
        queryKey: ['replenishment-impact'],
        queryFn: () => api.get<RecommendationImpact>('/api/v1/replenishment/impact'),
    })
}

export function useAcceptRecommendation() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ recommendationId, payload }: { recommendationId: string; payload: RecommendationAcceptPayload }) =>
            api.post<ReplenishmentRecommendation>(
                `/api/v1/replenishment/recommendations/${recommendationId}/accept`,
                payload,
            ),
        onSuccess: recommendation => {
            queryClient.invalidateQueries({ queryKey: ['replenishment-queue'] })
            queryClient.invalidateQueries({ queryKey: ['replenishment-impact'] })
            queryClient.invalidateQueries({ queryKey: ['replenishment-recommendation', recommendation.recommendation_id] })
        },
    })
}

export function useEditRecommendation() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ recommendationId, payload }: { recommendationId: string; payload: RecommendationEditPayload }) =>
            api.post<ReplenishmentRecommendation>(
                `/api/v1/replenishment/recommendations/${recommendationId}/edit`,
                payload,
            ),
        onSuccess: recommendation => {
            queryClient.invalidateQueries({ queryKey: ['replenishment-queue'] })
            queryClient.invalidateQueries({ queryKey: ['replenishment-impact'] })
            queryClient.invalidateQueries({ queryKey: ['replenishment-recommendation', recommendation.recommendation_id] })
        },
    })
}

export function useRejectRecommendation() {
    const api = useApi()
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ recommendationId, payload }: { recommendationId: string; payload: RecommendationRejectPayload }) =>
            api.post<ReplenishmentRecommendation>(
                `/api/v1/replenishment/recommendations/${recommendationId}/reject`,
                payload,
            ),
        onSuccess: recommendation => {
            queryClient.invalidateQueries({ queryKey: ['replenishment-queue'] })
            queryClient.invalidateQueries({ queryKey: ['replenishment-impact'] })
            queryClient.invalidateQueries({ queryKey: ['replenishment-recommendation', recommendation.recommendation_id] })
        },
    })
}

// ─── Data Readiness ──────────────────────────────────────────────────────

export function useDataReadiness() {
    const api = useApi()
    return useQuery({
        queryKey: ['data-readiness'],
        queryFn: () => api.get<DataReadiness>('/api/v1/data/readiness'),
    })
}

export function useReplenishmentSimulation() {
    const api = useApi()
    return useQuery({
        queryKey: ['replenishment-simulation'],
        queryFn: () => api.get<ReplenishmentSimulationReport>('/api/v1/simulations/replenishment'),
    })
}
