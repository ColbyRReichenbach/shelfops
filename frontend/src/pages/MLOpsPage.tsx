/**
 * ML Ops Command Center — Model health, experiments, backtests, data health.
 */

import { useState } from 'react'
import { Brain, FlaskConical, TrendingDown, Database, Sparkles } from 'lucide-react'
import {
    useMLModels, useBacktests, useExperiments,
    useModelSHAP, useMLHealth, useSyncHealth,
} from '@/hooks/useShelfOps'
import ModelArena from '@/components/mlops/ModelArena'
import BacktestCharts from '@/components/mlops/BacktestCharts'
import FeatureImportance from '@/components/mlops/FeatureImportance'
import ExperimentHistory from '@/components/mlops/ExperimentHistory'
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
    const { data: experiments = [], isLoading: experimentsLoading } = useExperiments(modelFilter || undefined)
    const { data: syncData = [], isLoading: syncLoading } = useSyncHealth()

    // Find champion version for SHAP
    const championVersion = health?.champions?.[0]?.version ?? ''
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
                                <p className="text-xs text-shelf-foreground/60 mt-1">
                                    MAE: {(c.metrics.mae ?? c.metrics.test_mae)?.toFixed(2) ?? '—'}
                                </p>
                            )}
                        </div>
                    ))}
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
                    <ModelArena models={models} />
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
                <ExperimentHistory experiments={experiments} isLoading={experimentsLoading} />
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
