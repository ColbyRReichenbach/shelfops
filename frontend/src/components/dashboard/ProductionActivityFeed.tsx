import { useMemo } from 'react'
import { Activity, Loader2 } from 'lucide-react'

import { useExperimentLedger, useRuntimeModelHealth, useSyncHealth } from '@/hooks/useShelfOps'

type ActivityItem = {
    id: string
    timestamp: string
    title: string
    detail: string
    tone: 'neutral' | 'success' | 'warning'
}

const TONE_STYLE: Record<ActivityItem['tone'], string> = {
    neutral: 'bg-slate-300',
    success: 'bg-green-500',
    warning: 'bg-amber-400',
}

export default function ProductionActivityFeed() {
    const { data: runtimeHealth, isLoading: runtimeLoading } = useRuntimeModelHealth()
    const { data: experimentLedger = [], isLoading: ledgerLoading } = useExperimentLedger({ limit: 6 })
    const { data: syncSources = [], isLoading: syncLoading } = useSyncHealth()

    const items = useMemo<ActivityItem[]>(() => {
        const retrains = (runtimeHealth?.recent_retraining_events ?? []).map((event, index) => {
            const tone: ActivityItem['tone'] =
                event.status === 'completed' ? 'success' : event.status === 'failed' ? 'warning' : 'neutral'
            return {
                id: `retrain-${index}-${event.started_at ?? 'unknown'}`,
                timestamp: event.started_at ?? event.completed_at ?? new Date(0).toISOString(),
                title: `Retrain ${event.status}`,
                detail: `${event.trigger_type} trigger${event.version_produced ? ` produced ${event.version_produced}` : ''}`,
                tone,
            }
        })

        const experiments = experimentLedger.map((entry) => {
            const tone: ActivityItem['tone'] =
                entry.status === 'completed' || entry.status === 'approved' ? 'success' : 'neutral'
            return {
                id: entry.experiment_id,
                timestamp: entry.completed_at ?? entry.approved_at ?? entry.created_at,
                title: `Experiment ${entry.status.replace(/_/g, ' ')}`,
                detail: `${entry.experiment_name} · ${entry.experiment_type}`,
                tone,
            }
        })

        const syncEvents = syncSources
            .filter((source) => source.last_sync)
            .map((source) => {
                const tone: ActivityItem['tone'] = source.sla_status === 'breach' ? 'warning' : 'neutral'
                return {
                    id: `sync-${source.integration_type}-${source.integration_name}`,
                    timestamp: source.last_sync ?? new Date(0).toISOString(),
                    title: source.sla_status === 'breach' ? 'Sync SLA breach' : 'Sync completed',
                    detail: `${source.integration_name} · ${source.records_24h} records in last 24h`,
                    tone,
                }
            })

        return [...retrains, ...experiments, ...syncEvents]
            .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
            .slice(0, 10)
    }, [experimentLedger, runtimeHealth?.recent_retraining_events, syncSources])

    if (runtimeLoading || ledgerLoading || syncLoading) {
        return (
            <div className="card border border-white/40 shadow-sm p-8 text-center">
                <Loader2 className="mx-auto h-6 w-6 animate-spin text-shelf-primary" />
                <p className="mt-2 text-sm text-shelf-foreground/60">Loading platform activity...</p>
            </div>
        )
    }

    if (items.length === 0) {
        return null
    }

    return (
        <div className="card border border-white/40 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-semibold uppercase tracking-wider text-shelf-primary">Platform Activity</h3>
                    <p className="mt-1 text-xs text-shelf-foreground/55">
                        Recent retraining, experiment, and sync activity from live runtime systems.
                    </p>
                </div>
                <Activity className="h-4 w-4 text-shelf-primary/60" />
            </div>

            <div className="relative pl-6">
                <div className="absolute bottom-1 left-2.5 top-1 w-px bg-shelf-foreground/10" />
                <div className="space-y-4">
                    {items.map((item) => (
                        <div key={item.id} className="relative flex items-start gap-3">
                            <div className={`absolute -left-4 mt-1 h-3 w-3 rounded-full ${TONE_STYLE[item.tone]}`} />
                            <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-baseline gap-2">
                                    <span className="text-xs font-semibold text-shelf-foreground/70">
                                        {new Date(item.timestamp).toLocaleDateString()}
                                    </span>
                                    <span className="text-xs font-medium text-shelf-foreground/85">{item.title}</span>
                                </div>
                                <p className="mt-1 text-xs leading-relaxed text-shelf-foreground/60">{item.detail}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
