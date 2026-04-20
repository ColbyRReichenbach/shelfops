import { ArrowRightLeft } from 'lucide-react'

import MetricProvenanceBadge from '@/components/impact/MetricProvenanceBadge'
import type { ReplenishmentSimulationReport } from '@/lib/types'

interface PolicyComparisonTableProps {
    report: ReplenishmentSimulationReport | undefined
}

export default function PolicyComparisonTable({ report }: PolicyComparisonTableProps) {
    return (
        <section className="card overflow-hidden p-0">
            <div className="border-b border-black/[0.04] bg-[#1d1d1f] px-6 py-5 text-white">
                <div className="flex items-center gap-2">
                    <ArrowRightLeft className="h-4 w-4 text-white" />
                    <h2 className="text-lg font-semibold">Policy Scenario Comparison</h2>
                </div>
                <p className="mt-2 max-w-3xl text-sm text-white/75">
                    Use this table to compare planning policies in a controlled benchmark replay environment. It is a scenario tool, not a record of live business results.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                    <MetricProvenanceBadge label={report?.impact_confidence ?? 'simulated'} tone="simulated" />
                    <MetricProvenanceBadge label={report?.claim_boundary ?? 'Benchmark simulation only.'} tone="neutral" />
                </div>
            </div>

            {report?.results?.length ? (
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-black/[0.04] bg-white">
                        <thead className="bg-[#fbfbfd] text-left text-xs uppercase tracking-[0.18em] text-[#86868b]">
                            <tr>
                                <th className="px-6 py-4 font-medium">Policy</th>
                                <th className="px-4 py-4 font-medium">Service level</th>
                                <th className="px-4 py-4 font-medium">Stockout days</th>
                                <th className="px-4 py-4 font-medium">Lost sales proxy</th>
                                <th className="px-4 py-4 font-medium">Overstock dollars</th>
                                <th className="px-4 py-4 font-medium">PO count</th>
                                <th className="px-6 py-4 font-medium">Combined cost proxy</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-black/[0.04]">
                            {report.results.map(row => (
                                <tr key={row.policy_name}>
                                    <td className="px-6 py-4">
                                        <div>
                                            <p className="text-sm font-semibold text-[#1d1d1f]">{row.policy_name}</p>
                                            <p className="mt-1 text-xs text-[#86868b]">{report.policy_version ?? report.policy_versions?.[0] ?? 'policy version unavailable'}</p>
                                        </div>
                                    </td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{(row.service_level * 100).toFixed(1)}%</td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{row.stockout_days.toLocaleString()}</td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{row.lost_sales_proxy.toFixed(1)}</td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{formatCurrency(row.overstock_dollars)}</td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{row.po_count.toLocaleString()}</td>
                                    <td className="px-6 py-4 text-sm font-semibold text-[#1d1d1f]">{row.combined_cost_proxy.toFixed(1)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            ) : (
                <div className="px-6 py-14 text-center text-sm text-[#86868b]">No scenario report available.</div>
            )}
        </section>
    )
}

function formatCurrency(value: number) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
    }).format(value)
}
