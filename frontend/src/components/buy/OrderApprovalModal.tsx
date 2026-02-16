import { useEffect, useMemo, useState } from 'react'
import type { Alert, OrderFromAlertRequest, ReorderAlertContext } from '@/lib/types'

interface OrderApprovalModalProps {
    open: boolean
    alert: Alert | null
    productName: string
    storeName: string
    suggestedQty: number | null
    velocityContext?: ReorderAlertContext
    isPending?: boolean
    onClose: () => void
    onConfirm: (payload: OrderFromAlertRequest) => Promise<unknown>
}

const REASON_CODES = [
    'overstock',
    'seasonal_end',
    'budget_constraint',
    'vendor_issue',
    'forecast_disagree',
    'manual_ordered_elsewhere',
] as const

export default function OrderApprovalModal({
    open,
    alert,
    productName,
    storeName,
    suggestedQty,
    velocityContext,
    isPending = false,
    onClose,
    onConfirm,
}: OrderApprovalModalProps) {
    const [quantity, setQuantity] = useState<string>('')
    const [reasonCode, setReasonCode] = useState<string>('')
    const [notes, setNotes] = useState<string>('')
    const [error, setError] = useState<string>('')

    useEffect(() => {
        if (!open) return
        setQuantity(String(suggestedQty ?? ''))
        setReasonCode('')
        setNotes('')
        setError('')
    }, [open, suggestedQty])

    const parsedQuantity = useMemo(() => {
        const parsed = Number(quantity)
        if (!Number.isFinite(parsed)) return null
        return Math.trunc(parsed)
    }, [quantity])

    const requiresReason = suggestedQty != null && parsedQuantity != null && parsedQuantity !== suggestedQty
    const perishableRisk =
        alert != null &&
        velocityContext?.is_perishable &&
        velocityContext?.shelf_life_days != null &&
        parsedQuantity != null &&
        velocityContext?.avg_sold_per_day_28d != null &&
        velocityContext.avg_sold_per_day_28d > 0 &&
        ((getAlertNumber(alert, 'current_stock') ?? 0) + parsedQuantity) / velocityContext.avg_sold_per_day_28d >
            velocityContext.shelf_life_days * 0.8

    if (!open || !alert) return null

    async function submit() {
        if (parsedQuantity == null || parsedQuantity <= 0) {
            setError('Quantity must be a positive number.')
            return
        }
        if (requiresReason && !reasonCode) {
            setError('Reason code is required when overriding suggested quantity.')
            return
        }
        setError('')
        try {
            await onConfirm({
                quantity: parsedQuantity,
                reason_code: reasonCode || undefined,
                notes: notes.trim() || undefined,
            })
        } catch (err) {
            const maybeDetail = (err as { detail?: string } | null)?.detail
            setError(maybeDetail ?? 'Failed to submit order decision.')
        }
    }

    return (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl border border-shelf-foreground/10 p-5 space-y-4">
                <div>
                    <h4 className="text-lg font-semibold text-shelf-primary">Approve & Order</h4>
                    <p className="text-sm text-shelf-foreground/70 mt-1">
                        {productName} • {storeName}
                    </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <p className="text-xs uppercase tracking-wider text-shelf-foreground/50 mb-1">Suggested Qty</p>
                        <p className="text-sm font-semibold text-shelf-foreground">{suggestedQty ?? 'N/A'}</p>
                    </div>
                    <div>
                        <label className="text-xs uppercase tracking-wider text-shelf-foreground/50 mb-1 block">Final Qty</label>
                        <input
                            value={quantity}
                            onChange={(e) => setQuantity(e.target.value)}
                            type="number"
                            min={1}
                            className="w-full rounded-lg border border-shelf-foreground/10 px-3 py-2 text-sm"
                        />
                    </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <MiniMetric
                        label="Avg/day (28d)"
                        value={velocityContext?.avg_sold_per_day_28d != null ? velocityContext.avg_sold_per_day_28d.toFixed(2) : '—'}
                    />
                    <MiniMetric
                        label="Avg/week (28d)"
                        value={velocityContext?.avg_sold_per_week_28d != null ? velocityContext.avg_sold_per_week_28d.toFixed(1) : '—'}
                    />
                    <MiniMetric
                        label="Cover now"
                        value={velocityContext?.days_of_cover_current != null ? `${velocityContext.days_of_cover_current}d` : '—'}
                    />
                    <MiniMetric
                        label="Cover after"
                        value={velocityContext?.days_of_cover_after_order != null ? `${velocityContext.days_of_cover_after_order}d` : '—'}
                    />
                </div>

                {velocityContext?.is_perishable && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                        Perishable item
                        {velocityContext.shelf_life_days != null ? ` · shelf life ${velocityContext.shelf_life_days} days` : ''}.
                        Use velocity and cover metrics to manually right-size this order.
                    </div>
                )}

                {perishableRisk && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                        Manual review recommended: projected cover after this order may exceed perishable shelf-life guidance.
                    </div>
                )}

                <div>
                    <label className="text-xs uppercase tracking-wider text-shelf-foreground/50 mb-1 block">
                        Reason Code {requiresReason ? '(Required)' : '(Optional)'}
                    </label>
                    <select
                        value={reasonCode}
                        onChange={(e) => setReasonCode(e.target.value)}
                        className="w-full rounded-lg border border-shelf-foreground/10 px-3 py-2 text-sm"
                    >
                        <option value="">Select reason</option>
                        {REASON_CODES.map((code) => (
                            <option key={code} value={code}>{code}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="text-xs uppercase tracking-wider text-shelf-foreground/50 mb-1 block">Notes (Optional)</label>
                    <textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        rows={3}
                        className="w-full rounded-lg border border-shelf-foreground/10 px-3 py-2 text-sm"
                        placeholder="Add decision context for audit trail"
                    />
                </div>

                {error && (
                    <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm px-3 py-2">
                        {error}
                    </div>
                )}

                <div className="flex justify-end gap-2">
                    <button className="btn-secondary text-xs h-8 px-3" onClick={onClose} disabled={isPending}>
                        Cancel
                    </button>
                    <button className="btn-primary text-xs h-8 px-3" onClick={submit} disabled={isPending}>
                        {isPending ? 'Submitting...' : 'Approve & Order'}
                    </button>
                </div>
            </div>
        </div>
    )
}

function MiniMetric({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-lg border border-shelf-foreground/10 bg-white px-2 py-1.5">
            <p className="text-[10px] uppercase tracking-wider text-shelf-foreground/50">{label}</p>
            <p className="text-xs font-semibold text-shelf-foreground mt-0.5">{value}</p>
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
