/**
 * ExperimentHistory — Training run table with metrics.
 */

import { AlertCircle, FlaskConical, Loader2 } from 'lucide-react'
import type { ExperimentRun } from '@/lib/types'

export default function ExperimentHistory({
    experiments,
    isLoading,
    isError,
    errorMessage,
}: {
    experiments: ExperimentRun[]
    isLoading: boolean
    isError: boolean
    errorMessage: string
}) {
    if (isLoading) {
        return (
            <div className="card border border-black/[0.02] shadow-sm text-center py-16">
                <Loader2 className="h-8 w-8 mx-auto mb-3 text-[#0071e3] animate-spin" />
                <p className="text-sm text-[#86868b]">Loading experiments...</p>
            </div>
        )
    }

    if (isError) {
        return (
            <div className="card border border-[#ff3b30]/20 bg-[#ff3b30]/5 shadow-sm text-center py-16">
                <AlertCircle className="h-8 w-8 mx-auto mb-3 text-[#ff3b30]" />
                <p className="text-sm text-[#ff3b30]">{errorMessage}</p>
            </div>
        )
    }

    if (experiments.length === 0) {
        return (
            <div className="card border border-black/[0.02] shadow-sm text-center py-16">
                <FlaskConical className="h-8 w-8 mx-auto mb-3 text-[#86868b]" />
                <p className="text-sm text-[#86868b]">No training runs recorded</p>
                <p className="text-xs text-[#86868b] mt-1">Log a hypothesis above, then run the training pipeline to populate this history.</p>
            </div>
        )
    }

    return (
        <div className="card border border-black/[0.02] shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-black/5 text-left text-xs font-semibold uppercase tracking-wider text-[#86868b]">
                            <th className="px-4 py-3">Experiment</th>
                            <th className="px-4 py-3">Model</th>
                            <th className="px-4 py-3 text-right">MAE</th>
                            <th className="px-4 py-3 text-right">WAPE</th>
                            <th className="px-4 py-3 text-right">MASE</th>
                            <th className="px-4 py-3 text-right">Bias</th>
                            <th className="px-4 py-3">Date</th>
                            <th className="px-4 py-3">Trigger</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-black/5">
                        {experiments.map((run, idx) => {
                            const mae = run.metrics?.mae ?? run.metrics?.test_mae
                            const wape = run.metrics?.wape ?? run.metrics?.test_wape
                            const mase = run.metrics?.mase ?? run.metrics?.test_mase
                            const biasPct = run.metrics?.bias_pct

                            return (
                                <tr key={run.source_file ?? idx} className="hover:bg-[#f5f5f7] transition-colors">
                                    <td className="px-4 py-3">
                                        <div className="flex items-center gap-2">
                                            <FlaskConical className="h-4 w-4 text-[#0071e3]/60" />
                                            <span className="font-medium text-[#1d1d1f] truncate max-w-[200px]">
                                                {run.experiment}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="inline-flex rounded-full bg-[#0071e3]/10 px-2 py-0.5 text-xs font-medium text-[#0071e3]">
                                            {run.model_name}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right font-mono">
                                        {mae !== undefined ? Number(mae).toFixed(2) : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-right font-mono">
                                        {wape !== undefined ? `${(Number(wape) * 100).toFixed(1)}%` : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-right font-mono">
                                        {mase !== undefined ? Number(mase).toFixed(2) : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-right font-mono">
                                        {biasPct !== undefined ? `${(Number(biasPct) * 100).toFixed(1)}%` : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-[#86868b] text-xs">
                                        {run.timestamp
                                            ? new Date(run.timestamp).toLocaleDateString()
                                            : '—'}
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="text-xs text-[#86868b]">
                                            {run.tags?.trigger ?? 'manual'}
                                        </span>
                                    </td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
