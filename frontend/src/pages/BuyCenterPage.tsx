import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import {
    useAlerts,
    useDismissAlert,
    useOrderFromAlert,
    useProducts,
    usePurchaseOrderSummary,
    usePurchaseOrders,
    useReorderAlertContext,
    useStores,
} from '@/hooks/useShelfOps'
import type { Alert } from '@/lib/types'
import OrderApprovalModal from '@/components/buy/OrderApprovalModal'
import PurchaseOrderSummaryCards from '@/components/buy/PurchaseOrderSummaryCards'
import PurchaseOrderTable from '@/components/buy/PurchaseOrderTable'
import ReorderQueueCard from '@/components/buy/ReorderQueueCard'

type PoStatusFilter = 'all' | 'suggested' | 'approved' | 'ordered' | 'received' | 'cancelled'

export default function BuyCenterPage() {
    const [searchParams, setSearchParams] = useSearchParams()
    const [poStatusFilter, setPoStatusFilter] = useState<PoStatusFilter>('all')
    const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)
    const [pendingDismissAlertId, setPendingDismissAlertId] = useState<string | null>(null)

    const { data: openAlerts = [], refetch: refetchOpen, isLoading: loadingOpen } = useAlerts({ status: 'open' })
    const { data: acknowledgedAlerts = [], refetch: refetchAcknowledged, isLoading: loadingAck } = useAlerts({
        status: 'acknowledged',
    })
    const { data: products = [], refetch: refetchProducts } = useProducts()
    const { data: stores = [], refetch: refetchStores } = useStores()
    const { data: reorderContext = [], refetch: refetchReorderContext } = useReorderAlertContext(28, [
        'open',
        'acknowledged',
    ])

    const {
        data: filteredPurchaseOrders = [],
        refetch: refetchFilteredPos,
        isLoading: loadingPos,
    } = usePurchaseOrders({
        status: poStatusFilter === 'all' ? undefined : poStatusFilter,
        limit: 200,
    })
    const { data: allPurchaseOrders = [], refetch: refetchAllPos } = usePurchaseOrders({ limit: 200 })
    const { data: poSummary, refetch: refetchSummary } = usePurchaseOrderSummary()

    const dismissAlert = useDismissAlert()
    const orderFromAlert = useOrderFromAlert()

    const highlightPoId = searchParams.get('po_id')
    const highlightAlertId = searchParams.get('alert_id')

    const productNameById = useMemo<Record<string, string>>(() => {
        const map: Record<string, string> = {}
        for (const product of products) {
            map[product.product_id] = product.name
        }
        return map
    }, [products])

    const productUnitCostById = useMemo<Record<string, number | null>>(() => {
        const map: Record<string, number | null> = {}
        for (const product of products) {
            map[product.product_id] = product.unit_cost
        }
        return map
    }, [products])

    const storeNameById = useMemo<Record<string, string>>(() => {
        const map: Record<string, string> = {}
        for (const store of stores) {
            map[store.store_id] = store.name
        }
        return map
    }, [stores])

    const reorderContextByAlertId = useMemo(() => {
        return new Map(reorderContext.map((row) => [row.alert_id, row]))
    }, [reorderContext])

    const reorderQueue = useMemo(() => {
        const merged = [...openAlerts, ...acknowledgedAlerts]
        return merged.filter((alert) => alert.alert_type === 'reorder_recommended')
    }, [acknowledgedAlerts, openAlerts])

    const suggestedSpend = useMemo(() => {
        return reorderQueue.reduce((sum, alert) => {
            const suggestedQty = getAlertNumber(alert, 'suggested_qty')
            const unitCost = productUnitCostById[alert.product_id]
            if (suggestedQty == null || unitCost == null) return sum
            return sum + suggestedQty * unitCost
        }, 0)
    }, [productUnitCostById, reorderQueue])

    const approvedToday = useMemo(() => {
        const today = new Date()
        return allPurchaseOrders.filter((po) => {
            if (po.status !== 'approved' || !po.ordered_at) return false
            const ordered = new Date(po.ordered_at)
            return ordered.toDateString() === today.toDateString()
        }).length
    }, [allPurchaseOrders])

    const receivedThisWeek = useMemo(() => {
        const now = Date.now()
        const sevenDaysMs = 7 * 24 * 60 * 60 * 1000
        return allPurchaseOrders.filter((po) => {
            if (po.status !== 'received' || !po.received_at) return false
            const receivedAtMs = new Date(po.received_at).getTime()
            return now - receivedAtMs <= sevenDaysMs
        }).length
    }, [allPurchaseOrders])

    const isLoading = loadingOpen || loadingAck || loadingPos

    async function refreshAll() {
        await Promise.all([
            refetchOpen(),
            refetchAcknowledged(),
            refetchFilteredPos(),
            refetchAllPos(),
            refetchSummary(),
            refetchProducts(),
            refetchStores(),
            refetchReorderContext(),
        ])
    }

    async function handleConfirmOrder(payload: { quantity?: number; reason_code?: string; notes?: string }) {
        if (!selectedAlert) return
        const result = await orderFromAlert.mutateAsync({
            alertId: selectedAlert.alert_id,
            payload,
        })
        setSuccessMessage(`Order created: ${result.po.po_id.slice(0, 8)}`)
        const nextParams = new URLSearchParams(searchParams)
        nextParams.set('po_id', result.po.po_id)
        nextParams.delete('alert_id')
        setSearchParams(nextParams, { replace: true })
        setSelectedAlert(null)
    }

    async function handleDismiss(alertId: string) {
        setPendingDismissAlertId(alertId)
        try {
            await dismissAlert.mutateAsync(alertId)
        } finally {
            setPendingDismissAlertId(null)
        }
    }

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Buy Center</h1>
                    <p className="text-sm text-shelf-foreground/60 mt-1">
                        Convert AI reorder recommendations into auditable purchase decisions.
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-shelf-secondary/10 text-shelf-primary border border-shelf-primary/20 px-3 py-1 text-xs font-medium">
                        Internal Dispatch Mode
                    </span>
                    <button onClick={refreshAll} className="btn-secondary text-xs h-8 px-3 gap-1">
                        <RefreshCw className="h-3 w-3" />
                        Refresh
                    </button>
                </div>
            </div>

            {successMessage && (
                <div className="rounded-xl border border-green-200 bg-green-50 text-green-700 text-sm px-4 py-3">
                    {successMessage}
                </div>
            )}

            <PurchaseOrderSummaryCards
                openRecommendations={reorderQueue.length}
                approvedToday={approvedToday}
                suggestedSpend={suggestedSpend}
                receivedThisWeek={receivedThisWeek}
            />

            <div className="card border border-white/40 shadow-sm">
                <div className="flex items-center justify-between gap-3 mb-4">
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">AI Reorder Queue</h3>
                    <p className="text-xs text-shelf-foreground/50">
                        Suggested PO cost total: ${poSummary?.total_estimated_cost?.toFixed(2) ?? '0.00'}
                    </p>
                </div>

                {isLoading ? (
                    <p className="text-sm text-shelf-foreground/50">Loading reorder recommendations...</p>
                ) : reorderQueue.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-shelf-foreground/15 p-8 text-center">
                        <p className="text-sm text-shelf-foreground/60">No reorder recommendations right now.</p>
                        <Link to="/alerts" className="text-sm text-shelf-primary hover:underline mt-2 inline-block">
                            Go to Alerts
                        </Link>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {reorderQueue.map((alert) => {
                            const suggestedQty = getAlertNumber(alert, 'suggested_qty')
                            const currentStock = getAlertNumber(alert, 'current_stock')
                            const reorderPoint = getAlertNumber(alert, 'reorder_point')
                            const safetyStock = getAlertNumber(alert, 'safety_stock')
                            const unitCost = productUnitCostById[alert.product_id]
                            const estimatedCost =
                                suggestedQty != null && unitCost != null ? suggestedQty * unitCost : null
                            return (
                                <ReorderQueueCard
                                    key={alert.alert_id}
                                    alert={alert}
                                    productName={productNameById[alert.product_id] ?? `Product ${alert.product_id.slice(0, 8)}`}
                                    storeName={storeNameById[alert.store_id] ?? `Store ${alert.store_id.slice(0, 8)}`}
                                    currentStock={currentStock}
                                    reorderPoint={reorderPoint}
                                    safetyStock={safetyStock}
                                    suggestedQty={suggestedQty}
                                    estimatedCost={estimatedCost}
                                    velocityContext={reorderContextByAlertId.get(alert.alert_id)}
                                    highlighted={highlightAlertId === alert.alert_id}
                                    approvePending={orderFromAlert.isPending && selectedAlert?.alert_id === alert.alert_id}
                                    dismissPending={dismissAlert.isPending && pendingDismissAlertId === alert.alert_id}
                                    onApprove={setSelectedAlert}
                                    onDismiss={handleDismiss}
                                />
                            )
                        })}
                    </div>
                )}
            </div>

            <PurchaseOrderTable
                orders={filteredPurchaseOrders}
                isLoading={loadingPos}
                highlightedPoId={highlightPoId}
                statusFilter={poStatusFilter}
                onStatusFilterChange={setPoStatusFilter}
                productNameById={productNameById}
                storeNameById={storeNameById}
            />

            <OrderApprovalModal
                open={selectedAlert != null}
                alert={selectedAlert}
                productName={
                    selectedAlert ? productNameById[selectedAlert.product_id] ?? selectedAlert.product_id.slice(0, 8) : ''
                }
                storeName={
                    selectedAlert ? storeNameById[selectedAlert.store_id] ?? selectedAlert.store_id.slice(0, 8) : ''
                }
                suggestedQty={selectedAlert ? getAlertNumber(selectedAlert, 'suggested_qty') : null}
                velocityContext={selectedAlert ? reorderContextByAlertId.get(selectedAlert.alert_id) : undefined}
                isPending={orderFromAlert.isPending}
                onClose={() => setSelectedAlert(null)}
                onConfirm={handleConfirmOrder}
            />
        </div>
    )
}

function getAlertNumber(alert: Alert, key: string): number | null {
    const metadata = alert.alert_metadata
    if (!metadata || typeof metadata !== 'object') return null
    const raw = metadata[key]
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw
    if (typeof raw === 'string') {
        const parsed = Number(raw)
        return Number.isFinite(parsed) ? parsed : null
    }
    return null
}
