/**
 * ModelArena — Active model vs test model comparison cards.
 */

import { useState } from 'react'
import { Trophy, Swords, Archive, CheckCircle2, XCircle } from 'lucide-react'
import type { MLModel } from '@/lib/types'

const STATUS_CONFIG = {
    champion: { icon: Trophy, color: 'text-[#ff9500]', bg: 'bg-[#ff9500]/10', border: 'border-[#ff9500]/20', label: 'Active' },
    challenger: { icon: Swords, color: 'text-[#0071e3]', bg: 'bg-[#0071e3]/10', border: 'border-[#0071e3]/20', label: 'Test' },
    archived: { icon: Archive, color: 'text-[#86868b]', bg: 'bg-[#86868b]/10', border: 'border-[#86868b]/20', label: 'Archived' },
    candidate: { icon: Swords, color: 'text-[#5856d6]', bg: 'bg-[#5856d6]/10', border: 'border-[#5856d6]/20', label: 'Candidate' },
} as const

function formatModelName(name: string): string {
    return name
        .replace('demand_forecast_', '')
        .replace('demand_forecast', 'Global')
        .replace('anomaly_detector', 'Anomaly')
        .replace('_', ' ')
        .replace(/\b\w/g, c => c.toUpperCase())
}

export default function ModelArena({ models, initialVisible = 3 }: { models: MLModel[]; initialVisible?: number }) {
    const [expanded, setExpanded] = useState(false)
    const orderedModels = [...models].sort(compareModelPriority)
    const visibleModels = expanded ? orderedModels : orderedModels.slice(0, initialVisible)
    const hiddenCount = Math.max(orderedModels.length - visibleModels.length, 0)

    const grouped = visibleModels.reduce<Record<string, MLModel[]>>((acc, m) => {
        const key = m.model_name
        if (!acc[key]) acc[key] = []
        acc[key].push(m)
        return acc
    }, {})

    if (Object.keys(grouped).length === 0) {
        return (
            <div className="card border border-black/[0.02] shadow-sm text-center py-16">
                <Trophy className="h-8 w-8 mx-auto mb-3 text-[#86868b]" />
                <p className="text-sm text-[#86868b]">No models registered yet.</p>
                <p className="text-xs text-[#86868b] mt-1">Approved model versions will appear here after validation runs complete.</p>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {Object.entries(grouped).map(([modelName, versions]) => {
                const champion = versions.find(v => v.status === 'champion')
                const challengers = versions.filter(v => v.status === 'challenger' || v.status === 'candidate')
                const archived = versions.filter(v => v.status === 'archived')

                return (
                    <div key={modelName} className="space-y-3">
                        <h3 className="text-sm font-semibold text-[#86868b] uppercase tracking-wider">
                            {formatModelName(modelName)}
                        </h3>

                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                            {champion && <ModelCard model={champion} />}
                            {challengers.map(c => <ModelCard key={c.model_id} model={c} />)}
                            {archived.map(model => <ModelCard key={model.model_id} model={model} />)}
                            {!champion && challengers.length === 0 && archived.length === 0 && (
                                <div className="card border border-dashed border-black/5 p-4 text-center">
                                    <p className="text-sm text-[#86868b]">No active version</p>
                                </div>
                            )}
                        </div>
                    </div>
                )
            })}

            {orderedModels.length > initialVisible && (
                <button
                    type="button"
                    onClick={() => setExpanded(current => !current)}
                    className="w-full rounded-lg border border-black/5 bg-white px-4 py-2 text-sm font-medium text-[#0071e3] shadow-sm transition hover:border-[#0071e3]/30"
                >
                    {expanded ? 'Show fewer models' : `Show ${hiddenCount} more model${hiddenCount === 1 ? '' : 's'}`}
                </button>
            )}
        </div>
    )
}

function compareModelPriority(a: MLModel, b: MLModel) {
    const statusRank: Record<string, number> = {
        champion: 0,
        challenger: 1,
        candidate: 2,
        archived: 3,
    }
    const rankDelta = (statusRank[a.status] ?? 4) - (statusRank[b.status] ?? 4)
    if (rankDelta !== 0) return rankDelta
    const aDate = a.created_at ? new Date(a.created_at).getTime() : 0
    const bDate = b.created_at ? new Date(b.created_at).getTime() : 0
    return bDate - aDate
}

function ModelCard({ model }: { model: MLModel }) {
    const config = STATUS_CONFIG[model.status] ?? STATUS_CONFIG.candidate
    const Icon = config.icon
    const metrics = model.metrics ?? {}
    const mae = Number(metrics.mae ?? metrics.test_mae ?? NaN)
    const wape = Number(metrics.wape ?? NaN)
    const mase = Number(metrics.mase ?? NaN)
    const biasPct = Number(metrics.bias_pct ?? NaN)
    const precision = Number(metrics.precision ?? NaN)
    const recall = Number(metrics.recall ?? NaN)
    const falsePositiveRate = Number(metrics.false_positive_rate ?? NaN)

    return (
        <div className={`card min-w-0 overflow-hidden border ${config.border} p-4 shadow-sm ${config.bg}/30`}>
            <div className="flex items-start justify-between mb-3">
                <div className="flex min-w-0 items-center gap-2">
                    <div className={`h-8 w-8 rounded-lg ${config.bg} flex items-center justify-center`}>
                        <Icon className={`h-4 w-4 ${config.color}`} />
                    </div>
                    <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-[#1d1d1f]" title={model.version}>{model.version}</p>
                        <span className={`text-xs font-medium ${config.color}`}>{config.label}</span>
                    </div>
                </div>
                {model.smoke_test_passed !== null && (
                    model.smoke_test_passed
                        ? <CheckCircle2 className="h-4 w-4 text-[#34c759]" />
                        : <XCircle className="h-4 w-4 text-[#ff3b30]" />
                )}
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
                {!Number.isNaN(mae) && (
                    <div>
                        <p className="text-[#86868b]">MAE</p>
                        <p className="font-mono font-semibold text-[#1d1d1f]">{mae.toFixed(2)}</p>
                    </div>
                )}
                {!Number.isNaN(wape) && (
                    <div>
                        <p className="text-[#86868b]">WAPE</p>
                        <p className="font-mono font-semibold text-[#1d1d1f]">{(wape * 100).toFixed(1)}%</p>
                    </div>
                )}
                {!Number.isNaN(mase) && (
                    <div>
                        <p className="text-[#86868b]">MASE</p>
                        <p className="font-mono font-semibold text-[#1d1d1f]">{mase.toFixed(2)}</p>
                    </div>
                )}
                {!Number.isNaN(biasPct) && (
                    <div>
                        <p className="text-[#86868b]">Bias</p>
                        <p className={`font-mono font-semibold ${biasPct > 0 ? 'text-[#ff3b30]' : biasPct < 0 ? 'text-[#0071e3]' : 'text-[#1d1d1f]'}`}>
                            {(biasPct * 100).toFixed(1)}%
                        </p>
                    </div>
                )}
                {!Number.isNaN(precision) && (
                    <div>
                        <p className="text-[#86868b]">Precision</p>
                        <p className="font-mono font-semibold text-[#1d1d1f]">{(precision * 100).toFixed(1)}%</p>
                    </div>
                )}
                {!Number.isNaN(recall) && (
                    <div>
                        <p className="text-[#86868b]">Recall</p>
                        <p className="font-mono font-semibold text-[#1d1d1f]">{(recall * 100).toFixed(1)}%</p>
                    </div>
                )}
                {!Number.isNaN(falsePositiveRate) && (
                    <div>
                        <p className="text-[#86868b]">FPR</p>
                        <p className="font-mono font-semibold text-[#1d1d1f]">{(falsePositiveRate * 100).toFixed(1)}%</p>
                    </div>
                )}
                {model.routing_weight !== null && (
                    <div>
                        <p className="text-[#86868b]">Traffic</p>
                        <p className="font-mono font-semibold text-[#1d1d1f]">{(model.routing_weight * 100).toFixed(0)}%</p>
                    </div>
                )}
                {model.created_at && (
                    <div>
                        <p className="text-[#86868b]">Trained</p>
                        <p className="font-mono text-[#1d1d1f]">{new Date(model.created_at).toLocaleDateString()}</p>
                    </div>
                )}
            </div>

            <div className="mt-3 space-y-1 border-t border-black/5 pt-3 text-[11px] text-[#86868b]">
                {model.dataset_id && <ModelMetadataRow label="Dataset" value={model.dataset_id} />}
                {model.forecast_grain && <ModelMetadataRow label="Grain" value={model.forecast_grain} />}
                {model.segment_strategy && <ModelMetadataRow label="Segmentation" value={model.segment_strategy} />}
                {typeof model.rule_overlay_enabled === 'boolean' && (
                    <ModelMetadataRow label="Policy overlay" value={model.rule_overlay_enabled ? 'enabled' : 'model only'} />
                )}
                {model.promotion_reason && (
                    <p className="break-words text-[#86868b]">Promotion: {model.promotion_reason.replace(/_/g, ' ')}</p>
                )}
            </div>
        </div>
    )
}

function ModelMetadataRow({ label, value }: { label: string; value: string }) {
    return (
        <p className="min-w-0">
            {label}:{' '}
            <span className="break-words font-mono text-[#1d1d1f] [overflow-wrap:anywhere]" title={value}>
                {value}
            </span>
        </p>
    )
}
