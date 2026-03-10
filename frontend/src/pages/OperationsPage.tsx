import { Activity, AlertTriangle, Brain, Clock3, Link2, ShieldCheck } from 'lucide-react'

import {
    useAlertSummary,
    useMLEffectiveness,
    useMLHealth,
    useRuntimeModelHealth,
    useSyncHealth,
} from '@/hooks/useShelfOps'

export default function OperationsPage() {
    const { data: alertSummary } = useAlertSummary()
    const { data: runtimeHealth } = useRuntimeModelHealth()
    const { data: modelHealth } = useMLHealth()
    const { data: syncSources = [] } = useSyncHealth()
    const { data: effectiveness } = useMLEffectiveness(30, 'demand_forecast')

    const breachedSources = syncSources.filter(source => source.sla_status === 'breach')
    const champion = runtimeHealth?.champion
    const retraining = runtimeHealth?.retraining_triggers
    const lastRetrain = runtimeHealth?.recent_retraining_events?.[0] ?? modelHealth?.recent_retraining_events?.[0] ?? null

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Operations</h1>
                    <p className="text-sm text-shelf-foreground/60 mt-1">
                        Tenant-safe control view for pilot support: model health, sync status, alerts, and pipeline freshness.
                    </p>
                </div>
                <div className="rounded-full bg-shelf-primary/10 px-3 py-1.5 text-xs font-medium text-shelf-primary">
                    Manual-support pilot view
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
                    label="Champion"
                    value={champion?.version ?? '—'}
                    detail={champion?.trend ? `${champion.trend} · 30d MAE ${champion.mae_30d ?? '—'}` : 'No champion loaded'}
                />
                <SummaryCard
                    icon={Clock3}
                    label="Last Retrain"
                    value={lastRetrain?.completed_at ? new Date(lastRetrain.completed_at).toLocaleDateString() : '—'}
                    detail={lastRetrain?.trigger_type ? `${lastRetrain.trigger_type} · ${lastRetrain.status}` : 'No recent retrain'}
                />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-[1fr,1.1fr] gap-6">
                <section className="card border border-white/40 shadow-sm p-5 space-y-4">
                    <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4 text-shelf-primary" />
                        <h2 className="text-lg font-semibold text-shelf-primary">Current Runtime Status</h2>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-shelf-foreground/70">
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

                <section className="card border border-white/40 shadow-sm p-5 space-y-4">
                    <div className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-shelf-primary" />
                        <h2 className="text-lg font-semibold text-shelf-primary">Integration Freshness</h2>
                    </div>
                    <div className="space-y-3">
                        {syncSources.length === 0 ? (
                            <p className="text-sm text-shelf-foreground/50">No integration sources available.</p>
                        ) : (
                            syncSources.map(source => (
                                <div
                                    key={`${source.integration_type}-${source.integration_name}`}
                                    className="rounded-xl border border-shelf-foreground/10 bg-white/70 p-4"
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <p className="text-sm font-semibold text-shelf-foreground">{source.integration_name}</p>
                                            <p className="text-xs text-shelf-foreground/55 mt-1">
                                                {source.integration_type} · Last sync {source.last_sync ? new Date(source.last_sync).toLocaleString() : 'unknown'}
                                            </p>
                                        </div>
                                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                                            source.sla_status === 'ok'
                                                ? 'bg-green-50 text-green-600'
                                                : 'bg-red-50 text-red-600'
                                        }`}>
                                            {source.sla_status}
                                        </span>
                                    </div>
                                    <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-shelf-foreground/60">
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
        <div className="card border border-white/40 shadow-sm p-4">
            <div className="flex items-center gap-2 mb-2">
                <Icon className="h-4 w-4 text-shelf-primary" />
                <p className="text-xs uppercase tracking-wider text-shelf-foreground/50 font-medium">{label}</p>
            </div>
            <p className="text-2xl font-semibold text-shelf-foreground">{value}</p>
            <p className="text-xs text-shelf-foreground/55 mt-1">{detail}</p>
        </div>
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
        <div className="rounded-xl border border-shelf-foreground/10 bg-shelf-secondary/5 p-3">
            <p className="text-xs uppercase tracking-wider text-shelf-foreground/45">{label}</p>
            <p className={`mt-1 text-base font-semibold ${
                tone === 'ok' ? 'text-green-600' : tone === 'warn' ? 'text-orange-600' : 'text-shelf-foreground'
            }`}>
                {value}
            </p>
        </div>
    )
}

function Metric({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <p className="uppercase tracking-wider text-[10px] text-shelf-foreground/40">{label}</p>
            <p className="mt-1 font-medium text-shelf-foreground">{value}</p>
        </div>
    )
}
