import { useDeferredValue, useState } from 'react'
import { AlertTriangle, ClipboardList, Filter, ShieldCheck, TrendingUp } from 'lucide-react'

import DecisionModal from '@/components/replenishment/DecisionModal'
import RecommendationDrawer from '@/components/replenishment/RecommendationDrawer'
import ReplenishmentTable from '@/components/replenishment/ReplenishmentTable'
import {
    useAcceptRecommendation,
    useEditRecommendation,
    useProducts,
    useRecommendationImpact,
    useRecommendationQueue,
    useRejectRecommendation,
    useStores,
} from '@/hooks/useShelfOps'
import { getApiErrorDetail } from '@/lib/api'

const statusOptions = [
    { value: 'open', label: 'Open' },
    { value: 'accepted', label: 'Accepted' },
    { value: 'edited', label: 'Edited' },
    { value: 'rejected', label: 'Rejected' },
] as const

export default function ReplenishmentPage() {
    const [status, setStatus] = useState<(typeof statusOptions)[number]['value']>('open')
    const [search, setSearch] = useState('')
    const [selectedRecommendationId, setSelectedRecommendationId] = useState<string | null>(null)
    const [decisionAction, setDecisionAction] = useState<'accept' | 'edit' | 'reject' | null>(null)
    const [decisionError, setDecisionError] = useState<string | null>(null)
    const deferredSearch = useDeferredValue(search)

    const { data: recommendations = [], isLoading, isError, error } = useRecommendationQueue(status, 100)
    const { data: impact } = useRecommendationImpact()
    const { data: stores = [] } = useStores()
    const { data: products = [] } = useProducts()

    const acceptRecommendation = useAcceptRecommendation()
    const editRecommendation = useEditRecommendation()
    const rejectRecommendation = useRejectRecommendation()

    const storeLookup = Object.fromEntries(stores.map(store => [store.store_id, store]))
    const productLookup = Object.fromEntries(products.map(product => [product.product_id, product]))

    const filteredRecommendations = recommendations.filter(recommendation => {
        const lookupProduct = productLookup[recommendation.product_id]
        const lookupStore = storeLookup[recommendation.store_id]
        const normalized = deferredSearch.trim().toLowerCase()

        if (!normalized) {
            return true
        }

        return [
            lookupProduct?.name,
            lookupProduct?.sku,
            lookupStore?.name,
            recommendation.forecast_model_version,
            recommendation.policy_version,
        ]
            .filter(Boolean)
            .some(value => String(value).toLowerCase().includes(normalized))
    })

    const lookupByRecommendationId = Object.fromEntries(
        filteredRecommendations.map(recommendation => [
            recommendation.recommendation_id,
            {
                productName: productLookup[recommendation.product_id]?.name ?? recommendation.product_id.slice(0, 8),
                sku: productLookup[recommendation.product_id]?.sku ?? null,
                storeName: storeLookup[recommendation.store_id]?.name ?? recommendation.store_id.slice(0, 8),
            },
        ]),
    )

    const selectedRecommendation = filteredRecommendations.find(
        recommendation => recommendation.recommendation_id === selectedRecommendationId,
    ) ?? null

    const selectedLookup = selectedRecommendation
        ? lookupByRecommendationId[selectedRecommendation.recommendation_id] ?? null
        : null

    const coverageCount = filteredRecommendations.filter(
        recommendation => recommendation.calibration_status === 'calibrated',
    ).length

    const highRiskCount = filteredRecommendations.filter(
        recommendation =>
            recommendation.no_order_stockout_risk.toLowerCase() === 'high'
            || recommendation.order_overstock_risk.toLowerCase() === 'high',
    ).length

    const pendingMutation = acceptRecommendation.isPending || editRecommendation.isPending || rejectRecommendation.isPending

    return (
        <div className="page-shell">
            <div className="hero-panel hero-panel-blue-soft">
                <div className="max-w-3xl">
                    <div className="hero-chip text-[#0071e3]">
                        <ClipboardList className="h-3.5 w-3.5" />
                        Replenishment Queue
                    </div>
                    <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">
                        Review order recommendations and act with confidence.
                    </h1>
                    <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                        Use this queue to review suggested order quantities, compare forecast ranges, and accept, adjust, or dismiss recommendations with a recorded decision history.
                    </p>
                </div>

                <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <SummaryCard
                        icon={ClipboardList}
                        label="Queue volume"
                        value={String(filteredRecommendations.length)}
                        detail={`${status} recommendations`}
                    />
                    <SummaryCard
                        icon={ShieldCheck}
                        label="Calibrated intervals"
                        value={String(coverageCount)}
                        detail={`${filteredRecommendations.length === 0 ? 0 : Math.round((coverageCount / filteredRecommendations.length) * 100)}% of visible queue`}
                    />
                    <SummaryCard
                        icon={AlertTriangle}
                        label="High-risk items"
                        value={String(highRiskCount)}
                        detail="High stockout or overstock risk"
                    />
                    <SummaryCard
                        icon={TrendingUp}
                        label="Net value"
                        value={formatCurrency(impact?.net_estimated_value ?? null)}
                        detail={impact?.net_estimated_value_confidence ?? 'unavailable'}
                    />
                </div>
            </div>

            <section className="card space-y-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Queue Filters</h2>
                        <p className="mt-1 text-sm text-[#86868b]">
                            Filter by decision status and focus on the work that still needs attention.
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <div className="flex items-center gap-2 rounded-full bg-[#f5f5f7] px-3 py-2 text-sm font-medium text-[#1d1d1f]">
                            <Filter className="h-4 w-4 text-[#86868b]" />
                            Status
                        </div>
                        {statusOptions.map(option => (
                            <button
                                key={option.value}
                                type="button"
                                onClick={() => {
                                    setStatus(option.value)
                                    setSelectedRecommendationId(null)
                                }}
                                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                                    status === option.value
                                        ? 'bg-[#1d1d1f] text-white'
                                        : 'bg-[#f5f5f7] text-[#1d1d1f] hover:bg-[#ececf0]'
                                }`}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                </div>
            </section>

            {isLoading ? (
                <div className="card p-12 text-center text-sm text-[#86868b]">Loading replenishment recommendations…</div>
            ) : isError ? (
                <div className="card border border-[#ff3b30]/20 bg-[#ff3b30]/5 p-12 text-center text-sm text-[#c9342a]">
                    {getApiErrorDetail(error, 'Failed to load replenishment queue.')}
                </div>
            ) : (
                <ReplenishmentTable
                    recommendations={filteredRecommendations}
                    selectedRecommendationId={selectedRecommendationId}
                    lookupByRecommendationId={lookupByRecommendationId}
                    searchValue={search}
                    onSearchChange={setSearch}
                    onSelect={setSelectedRecommendationId}
                />
            )}

            <RecommendationDrawer
                isOpen={selectedRecommendation !== null}
                recommendation={selectedRecommendation}
                lookup={selectedLookup}
                impact={impact}
                onClose={() => {
                    setSelectedRecommendationId(null)
                    setDecisionAction(null)
                    setDecisionError(null)
                }}
                onAccept={() => {
                    setDecisionError(null)
                    setDecisionAction('accept')
                }}
                onEdit={() => {
                    setDecisionError(null)
                    setDecisionAction('edit')
                }}
                onReject={() => {
                    setDecisionError(null)
                    setDecisionAction('reject')
                }}
            />

            <DecisionModal
                action={decisionAction ?? 'accept'}
                isOpen={decisionAction !== null}
                isPending={pendingMutation}
                recommendation={selectedRecommendation}
                errorMessage={decisionError}
                onClose={() => {
                    setDecisionAction(null)
                    setDecisionError(null)
                }}
                onSubmit={async payload => {
                    if (!selectedRecommendation || !decisionAction) {
                        return
                    }

                    setDecisionError(null)

                    try {
                        if (decisionAction === 'accept') {
                            await acceptRecommendation.mutateAsync({
                                recommendationId: selectedRecommendation.recommendation_id,
                                payload: {
                                    reason_code: payload.reasonCode,
                                    notes: payload.notes,
                                },
                            })
                        } else if (decisionAction === 'edit') {
                            if (!payload.quantity || !payload.reasonCode) {
                                setDecisionError('Edited quantity and reason code are required.')
                                return
                            }

                            await editRecommendation.mutateAsync({
                                recommendationId: selectedRecommendation.recommendation_id,
                                payload: {
                                    quantity: payload.quantity,
                                    reason_code: payload.reasonCode,
                                    notes: payload.notes,
                                },
                            })
                        } else {
                            if (!payload.reasonCode) {
                                setDecisionError('Reason code is required for rejection.')
                                return
                            }

                            await rejectRecommendation.mutateAsync({
                                recommendationId: selectedRecommendation.recommendation_id,
                                payload: {
                                    reason_code: payload.reasonCode,
                                    notes: payload.notes,
                                },
                            })
                        }

                        setDecisionAction(null)
                        setSelectedRecommendationId(null)
                    } catch (mutationError) {
                        setDecisionError(getApiErrorDetail(mutationError, 'Failed to save recommendation decision.'))
                    }
                }}
            />
        </div>
    )
}

function SummaryCard({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof ClipboardList
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
            <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <p className="mt-2 text-xs text-[#6e6e73]">{detail}</p>
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
