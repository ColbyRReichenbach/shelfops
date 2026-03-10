/**
 * ModelArena — Champion vs Challenger model comparison cards.
 */

import { Trophy, Swords, Archive, CheckCircle2, XCircle } from 'lucide-react'
import type { MLModel } from '@/lib/types'

const STATUS_CONFIG = {
    champion: { icon: Trophy, color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200', label: 'Champion' },
    challenger: { icon: Swords, color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200', label: 'Challenger' },
    archived: { icon: Archive, color: 'text-gray-500', bg: 'bg-gray-50', border: 'border-gray-200', label: 'Archived' },
    candidate: { icon: Swords, color: 'text-purple-600', bg: 'bg-purple-50', border: 'border-purple-200', label: 'Candidate' },
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
    // Group by model_name, then show champion + challengers
    const grouped = models.reduce<Record<string, MLModel[]>>((acc, m) => {
        const key = m.model_name
        if (!acc[key]) acc[key] = []
        acc[key].push(m)
        return acc
    }, {})

    if (Object.keys(grouped).length === 0) {
        return (
            <div className="card border border-white/40 shadow-sm text-center py-16">
                <Trophy className="h-8 w-8 mx-auto mb-3 text-shelf-foreground/30" />
                <p className="text-sm text-shelf-foreground/50">No models registered yet</p>
                <p className="text-xs text-shelf-foreground/40 mt-1">Train a model to populate the arena</p>
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
                        <h3 className="text-sm font-semibold text-shelf-foreground/70 uppercase tracking-wider">
                            {formatModelName(modelName)}
                        </h3>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {champion && <ModelCard model={champion} />}
                            {challengers.map(c => <ModelCard key={c.model_id} model={c} />)}
                            {!champion && challengers.length === 0 && (
                                <div className="card border border-dashed border-shelf-foreground/20 p-4 text-center">
                                    <p className="text-sm text-shelf-foreground/40">No active version</p>
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
                        <p className="text-sm font-semibold text-shelf-foreground">{model.version}</p>
                        <span className={`text-xs font-medium ${config.color}`}>{config.label}</span>
                    </div>
                </div>
                {model.smoke_test_passed !== null && (
                    model.smoke_test_passed
                        ? <CheckCircle2 className="h-4 w-4 text-green-500" />
                        : <XCircle className="h-4 w-4 text-red-500" />
                )}
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
                {!Number.isNaN(mae) && (
                    <div>
                        <p className="text-shelf-foreground/50">MAE</p>
                        <p className="font-mono font-semibold text-shelf-foreground">{mae.toFixed(2)}</p>
                    </div>
                )}
                {!Number.isNaN(wape) && (
                    <div>
                        <p className="text-shelf-foreground/50">WAPE</p>
                        <p className="font-mono font-semibold text-shelf-foreground">{(wape * 100).toFixed(1)}%</p>
                    </div>
                )}
                {!Number.isNaN(mase) && (
                    <div>
                        <p className="text-shelf-foreground/50">MASE</p>
                        <p className="font-mono font-semibold text-shelf-foreground">{mase.toFixed(2)}</p>
                    </div>
                )}
                {!Number.isNaN(biasPct) && (
                    <div>
                        <p className="text-shelf-foreground/50">Bias</p>
                        <p className={`font-mono font-semibold ${biasPct > 0 ? 'text-red-600' : biasPct < 0 ? 'text-blue-600' : 'text-shelf-foreground'}`}>
                            {(biasPct * 100).toFixed(1)}%
                        </p>
                    </div>
                )}
                {model.routing_weight !== null && (
                    <div>
                        <p className="text-shelf-foreground/50">Traffic</p>
                        <p className="font-mono font-semibold text-shelf-foreground">{(model.routing_weight * 100).toFixed(0)}%</p>
                    </div>
                )}
                {model.created_at && (
                    <div>
                        <p className="text-shelf-foreground/50">Trained</p>
                        <p className="font-mono text-shelf-foreground">{new Date(model.created_at).toLocaleDateString()}</p>
                    </div>
                )}
            </div>

            <div className="mt-3 border-t border-shelf-foreground/5 pt-3 space-y-1 text-[11px] text-shelf-foreground/55">
                {model.dataset_id && <p>Dataset: <span className="font-mono text-shelf-foreground">{model.dataset_id}</span></p>}
                {model.forecast_grain && <p>Grain: <span className="font-mono text-shelf-foreground">{model.forecast_grain}</span></p>}
                {model.segment_strategy && <p>Segmentation: <span className="font-mono text-shelf-foreground">{model.segment_strategy}</span></p>}
                {typeof model.rule_overlay_enabled === 'boolean' && (
                    <p>Rule overlay: <span className="font-mono text-shelf-foreground">{model.rule_overlay_enabled ? 'enabled' : 'raw model only'}</span></p>
                )}
                {model.promotion_reason && (
                    <p className="text-shelf-foreground/70">Promotion: {model.promotion_reason.replace(/_/g, ' ')}</p>
                )}
            </div>
        </div>
    )
}
