import { Link } from 'react-router-dom'
import { ArrowRight, Loader2, Sparkles } from 'lucide-react'
import type { Alert, ReorderAlertContext } from '@/lib/types'

interface ReorderQueueCardProps {
    alert: Alert
    productName: string
    storeName: string
    currentStock: number | null
    reorderPoint: number | null
    safetyStock: number | null
    suggestedQty: number | null
    estimatedCost: number | null
    velocityContext?: ReorderAlertContext
    highlighted?: boolean
    approvePending?: boolean
    dismissPending?: boolean
    onApprove: (alert: Alert) => void
    onDismiss: (alertId: string) => void
}

export default function ReorderQueueCard({
    alert,
    productName,
    storeName,
    currentStock,
    reorderPoint,
    safetyStock,
    suggestedQty,
    estimatedCost,
    velocityContext,
    highlighted = false,
    approvePending = false,
    dismissPending = false,
    onApprove,
    onDismiss,
}: ReorderQueueCardProps) {
    const perishableRisk =
        velocityContext?.is_perishable &&
        velocityContext?.shelf_life_days != null &&
        velocityContext?.days_of_cover_after_order != null &&
        velocityContext.days_of_cover_after_order > velocityContext.shelf_life_days * 0.8

    return (
        <div
            className={`card border shadow-sm p-4 transition-all ${
                highlighted ? 'border-shelf-primary ring-2 ring-shelf-primary/20' : 'border-white/40'
            }`}
        >
            <div className="flex items-start justify-between gap-3">
                <div>
                    <p className="text-sm font-semibold text-shelf-foreground">{productName}</p>
                    <p className="text-xs text-shelf-foreground/60 mt-0.5">{storeName}</p>
                    <div className="inline-flex items-center gap-1 mt-2 rounded-full bg-shelf-primary/10 text-shelf-primary px-2.5 py-0.5 text-xs font-medium">
                        <Sparkles className="h-3 w-3" />
                        Order now: stock at/under reorder point
                    </div>
                </div>
                <span className="badge bg-orange-100 text-orange-700 border-orange-200">
                    {alert.status}
                </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3 mt-4">
                <Metric label="Current Stock" value={currentStock != null ? String(currentStock) : '—'} />
                <Metric label="Reorder Point" value={reorderPoint != null ? String(reorderPoint) : '—'} />
                <Metric label="Safety Stock" value={safetyStock != null ? String(safetyStock) : '—'} />
                <Metric label="Suggested Qty" value={suggestedQty != null ? String(suggestedQty) : '—'} />
                <Metric
                    label="Avg Sold/Day (28d)"
                    value={velocityContext?.avg_sold_per_day_28d != null ? velocityContext.avg_sold_per_day_28d.toFixed(2) : '—'}
                />
                <Metric
                    label="Avg Sold/Week (28d)"
                    value={velocityContext?.avg_sold_per_week_28d != null ? velocityContext.avg_sold_per_week_28d.toFixed(1) : '—'}
                />
                <Metric
                    label="Days Cover Now"
                    value={velocityContext?.days_of_cover_current != null ? `${velocityContext.days_of_cover_current}d` : '—'}
                />
                <Metric
                    label="Days Cover After"
                    value={velocityContext?.days_of_cover_after_order != null ? `${velocityContext.days_of_cover_after_order}d` : '—'}
                />
            </div>

            {perishableRisk && (
                <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    Perishable risk: projected cover after this order exceeds shelf-life guidance.
                    Review quantity manually before approval.
                </div>
            )}

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-4">
                <p className="text-sm text-shelf-foreground/70">
                    Estimated cost:{' '}
                    <span className="font-semibold text-shelf-foreground">
                        {estimatedCost != null ? `$${estimatedCost.toFixed(2)}` : 'Cost unavailable'}
                    </span>
                </p>
                <div className="flex flex-wrap gap-2">
                    <button className="btn-primary text-xs h-8 px-3 gap-1" onClick={() => onApprove(alert)} disabled={approvePending}>
                        {approvePending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                        {approvePending ? 'Ordering...' : 'Approve & Order'}
                    </button>
                    <button
                        className="btn-secondary text-xs h-8 px-3 gap-1"
                        onClick={() => onDismiss(alert.alert_id)}
                        disabled={dismissPending}
                    >
                        {dismissPending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                        {dismissPending ? 'Dismissing...' : 'Dismiss'}
                    </button>
                    <Link
                        to={`/alerts?status=${encodeURIComponent(alert.status)}&alert_id=${alert.alert_id}`}
                        className="btn-secondary text-xs h-8 px-3 gap-1"
                    >
                        Open in Alerts
                        <ArrowRight className="h-3 w-3" />
                    </Link>
                </div>
            </div>
        </div>
    )
}

function Metric({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-lg border border-shelf-foreground/10 bg-white p-2.5">
            <p className="text-[11px] uppercase tracking-wider text-shelf-foreground/50">{label}</p>
            <p className="text-sm font-semibold text-shelf-foreground mt-1">{value}</p>
        </div>
    )
}
