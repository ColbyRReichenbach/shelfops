/**
 * ModelArena — Active model vs test model comparison cards.
 */

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

export default function ModelArena({ models }: { models: MLModel[] }) {
    // Group by model_name, then show the active version and any test candidates.
    const grouped = models.reduce<Record<string, MLModel[]>>((acc, m) => {
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
                <p className="text-xs text-[#86868b] mt-1">Run training to populate this view.</p>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {Object.entries(grouped).map(([modelName, versions]) => {
                const champion = versions.find(v => v.status === 'champion')
                const challengers = versions.filter(v => v.status === 'challenger' || v.status === 'candidate')

                return (
                    <div key={modelName} className="space-y-3">
                        <h3 className="text-sm font-semibold text-[#86868b] uppercase tracking-wider">
                            {formatModelName(modelName)}
                        </h3>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {champion && <ModelCard model={champion} />}
                            {challengers.map(c => <ModelCard key={c.model_id} model={c} />)}
                            {!champion && challengers.length === 0 && (
                                <div className="card border border-dashed border-black/5 p-4 text-center">
                                    <p className="text-sm text-[#86868b]">No active version</p>
                                </div>
                            )}
                        </div>
                    </div>
                )
            })}
        </div>
    )
}

function ModelCard({ model }: { model: MLModel }) {
    const config = STATUS_CONFIG[model.status] ?? STATUS_CONFIG.candidate
    const Icon = config.icon
    const metrics = model.metrics ?? {}
    const mae = Number(metrics.mae ?? metrics.test_mae ?? NaN)
    const wape = Number(metrics.wape ?? NaN)
    const mase = Number(metrics.mase ?? NaN)
    const biasPct = Number(metrics.bias_pct ?? NaN)

    return (
        <div className={`card border ${config.border} shadow-sm p-4 ${config.bg}/30`}>
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                    <div className={`h-8 w-8 rounded-lg ${config.bg} flex items-center justify-center`}>
                        <Icon className={`h-4 w-4 ${config.color}`} />
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-[#1d1d1f]">{model.version}</p>
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

            <div className="mt-3 border-t border-black/5 pt-3 space-y-1 text-[11px] text-[#86868b]">
                {model.dataset_id && <p>Dataset: <span className="font-mono text-[#1d1d1f]">{model.dataset_id}</span></p>}
                {model.forecast_grain && <p>Grain: <span className="font-mono text-[#1d1d1f]">{model.forecast_grain}</span></p>}
                {model.segment_strategy && <p>Segmentation: <span className="font-mono text-[#1d1d1f]">{model.segment_strategy}</span></p>}
                {typeof model.rule_overlay_enabled === 'boolean' && (
                    <p>Rule overlay: <span className="font-mono text-[#1d1d1f]">{model.rule_overlay_enabled ? 'enabled' : 'raw model only'}</span></p>
                )}
                {model.promotion_reason && (
                    <p className="text-[#86868b]">Promotion: {model.promotion_reason.replace(/_/g, ' ')}</p>
                )}
            </div>
        </div>
    )
}
