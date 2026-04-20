import { CheckCircle2, FileBarChart2, ShieldAlert } from 'lucide-react'

import type { ActiveModelEvidence, MLModel, ModelHistoryEntry } from '@/lib/types'

interface ModelCardPanelProps {
    evidence: ActiveModelEvidence | undefined
    championModel: MLModel | undefined
    championHistory: ModelHistoryEntry | undefined
}

export default function ModelCardPanel({
    evidence,
    championModel,
    championHistory,
}: ModelCardPanelProps) {
    if (!evidence) {
        return (
            <section className="card space-y-4">
                <div className="flex items-center gap-2">
                    <FileBarChart2 className="h-4 w-4 text-[#0071e3]" />
                    <h2 className="text-lg font-semibold text-[#1d1d1f]">Active Model Summary</h2>
                </div>
                <div className="rounded-[18px] bg-[#f5f5f7] px-4 py-10 text-sm text-[#6e6e73]">
                    Active model evidence is unavailable.
                </div>
            </section>
        )
    }

    const promotionDecision = championHistory?.promotion_decision
    const gateChecks = normalizeGateChecks(promotionDecision)

    return (
        <section className="card space-y-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <FileBarChart2 className="h-4 w-4 text-[#0071e3]" />
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Active Model Summary</h2>
                    </div>
                    <p className="mt-2 text-sm text-[#6e6e73]">
                        Overview of the model currently powering replenishment recommendations.
                    </p>
                </div>
                <span className="inline-flex w-fit rounded-full bg-[#34c759]/10 px-3 py-1 text-xs font-semibold text-[#1f8f45]">
                    {formatStatusLabel(championModel?.status ?? 'active')}
                </span>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <InfoTile label="Version" value={evidence.version} detail={formatLabel(evidence.model_name ?? 'unknown')} />
                <InfoTile label="Architecture" value={evidence.architecture ?? 'unknown'} detail={evidence.objective ?? 'unknown'} />
                <InfoTile label="Dataset" value={evidence.dataset_id ?? 'unknown'} detail={evidence.dataset_snapshot_id ?? 'unknown'} />
                <InfoTile label="Promotion" value={formatLabel(evidence.promotion_reason ?? 'unknown')} detail={formatDate(evidence.promoted_at)} />
            </div>

            <div className="grid gap-5 xl:grid-cols-[1.05fr,0.95fr]">
                <div className="rounded-[20px] bg-[#f5f5f7] p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#86868b]">Training Evidence</p>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <EvidenceRow label="Rows trained" value={formatNumber(evidence.rows_trained)} />
                        <EvidenceRow label="Selected series" value={formatNumber(evidence.series_selected)} />
                        <EvidenceRow label="Coverage" value={`${evidence.coverage_start ?? 'unknown'} to ${evidence.coverage_end ?? 'unknown'}`} />
                        <EvidenceRow label="Subset strategy" value={evidence.subset_strategy ?? 'unknown'} />
                        <EvidenceRow label="Stores / Products" value={`${formatNumber(evidence.stores)} / ${formatNumber(evidence.products)}`} />
                        <EvidenceRow label="Feature tier" value={`${evidence.feature_tier ?? 'unknown'} · ${formatNumber(evidence.feature_count)} features`} />
                    </div>
                </div>

                <div className="rounded-[20px] border border-[#0071e3]/10 bg-[linear-gradient(135deg,rgba(0,113,227,0.08),rgba(255,255,255,0.7))] p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#0071e3]">Reference Benchmarks</p>
                    <div className="mt-4 space-y-3">
                        {evidence.benchmark_rows.map(row => (
                            <div key={row.label} className="rounded-[18px] bg-white/85 px-4 py-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <p className="text-sm font-semibold text-[#1d1d1f]">{row.label}</p>
                                        <p className="mt-1 text-xs text-[#6e6e73]">{row.source} · {row.note}</p>
                                    </div>
                                    <div className="text-right text-sm">
                                        <p className="font-semibold text-[#1d1d1f]">WAPE {(row.wape * 100).toFixed(1)}%</p>
                                        <p className="text-xs text-[#6e6e73]">MASE {row.mase.toFixed(3)}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="grid gap-5 xl:grid-cols-[1fr,1fr]">
                <div className="rounded-[20px] bg-white shadow-[inset_0_0_0_1px_rgba(0,0,0,0.04)] p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#86868b]">Release Checks</p>
                    <div className="mt-4 space-y-3">
                        {gateChecks.length > 0 ? gateChecks.map(check => (
                            <div key={check.label} className="flex items-start gap-3 rounded-[16px] bg-[#f5f5f7] px-4 py-3">
                                <div className={`mt-0.5 flex h-6 w-6 items-center justify-center rounded-full ${check.passed ? 'bg-[#34c759]/15 text-[#1f8f45]' : 'bg-[#ff3b30]/10 text-[#c9342a]'}`}>
                                    <CheckCircle2 className="h-4 w-4" />
                                </div>
                                <div>
                                    <p className="text-sm font-semibold text-[#1d1d1f]">{check.label}</p>
                                <p className="mt-1 text-sm text-[#6e6e73]">{check.passed ? 'Passed' : 'Needs review or unavailable'}</p>
                            </div>
                        </div>
                    )) : (
                        <div className="rounded-[16px] bg-[#f5f5f7] px-4 py-3 text-sm text-[#6e6e73]">
                            The runtime API did not return a structured release decision, so this view is using the stored release reason: {formatLabel(evidence.promotion_reason ?? 'unknown')}.
                        </div>
                    )}
                </div>
            </div>

                <div className="rounded-[20px] border border-[#ffcc00]/25 bg-[#ffcc00]/10 p-5">
                    <div className="flex items-center gap-2">
                        <ShieldAlert className="h-4 w-4 text-[#8a6a00]" />
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#8a6a00]">How To Read These Results</p>
                    </div>
                    <p className="mt-4 text-sm text-[#6e6e73]">{evidence.claim_boundary}</p>
                    <div className="mt-4 space-y-3">
                        {evidence.limitations.map(item => (
                            <div key={item} className="rounded-[16px] bg-white/80 px-4 py-3 text-sm text-[#1d1d1f]">
                                {item}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    )
}

function InfoTile({ label, value, detail }: { label: string; value: string; detail: string }) {
    return (
        <div className="rounded-[18px] bg-[#f5f5f7] px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-[#86868b]">{label}</p>
            <p className="mt-2 text-lg font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <p className="mt-1 text-xs text-[#6e6e73]">{detail}</p>
        </div>
    )
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#86868b]">{label}</p>
            <p className="mt-1 text-sm font-semibold text-[#1d1d1f]">{value}</p>
        </div>
    )
}

function normalizeGateChecks(promotionDecision: Record<string, unknown> | null | undefined) {
    if (!promotionDecision || typeof promotionDecision !== 'object') {
        return []
    }

    const gateChecks = promotionDecision.gate_checks
    if (!gateChecks || typeof gateChecks !== 'object') {
        return []
    }

    return Object.entries(gateChecks).map(([label, passed]) => ({
        label: formatLabel(label),
        passed: Boolean(passed),
    }))
}

function formatDate(value: string | null) {
    if (!value) {
        return 'Unknown'
    }
    return new Date(value).toLocaleDateString()
}

function formatLabel(value: string) {
    return value.replace(/_/g, ' ')
}

function formatNumber(value: number | null) {
    if (value === null || value === undefined) {
        return '—'
    }
    return value.toLocaleString()
}

function formatStatusLabel(value: string) {
    if (value === 'champion') {
        return 'active'
    }
    if (value === 'challenger') {
        return 'test'
    }
    return formatLabel(value)
}
