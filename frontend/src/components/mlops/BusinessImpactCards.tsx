import { AlertTriangle, Clock3, ShieldCheck, Wallet } from 'lucide-react'
import type {
    AlertEffectiveness,
    AnomalyEffectiveness,
    MLAlertStats,
    ROIResponse,
} from '@/lib/types'

interface BusinessImpactCardsProps {
    mlAlertStats?: MLAlertStats
    alertEffectiveness?: AlertEffectiveness
    anomalyEffectiveness?: AnomalyEffectiveness
    roi?: ROIResponse
    isLoading?: boolean
}

const currency = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
})

function formatPct(value: number | null | undefined) {
    if (value == null) return '—'
    return `${(value * 100).toFixed(1)}%`
}

export default function BusinessImpactCards({
    mlAlertStats,
    alertEffectiveness,
    anomalyEffectiveness,
    roi,
    isLoading = false,
}: BusinessImpactCardsProps) {
    const cards = [
        {
            label: 'Risk Inbox',
            icon: AlertTriangle,
            value: mlAlertStats ? String(mlAlertStats.total_unread) : '—',
            detail: mlAlertStats
                ? `${mlAlertStats.critical_unread} critical · ${mlAlertStats.warning_unread} warning`
                : 'Unread ML alerts',
            tone: 'text-red-600',
            bg: 'bg-red-50',
        },
        {
            label: 'Alert Quality',
            icon: Clock3,
            value: alertEffectiveness ? formatPct(alertEffectiveness.false_positive_rate) : '—',
            detail: alertEffectiveness
                ? `Avg response ${alertEffectiveness.avg_response_time_hours}h`
                : 'False positive rate',
            tone: 'text-amber-600',
            bg: 'bg-amber-50',
        },
        {
            label: 'Anomaly Precision',
            icon: ShieldCheck,
            value: anomalyEffectiveness ? formatPct(anomalyEffectiveness.precision) : '—',
            detail: anomalyEffectiveness
                ? `${anomalyEffectiveness.total_anomalies} anomalies in window`
                : 'True positive quality',
            tone: 'text-emerald-600',
            bg: 'bg-emerald-50',
        },
        {
            label: 'Value Recovered',
            icon: Wallet,
            value: roi ? currency.format(roi.total_value_created ?? 0) : '—',
            detail: roi
                ? `Ghost stock: ${currency.format(roi.ghost_stock_recovered_value ?? 0)}`
                : 'ROI proxy',
            tone: 'text-shelf-primary',
            bg: 'bg-shelf-primary/10',
        },
    ]

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {cards.map((card) => (
                <div key={card.label} className="card border border-white/40 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <p className="text-xs font-medium text-shelf-foreground/50 uppercase tracking-wider">
                                {card.label}
                            </p>
                            <p className="text-2xl font-bold mt-1 text-shelf-foreground">
                                {isLoading ? '...' : card.value}
                            </p>
                            <p className="text-xs text-shelf-foreground/60 mt-1">
                                {card.detail}
                            </p>
                        </div>
                        <div className={`h-10 w-10 rounded-xl ${card.bg} flex items-center justify-center`}>
                            <card.icon className={`h-5 w-5 ${card.tone}`} />
                        </div>
                    </div>
                </div>
            ))}
        </div>
    )
}
