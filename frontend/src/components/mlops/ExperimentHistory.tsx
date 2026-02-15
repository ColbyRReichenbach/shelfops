/**
 * ExperimentHistory — Training run table with metrics.
 */

import { FlaskConical, Loader2 } from 'lucide-react'
import type { ExperimentRun } from '@/lib/types'

export default function ExperimentHistory({
    experiments,
    isLoading,
}: {
    experiments: ExperimentRun[]
    isLoading: boolean
}) {
    if (isLoading) {
        return (
            <div className="card border border-white/40 shadow-sm text-center py-16">
                <Loader2 className="h-8 w-8 mx-auto mb-3 text-shelf-primary animate-spin" />
                <p className="text-sm text-shelf-foreground/60">Loading experiments...</p>
            </div>
        )
    }

    if (experiments.length === 0) {
        return (
            <div className="card border border-white/40 shadow-sm text-center py-16">
                <FlaskConical className="h-8 w-8 mx-auto mb-3 text-shelf-foreground/30" />
                <p className="text-sm text-shelf-foreground/50">No training runs recorded</p>
                <p className="text-xs text-shelf-foreground/40 mt-1">Run train_category_models.py to create experiments</p>
            </div>
        )
    }

    return (
        <div className="card border border-white/40 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-shelf-foreground/5 text-left text-xs font-semibold uppercase tracking-wider text-shelf-foreground/50">
                            <th className="px-4 py-3">Experiment</th>
                            <th className="px-4 py-3">Model</th>
                            <th className="px-4 py-3 text-right">MAE</th>
                            <th className="px-4 py-3 text-right">MAPE</th>
                            <th className="px-4 py-3 text-right">R²</th>
                            <th className="px-4 py-3">Date</th>
                            <th className="px-4 py-3">Trigger</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-shelf-foreground/5">
                        {experiments.map((run, idx) => {
                            const mae = run.metrics?.mae ?? run.metrics?.test_mae
                            const mape = run.metrics?.mape ?? run.metrics?.test_mape
                            const r2 = run.metrics?.r2 ?? run.metrics?.test_r2

                            return (
                                <tr key={run.source_file ?? idx} className="hover:bg-shelf-foreground/[0.02] transition-colors">
                                    <td className="px-4 py-3">
                                        <div className="flex items-center gap-2">
                                            <FlaskConical className="h-4 w-4 text-shelf-primary/60" />
                                            <span className="font-medium text-shelf-foreground truncate max-w-[200px]">
                                                {run.experiment}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="inline-flex rounded-full bg-shelf-primary/10 px-2 py-0.5 text-xs font-medium text-shelf-primary">
                                            {run.model_name}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right font-mono">
                                        {mae !== undefined ? Number(mae).toFixed(2) : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-right font-mono">
                                        {mape !== undefined ? `${(Number(mape) * 100).toFixed(1)}%` : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-right font-mono">
                                        {r2 !== undefined ? Number(r2).toFixed(3) : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-shelf-foreground/60 text-xs">
                                        {run.timestamp
                                            ? new Date(run.timestamp).toLocaleDateString()
                                            : '—'}
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="text-xs text-shelf-foreground/50">
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
