import { AlertTriangle, ArrowRight, PackageCheck, Search, Store } from 'lucide-react'

import type { ReplenishmentRecommendation } from '@/lib/types'

type RecommendationLookup = {
    productName: string
    sku: string | null
    storeName: string
}

interface ReplenishmentTableProps {
    recommendations: ReplenishmentRecommendation[]
    selectedRecommendationId: string | null
    lookupByRecommendationId: Record<string, RecommendationLookup>
    searchValue: string
    onSearchChange: (value: string) => void
    onSelect: (recommendationId: string) => void
}

export default function ReplenishmentTable({
    recommendations,
    selectedRecommendationId,
    lookupByRecommendationId,
    searchValue,
    onSearchChange,
    onSelect,
}: ReplenishmentTableProps) {
    return (
        <section className="card overflow-hidden p-0">
            <div className="border-b border-black/[0.04] bg-[linear-gradient(135deg,rgba(0,113,227,0.08),rgba(52,199,89,0.04))] px-6 py-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Action Queue</h2>
                        <p className="mt-1 max-w-2xl text-sm text-[#6e6e73]">
                            Review recommendations, inspect lead-time coverage, and move each order into an accept, edit, or reject decision.
                        </p>
                    </div>
                    <label className="relative block w-full max-w-sm">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#86868b]" />
                        <input
                            value={searchValue}
                            onChange={event => onSearchChange(event.target.value)}
                            placeholder="Search SKU, product, or store"
                            className="input pl-10"
                        />
                    </label>
                </div>
            </div>

            {recommendations.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
                    <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#f5f5f7]">
                        <PackageCheck className="h-6 w-6 text-[#0071e3]" />
                    </div>
                    <div>
                        <p className="text-base font-semibold text-[#1d1d1f]">No recommendations in this view</p>
                        <p className="mt-1 text-sm text-[#86868b]">
                            Try a different queue status or clear the current search filter.
                        </p>
                    </div>
                </div>
            ) : (
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-black/[0.04] text-left">
                        <thead className="bg-[#fbfbfd] text-xs uppercase tracking-[0.18em] text-[#86868b]">
                            <tr>
                                <th className="px-6 py-4 font-medium">Item</th>
                                <th className="px-4 py-4 font-medium">Store</th>
                                <th className="px-4 py-4 font-medium">Recommended</th>
                                <th className="px-4 py-4 font-medium">Inventory Position</th>
                                <th className="px-4 py-4 font-medium">Coverage</th>
                                <th className="px-4 py-4 font-medium">Decision Risk</th>
                                <th className="px-4 py-4 font-medium">Provenance</th>
                                <th className="px-6 py-4 font-medium text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-black/[0.04] bg-white">
                            {recommendations.map(recommendation => {
                                const lookup = lookupByRecommendationId[recommendation.recommendation_id]
                                const isSelected = selectedRecommendationId === recommendation.recommendation_id

                                return (
                                    <tr
                                        key={recommendation.recommendation_id}
                                        className={`transition-colors ${isSelected ? 'bg-[#0071e3]/[0.04]' : 'hover:bg-[#f5f5f7]/70'}`}
                                    >
                                        <td className="px-6 py-4">
                                            <div className="flex items-start gap-3">
                                                <div className="mt-1 flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                                                    <PackageCheck className="h-5 w-5 text-[#1d1d1f]" />
                                                </div>
                                                <div>
                                                    <p className="text-sm font-semibold text-[#1d1d1f]">
                                                        {lookup?.productName ?? shortId(recommendation.product_id)}
                                                    </p>
                                                    <p className="mt-1 text-xs text-[#86868b]">
                                                        {lookup?.sku ?? 'SKU unavailable'} · {shortId(recommendation.recommendation_id)}
                                                    </p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="flex items-center gap-2 text-sm text-[#1d1d1f]">
                                                <Store className="h-4 w-4 text-[#86868b]" />
                                                <span>{lookup?.storeName ?? shortId(recommendation.store_id)}</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="text-sm text-[#1d1d1f]">
                                                <p className="font-semibold">{recommendation.recommended_quantity.toLocaleString()} units</p>
                                                <p className="mt-1 text-xs text-[#86868b]">
                                                    EOQ {recommendation.economic_order_qty.toLocaleString()} · ROP {recommendation.reorder_point.toLocaleString()}
                                                </p>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <p className="text-sm font-semibold text-[#1d1d1f]">
                                                {recommendation.inventory_position.toLocaleString()}
                                            </p>
                                            <p className="mt-1 text-xs text-[#86868b]">
                                                On hand {recommendation.quantity_available.toLocaleString()} · On order {recommendation.quantity_on_order.toLocaleString()}
                                            </p>
                                        </td>
                                        <td className="px-4 py-4">
                                            <p className="text-sm font-semibold text-[#1d1d1f]">
                                                {recommendation.lead_time_demand_mean.toFixed(1)}
                                            </p>
                                            <p className="mt-1 text-xs text-[#86868b]">
                                                Lead time {recommendation.lead_time_days}d · {formatLeadTimeBand(recommendation.lead_time_demand_upper)}
                                            </p>
                                            <p className="mt-1 text-xs text-[#a1a1a6]">
                                                {recommendation.horizon_days}d plan {recommendation.horizon_demand_mean.toFixed(1)} units
                                            </p>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="flex flex-col gap-2">
                                                <RiskBadge
                                                    label={`Skip order ${recommendation.no_order_stockout_risk}`}
                                                    tone={recommendation.no_order_stockout_risk}
                                                />
                                                <RiskBadge
                                                    label={`Place order ${recommendation.order_overstock_risk}`}
                                                    tone={recommendation.order_overstock_risk}
                                                />
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="flex flex-col gap-2">
                                                <ProvenanceBadge label={recommendation.interval_method ?? 'interval unavailable'} tone="neutral" />
                                                <ProvenanceBadge
                                                    label={recommendation.calibration_status ?? 'coverage unavailable'}
                                                    tone={recommendation.calibration_status === 'calibrated' ? 'good' : 'warning'}
                                                />
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <button
                                                type="button"
                                                onClick={() => onSelect(recommendation.recommendation_id)}
                                                className="btn-secondary px-4 py-2 text-sm"
                                            >
                                                Review
                                                <ArrowRight className="h-4 w-4" />
                                            </button>
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </section>
    )
}

function RiskBadge({ label, tone }: { label: string; tone: string }) {
    const normalized = tone.toLowerCase()
    let classes = 'bg-[#f5f5f7] text-[#1d1d1f]'

    if (normalized.includes('high')) {
        classes = 'bg-[#ff3b30]/10 text-[#ff3b30]'
    } else if (normalized.includes('medium')) {
        classes = 'bg-[#ff9500]/10 text-[#ff9500]'
    } else if (normalized.includes('low')) {
        classes = 'bg-[#34c759]/10 text-[#1f8f45]'
    }

    return (
        <span className={`inline-flex w-fit items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold shadow-[0_2px_8px_rgba(0,0,0,0.03)] ${classes}`}>
            <AlertTriangle className="h-3.5 w-3.5" />
            {label}
        </span>
    )
}

function ProvenanceBadge({ label, tone }: { label: string; tone: 'good' | 'warning' | 'neutral' }) {
    const classes = tone === 'good'
        ? 'bg-[#34c759]/10 text-[#1f8f45]'
        : tone === 'warning'
            ? 'bg-[#ffcc00]/20 text-[#8a6a00]'
            : 'bg-[#f5f5f7] text-[#1d1d1f]'

    return (
        <span className={`inline-flex w-fit rounded-full px-2.5 py-1 text-xs font-semibold ${classes}`}>
            {label}
        </span>
    )
}

function formatLeadTimeBand(upper: number | null) {
    if (upper === null) {
        return 'No upper coverage band'
    }
    return `Upper ${upper.toFixed(1)}`
}

function shortId(value: string) {
    return value.slice(0, 8)
}
