/**
 * Alert Card — Displays a single alert with severity badge and action buttons.
 * Agent: full-stack-engineer | Skill: react-dashboard + alert-systems
 */

import { AlertTriangle, CheckCircle, Clock, XCircle } from 'lucide-react'
import type { Alert } from '@/lib/types'

const severityBadge: Record<string, string> = {
    critical: 'badge-critical',
    high: 'badge-high',
    medium: 'badge-medium',
    low: 'badge-low',
}

const typeIcons: Record<string, typeof AlertTriangle> = {
    stockout_predicted: AlertTriangle,
    anomaly_detected: AlertTriangle,
    reorder_recommended: CheckCircle,
    forecast_accuracy_low: Clock,
}

interface AlertCardProps {
    alert: Alert
    onAcknowledge?: (id: string) => void
    onDismiss?: (id: string) => void
}

export default function AlertCard({ alert, onAcknowledge, onDismiss }: AlertCardProps) {
    const Icon = typeIcons[alert.alert_type] ?? AlertTriangle
    const timeAgo = getTimeAgo(alert.created_at)

    return (
        <div className="card-compact flex items-start gap-4 animate-slide-up">
            <div className={`mt-0.5 rounded-lg p-2 ${alert.severity === 'critical' ? 'bg-red-500/15 text-red-400' :
                alert.severity === 'high' ? 'bg-orange-500/15 text-orange-400' :
                    alert.severity === 'medium' ? 'bg-yellow-500/15 text-yellow-400' :
                        'bg-green-500/15 text-green-400'
                }`}>
                <Icon className="h-4 w-4" />
            </div>

            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                    <span className={severityBadge[alert.severity]}>{alert.severity}</span>
                    <span className="text-xs text-surface-200/40">{timeAgo}</span>
                </div>
                <p className="text-sm text-surface-50 leading-relaxed">{alert.message}</p>
            </div>

            {alert.status === 'open' && (
                <div className="flex items-center gap-1.5 flex-shrink-0">
                    <button
                        onClick={() => onAcknowledge?.(alert.alert_id)}
                        className="rounded-md p-1.5 text-surface-200/50 hover:bg-brand-600/15 hover:text-brand-400 transition-colors"
                        title="Acknowledge"
                    >
                        <CheckCircle className="h-4 w-4" />
                    </button>
                    <button
                        onClick={() => onDismiss?.(alert.alert_id)}
                        className="rounded-md p-1.5 text-surface-200/50 hover:bg-red-600/15 hover:text-red-400 transition-colors"
                        title="Dismiss"
                    >
                        <XCircle className="h-4 w-4" />
                    </button>
                </div>
            )}
        </div>
    )
}

function getTimeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
}
