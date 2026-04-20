import { AlertCircle, CheckCircle2, DatabaseZap, TimerReset } from 'lucide-react'

import type { DataReadiness } from '@/lib/types'

interface DataReadinessSummaryProps {
    readiness: DataReadiness | undefined
}

export default function DataReadinessSummary({ readiness }: DataReadinessSummaryProps) {
    const snapshot = readiness?.snapshot ?? {}
    const thresholds = snapshot.thresholds ?? {}
    const stateLabel = readiness?.state?.replace(/_/g, ' ') ?? 'not started'

    return (
        <section className="grid gap-4 lg:grid-cols-[1.1fr,0.9fr]">
            <div className="card space-y-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#0071e3]">Readiness Status</p>
                        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#1d1d1f] capitalize">
                            {stateLabel}
                        </h2>
                        <p className="mt-2 max-w-2xl text-sm text-[#6e6e73]">
                            {describeReason(readiness?.reason_code)}
                        </p>
                    </div>
                    <span className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold ${stateTone(readiness?.state)}`}>
                        {formatReasonCode(readiness?.reason_code)}
                    </span>
                </div>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <SummaryTile
                        icon={TimerReset}
                        label="History days"
                        value={String(snapshot.history_days ?? 0)}
                        detail={`Need ${thresholds.min_history_days ?? '—'} days`}
                    />
                    <SummaryTile
                        icon={DatabaseZap}
                        label="Store count"
                        value={String(snapshot.store_count ?? 0)}
                        detail={`Need ${thresholds.min_store_count ?? '—'} stores`}
                    />
                    <SummaryTile
                        icon={CheckCircle2}
                        label="Product count"
                        value={String(snapshot.product_count ?? 0)}
                        detail={`Need ${thresholds.min_product_count ?? '—'} products`}
                    />
                    <SummaryTile
                        icon={AlertCircle}
                        label="Accuracy samples"
                        value={String(snapshot.candidate_accuracy_samples ?? 0)}
                        detail={`Need ${thresholds.min_accuracy_samples ?? '—'} recent samples`}
                    />
                </div>
            </div>

            <div className="card space-y-4">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#86868b]">Next Steps</p>
                    <h3 className="mt-2 text-lg font-semibold text-[#1d1d1f]">What the system is waiting for</h3>
                </div>
                <StepRow
                    complete={Boolean((snapshot.history_days ?? 0) >= (thresholds.min_history_days ?? Number.POSITIVE_INFINITY))}
                    title="History threshold"
                    body="Enough sales history is available to support stable forecasting."
                />
                <StepRow
                    complete={Boolean((snapshot.product_count ?? 0) >= (thresholds.min_product_count ?? Number.POSITIVE_INFINITY))}
                    title="Catalog coverage"
                    body="The catalog is broad enough to support dependable recommendations."
                />
                <StepRow
                    complete={Boolean((snapshot.candidate_accuracy_samples ?? 0) >= (thresholds.min_accuracy_samples ?? Number.POSITIVE_INFINITY))}
                    title="Recent forecast accuracy"
                    body="Enough recent forecast checks exist to validate current model quality."
                />
                <StepRow
                    complete={readiness?.state === 'production_tier_active'}
                    title="Full operating readiness"
                    body="The current model has enough recent performance history to run without additional warm-up."
                />
            </div>
        </section>
    )
}

function SummaryTile({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof TimerReset
    label: string
    value: string
    detail: string
}) {
    return (
        <div className="surface-muted px-4 py-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-white">
                <Icon className="h-4 w-4 text-[#1d1d1f]" />
            </div>
            <p className="mt-3 text-xs font-medium uppercase tracking-[0.16em] text-[#86868b]">{label}</p>
            <p className="mt-1 text-xl font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <p className="mt-1 text-xs text-[#6e6e73]">{detail}</p>
        </div>
    )
}

function StepRow({
    complete,
    title,
    body,
}: {
    complete: boolean
    title: string
    body: string
}) {
    return (
        <div className="surface-muted flex items-start gap-3 px-4 py-3">
            <div className={`mt-0.5 flex h-6 w-6 items-center justify-center rounded-full ${complete ? 'bg-[#34c759]/15 text-[#1f8f45]' : 'bg-[#ffcc00]/20 text-[#8a6a00]'}`}>
                {complete ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            </div>
            <div>
                <p className="text-sm font-semibold text-[#1d1d1f]">{title}</p>
                <p className="mt-1 text-sm text-[#6e6e73]">{body}</p>
            </div>
        </div>
    )
}

function describeReason(reasonCode: string | undefined) {
    switch (reasonCode) {
        case 'insufficient_history_days':
            return 'More sales history is required before the system can produce stable forecasts.'
        case 'insufficient_store_count':
            return 'More store coverage is needed before forecasts can be generalized with confidence.'
        case 'insufficient_product_count':
            return 'More product coverage is needed before recommendations can be broadly supported.'
        case 'insufficient_candidate_accuracy_samples':
            return 'The system can forecast, but it needs more recent performance checks before it can move into full operating mode.'
        case 'candidate_ready_no_champion':
            return 'The account has enough data to evaluate a stronger model, but no active version has been selected yet.'
        case 'insufficient_champion_accuracy_samples':
            return 'An active model exists, but it still needs more recent performance checks before it is fully validated.'
        case 'all_gates_passed':
            return 'Core readiness checks are met for ongoing forecasting and replenishment use.'
        case 'no_csv_or_training_history':
            return 'No imported data or forecast history is available yet for this account.'
        default:
            return 'A readiness state is available, but the API did not return a more specific explanation.'
    }
}

function stateTone(state: string | undefined) {
    switch (state) {
        case 'production_tier_active':
            return 'bg-[#34c759]/10 text-[#1f8f45]'
        case 'production_tier_candidate':
            return 'bg-[#0071e3]/10 text-[#0071e3]'
        case 'warming':
            return 'bg-[#ffcc00]/20 text-[#8a6a00]'
        default:
            return 'bg-[#ff3b30]/10 text-[#c9342a]'
    }
}

function formatReasonCode(reasonCode: string | undefined) {
    if (!reasonCode) {
        return 'Status unavailable'
    }

    return reasonCode.replace(/_/g, ' ')
}
