import { ArrowUpRight, CircleDollarSign, Package2, ShieldAlert, Sparkles, X } from 'lucide-react'

import type { RecommendationImpact, ReplenishmentRecommendation } from '@/lib/types'

type RecommendationLookup = {
    productName: string
    sku: string | null
    storeName: string
}

interface RecommendationDrawerProps {
    recommendation: ReplenishmentRecommendation | null
    lookup: RecommendationLookup | null
    impact: RecommendationImpact | undefined
    isOpen: boolean
    onClose: () => void
    onAccept: () => void
    onEdit: () => void
    onReject: () => void
}

export default function RecommendationDrawer({
    recommendation,
    lookup,
    impact,
    isOpen,
    onClose,
    onAccept,
    onEdit,
    onReject,
}: RecommendationDrawerProps) {
    if (!isOpen || !recommendation) {
        return null
    }

    return (
        <div className="fixed inset-y-0 right-0 z-[60] flex w-full justify-end bg-[#1d1d1f]/20 backdrop-blur-[2px]">
            <div className="flex h-full w-full max-w-2xl flex-col overflow-y-auto border-l border-black/5 bg-[linear-gradient(180deg,#fbfbfd,#f3f5f8)] shadow-[-24px_0_80px_rgba(0,0,0,0.12)]">
                <div className="sticky top-0 z-10 border-b border-black/[0.05] bg-[#fbfbfd]/95 px-6 py-5 backdrop-blur">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#86868b]">Recommendation Detail</p>
                            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#1d1d1f]">
                                {lookup?.productName ?? recommendation.product_id.slice(0, 8)}
                            </h2>
                            <p className="mt-2 text-sm text-[#6e6e73]">
                                {lookup?.storeName ?? recommendation.store_id.slice(0, 8)} · {lookup?.sku ?? 'SKU unavailable'} · {recommendation.status}
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={onClose}
                            className="rounded-full bg-white p-2 text-[#86868b] shadow-[0_2px_10px_rgba(0,0,0,0.04)] transition hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>
                </div>

                <div className="space-y-6 px-6 py-6">
                    <section className="grid gap-4 md:grid-cols-3">
                        <HighlightCard
                            icon={Package2}
                            label="Recommended order"
                            value={`${recommendation.recommended_quantity.toLocaleString()} units`}
                            detail={`EOQ ${recommendation.economic_order_qty.toLocaleString()} · Lead time ${recommendation.lead_time_days}d`}
                        />
                        <HighlightCard
                            icon={ShieldAlert}
                            label="No-order risk"
                            value={recommendation.no_order_stockout_risk}
                            detail={`Overstock risk ${recommendation.order_overstock_risk}`}
                        />
                        <HighlightCard
                            icon={CircleDollarSign}
                            label="Estimated spend"
                            value={formatCurrency(recommendation.estimated_total_cost)}
                            detail={`Unit cost ${formatCurrency(recommendation.estimated_unit_cost)}`}
                        />
                    </section>

                    <section className="card-compact space-y-4">
                        <div className="flex items-center gap-2">
                            <Sparkles className="h-4 w-4 text-[#0071e3]" />
                            <h3 className="text-base font-semibold text-[#1d1d1f]">Forecast Context</h3>
                        </div>
                        <div className="grid gap-4 md:grid-cols-2">
                            <MetricTile label="Forecast window" value={`${recommendation.forecast_start_date} to ${recommendation.forecast_end_date}`} />
                            <MetricTile label="Policy version" value={recommendation.policy_version} />
                            <MetricTile label="Horizon demand mean" value={recommendation.horizon_demand_mean.toFixed(1)} />
                            <MetricTile label="Lead-time demand mean" value={recommendation.lead_time_demand_mean.toFixed(1)} />
                            <MetricTile
                                label="Prediction band"
                                value={formatBand(recommendation.horizon_demand_lower, recommendation.horizon_demand_upper)}
                            />
                            <MetricTile
                                label="Range quality"
                                value={`${recommendation.interval_method ?? 'unavailable'} · ${recommendation.calibration_status ?? 'unknown'}`}
                            />
                        </div>
                    </section>

                    <section className="card-compact space-y-4">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <h3 className="text-base font-semibold text-[#1d1d1f]">Impact Summary</h3>
                                <p className="mt-1 text-sm text-[#6e6e73]">
                                    A rollup of recent recommendation outcomes across the queue. Status tags below come directly from the backend.
                                </p>
                            </div>
                            <span className="rounded-full bg-[#f5f5f7] px-3 py-1 text-xs font-semibold text-[#1d1d1f]">
                                as of {impact?.as_of_date ?? '—'}
                            </span>
                        </div>

                        {impact ? (
                            <div className="grid gap-4 md:grid-cols-2">
                                <ImpactTile
                                    label="Net value"
                                    value={formatCurrency(impact.net_estimated_value)}
                                    provenance={impact.net_estimated_value_confidence}
                                />
                                <ImpactTile
                                    label="Forecast error"
                                    value={impact.average_forecast_error_abs !== null ? impact.average_forecast_error_abs.toFixed(2) : '—'}
                                    provenance={impact.average_forecast_error_abs_confidence}
                                />
                                <ImpactTile
                                    label="Stockout events"
                                    value={impact.stockout_events.toLocaleString()}
                                    provenance={impact.stockout_events_confidence}
                                />
                                <ImpactTile
                                    label="Overstock events"
                                    value={impact.overstock_events.toLocaleString()}
                                    provenance={impact.overstock_events_confidence}
                                />
                            </div>
                        ) : (
                            <p className="text-sm text-[#86868b]">Impact summary unavailable.</p>
                        )}
                    </section>

                    <section className="card-compact space-y-4">
                        <div className="flex items-center gap-2">
                            <ArrowUpRight className="h-4 w-4 text-[#0071e3]" />
                            <h3 className="text-base font-semibold text-[#1d1d1f]">Decision Controls</h3>
                        </div>
                        <div className="grid gap-3 md:grid-cols-3">
                            <button type="button" onClick={onAccept} className="btn-primary justify-center">
                                Accept
                            </button>
                            <button type="button" onClick={onEdit} className="btn-secondary justify-center">
                                Edit Quantity
                            </button>
                            <button
                                type="button"
                                onClick={onReject}
                                className="inline-flex items-center justify-center rounded-full bg-[#1d1d1f] px-5 py-2.5 text-sm font-medium text-white transition hover:bg-black hover:shadow-[0_10px_24px_rgba(29,29,31,0.22)]"
                            >
                                Reject
                            </button>
                        </div>
                    </section>
                </div>
            </div>
        </div>
    )
}

function HighlightCard({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof Package2
    label: string
    value: string
    detail: string
}) {
    return (
        <div className="hero-stat-card">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                <Icon className="h-5 w-5 text-[#1d1d1f]" />
            </div>
            <p className="mt-4 text-sm font-medium text-[#86868b]">{label}</p>
            <p className="mt-1 text-xl font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <p className="mt-2 text-xs text-[#86868b]">{detail}</p>
        </div>
    )
}

function MetricTile({ label, value }: { label: string; value: string }) {
    return (
        <div className="surface-muted bg-white px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#86868b]">{label}</p>
            <p className="mt-2 text-sm font-semibold text-[#1d1d1f]">{value}</p>
        </div>
    )
}

function ImpactTile({
    label,
    value,
    provenance,
}: {
    label: string
    value: string
    provenance: string
}) {
    return (
        <div className="surface-muted bg-white px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#86868b]">{label}</p>
            <p className="mt-2 text-lg font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <span className="mt-3 inline-flex rounded-full bg-[#f5f5f7] px-2.5 py-1 text-xs font-semibold text-[#1d1d1f]">
                {provenance}
            </span>
        </div>
    )
}

function formatCurrency(value: number | null) {
    if (value === null) {
        return '—'
    }
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
    }).format(value)
}

function formatBand(lower: number | null, upper: number | null) {
    if (lower === null || upper === null) {
        return 'Unavailable'
    }
    return `${lower.toFixed(1)} to ${upper.toFixed(1)}`
}
