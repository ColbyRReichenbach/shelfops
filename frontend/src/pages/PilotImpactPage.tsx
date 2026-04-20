import { BarChart3, Microscope, Wallet } from 'lucide-react'

import ImpactScorecard from '@/components/impact/ImpactScorecard'
import MetricProvenanceBadge from '@/components/impact/MetricProvenanceBadge'
import PolicyComparisonTable from '@/components/impact/PolicyComparisonTable'
import { useRecommendationImpact, useReplenishmentSimulation } from '@/hooks/useShelfOps'
import { getApiErrorDetail } from '@/lib/api'

export default function PilotImpactPage() {
    const impactQuery = useRecommendationImpact()
    const simulationQuery = useReplenishmentSimulation()

    return (
        <div className="page-shell">
            <div className="hero-panel hero-panel-blue">
                <div className="max-w-3xl">
                    <div className="hero-chip text-[#0071e3]">
                        <BarChart3 className="h-3.5 w-3.5" />
                        Impact
                    </div>
                    <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">
                        Track business results and planning scenarios.
                    </h1>
                    <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                        Review recent recommendation outcomes alongside scenario comparisons. Labels on each metric show whether the number comes from live activity, modeled estimates, or benchmark replay.
                    </p>
                </div>
            </div>

            <section className="card space-y-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <Wallet className="h-4 w-4 text-[#0071e3]" />
                            <h2 className="text-lg font-semibold text-[#1d1d1f]">Outcome Scorecard</h2>
                        </div>
                        <p className="mt-2 text-sm text-[#6e6e73]">
                            These metrics summarize recent recommendation performance. Some values come from observed activity, while others stay modeled until the full closeout window is complete.
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
                        {getApiErrorDetail(impactQuery.error, 'Failed to load operational impact.')}
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
                        {getApiErrorDetail(simulationQuery.error, 'Failed to load simulation report.')}
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
