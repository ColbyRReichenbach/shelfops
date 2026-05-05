import { BarChart3, Brain, ClipboardCheck, DatabaseZap, Microscope, Wallet } from 'lucide-react'

import ImpactScorecard from '@/components/impact/ImpactScorecard'
import MetricProvenanceBadge from '@/components/impact/MetricProvenanceBadge'
import PolicyComparisonTable from '@/components/impact/PolicyComparisonTable'
import { useActiveModelEvidence, useDataReadiness, useRecommendationImpact, useReplenishmentSimulation } from '@/hooks/useShelfOps'
import { getApiErrorDetail } from '@/lib/api'
import type { ActiveModelEvidence, DataReadiness, RecommendationImpact, ReplenishmentSimulationReport } from '@/lib/types'

export default function PilotImpactPage() {
    const impactQuery = useRecommendationImpact()
    const simulationQuery = useReplenishmentSimulation()
    const readinessQuery = useDataReadiness()
    const evidenceQuery = useActiveModelEvidence()

    return (
        <div className="page-shell">
            <div className="hero-panel hero-panel-blue">
                <div className="max-w-3xl">
                    <div className="hero-chip text-[#0071e3]">
                        <BarChart3 className="h-3.5 w-3.5" />
                        Merchant Evidence
                    </div>
                    <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">
                        Separate measured outcomes from scenario evidence.
                    </h1>
                    <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                        Review readiness, forecast evidence, recommendation closeout, and policy replay without blending pilot results with benchmark or simulated evidence.
                    </p>
                </div>
            </div>

            <EvidenceBoundaryPanel
                readiness={readinessQuery.data}
                modelEvidence={evidenceQuery.data}
                impact={impactQuery.data}
                simulation={simulationQuery.data}
                loading={{
                    readiness: readinessQuery.isLoading,
                    modelEvidence: evidenceQuery.isLoading,
                    impact: impactQuery.isLoading,
                    simulation: simulationQuery.isLoading,
                }}
            />

            <section className="card space-y-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <Wallet className="h-4 w-4 text-[#0071e3]" />
                            <h2 className="text-lg font-semibold text-[#1d1d1f]">Outcome Scorecard</h2>
                        </div>
                        <p className="mt-2 text-sm text-[#6e6e73]">
                            These metrics split forecast closeout from decision-policy value. Observed sales close the loop today, while policy value remains an estimated proxy against a do-nothing baseline until richer demand recovery and counterfactual evidence are available.
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <MetricProvenanceBadge label="measured" tone="measured" />
                        <MetricProvenanceBadge label="estimated" tone="estimated" />
                        <MetricProvenanceBadge label="provisional" tone="provisional" />
                    </div>
                </div>

                {impactQuery.isError ? (
                    <div className="rounded-[20px] border border-[#ff3b30]/20 bg-[#ff3b30]/5 px-4 py-4 text-sm text-[#c9342a]">
                        {getApiErrorDetail(impactQuery.error, 'Unable to load operational impact.')}
                    </div>
                ) : impactQuery.isLoading ? (
                    <div className="rounded-[20px] bg-[#f5f5f7] px-4 py-10 text-center text-sm text-[#86868b]">
                        Loading operational impact…
                    </div>
                ) : (
                    <ImpactScorecard impact={impactQuery.data} />
                )}
            </section>

            <section className="space-y-4">
                <div className="flex items-center gap-2">
                    <Microscope className="h-4 w-4 text-[#1d1d1f]" />
                    <h2 className="text-lg font-semibold text-[#1d1d1f]">Scenario Comparison</h2>
                </div>
                {simulationQuery.isError ? (
                    <div className="card border border-[#ff3b30]/20 bg-[#ff3b30]/5 p-12 text-center text-sm text-[#c9342a]">
                        {getApiErrorDetail(simulationQuery.error, 'Unable to load scenario comparison.')}
                    </div>
                ) : simulationQuery.isLoading ? (
                    <div className="card p-12 text-center text-sm text-[#86868b]">Loading scenario comparison…</div>
                ) : (
                    <PolicyComparisonTable report={simulationQuery.data} />
                )}
            </section>
        </div>
    )
}

function EvidenceBoundaryPanel({
    readiness,
    modelEvidence,
    impact,
    simulation,
    loading,
}: {
    readiness: DataReadiness | undefined
    modelEvidence: ActiveModelEvidence | undefined
    impact: RecommendationImpact | undefined
    simulation: ReplenishmentSimulationReport | undefined
    loading: {
        readiness: boolean
        modelEvidence: boolean
        impact: boolean
        simulation: boolean
    }
}) {
    return (
        <section className="card space-y-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <ClipboardCheck className="h-4 w-4 text-[#0071e3]" />
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Evidence Boundaries</h2>
                    </div>
                    <p className="mt-2 text-sm text-[#6e6e73]">
                        Each layer keeps its provenance visible so the page can be used in buyer reviews without overstating what has been proven.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <MetricProvenanceBadge label="measured" tone="measured" />
                    <MetricProvenanceBadge label="benchmark" tone="benchmark" />
                    <MetricProvenanceBadge label="simulated" tone="simulated" />
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <EvidenceTile
                    icon={DatabaseZap}
                    label="Data readiness"
                    value={loading.readiness ? 'Loading' : formatLabel(readiness?.state ?? 'not ready')}
                    detail={loading.readiness ? 'readiness check loading' : readiness?.reason_code ?? 'readiness check pending'}
                    provenance={loading.readiness ? 'loading' : readiness ? 'measured' : 'unavailable'}
                />
                <EvidenceTile
                    icon={Brain}
                    label="Active forecast"
                    value={loading.modelEvidence ? 'Loading' : modelEvidence?.version ?? 'not selected'}
                    detail={loading.modelEvidence
                        ? 'forecast evidence loading'
                        : modelEvidence?.holdout.wape !== null && modelEvidence?.holdout.wape !== undefined
                        ? `Holdout WAPE ${formatPercent(modelEvidence.holdout.wape)}`
                        : modelEvidence?.dataset_id ?? 'forecast evidence pending'}
                    provenance={loading.modelEvidence ? 'loading' : modelEvidence ? 'benchmark' : 'unavailable'}
                />
                <EvidenceTile
                    icon={Wallet}
                    label="Decision closeout"
                    value={loading.impact ? 'Loading' : impact ? `${impact.closed_outcomes} closed` : 'not measured yet'}
                    detail={loading.impact
                        ? 'outcome evidence loading'
                        : impact
                        ? `${impact.accepted_count} accepted · ${impact.edited_count} edited · ${impact.rejected_count} rejected`
                        : 'outcome evidence pending'}
                    provenance={loading.impact ? 'loading' : impact?.closed_outcomes_confidence ?? 'unavailable'}
                />
                <EvidenceTile
                    icon={Microscope}
                    label="Policy replay"
                    value={loading.simulation ? 'Loading' : simulation?.series_used ? `${simulation.series_used.toLocaleString()} series` : 'not run yet'}
                    detail={loading.simulation ? 'simulation report loading' : simulation ? `${simulation.replay_start} to ${simulation.replay_end}` : 'simulation report pending'}
                    provenance={loading.simulation ? 'loading' : simulation?.impact_confidence ?? 'unavailable'}
                />
            </div>
        </section>
    )
}

function EvidenceTile({
    icon: Icon,
    label,
    value,
    detail,
    provenance,
}: {
    icon: typeof ClipboardCheck
    label: string
    value: string
    detail: string
    provenance: string
}) {
    return (
        <div className="hero-stat-card">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                <Icon className="h-5 w-5 text-[#1d1d1f]" />
            </div>
            <p className="mt-4 text-sm font-medium text-[#86868b]">{label}</p>
            <p className="mt-1 text-xl font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <p className="mt-2 text-xs text-[#6e6e73]">{detail}</p>
            <div className="mt-3">
                <MetricProvenanceBadge label={provenance} tone={mapTone(provenance)} />
            </div>
        </div>
    )
}

function mapTone(label: string) {
    if (label === 'measured') {
        return 'measured'
    }
    if (label === 'estimated') {
        return 'estimated'
    }
    if (label === 'provisional') {
        return 'provisional'
    }
    if (label === 'simulated') {
        return 'simulated'
    }
    if (label === 'benchmark') {
        return 'benchmark'
    }
    return 'neutral'
}

function formatLabel(value: string) {
    return value.replace(/_/g, ' ')
}

function formatPercent(value: number) {
    return `${(value * 100).toFixed(1)}%`
}
