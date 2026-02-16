import { useState, useCallback } from 'react'
import { AlertTriangle, ArrowRight, Loader2, AlertCircle, Wifi, WifiOff } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
    useAlerts,
    useAlertSummary,
    useAcknowledgeAlert,
    useDismissAlert,
    useOrderFromAlert,
    useProducts,
    useResolveAlert,
    useStores,
} from '@/hooks/useShelfOps'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WsMessage } from '@/hooks/useWebSocket'
import type { Alert } from '@/lib/types'
import OrderApprovalModal from '@/components/buy/OrderApprovalModal'

const STATUS_TABS = ['open', 'acknowledged', 'resolved', 'dismissed'] as const

function isStatusTab(value: string | null): value is (typeof STATUS_TABS)[number] {
    return value != null && (STATUS_TABS as readonly string[]).includes(value)
}

export default function AlertsPage() {
    const [searchParams] = useSearchParams()
    const initialStatus = searchParams.get('status')
    const [activeTab, setActiveTab] = useState<string>(isStatusTab(initialStatus) ? initialStatus : 'open')
    const [selectedOrderAlert, setSelectedOrderAlert] = useState<Alert | null>(null)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)
    const [pendingAcknowledgeAlertId, setPendingAcknowledgeAlertId] = useState<string | null>(null)
    const [pendingResolveAlertId, setPendingResolveAlertId] = useState<string | null>(null)
    const [pendingDismissAlertId, setPendingDismissAlertId] = useState<string | null>(null)
    const queryClient = useQueryClient()

    // Real-time: invalidate alert queries when WebSocket delivers new alerts
    const handleWsMessage = useCallback((msg: WsMessage) => {
        if (msg.type === 'alert') {
            queryClient.invalidateQueries({ queryKey: ['alerts'] })
            queryClient.invalidateQueries({ queryKey: ['alert-summary'] })
        }
    }, [queryClient])

    const { connected } = useWebSocket(handleWsMessage)

    const { data: alerts = [], isLoading, isError } = useAlerts({ status: activeTab })
    const { data: summary } = useAlertSummary()
    const { data: products = [] } = useProducts()
    const { data: stores = [] } = useStores()
    const acknowledgeAlert = useAcknowledgeAlert()
    const resolveAlert = useResolveAlert()
    const dismissAlert = useDismissAlert()
    const orderFromAlert = useOrderFromAlert()

    const totalAlerts = summary?.total ?? alerts.length
    const openAlerts = summary?.open ?? 0
    const highlightedAlertId = searchParams.get('alert_id')

    const productNames = new Map(products.map((product) => [product.product_id, product.name]))
    const storeNames = new Map(stores.map((store) => [store.store_id, store.name]))

    const selectedSuggestedQty = selectedOrderAlert ? getAlertNumber(selectedOrderAlert, 'suggested_qty') : null

    async function handleOrderConfirm(payload: { quantity?: number; reason_code?: string; notes?: string }) {
        if (!selectedOrderAlert) return
        const result = await orderFromAlert.mutateAsync({
            alertId: selectedOrderAlert.alert_id,
            payload,
        })
        setSuccessMessage(`Order created: ${result.po.po_id.slice(0, 8)}`)
        setSelectedOrderAlert(null)
    }

    async function handleAcknowledge(alertId: string) {
        setPendingAcknowledgeAlertId(alertId)
        try {
            await acknowledgeAlert.mutateAsync(alertId)
        } finally {
            setPendingAcknowledgeAlertId(null)
        }
    }

    async function handleResolve(alertId: string) {
        setPendingResolveAlertId(alertId)
        try {
            await resolveAlert.mutateAsync({ alertId })
        } finally {
            setPendingResolveAlertId(null)
        }
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
            <div className="flex items-start justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Alerts</h1>
                    <p className="text-sm text-shelf-foreground/60 mt-1">
                        {totalAlerts} total · {openAlerts} open
                        {summary ? ` · ${summary.critical} critical · ${summary.high} high` : ''}
                    </p>
                </div>
                <span className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
                    connected
                        ? 'bg-green-50 text-green-600'
                        : 'bg-gray-100 text-gray-500'
                }`}>
                    {connected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                    {connected ? 'Live' : 'Offline'}
                </span>
            </div>

            {successMessage && (
                <div className="rounded-xl border border-green-200 bg-green-50 text-green-700 text-sm px-4 py-3">
                    {successMessage}
                </div>
            )}

            {/* Status tabs */}
            <div className="flex gap-1 rounded-lg bg-shelf-secondary/10 p-1 w-fit">
                {STATUS_TABS.map((tab) => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`rounded-md px-4 py-1.5 text-sm font-medium transition-all ${activeTab === tab
                            ? 'bg-white text-shelf-primary shadow-sm'
                            : 'text-shelf-foreground/60 hover:text-shelf-primary'
                            }`}
                    >
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                ))}
            </div>

            {/* Loading state */}
            {isLoading && (
                <div className="card text-center py-16 border border-white/40 shadow-sm">
                    <Loader2 className="h-8 w-8 mx-auto mb-3 text-shelf-primary animate-spin" />
                    <p className="text-sm text-shelf-foreground/60">Loading alerts...</p>
                </div>
            )}

            {/* Error state */}
            {isError && (
                <div className="card text-center py-16 border border-red-200 bg-red-50/50 shadow-sm">
                    <AlertCircle className="h-8 w-8 mx-auto mb-3 text-red-500" />
                    <p className="text-sm text-red-600">Failed to load alerts</p>
                </div>
            )}

            {/* Alert list */}
            {!isLoading && !isError && (
                <div className="space-y-3">
                    {alerts.length === 0 ? (
                        <div className="card text-center text-shelf-foreground/40 py-16 border border-white/40 shadow-sm">
                            <p>No {activeTab} alerts</p>
                        </div>
                    ) : (
                        alerts.map((alert) => (
                            <div
                                key={alert.alert_id}
                                className={`card border shadow-sm hover:shadow-md transition-all p-4 flex items-center justify-between group ${
                                    highlightedAlertId === alert.alert_id
                                        ? 'border-shelf-primary ring-2 ring-shelf-primary/20'
                                        : 'border-white/40'
                                }`}
                            >
                                <div className="flex items-start gap-4">
                                    <div className={`p-2 rounded-full ${alert.severity === 'critical' ? 'bg-red-100 text-red-600' :
                                        alert.severity === 'high' ? 'bg-orange-100 text-orange-600' :
                                            alert.severity === 'medium' ? 'bg-yellow-100 text-yellow-600' :
                                                'bg-blue-100 text-blue-600'
                                        }`}>
                                        <AlertTriangle className="h-5 w-5" />
                                    </div>
                                    <div>
                                        <h3 className="text-sm font-bold text-shelf-foreground">
                                            {alert.alert_type.replace(/_/g, ' ').toUpperCase()}
                                        </h3>
                                        <p className="text-sm text-shelf-foreground/80 mt-1">{alert.message}</p>
                                        <div className="flex gap-2 mt-2 text-xs text-shelf-foreground/50">
                                            <span className="font-mono bg-shelf-foreground/5 px-1.5 rounded">Store: {alert.store_id.slice(0, 8)}</span>
                                            <span>•</span>
                                            <span className={`font-semibold ${alert.severity === 'critical' ? 'text-red-600' :
                                                    alert.severity === 'high' ? 'text-orange-600' :
                                                        'text-shelf-foreground/60'
                                                }`}>{alert.severity.toUpperCase()}</span>
                                            <span>•</span>
                                            <span>{new Date(alert.created_at).toLocaleDateString()}</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    {alert.alert_type === 'reorder_recommended' && (
                                        <Link
                                            to={`/buy?alert_id=${alert.alert_id}`}
                                            className="btn-secondary text-xs h-8 px-3"
                                        >
                                            Open Buy
                                        </Link>
                                    )}

                                    {alert.status === 'open' && (
                                        <button
                                            onClick={async (e) => {
                                                e.stopPropagation()
                                                await handleAcknowledge(alert.alert_id)
                                            }}
                                            className="btn-secondary text-xs h-8 px-3 gap-1"
                                            disabled={acknowledgeAlert.isPending}
                                        >
                                            {acknowledgeAlert.isPending && pendingAcknowledgeAlertId === alert.alert_id ? (
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                            ) : null}
                                            {acknowledgeAlert.isPending && pendingAcknowledgeAlertId === alert.alert_id
                                                ? 'Acknowledging...'
                                                : 'Acknowledge'}
                                        </button>
                                    )}

                                    {alert.alert_type === 'reorder_recommended' &&
                                        (alert.status === 'open' || alert.status === 'acknowledged') && (
                                        <>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation()
                                                    setSelectedOrderAlert(alert)
                                                }}
                                                className="btn-primary text-xs h-8 px-3 gap-1"
                                                disabled={orderFromAlert.isPending}
                                            >
                                                {orderFromAlert.isPending && selectedOrderAlert?.alert_id === alert.alert_id ? (
                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                ) : null}
                                                {orderFromAlert.isPending && selectedOrderAlert?.alert_id === alert.alert_id
                                                    ? 'Ordering...'
                                                    : 'Approve & Order'}
                                            </button>
                                            <button
                                                onClick={async (e) => {
                                                    e.stopPropagation()
                                                    await handleDismiss(alert.alert_id)
                                                }}
                                                className="btn-secondary text-xs h-8 px-3 gap-1"
                                                disabled={dismissAlert.isPending}
                                            >
                                                {dismissAlert.isPending && pendingDismissAlertId === alert.alert_id ? (
                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                ) : null}
                                                {dismissAlert.isPending && pendingDismissAlertId === alert.alert_id
                                                    ? 'Dismissing...'
                                                    : 'Dismiss'}
                                            </button>
                                        </>
                                    )}

                                    {alert.alert_type !== 'reorder_recommended' &&
                                        (alert.status === 'open' || alert.status === 'acknowledged') && (
                                        <button
                                            onClick={async (e) => {
                                                e.stopPropagation()
                                                await handleResolve(alert.alert_id)
                                            }}
                                            className="btn-secondary text-xs h-8 px-3 gap-1"
                                            disabled={resolveAlert.isPending}
                                        >
                                            {resolveAlert.isPending && pendingResolveAlertId === alert.alert_id ? (
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                            ) : null}
                                            {resolveAlert.isPending && pendingResolveAlertId === alert.alert_id
                                                ? 'Resolving...'
                                                : 'Resolve'}
                                        </button>
                                    )}

                                    <Link
                                        to={`/products/${alert.product_id}`}
                                        className="btn-secondary text-xs h-8 px-3 gap-1"
                                    >
                                        Details
                                        <ArrowRight className="h-3 w-3" />
                                    </Link>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}

            <OrderApprovalModal
                open={selectedOrderAlert != null}
                alert={selectedOrderAlert}
                productName={
                    selectedOrderAlert
                        ? productNames.get(selectedOrderAlert.product_id) ?? selectedOrderAlert.product_id.slice(0, 8)
                        : ''
                }
                storeName={
                    selectedOrderAlert
                        ? storeNames.get(selectedOrderAlert.store_id) ?? selectedOrderAlert.store_id.slice(0, 8)
                        : ''
                }
                suggestedQty={selectedSuggestedQty}
                isPending={orderFromAlert.isPending}
                onClose={() => setSelectedOrderAlert(null)}
                onConfirm={handleOrderConfirm}
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
