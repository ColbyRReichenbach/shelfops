import { useState, useCallback } from 'react'
import { AlertTriangle, ArrowRight, Loader2, AlertCircle, Wifi, WifiOff } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAlerts, useAlertSummary, useAcknowledgeAlert, useResolveAlert } from '@/hooks/useShelfOps'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WsMessage } from '@/hooks/useWebSocket'

const STATUS_TABS = ['open', 'acknowledged', 'resolved', 'dismissed'] as const

export default function AlertsPage() {
    const [activeTab, setActiveTab] = useState<string>('open')
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
    const acknowledgeAlert = useAcknowledgeAlert()
    const resolveAlert = useResolveAlert()

    const totalAlerts = summary?.total ?? alerts.length
    const openAlerts = summary?.open ?? 0

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
                            <div key={alert.alert_id} className="card border border-white/40 shadow-sm hover:shadow-md transition-all p-4 flex items-center justify-between group">
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
                                    {alert.status === 'open' && (
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                acknowledgeAlert.mutate(alert.alert_id)
                                            }}
                                            className="btn-secondary text-xs h-8 px-3"
                                            disabled={acknowledgeAlert.isPending}
                                        >
                                            Acknowledge
                                        </button>
                                    )}
                                    {(alert.status === 'open' || alert.status === 'acknowledged') && (
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                resolveAlert.mutate({ alertId: alert.alert_id })
                                            }}
                                            className="btn-secondary text-xs h-8 px-3"
                                            disabled={resolveAlert.isPending}
                                        >
                                            Resolve
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
        </div>
    )
}
