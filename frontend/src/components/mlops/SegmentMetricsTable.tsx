import type { MLEffectiveness } from '@/lib/types'

interface SegmentMetricsTableProps {
    effectiveness: MLEffectiveness | undefined
}

export default function SegmentMetricsTable({ effectiveness }: SegmentMetricsTableProps) {
    const segmentRows = flattenSegmentRows(effectiveness)
    const unavailableSegments = Object.entries(effectiveness?.segment_breakdowns ?? {}).filter(
        ([, breakdown]) => !breakdown.available,
    )

    return (
        <section className="card overflow-hidden border border-black/[0.02] p-0 shadow-sm">
            <div className="border-b border-black/[0.04] px-6 py-5">
                <h2 className="text-lg font-semibold text-[#1d1d1f]">Segment Metrics</h2>
                <p className="mt-2 text-sm text-[#6e6e73]">
                    Review model quality across segments instead of relying on a single rolled-up score.
                </p>
            </div>

            {segmentRows.length === 0 ? (
                <div className="px-6 py-14 text-center text-sm text-[#86868b]">
                    No segment breakdowns are currently available from the effectiveness endpoint.
                </div>
            ) : (
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-black/[0.04] bg-white">
                        <thead className="bg-[#fbfbfd] text-left text-xs uppercase tracking-[0.18em] text-[#86868b]">
                            <tr>
                                <th className="px-6 py-4 font-medium">Breakdown</th>
                                <th className="px-4 py-4 font-medium">Segment</th>
                                <th className="px-4 py-4 font-medium">Samples</th>
                                <th className="px-4 py-4 font-medium">WAPE</th>
                                <th className="px-4 py-4 font-medium">Bias</th>
                                <th className="px-4 py-4 font-medium">Stockout miss</th>
                                <th className="px-6 py-4 font-medium">Overstock rate</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-black/[0.04]">
                            {segmentRows.map(row => (
                                <tr key={`${row.breakdown}-${row.segment}`}>
                                    <td className="px-6 py-4 text-sm font-semibold text-[#1d1d1f]">{row.breakdown}</td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{row.segment}</td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{row.samples.toLocaleString()}</td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{(row.wape * 100).toFixed(1)}%</td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{(row.bias_pct * 100).toFixed(1)}%</td>
                                    <td className="px-4 py-4 text-sm text-[#1d1d1f]">{(row.stockout_miss_rate * 100).toFixed(1)}%</td>
                                    <td className="px-6 py-4 text-sm text-[#1d1d1f]">{(row.overstock_rate * 100).toFixed(1)}%</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {unavailableSegments.length > 0 ? (
                <div className="border-t border-black/[0.04] bg-[#fbfbfd] px-6 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#86868b]">Unavailable Breakdowns</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {unavailableSegments.map(([key, breakdown]) => (
                            <span key={key} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-[#6e6e73] shadow-[0_1px_3px_rgba(0,0,0,0.03)]">
                                {key}: {breakdown.reason ?? 'not available'}
                            </span>
                        ))}
                    </div>
                </div>
            ) : null}
        </section>
    )
}

function flattenSegmentRows(effectiveness: MLEffectiveness | undefined) {
    const breakdowns = effectiveness?.segment_breakdowns ?? {}
    const rows: Array<{
        breakdown: string
        segment: string
        samples: number
        wape: number
        bias_pct: number
        stockout_miss_rate: number
        overstock_rate: number
    }> = []

    for (const [key, breakdown] of Object.entries(breakdowns)) {
        if (!breakdown.available) {
            continue
        }

        for (const segment of breakdown.segments) {
            rows.push({
                breakdown: breakdown.label ?? key,
                segment: segment.segment,
                samples: segment.samples,
                wape: segment.wape,
                bias_pct: segment.bias_pct,
                stockout_miss_rate: segment.stockout_miss_rate,
                overstock_rate: segment.overstock_rate,
            })
        }
    }

    return rows.sort((left, right) => right.samples - left.samples)
}
