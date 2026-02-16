import { Activity, GitBranch, Radar } from 'lucide-react'
import type { ModelHealthResponse } from '@/lib/types'

interface ModelHealthDeckProps {
    health?: ModelHealthResponse
    isLoading?: boolean
    canPromote: boolean
    promotableVersion?: string | null
    onRequestPromote: (version: string) => void
    promotePending: boolean
}

function DateValue({ value }: { value: string | null | undefined }) {
    if (!value) return <span className="text-shelf-foreground/40">—</span>
    return <span>{new Date(value).toLocaleString()}</span>
}

export default function ModelHealthDeck({
    health,
    isLoading = false,
    canPromote,
    promotableVersion,
    onRequestPromote,
    promotePending,
}: ModelHealthDeckProps) {
    const champion = health?.champion
    const challenger = health?.challenger
    const triggers = health?.retraining_triggers

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="card border border-white/40 shadow-sm">
                <div className="flex items-start justify-between mb-3">
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Champion</h3>
                    <Activity className="h-4 w-4 text-shelf-primary/70" />
                </div>
                {isLoading ? (
                    <p className="text-sm text-shelf-foreground/50">Loading champion...</p>
                ) : champion ? (
                    <div className="space-y-2 text-sm">
                        <p><span className="text-shelf-foreground/50">Version:</span> <span className="font-mono">{champion.version}</span></p>
                        <p><span className="text-shelf-foreground/50">Trend:</span> {champion.trend}</p>
                        <p><span className="text-shelf-foreground/50">MAE 7d:</span> {champion.mae_7d ?? '—'}</p>
                        <p><span className="text-shelf-foreground/50">MAE 30d:</span> {champion.mae_30d ?? '—'}</p>
                        <p><span className="text-shelf-foreground/50">Promoted:</span> <DateValue value={champion.promoted_at} /></p>
                    </div>
                ) : (
                    <p className="text-sm text-shelf-foreground/50">No registered forecast model yet.</p>
                )}
            </div>

            <div className="card border border-white/40 shadow-sm">
                <div className="flex items-start justify-between mb-3">
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Challenger</h3>
                    <GitBranch className="h-4 w-4 text-shelf-primary/70" />
                </div>
                {isLoading ? (
                    <p className="text-sm text-shelf-foreground/50">Loading challenger...</p>
                ) : challenger ? (
                    <div className="space-y-2 text-sm">
                        <p><span className="text-shelf-foreground/50">Version:</span> <span className="font-mono">{challenger.version}</span></p>
                        <p><span className="text-shelf-foreground/50">Status:</span> {challenger.status}</p>
                        <p><span className="text-shelf-foreground/50">MAE 7d:</span> {challenger.mae_7d ?? '—'}</p>
                        <p><span className="text-shelf-foreground/50">Confidence:</span> {challenger.confidence ?? '—'}</p>
                        <p><span className="text-shelf-foreground/50">Eligible:</span> {challenger.promotion_eligible ? 'Yes' : 'No'}</p>
                        {canPromote && promotableVersion && (
                            <button
                                onClick={() => onRequestPromote(promotableVersion)}
                                className="btn-primary text-xs h-8 px-3 mt-2"
                                disabled={promotePending}
                            >
                                {promotePending ? 'Promoting...' : `Promote ${promotableVersion}`}
                            </button>
                        )}
                    </div>
                ) : (
                    <p className="text-sm text-shelf-foreground/50">No challenger model available.</p>
                )}
            </div>

            <div className="card border border-white/40 shadow-sm">
                <div className="flex items-start justify-between mb-3">
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Retrain Triggers</h3>
                    <Radar className="h-4 w-4 text-shelf-primary/70" />
                </div>
                {isLoading ? (
                    <p className="text-sm text-shelf-foreground/50">Loading trigger state...</p>
                ) : (
                    <div className="space-y-2 text-sm">
                        <p><span className="text-shelf-foreground/50">Drift detected:</span> {triggers?.drift_detected ? 'Yes' : 'No'}</p>
                        <p><span className="text-shelf-foreground/50">New data:</span> {triggers?.new_data_available ? 'Yes' : 'No'}</p>
                        <p><span className="text-shelf-foreground/50">Last trigger:</span> {triggers?.last_trigger ?? '—'}</p>
                        <p><span className="text-shelf-foreground/50">Last retrain:</span> <DateValue value={triggers?.last_retrain_at} /></p>
                        <p><span className="text-shelf-foreground/50">Next window:</span> Weekly Sunday 02:00 UTC</p>
                    </div>
                )}
            </div>
        </div>
    )
}
