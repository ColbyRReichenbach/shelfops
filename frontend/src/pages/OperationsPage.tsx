import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
    Activity,
    AlertCircle,
    AlertTriangle,
    ArrowRight,
    Brain,
    Clock3,
    Link2,
    Loader2,
    ShieldCheck,
    Wifi,
    WifiOff,
    XCircle,
} from 'lucide-react'

import {
    useAcknowledgeAlert,
    useAlerts,
    useAlertSummary,
    useDismissAlert,
    useMLEffectiveness,
    useMLHealth,
    useResolveAlert,
    useRuntimeModelHealth,
    useSyncHealth,
} from '@/hooks/useShelfOps'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WsMessage } from '@/hooks/useWebSocket'

const STATUS_TABS = ['open', 'acknowledged', 'resolved', 'dismissed'] as const

const ALERT_LABELS: Record<string, string> = {
    anomaly_detected: 'Anomaly Review',
    stockout_predicted: 'Stockout Risk',
    reorder_recommended: 'Reorder Suggested',
    forecast_accuracy_low: 'Forecast Accuracy Low',
    model_drift_detected: 'Model Drift',
    data_stale: 'Data Stale',
    receiving_discrepancy: 'Receiving Discrepancy',
    vendor_reliability_low: 'Vendor Reliability Low',
    reorder_point_changed: 'Reorder Point Changed',
}

export default function OperationsPage() {
    const [activeTab, setActiveTab] = useState<string>('open')
    const queryClient = useQueryClient()
    const handleWsMessage = useCallback((msg: WsMessage) => {
        if (msg.type === 'alert') {
            queryClient.invalidateQueries({ queryKey: ['alerts'] })
            queryClient.invalidateQueries({ queryKey: ['alert-summary'] })
        }
    }, [queryClient])
    const { connected } = useWebSocket(handleWsMessage)

    const { data: alerts = [], isLoading: alertsLoading, isError: alertsError } = useAlerts({ status: activeTab })
    const { data: alertSummary } = useAlertSummary()
    const acknowledgeAlert = useAcknowledgeAlert()
    const resolveAlert = useResolveAlert()
    const dismissAlert = useDismissAlert()
    const { data: runtimeHealth } = useRuntimeModelHealth()
    const { data: modelHealth } = useMLHealth()
    const { data: syncSources = [] } = useSyncHealth()
    const { data: effectiveness } = useMLEffectiveness(30, 'demand_forecast')

    const breachedSources = syncSources.filter(source => source.sla_status === 'breach')
    const champion = runtimeHealth?.champion
    const retraining = runtimeHealth?.retraining_triggers
    const lastRetrain = runtimeHealth?.recent_retraining_events?.[0] ?? modelHealth?.recent_retraining_events?.[0] ?? null

    return (
        <div className="page-shell animate-fade-in">
            <div className="hero-panel hero-panel-neutral">
                <div className="flex items-start justify-between gap-4">
                    <div className="max-w-3xl">
                        <div className="hero-chip text-[#1d1d1f]">
                            <Activity className="h-3.5 w-3.5" />
                            Operations
                        </div>
                        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">
                            Monitor alerts, syncs, and model status in one place.
                        </h1>
                        <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                            Use this view to track alerts, integrations, retraining activity, and overall system health.
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
                            connected
                                ? 'bg-[#34c759]/10 text-[#34c759]'
                                : 'bg-[#86868b]/10 text-[#86868b]'
                        }`}>
                            {connected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                            {connected ? 'Live' : 'Offline'}
                        </span>
                        <div className="rounded-full bg-[#0071e3]/10 px-3 py-1.5 text-xs font-medium text-[#0071e3]">
                            Admin view
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <SummaryCard
                    icon={AlertTriangle}
                    label="Open Alerts"
                    value={String(alertSummary?.open ?? 0)}
                    detail={`${alertSummary?.critical ?? 0} critical · ${alertSummary?.high ?? 0} high`}
                />
                <SummaryCard
                    icon={Link2}
                    label="Sync Breaches"
                    value={String(breachedSources.length)}
                    detail={syncSources.length > 0 ? `${syncSources.length} sources monitored` : 'No sync sources yet'}
                />
                <SummaryCard
                    icon={Brain}
                    label="Active model"
                    value={champion?.version ?? '—'}
                    detail={champion?.trend ? `${champion.trend} · 30d MAE ${champion.mae_30d ?? '—'}` : 'No active model loaded'}
                />
                <SummaryCard
                    icon={Clock3}
                    label="Last Retrain"
                    value={lastRetrain?.completed_at ? new Date(lastRetrain.completed_at).toLocaleDateString() : '—'}
                    detail={lastRetrain?.trigger_type ? `${lastRetrain.trigger_type} · ${lastRetrain.status}` : 'No recent retrain'}
                />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-[1fr,1.1fr] gap-6">
                <section className="card p-5 space-y-4">
                    <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4 text-[#0071e3]" />
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Current Runtime Status</h2>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <StatusRow
                            label="Drift detected"
                            value={retraining?.drift_detected ? 'Yes' : 'No'}
                            tone={retraining?.drift_detected ? 'warn' : 'ok'}
                        />
                        <StatusRow
                            label="New data waiting"
                            value={retraining ? String(retraining.new_data_rows_since_last_retrain) : '—'}
                            tone={retraining && retraining.new_data_rows_since_last_retrain > 0 ? 'warn' : 'neutral'}
                        />
                        <StatusRow
                            label="Challenger eligible"
                            value={runtimeHealth?.challenger?.promotion_eligible ? 'Yes' : 'No'}
                            tone={runtimeHealth?.challenger?.promotion_eligible ? 'ok' : 'neutral'}
                        />
                        <StatusRow
                            label="30d WAPE"
                            value={effectiveness?.metrics?.wape !== null && effectiveness?.metrics?.wape !== undefined
                                ? `${(effectiveness.metrics.wape * 100).toFixed(1)}%`
                                : '—'}
                            tone="neutral"
                        />
                        <StatusRow
                            label="30d MASE"
                            value={effectiveness?.metrics?.mase !== null && effectiveness?.metrics?.mase !== undefined
                                ? effectiveness.metrics.mase.toFixed(2)
                                : '—'}
                            tone="neutral"
                        />
                        <StatusRow
                            label="Opportunity cost"
                            value={effectiveness?.metrics?.opportunity_cost_stockout !== null && effectiveness?.metrics?.opportunity_cost_stockout !== undefined
                                ? `$${Math.round(effectiveness.metrics.opportunity_cost_stockout).toLocaleString()}`
                                : '—'}
                            tone="neutral"
                        />
                    </div>
                </section>

                <section className="card p-5 space-y-4">
                    <div className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-[#0071e3]" />
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Integration Freshness</h2>
                    </div>
                    <div className="space-y-3">
                        {syncSources.length === 0 ? (
                            <p className="text-sm text-[#86868b]">No integration sources available.</p>
                        ) : (
                            syncSources.map(source => (
                                <div
                                    key={`${source.integration_type}-${source.integration_name}`}
                                    className="rounded-[16px] border border-black/5 bg-[#f5f5f7] p-4"
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <p className="text-sm font-semibold text-[#1d1d1f]">{source.integration_name}</p>
                                            <p className="text-xs text-[#86868b] mt-1">
                                                {source.integration_type} · Last sync {source.last_sync ? new Date(source.last_sync).toLocaleString() : 'unknown'}
                                            </p>
                                        </div>
                                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                                            source.sla_status === 'ok'
                                                ? 'bg-[#34c759]/10 text-[#34c759]'
                                                : 'bg-[#ff3b30]/10 text-[#ff3b30]'
                                        }`}>
                                            {source.sla_status}
                                        </span>
                                    </div>
                                    <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-[#86868b]">
                                        <Metric label="Failures 24h" value={String(source.failures_24h)} />
                                        <Metric label="Syncs 24h" value={String(source.syncs_24h)} />
                                        <Metric label="Records 24h" value={String(source.records_24h)} />
                                        <Metric label="Hours since sync" value={source.hours_since_sync !== null ? source.hours_since_sync.toFixed(1) : '—'} />
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </section>
            </div>

            <section className="card p-5 space-y-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <AlertTriangle className="h-4 w-4 text-[#0071e3]" />
                            <h2 className="text-lg font-semibold text-[#1d1d1f]">Alert Queue</h2>
                        </div>
                        <p className="mt-1 text-sm text-[#86868b]">
                            Review active issues without leaving the operations surface.
                        </p>
                    </div>
                    <div className="flex gap-1 rounded-lg bg-black/5 p-1 w-fit">
                        {STATUS_TABS.map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`rounded-md px-4 py-1.5 text-sm font-medium transition-all ${
                                    activeTab === tab
                                        ? 'bg-white text-[#0071e3] shadow-sm'
                                        : 'text-[#86868b] hover:text-[#0071e3]'
                                }`}
                            >
                                {tab.charAt(0).toUpperCase() + tab.slice(1)}
                            </button>
                        ))}
                    </div>
                </div>

                {alertsLoading && (
                    <div className="rounded-[16px] border border-black/5 py-12 text-center">
                        <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-[#0071e3]" />
                        <p className="text-sm text-[#86868b]">Loading alerts...</p>
                    </div>
                )}

                {alertsError && (
                    <div className="rounded-[16px] bg-[#ff3b30]/5 py-12 text-center">
                        <AlertCircle className="mx-auto mb-3 h-8 w-8 text-[#ff3b30]" />
                        <p className="text-sm text-[#ff3b30]">Failed to load alerts</p>
                    </div>
                )}

                {!alertsLoading && !alertsError && (
                    <div className="space-y-3">
                        {alerts.length === 0 ? (
                            <div className="rounded-[16px] border border-black/5 py-12 text-center text-[#86868b]">
                                No {activeTab} alerts
                            </div>
                        ) : (
                            alerts.map((alert) => (
                                <motion.div
                                    key={alert.alert_id}
                                    initial={{ opacity: 0, y: 5 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="rounded-[18px] border border-black/5 bg-white/80 p-4 transition-all hover:shadow-md"
                                >
                                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                                        <div className="flex items-start gap-4">
                                            <div className={`rounded-full p-2 ${
                                                alert.severity === 'critical' ? 'bg-[#ff3b30]/10 text-[#ff3b30]' :
                                                alert.severity === 'high' ? 'bg-[#ff9500]/10 text-[#ff9500]' :
                                                alert.severity === 'medium' ? 'bg-[#ffcc00]/10 text-[#b38f00]' :
                                                'bg-[#0071e3]/10 text-[#0071e3]'
                                            }`}>
                                                <AlertTriangle className="h-5 w-5" />
                                            </div>
                                            <div>
                                                <h3 className="text-sm font-bold text-[#1d1d1f]">
                                                    {ALERT_LABELS[alert.alert_type] ?? alert.alert_type.replace(/_/g, ' ').toUpperCase()}
                                                </h3>
                                                <p className="mt-1 text-sm text-[#86868b]">{alert.message}</p>
                                                <div className="mt-2 flex flex-wrap gap-2 text-xs text-[#86868b]">
                                                    <span className="rounded bg-[#f5f5f7] px-1.5 py-0.5 font-mono">
                                                        Store: {alert.store_id.slice(0, 8)}
                                                    </span>
                                                    <span className={`font-semibold ${
                                                        alert.severity === 'critical' ? 'text-[#ff3b30]' :
                                                        alert.severity === 'high' ? 'text-[#ff9500]' :
                                                        'text-[#86868b]'
                                                    }`}>
                                                        {alert.severity.toUpperCase()}
                                                    </span>
                                                    <span>{new Date(alert.created_at).toLocaleDateString()}</span>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="flex flex-wrap items-center gap-2">
                                            {alert.status === 'open' && (
                                                <button
                                                    onClick={() => acknowledgeAlert.mutate(alert.alert_id)}
                                                    className="btn-secondary h-8 px-3 text-xs"
                                                    disabled={acknowledgeAlert.isPending}
                                                >
                                                    Acknowledge
                                                </button>
                                            )}
                                            {(alert.status === 'open' || alert.status === 'acknowledged') && (
                                                <button
                                                    onClick={() => resolveAlert.mutate({ alertId: alert.alert_id })}
                                                    className="btn-secondary h-8 px-3 text-xs"
                                                    disabled={resolveAlert.isPending}
                                                >
                                                    Resolve
                                                </button>
                                            )}
                                            {(alert.status === 'open' || alert.status === 'acknowledged') && (
                                                <button
                                                    onClick={() => dismissAlert.mutate(alert.alert_id)}
                                                    className="btn-secondary h-8 gap-1 px-3 text-xs text-[#ff3b30] hover:bg-[#0071e3]/5"
                                                    disabled={dismissAlert.isPending}
                                                >
                                                    <XCircle className="h-3 w-3" />
                                                    Dismiss
                                                </button>
                                            )}
                                            <Link to={`/products/${alert.product_id}`} className="btn-secondary h-8 gap-1 px-3 text-xs">
                                                Details
                                                <ArrowRight className="h-3 w-3" />
                                            </Link>
                                        </div>
                                    </div>
                                </motion.div>
                            ))
                        )}
                    </div>
                )}
            </section>
        </div>
    )
}

function SummaryCard({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof AlertTriangle
    label: string
    value: string
    detail: string
}) {
    return (
        <motion.div
            whileHover={{ y: -4, scale: 1.01 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            className="hero-stat-card"
        >
            <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-full bg-[#f5f5f7] flex items-center justify-center">
                    <Icon className="h-4 w-4 text-[#1d1d1f]" />
                </div>
            </div>
            <p className="text-sm font-medium text-[#86868b]">{label}</p>
            <p className="text-2xl font-semibold tracking-tight text-[#1d1d1f] mt-1">{value}</p>
            <p className="text-xs text-[#86868b] mt-1">{detail}</p>
        </motion.div>
    )
}

function StatusRow({
    label,
    value,
    tone,
}: {
    label: string
    value: string
    tone: 'ok' | 'warn' | 'neutral'
}) {
    return (
        <div className="rounded-[12px] bg-[#f5f5f7] p-3">
            <p className="text-xs font-medium text-[#86868b]">{label}</p>
            <p className={`mt-1 text-base font-semibold ${
                tone === 'ok' ? 'text-[#34c759]' : tone === 'warn' ? 'text-[#ff9500]' : 'text-[#1d1d1f]'
            }`}>
                {value}
            </p>
        </div>
    )
}

function Metric({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <p className="text-[10px] font-medium text-[#86868b] uppercase tracking-wider">{label}</p>
            <p className="mt-1 font-medium text-[#1d1d1f]">{value}</p>
        </div>
    )
}
