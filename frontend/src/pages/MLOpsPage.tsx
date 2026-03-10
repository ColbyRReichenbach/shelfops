/**
 * ML Ops Command Center — Model health, experiments, backtests, data health.
 */

import { useState } from 'react'
import { Brain, FlaskConical, TrendingDown, Database, Sparkles, ShieldCheck, DollarSign, Activity } from 'lucide-react'
import {
    useMLModels, useBacktests, useExperiments,
    useModelHistory, useModelSHAP, useMLEffectiveness, useMLHealth, useSyncHealth,
} from '@/hooks/useShelfOps'
import type { MLEffectiveness, ModelHistoryEntry } from '@/lib/types'
import ModelArena from '@/components/mlops/ModelArena'
import BacktestCharts from '@/components/mlops/BacktestCharts'
import FeatureImportance from '@/components/mlops/FeatureImportance'
import ExperimentWorkbench from '@/components/mlops/ExperimentWorkbench'
import DataHealthDashboard from '@/components/mlops/DataHealthDashboard'

const TABS = [
    { key: 'models', label: 'Models', icon: Brain },
    { key: 'experiments', label: 'Experiments', icon: FlaskConical },
    { key: 'backtests', label: 'Backtests', icon: TrendingDown },
    { key: 'data', label: 'Data Health', icon: Database },
] as const

type TabKey = (typeof TABS)[number]['key']

export default function MLOpsPage() {
    const [activeTab, setActiveTab] = useState<TabKey>('models')
    const [modelFilter, setModelFilter] = useState<string>('')

    const { data: health, isLoading: healthLoading } = useMLHealth()
    const { data: models = [] } = useMLModels(modelFilter || undefined)
    const { data: backtests = [], isLoading: backtestsLoading } = useBacktests(90, modelFilter || undefined)
    const {
        data: experiments = [],
        isLoading: experimentsLoading,
        isError: experimentsError,
        error: experimentsErrorDetail,
    } = useExperiments(modelFilter || undefined)
    const { data: modelHistory = [], isError: modelHistoryError, error: modelHistoryErrorDetail } = useModelHistory(12)
    const { data: syncData = [], isLoading: syncLoading } = useSyncHealth()
    const { data: effectiveness } = useMLEffectiveness(30, modelFilter || 'demand_forecast')

    const activeModelName = modelFilter || 'demand_forecast'
    const championForInsights =
        health?.champions?.find(champion => champion.model_name === activeModelName) ??
        health?.champions?.find(champion => champion.model_name === 'demand_forecast') ??
        health?.champions?.[0]
    const championVersion = championForInsights?.version ?? ''
    const { data: shapData, isLoading: shapLoading } = useModelSHAP(championVersion)

    // Unique model names for filter dropdown
    const modelNames = [...new Set(models.map(m => m.model_name))]

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">ML Ops</h1>
                    <p className="text-sm text-shelf-foreground/60 mt-1">
                        {healthLoading ? 'Loading...' : (
                            <>
                                {health?.champions?.length ?? 0} champion{(health?.champions?.length ?? 0) !== 1 ? 's' : ''} active
                                {' '}&middot;{' '}
                                {health?.recent_backtests_7d ?? 0} backtests this week
                                {' '}&middot;{' '}
                                {Object.values(health?.model_counts ?? {}).reduce((a, b) => a + b, 0)} total versions
                            </>
                        )}
                    </p>
                </div>

                {/* Health indicator */}
                {health && (
                    <div className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium ${
                        health.status === 'healthy'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-yellow-100 text-yellow-700'
                    }`}>
                        <div className={`h-2 w-2 rounded-full ${health.status === 'healthy' ? 'bg-green-500' : 'bg-yellow-500'} animate-pulse`} />
                        {health.status === 'healthy' ? 'System Healthy' : 'Needs Attention'}
                    </div>
                )}
            </div>

            {/* Champion Summary Cards */}
            {health && health.champions.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {health.champions.map(c => (
                        <div key={c.model_name} className="card border border-amber-200 shadow-sm p-4 bg-amber-50/30">
                            <div className="flex items-center gap-2 mb-2">
                                <Sparkles className="h-4 w-4 text-amber-600" />
                                <p className="text-xs font-medium text-amber-700 uppercase tracking-wider">Champion</p>
                            </div>
                            <p className="text-sm font-semibold text-shelf-foreground">{c.model_name.replace('demand_forecast', 'Forecast').replace(/_/g, ' ')}</p>
                            <p className="text-xs text-shelf-foreground/50 font-mono">{c.version}</p>
                            {c.metrics && (
                                <div className="mt-1 space-y-1 text-xs text-shelf-foreground/60">
                                    <p>MASE: {typeof c.metrics.mase === 'number' ? c.metrics.mase.toFixed(2) : '—'}</p>
                                    <p>WAPE: {typeof c.metrics.wape === 'number' ? `${(c.metrics.wape * 100).toFixed(1)}%` : '—'}</p>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {effectiveness?.status === 'ok' && effectiveness.metrics && (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                    <MetricCard
                        icon={ShieldCheck}
                        label="Current Champion"
                        value={effectiveness.metrics.mase !== null ? effectiveness.metrics.mase.toFixed(2) : '—'}
                        detail={`MASE · ${effectiveness.trend}`}
                    />
                    <MetricCard
                        icon={Activity}
                        label="Forecast Bias"
                        value={effectiveness.metrics.bias_pct !== null ? `${(effectiveness.metrics.bias_pct * 100).toFixed(1)}%` : '—'}
                        detail="Signed bias; positive means over-forecasting"
                    />
                    <MetricCard
                        icon={TrendingDown}
                        label="Stockout Miss"
                        value={effectiveness.metrics.stockout_miss_rate !== null ? `${(effectiveness.metrics.stockout_miss_rate * 100).toFixed(1)}%` : '—' }
                        detail={`Coverage ${effectiveness.metrics.coverage !== null ? `${(effectiveness.metrics.coverage * 100).toFixed(0)}%` : '—'}`}
                    />
                    <MetricCard
                        icon={DollarSign}
                        label="Opportunity Cost"
                        value={effectiveness.metrics.opportunity_cost_stockout !== null ? `$${Math.round(effectiveness.metrics.opportunity_cost_stockout).toLocaleString()}` : '—'}
                        detail="Lost-sales risk over the active window"
                    />
                </div>
            )}

            {/* Tabs + Filter */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex gap-1 rounded-lg bg-shelf-secondary/10 p-1">
                    {TABS.map(tab => {
                        const Icon = tab.icon
                        return (
                            <button
                                key={tab.key}
                                onClick={() => setActiveTab(tab.key)}
                                className={`flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-all ${
                                    activeTab === tab.key
                                        ? 'bg-white text-shelf-primary shadow-sm'
                                        : 'text-shelf-foreground/60 hover:text-shelf-primary'
                                }`}
                            >
                                <Icon className="h-4 w-4" />
                                {tab.label}
                            </button>
                        )
                    })}
                </div>

                {activeTab !== 'data' && modelNames.length > 1 && (
                    <select
                        value={modelFilter}
                        onChange={e => setModelFilter(e.target.value)}
                        className="rounded-lg border border-shelf-foreground/10 bg-white px-3 py-1.5 text-sm text-shelf-foreground"
                    >
                        <option value="">All Models</option>
                        {modelNames.map(name => (
                            <option key={name} value={name}>{name}</option>
                        ))}
                    </select>
                )}
            </div>

            {/* Tab Content */}
            {activeTab === 'models' && (
                <div className="space-y-6">
                    {effectiveness?.status === 'ok' && effectiveness.metrics && (
                        <GovernanceScorecard effectiveness={effectiveness} />
                    )}
                    <ModelArena models={models} />
                    {modelHistory.length > 0 && (
                        <ModelHistoryTable
                            history={modelHistory}
                            isError={modelHistoryError}
                            errorMessage={modelHistoryErrorDetail instanceof Error ? modelHistoryErrorDetail.message : 'Unable to load model lineage.'}
                        />
                    )}
                    {shapData && shapData.features.length > 0 && (
                        <FeatureImportance
                            features={shapData.features}
                            isLoading={shapLoading}
                            version={championVersion}
                        />
                    )}
                </div>
            )}

            {activeTab === 'experiments' && (
                <ExperimentWorkbench
                    modelNames={modelNames}
                    defaultModelName={modelFilter || modelNames[0] || 'demand_forecast'}
                    runHistory={experiments}
                    runsLoading={experimentsLoading}
                    runsError={experimentsError}
                    runsErrorMessage={experimentsErrorDetail instanceof Error ? experimentsErrorDetail.message : 'Unable to load training run evidence.'}
                />
            )}

            {activeTab === 'backtests' && (
                <BacktestCharts backtests={backtests} isLoading={backtestsLoading} />
            )}

            {activeTab === 'data' && (
                <DataHealthDashboard syncData={syncData} isLoading={syncLoading} />
            )}
        </div>
    )
}

function MetricCard({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof ShieldCheck
    label: string
    value: string
    detail: string
}) {
    return (
        <div className="card border border-white/40 shadow-sm p-4">
            <div className="flex items-center gap-2 mb-2">
                <Icon className="h-4 w-4 text-shelf-primary" />
                <p className="text-xs uppercase tracking-wider text-shelf-foreground/50 font-medium">{label}</p>
            </div>
            <p className="text-2xl font-semibold text-shelf-foreground">{value}</p>
            <p className="text-xs text-shelf-foreground/55 mt-1">{detail}</p>
        </div>
    )
}

function GovernanceScorecard({ effectiveness }: { effectiveness: MLEffectiveness }) {
    const familySegments = effectiveness.segment_breakdowns?.family?.segments ?? []
    const topFamily = familySegments[0]

    return (
        <div className="card border border-white/40 shadow-sm p-5 space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h2 className="text-lg font-semibold text-shelf-primary">Model Governance Scorecard</h2>
                    <p className="text-sm text-shelf-foreground/60 mt-1">
                        {effectiveness.model_name.replace(/_/g, ' ')} · {effectiveness.forecast_grain ?? 'unknown grain'} · {effectiveness.confidence}
                    </p>
                </div>
                <div className="text-xs text-shelf-foreground/55">
                    Window: {effectiveness.evaluation_window?.start_date ?? '—'} to {effectiveness.evaluation_window?.end_date ?? '—'}
                </div>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                <ScoreCell label="WAPE" value={effectiveness.metrics?.wape !== null ? `${((effectiveness.metrics?.wape ?? 0) * 100).toFixed(1)}%` : '—'} />
                <ScoreCell label="MASE" value={effectiveness.metrics?.mase !== null ? (effectiveness.metrics?.mase ?? 0).toFixed(2) : '—'} />
                <ScoreCell label="Overstock $" value={effectiveness.metrics?.overstock_dollars !== null ? `$${Math.round(effectiveness.metrics?.overstock_dollars ?? 0).toLocaleString()}` : '—'} />
                <ScoreCell label="Lost Sales Qty" value={effectiveness.metrics?.lost_sales_qty !== null ? Math.round(effectiveness.metrics?.lost_sales_qty ?? 0).toLocaleString() : '—'} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-xl border border-shelf-foreground/10 bg-shelf-secondary/5 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-shelf-foreground/50">Promotion Logic</p>
                    <div className="mt-3 space-y-2 text-sm text-shelf-foreground/70">
                        <p>Champion/challenger promotion now follows business and DS guardrails together.</p>
                        <p>Primary scorecard: MASE, WAPE, bias, stockout miss, and overstock economics.</p>
                        <p>Rule overlays are tracked separately so raw model quality is visible.</p>
                        {effectiveness.by_version?.[0]?.dataset_id && (
                            <p>Dataset lineage: {effectiveness.by_version[0].dataset_id} / {effectiveness.by_version[0].forecast_grain ?? 'unknown grain'}</p>
                        )}
                    </div>
                </div>
                <div className="rounded-xl border border-shelf-foreground/10 bg-shelf-secondary/5 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-shelf-foreground/50">Segment Evidence</p>
                    <div className="mt-3 space-y-2 text-sm text-shelf-foreground/70">
                        <p>Family breakdowns available: {effectiveness.segment_breakdowns?.family?.available ? 'yes' : 'no'}</p>
                        <p>Store deciles available: {effectiveness.segment_breakdowns?.store_decile?.available ? 'yes' : 'no'}</p>
                        <p>Promo breakdowns available: {effectiveness.segment_breakdowns?.promo?.available ? 'yes' : 'no'}</p>
                        {topFamily && (
                            <p>
                                Largest family segment: <span className="font-medium text-shelf-foreground">{topFamily.segment}</span>
                                {' '}({topFamily.samples} rows, {(topFamily.wape * 100).toFixed(1)}% WAPE)
                            </p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

function ScoreCell({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-xl border border-shelf-foreground/10 bg-white/70 p-3">
            <p className="text-xs uppercase tracking-wider text-shelf-foreground/50">{label}</p>
            <p className="mt-1 text-lg font-semibold text-shelf-foreground">{value}</p>
        </div>
    )
}

function ModelHistoryTable({
    history,
    isError,
    errorMessage,
}: {
    history: ModelHistoryEntry[]
    isError: boolean
    errorMessage: string
}) {
    if (isError) {
        return (
            <div className="card border border-red-200 bg-red-50/50 shadow-sm p-5 text-sm text-red-700">
                {errorMessage}
            </div>
        )
    }

    return (
        <div className="card border border-white/40 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-shelf-foreground/5">
                <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Model Lineage</h3>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-shelf-foreground/5 text-left text-xs font-semibold uppercase tracking-wider text-shelf-foreground/50">
                            <th className="px-4 py-3">Version</th>
                            <th className="px-4 py-3">Status</th>
                            <th className="px-4 py-3">Lineage</th>
                            <th className="px-4 py-3 text-right">MASE</th>
                            <th className="px-4 py-3 text-right">WAPE</th>
                            <th className="px-4 py-3">Dates</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-shelf-foreground/5">
                        {history.map(row => (
                            <tr key={row.version} className="hover:bg-shelf-foreground/[0.02] transition-colors">
                                <td className="px-4 py-3 font-mono text-xs">{row.version}</td>
                                <td className="px-4 py-3">
                                    <span className="inline-flex rounded-full bg-shelf-primary/10 px-2 py-0.5 text-xs font-medium text-shelf-primary">
                                        {row.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-xs text-shelf-foreground/65">
                                    <div>{row.lineage_label ?? '—'}</div>
                                    <div>{row.architecture ?? '—'} / {row.objective ?? '—'} / {row.feature_set_id ?? '—'}</div>
                                </td>
                                <td className="px-4 py-3 text-right font-mono">{row.mase !== null ? row.mase.toFixed(2) : '—'}</td>
                                <td className="px-4 py-3 text-right font-mono">{row.wape !== null ? `${(row.wape * 100).toFixed(1)}%` : '—'}</td>
                                <td className="px-4 py-3 text-xs text-shelf-foreground/60">
                                    <div>Created: {new Date(row.created_at).toLocaleDateString()}</div>
                                    <div>Promoted: {row.promoted_at ? new Date(row.promoted_at).toLocaleDateString() : '—'}</div>
                                    <div>Archived: {row.archived_at ? new Date(row.archived_at).toLocaleDateString() : '—'}</div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
