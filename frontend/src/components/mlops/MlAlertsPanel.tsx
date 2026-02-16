import { useMemo, useState } from 'react'
import { AlertTriangle, Check, X } from 'lucide-react'
import type { MLAlertItem } from '@/lib/types'

interface MlAlertsPanelProps {
    alerts: MLAlertItem[]
    isLoading?: boolean
    markReadPending?: boolean
    actionPending?: boolean
    onMarkRead: (alertId: string) => void
    onAction: (alertId: string, action: 'approve' | 'dismiss') => void
}

const STATUS_FILTERS = ['all', 'unread', 'read', 'actioned', 'dismissed'] as const

export default function MlAlertsPanel({
    alerts,
    isLoading = false,
    markReadPending = false,
    actionPending = false,
    onMarkRead,
    onAction,
}: MlAlertsPanelProps) {
    const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>('all')
    const [severityFilter, setSeverityFilter] = useState<'all' | 'critical' | 'warning' | 'info'>('all')

    const filtered = useMemo(() => {
        return alerts.filter((a) => {
            if (statusFilter !== 'all' && a.status !== statusFilter) return false
            if (severityFilter !== 'all' && a.severity !== severityFilter) return false
            return true
        })
    }, [alerts, severityFilter, statusFilter])

    return (
        <div className="card border border-white/40 shadow-sm">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
                <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">ML Alerts Queue</h3>
                <div className="flex gap-2">
                    <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value as (typeof STATUS_FILTERS)[number])}
                        className="rounded-lg border border-shelf-foreground/10 bg-white px-3 py-1.5 text-sm"
                    >
                        {STATUS_FILTERS.map((status) => (
                            <option key={status} value={status}>
                                Status: {status}
                            </option>
                        ))}
                    </select>
                    <select
                        value={severityFilter}
                        onChange={(e) => setSeverityFilter(e.target.value as 'all' | 'critical' | 'warning' | 'info')}
                        className="rounded-lg border border-shelf-foreground/10 bg-white px-3 py-1.5 text-sm"
                    >
                        <option value="all">Severity: all</option>
                        <option value="critical">Severity: critical</option>
                        <option value="warning">Severity: warning</option>
                        <option value="info">Severity: info</option>
                    </select>
                </div>
            </div>

            {isLoading ? (
                <p className="text-sm text-shelf-foreground/50">Loading ML alerts...</p>
            ) : filtered.length === 0 ? (
                <p className="text-sm text-shelf-foreground/50">No ML alerts in this view. System looks healthy.</p>
            ) : (
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                    {filtered.map((alert) => (
                        <div key={alert.ml_alert_id} className="rounded-xl border border-shelf-foreground/10 p-3 bg-white">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <p className="font-medium text-sm text-shelf-foreground">{alert.title}</p>
                                    <p className="text-xs text-shelf-foreground/70 mt-1">{alert.message}</p>
                                    <div className="flex items-center gap-2 mt-2 text-[11px] text-shelf-foreground/50">
                                        <span className="uppercase">{alert.severity}</span>
                                        <span>•</span>
                                        <span className="uppercase">{alert.status}</span>
                                        <span>•</span>
                                        <span>{new Date(alert.created_at).toLocaleString()}</span>
                                    </div>
                                </div>
                                <AlertTriangle className="h-4 w-4 text-shelf-primary/70 shrink-0 mt-0.5" />
                            </div>
                            <div className="flex flex-wrap gap-2 mt-3">
                                {alert.status === 'unread' && (
                                    <button
                                        className="btn-secondary text-xs h-8 px-3"
                                        onClick={() => onMarkRead(alert.ml_alert_id)}
                                        disabled={markReadPending}
                                    >
                                        Mark Read
                                    </button>
                                )}
                                {(alert.status === 'unread' || alert.status === 'read') && (
                                    <>
                                        <button
                                            className="btn-secondary text-xs h-8 px-3 gap-1"
                                            onClick={() => onAction(alert.ml_alert_id, 'approve')}
                                            disabled={actionPending}
                                        >
                                            <Check className="h-3 w-3" />
                                            Approve
                                        </button>
                                        <button
                                            className="btn-secondary text-xs h-8 px-3 gap-1"
                                            onClick={() => onAction(alert.ml_alert_id, 'dismiss')}
                                            disabled={actionPending}
                                        >
                                            <X className="h-3 w-3" />
                                            Dismiss
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
