import { useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import {
    useActOnMlAlert,
    useAlertEffectiveness,
    useAlertRoi,
    useAnomalyStats,
    useAnomalyEffectiveness,
    useExperiments,
    useMarkMlAlertRead,
    useMlAlerts,
    useMlAlertStats,
    useModelBacktest,
    useModelHealth,
    useModelHistory,
    usePromoteModel,
    useProposeExperiment,
} from '@/hooks/useShelfOps'
import BacktestPanel from '@/components/mlops/BacktestPanel'
import BusinessImpactCards from '@/components/mlops/BusinessImpactCards'
import ExperimentsPanel from '@/components/mlops/ExperimentsPanel'
import MlAlertsPanel from '@/components/mlops/MlAlertsPanel'
import MLOpsEmptyState from '@/components/mlops/MLOpsEmptyState'
import ModelHealthDeck from '@/components/mlops/ModelHealthDeck'
import type { ProposeExperimentRequest } from '@/lib/types'

const MODEL_OPTIONS = [
    { value: 'demand_forecast', label: 'Demand Forecast (v1)' },
    { value: 'anomaly_engine', label: 'Anomaly Engine' },
]
const TABS = ['performance', 'ml_alerts', 'experiments'] as const

export default function MLOpsPage() {
    const [selectedModel, setSelectedModel] = useState('demand_forecast')
    const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>('performance')
    const [backtestVersion, setBacktestVersion] = useState<string | null>(null)
    const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date())
    const [promoteTarget, setPromoteTarget] = useState<string | null>(null)
    const isForecastModel = selectedModel === 'demand_forecast'

    const healthQuery = useModelHealth()
    const historyQuery = useModelHistory(20)
    const statsQuery = useMlAlertStats()
    const alertsQuery = useMlAlerts({ limit: 50 })
    const experimentsQuery = useExperiments({ limit: 50 })
    const alertEffectivenessQuery = useAlertEffectiveness(30)
    const anomalyEffectivenessQuery = useAnomalyEffectiveness(30)
    const anomalyStatsQuery = useAnomalyStats(7)
    const roiQuery = useAlertRoi(90)

    const markRead = useMarkMlAlertRead()
    const actOnAlert = useActOnMlAlert()
    const proposeExperiment = useProposeExperiment()
    const promoteModel = usePromoteModel()

    const history = historyQuery.data ?? []
    const health = healthQuery.data

    useEffect(() => {
        const preferred =
            health?.champion?.version ??
            health?.challenger?.version ??
            history[0]?.version ??
            null
        if (!backtestVersion && preferred) {
            setBacktestVersion(preferred)
        } else if (backtestVersion && !history.some((h) => h.version === backtestVersion) && preferred) {
            setBacktestVersion(preferred)
        }
    }, [backtestVersion, health?.challenger?.version, health?.champion?.version, history])

    const backtestQuery = useModelBacktest(backtestVersion, 90)
    const backtest = backtestQuery.data ?? []

    const promotableVersion = health?.challenger?.promotion_eligible ? health.challenger.version : null
    const canPromote = Boolean(
        promotableVersion &&
        history.some((item) => item.version === promotableVersion)
    )

    const isAllEmpty = useMemo(() => {
        const noModel = !health?.champion && !health?.challenger && history.length === 0
        const noMlAlerts = (alertsQuery.data ?? []).length === 0
        const noExperiments = (experimentsQuery.data ?? []).length === 0
        return noModel && noMlAlerts && noExperiments
    }, [alertsQuery.data, experimentsQuery.data, health?.challenger, health?.champion, history.length])

    async function refreshAll() {
        await Promise.all([
            healthQuery.refetch(),
            historyQuery.refetch(),
            statsQuery.refetch(),
            alertsQuery.refetch(),
            experimentsQuery.refetch(),
            alertEffectivenessQuery.refetch(),
            anomalyEffectivenessQuery.refetch(),
            anomalyStatsQuery.refetch(),
            roiQuery.refetch(),
            backtestVersion ? backtestQuery.refetch() : Promise.resolve(),
        ])
        setLastRefreshed(new Date())
    }

    async function handleProposeExperiment(payload: ProposeExperimentRequest) {
        await proposeExperiment.mutateAsync(payload)
    }

    async function handlePromote(version: string) {
        await promoteModel.mutateAsync(version)
        setPromoteTarget(null)
    }

    const isTopRowLoading =
        statsQuery.isLoading ||
        alertEffectivenessQuery.isLoading ||
        anomalyEffectivenessQuery.isLoading ||
        roiQuery.isLoading

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">MLOps Command Center</h1>
                    <p className="text-sm text-shelf-foreground/60 mt-1">
                        Monitoring-first control layer for model health, governance, and experiments.
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <select
                        value={selectedModel}
                        onChange={(e) => setSelectedModel(e.target.value)}
                        className="rounded-lg border border-shelf-foreground/10 bg-white px-3 py-1.5 text-sm"
                    >
                        {MODEL_OPTIONS.map((model) => (
                            <option key={model.value} value={model.value}>{model.label}</option>
                        ))}
                    </select>
                    <button
                        onClick={refreshAll}
                        className="btn-secondary text-xs h-8 px-3 gap-1"
                    >
                        <RefreshCw className="h-3 w-3" />
                        Refresh
                    </button>
                    <span className="text-xs text-shelf-foreground/50">
                        Last refreshed {lastRefreshed.toLocaleTimeString()}
                    </span>
                </div>
            </div>

            <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-white border border-shelf-foreground/10 px-3 py-1 text-xs">
                    Champion present: {health?.champion ? 'Yes' : 'No'}
                </span>
                <span className="rounded-full bg-white border border-shelf-foreground/10 px-3 py-1 text-xs">
                    Unread ML alerts: {statsQuery.data?.total_unread ?? 0}
                </span>
                <span className="rounded-full bg-white border border-shelf-foreground/10 px-3 py-1 text-xs">
                    Last retrain trigger: {health?.retraining_triggers?.last_trigger ?? '—'}
                </span>
                <span className="rounded-full bg-white border border-shelf-foreground/10 px-3 py-1 text-xs">
                    Anomalies (7d): {anomalyStatsQuery.data?.total_anomalies ?? 0}
                </span>
            </div>

            <BusinessImpactCards
                mlAlertStats={statsQuery.data}
                alertEffectiveness={alertEffectivenessQuery.data}
                anomalyEffectiveness={anomalyEffectivenessQuery.data}
                roi={roiQuery.data}
                isLoading={isTopRowLoading}
            />

            {isForecastModel ? (
                <ModelHealthDeck
                    health={health}
                    isLoading={healthQuery.isLoading}
                    canPromote={canPromote}
                    promotableVersion={promotableVersion}
                    onRequestPromote={(version) => setPromoteTarget(version)}
                    promotePending={promoteModel.isPending}
                />
            ) : (
                <div className="card border border-white/40 shadow-sm">
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider mb-3">
                        Anomaly Engine Status
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                        <div>
                            <p className="text-shelf-foreground/50">Total (7d)</p>
                            <p className="font-semibold">{anomalyStatsQuery.data?.total_anomalies ?? '—'}</p>
                        </div>
                        <div>
                            <p className="text-shelf-foreground/50">Critical</p>
                            <p className="font-semibold">{anomalyStatsQuery.data?.critical ?? '—'}</p>
                        </div>
                        <div>
                            <p className="text-shelf-foreground/50">Warning</p>
                            <p className="font-semibold">{anomalyStatsQuery.data?.warning ?? '—'}</p>
                        </div>
                        <div>
                            <p className="text-shelf-foreground/50">Trend</p>
                            <p className="font-semibold">{anomalyStatsQuery.data?.trend ?? '—'}</p>
                        </div>
                    </div>
                    <p className="text-xs text-shelf-foreground/60 mt-3">
                        Anomaly detection is currently stateless and is monitored separately from champion/challenger forecasting models.
                    </p>
                </div>
            )}

            <div className="flex gap-1 rounded-lg bg-shelf-secondary/10 p-1 w-fit">
                <button
                    onClick={() => setActiveTab('performance')}
                    className={`rounded-md px-4 py-1.5 text-sm font-medium transition-all ${
                        activeTab === 'performance'
                            ? 'bg-white text-shelf-primary shadow-sm'
                            : 'text-shelf-foreground/60 hover:text-shelf-primary'
                    }`}
                >
                    Performance
                </button>
                <button
                    onClick={() => setActiveTab('ml_alerts')}
                    className={`rounded-md px-4 py-1.5 text-sm font-medium transition-all ${
                        activeTab === 'ml_alerts'
                            ? 'bg-white text-shelf-primary shadow-sm'
                            : 'text-shelf-foreground/60 hover:text-shelf-primary'
                    }`}
                >
                    ML Alerts
                </button>
                <button
                    onClick={() => setActiveTab('experiments')}
                    className={`rounded-md px-4 py-1.5 text-sm font-medium transition-all ${
                        activeTab === 'experiments'
                            ? 'bg-white text-shelf-primary shadow-sm'
                            : 'text-shelf-foreground/60 hover:text-shelf-primary'
                    }`}
                >
                    Experiments
                </button>
            </div>

            {activeTab === 'performance' &&
                (isForecastModel ? (
                    <BacktestPanel
                        history={history}
                        backtest={backtest}
                        selectedVersion={backtestVersion}
                        onSelectVersion={setBacktestVersion}
                        isLoadingHistory={historyQuery.isLoading}
                        isLoadingBacktest={backtestQuery.isLoading}
                    />
                ) : (
                    <div className="card border border-white/40 shadow-sm">
                        <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider mb-3">
                            Anomaly Monitoring
                        </h3>
                        <p className="text-sm text-shelf-foreground/70">
                            Anomaly engine does not use forecast-style backtests. Use anomaly effectiveness and false-positive metrics above for evaluation.
                        </p>
                    </div>
                ))}

            {activeTab === 'ml_alerts' && (
                <MlAlertsPanel
                    alerts={alertsQuery.data ?? []}
                    isLoading={alertsQuery.isLoading}
                    markReadPending={markRead.isPending}
                    actionPending={actOnAlert.isPending}
                    onMarkRead={(alertId) => markRead.mutate(alertId)}
                    onAction={(alertId, action) => actOnAlert.mutate({ alertId, action })}
                />
            )}

            {activeTab === 'experiments' && (
                <ExperimentsPanel
                    experiments={experimentsQuery.data ?? []}
                    isLoading={experimentsQuery.isLoading}
                    proposePending={proposeExperiment.isPending}
                    onPropose={handleProposeExperiment}
                />
            )}

            <MLOpsEmptyState showBootstrap={isAllEmpty} />

            {(healthQuery.isError || historyQuery.isError || alertsQuery.isError || experimentsQuery.isError) && (
                <div className="card border border-red-200 bg-red-50/50 text-red-700 text-sm">
                    Some MLOps endpoints failed to load. The page is still usable with available sections.
                </div>
            )}

            {promoteTarget && isForecastModel && (
                <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
                    <div className="w-full max-w-md rounded-2xl bg-white shadow-xl border border-shelf-foreground/10 p-5 space-y-4">
                        <h4 className="text-lg font-semibold text-shelf-primary">Confirm Promotion</h4>
                        <p className="text-sm text-shelf-foreground/70">
                            Promote <span className="font-mono">{promoteTarget}</span> to champion?
                            This action changes serving priority.
                        </p>
                        <div className="flex justify-end gap-2">
                            <button className="btn-secondary text-xs h-8 px-3" onClick={() => setPromoteTarget(null)}>
                                Cancel
                            </button>
                            <button
                                className="btn-primary text-xs h-8 px-3"
                                onClick={() => handlePromote(promoteTarget)}
                                disabled={promoteModel.isPending}
                            >
                                {promoteModel.isPending ? 'Promoting...' : 'Confirm Promote'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
