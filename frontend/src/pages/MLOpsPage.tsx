import { useState } from 'react'
import { Activity, AlertTriangle, Brain, CheckCircle2, Clock, Database, FlaskConical, GitBranch, ScrollText, ShieldCheck } from 'lucide-react'

import CalibrationPanel from '@/components/mlops/CalibrationPanel'
import DataHealthDashboard from '@/components/mlops/DataHealthDashboard'
import ExperimentWorkbench from '@/components/mlops/ExperimentWorkbench'
import ModelArena from '@/components/mlops/ModelArena'
import ModelCardPanel from '@/components/mlops/ModelCardPanel'
import SegmentMetricsTable from '@/components/mlops/SegmentMetricsTable'
import { useActiveModelEvidence, useExperimentLedger, useMLEffectiveness, useMLHealth, useMLModels, useModelHistory, useSyncHealth } from '@/hooks/useShelfOps'
import type { ActiveModelEvidence, ExperimentLedgerEntry, MLModel } from '@/lib/types'

export default function MLOpsPage() {
    const [activeModelName, setActiveModelName] = useState<'demand_forecast' | 'anomaly_detector'>('demand_forecast')
    const { data: health, isLoading: healthLoading } = useMLHealth()
    const { data: evidence, isLoading: evidenceLoading } = useActiveModelEvidence('demand_forecast')
    const { data: anomalyEvidence, isLoading: anomalyEvidenceLoading } = useActiveModelEvidence('anomaly_detector')
    const { data: models = [] } = useMLModels()
    const { data: modelHistory = [] } = useModelHistory(12)
    const { data: syncData = [], isLoading: syncLoading } = useSyncHealth()
    const { data: effectiveness } = useMLEffectiveness(30, 'demand_forecast')
    const { data: experimentLedger = [], isLoading: ledgerLoading } = useExperimentLedger({
        modelName: 'demand_forecast',
        limit: 50,
    })
    const { data: anomalyExperimentLedger = [], isLoading: anomalyLedgerLoading } = useExperimentLedger({
        modelName: 'anomaly_detector',
        limit: 50,
    })

    const forecastModels = models.filter(model => model.model_name === 'demand_forecast')
    const anomalyModels = models.filter(model => model.model_name === 'anomaly_detector')
    const championModel = forecastModels.find(model => model.version === evidence?.version)
        ?? forecastModels.find(model => model.status === 'champion')
    const championHistory = modelHistory.find(model => model.version === evidence?.version)
        ?? modelHistory.find(model => model.status === 'champion')
    const modelNames = [...new Set([...models.map(model => model.model_name), 'demand_forecast', 'anomaly_detector'])]
    const activeEvidence = activeModelName === 'anomaly_detector' ? anomalyEvidence : evidence
    const activeEvidenceLoading = activeModelName === 'anomaly_detector' ? anomalyEvidenceLoading : evidenceLoading
    const activeLedger = activeModelName === 'anomaly_detector' ? anomalyExperimentLedger : experimentLedger
    const activeLedgerLoading = activeModelName === 'anomaly_detector' ? anomalyLedgerLoading : ledgerLoading
    const activeModelLabel = activeModelName === 'anomaly_detector' ? 'Anomaly Detection' : 'Forecasting'
    const activeRegistryModels = models.filter(model => model.model_name === activeModelName)
    const activePrimaryMetric = activeModelName === 'anomaly_detector'
        ? {
            icon: Brain,
            label: 'Precision',
            value: activeEvidenceLoading ? 'Loading' : formatPercent(anomalyEvidence?.benchmark_metrics?.precision),
            detail: anomalyEvidence?.dataset_id ?? 'FreshRetailNet evidence',
        }
        : {
            icon: Activity,
            label: 'Holdout WAPE',
            value: activeEvidenceLoading ? 'Loading' : formatPercent(evidence?.holdout.wape),
            detail: evidence?.benchmark_rows?.[1]?.wape !== undefined
                ? `vs baseline ${formatPercent(evidence.benchmark_rows[1].wape)}`
                : 'baseline pending',
        }
    const activeSecondaryMetric = activeModelName === 'anomaly_detector'
        ? {
            icon: Activity,
            label: 'Recall',
            value: activeEvidenceLoading ? 'Loading' : formatPercent(anomalyEvidence?.benchmark_metrics?.recall),
            detail: 'known stockouts caught',
        }
        : {
            icon: ShieldCheck,
            label: 'Interval coverage',
            value: activeEvidenceLoading ? 'Loading' : formatPercent(evidence?.interval_coverage),
            detail: evidence?.calibration_status ?? 'calibration pending',
        }

    return (
        <div className="page-shell">
            <div className="hero-panel hero-panel-blue">
                <div className="max-w-3xl">
                    <div className="hero-chip text-[#0071e3]">
                        <Brain className="h-3.5 w-3.5" />
                        Model Lab
                    </div>
                    <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">
                        Run auditable model experiments before promotion.
                    </h1>
                    <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                        Track hypotheses, gated backtests, shadow decisions, champion evidence, and runtime freshness in one governed workflow.
                    </p>
                </div>

                <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <HeroStat
                        icon={ShieldCheck}
                        label={`${activeModelLabel} champion`}
                        value={activeEvidenceLoading ? 'Loading' : (activeEvidence?.version ?? 'not selected')}
                        detail={activeEvidence?.dataset_id ?? 'evidence pending'}
                    />
                    <HeroStat {...activePrimaryMetric} />
                    <HeroStat {...activeSecondaryMetric} />
                    <HeroStat
                        icon={Database}
                        label="Runtime status"
                        value={healthLoading ? 'Loading' : (health?.status ?? 'not reporting')}
                        detail={`${health?.champions?.length ?? 0} active models monitored`}
                    />
                </div>
            </div>

            <ModelFamilyFilter
                activeModelName={activeModelName}
                onChange={setActiveModelName}
                forecastVersion={evidence?.version}
                anomalyVersion={anomalyEvidence?.version}
            />

            <ModelLabWorkflow
                experiments={activeLedger}
                isLoading={activeLedgerLoading}
                activeVersion={activeEvidence?.version}
                activeModelLabel={activeModelLabel}
            />

            {activeModelName === 'anomaly_detector' && (
                <AnomalyEvidencePanel
                    evidence={anomalyEvidence}
                    models={anomalyModels}
                    isLoading={anomalyEvidenceLoading}
                />
            )}

            <section className="space-y-4">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <FlaskConical className="h-4 w-4 text-[#0071e3]" />
                            <h2 className="text-lg font-semibold text-[#1d1d1f]">Experiment Pipeline</h2>
                        </div>
                        <p className="mt-2 max-w-3xl text-sm text-[#6e6e73]">
                            Hypotheses, lineage, approvals, run reports, and shadow outcomes stay together before a challenger can affect recommendations.
                        </p>
                    </div>
                    <span className="inline-flex w-fit rounded-full bg-[#0071e3]/10 px-3 py-1 text-xs font-semibold text-[#0071e3]">
                        {activeLedgerLoading ? 'Loading ledger' : `${activeLedger.length} ledger entries`}
                    </span>
                </div>
                <ExperimentWorkbench
                    modelNames={modelNames}
                    defaultModelName={activeModelName}
                    showModelSwitcher={false}
                    key={activeModelName}
                />
            </section>

            {activeModelName === 'demand_forecast' && (
                <>
                    <ModelCardPanel evidence={evidence} championModel={championModel} championHistory={championHistory} />
                    <CalibrationPanel evidence={evidence} effectiveness={effectiveness} />
                    <SegmentMetricsTable effectiveness={effectiveness} />
                </>
            )}

            <section className="grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
                <div className="card space-y-4">
                    <div className="flex items-center gap-2">
                        <Brain className="h-4 w-4 text-[#0071e3]" />
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Runtime Registry</h2>
                    </div>
                    <p className="text-sm text-[#6e6e73]">
                        See the active model family first; expand when older challengers or archived versions are needed.
                    </p>
                    <ModelArena models={activeRegistryModels} initialVisible={3} />
                </div>

                <div className="card space-y-4">
                    <div className="flex items-center gap-2">
                        <Database className="h-4 w-4 text-[#0071e3]" />
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Data Freshness</h2>
                    </div>
                    <p className="text-sm text-[#6e6e73]">
                        Model quality depends on current, complete source data.
                    </p>
                    <DataHealthDashboard syncData={syncData} isLoading={syncLoading} />
                </div>
            </section>
        </div>
    )
}

function ModelFamilyFilter({
    activeModelName,
    onChange,
    forecastVersion,
    anomalyVersion,
}: {
    activeModelName: 'demand_forecast' | 'anomaly_detector'
    onChange: (modelName: 'demand_forecast' | 'anomaly_detector') => void
    forecastVersion: string | undefined
    anomalyVersion: string | undefined
}) {
    const options = [
        {
            modelName: 'demand_forecast' as const,
            label: 'Forecasting',
            detail: 'Demand, uncertainty, replenishment replay',
            version: forecastVersion,
        },
        {
            modelName: 'anomaly_detector' as const,
            label: 'Anomaly Detection',
            detail: 'Shelf availability, stockout review workload',
            version: anomalyVersion,
        },
    ]

    return (
        <section className="card border border-black/[0.02] p-3 shadow-sm">
            <div className="grid gap-2 md:grid-cols-2">
                {options.map(option => {
                    const active = activeModelName === option.modelName
                    return (
                        <button
                            key={option.modelName}
                            type="button"
                            onClick={() => onChange(option.modelName)}
                            className={`rounded-lg border px-4 py-3 text-left transition ${
                                active
                                    ? 'border-[#0071e3]/30 bg-[#f5f9ff] text-[#0071e3]'
                                    : 'border-transparent bg-[#f5f5f7] text-[#6e6e73] hover:border-black/[0.04] hover:bg-white hover:text-[#1d1d1f]'
                            }`}
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                    <p className="font-semibold">{option.label}</p>
                                    <p className="mt-1 truncate text-xs">{option.detail}</p>
                                </div>
                                <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                                    active ? 'bg-[#0071e3]/10 text-[#0071e3]' : 'bg-white text-[#86868b]'
                                }`}>
                                    {option.version ?? 'not selected'}
                                </span>
                            </div>
                        </button>
                    )
                })}
            </div>
        </section>
    )
}

function ModelLabWorkflow({
    experiments,
    isLoading,
    activeVersion,
    activeModelLabel,
}: {
    experiments: ExperimentLedgerEntry[]
    isLoading: boolean
    activeVersion: string | undefined
    activeModelLabel: string
}) {
    const proposed = countStatus(experiments, 'proposed')
    const approved = countStatus(experiments, 'approved')
    const shadowTesting = countStatus(experiments, 'shadow_testing')
    const completed = countStatus(experiments, 'completed')

    return (
        <section className="card space-y-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <GitBranch className="h-4 w-4 text-[#0071e3]" />
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Release Workflow</h2>
                    </div>
                    <p className="mt-2 text-sm text-[#6e6e73]">
                        The active model changes only after a recorded hypothesis, review gate, backtest, and promotion decision.
                    </p>
                </div>
                <span className="inline-flex w-fit rounded-full bg-[#34c759]/10 px-3 py-1 text-xs font-semibold text-[#1f8f45]">
                    {activeModelLabel} {activeVersion ?? 'not selected'}
                </span>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                <WorkflowStep
                    icon={ScrollText}
                    label="Hypotheses"
                    value={isLoading ? 'Loading' : proposed.toLocaleString()}
                    detail="awaiting review"
                    tone="neutral"
                />
                <WorkflowStep
                    icon={CheckCircle2}
                    label="Approved"
                    value={isLoading ? 'Loading' : approved.toLocaleString()}
                    detail="ready to run"
                    tone="good"
                />
                <WorkflowStep
                    icon={FlaskConical}
                    label="Backtests"
                    value={isLoading ? 'Loading' : experiments.length.toLocaleString()}
                    detail="ledger entries"
                    tone="blue"
                />
                <WorkflowStep
                    icon={Clock}
                    label="Shadow"
                    value={isLoading ? 'Loading' : shadowTesting.toLocaleString()}
                    detail="active model"
                    tone="warn"
                />
                <WorkflowStep
                    icon={ShieldCheck}
                    label="Reports"
                    value={isLoading ? 'Loading' : completed.toLocaleString()}
                    detail="release reports"
                    tone="purple"
                />
            </div>
        </section>
    )
}

function AnomalyEvidencePanel({
    evidence,
    models,
    isLoading,
}: {
    evidence: ActiveModelEvidence | undefined
    models: MLModel[]
    isLoading: boolean
}) {
    const champion = models.find(model => model.status === 'champion')
    const challenger = models.find(model => model.status === 'challenger' || model.status === 'candidate')
    const shadowDecision = evidence?.shadow?.decision
    const decisionReason = typeof shadowDecision?.reason === 'string'
        ? shadowDecision.reason
        : 'Awaiting benchmark and buyer feedback.'

    return (
        <section className="card space-y-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-[#ff9500]" />
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Anomaly Detector</h2>
                    </div>
                    <p className="mt-2 max-w-3xl text-sm text-[#6e6e73]">
                        FreshRetailNet stockout labels benchmark inventory-integrity detection separately from the M5 forecasting champion.
                    </p>
                </div>
                <span className="inline-flex w-fit rounded-full bg-[#ff9500]/10 px-3 py-1 text-xs font-semibold text-[#a15c00]">
                    {isLoading ? 'Loading evidence' : `champion ${evidence?.version ?? champion?.version ?? 'not selected'}`}
                </span>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
                <WorkflowStep
                    icon={ShieldCheck}
                    label="Precision"
                    value={formatPercent(evidence?.benchmark_metrics?.precision)}
                    detail="confirmed stockout hit rate"
                    tone="good"
                />
                <WorkflowStep
                    icon={Activity}
                    label="Recall"
                    value={formatPercent(evidence?.benchmark_metrics?.recall)}
                    detail="known stockouts caught"
                    tone="blue"
                />
                <WorkflowStep
                    icon={AlertTriangle}
                    label="False Positive"
                    value={formatPercent(evidence?.benchmark_metrics?.false_positive_rate)}
                    detail="cycle-count noise"
                    tone="warn"
                />
                <WorkflowStep
                    icon={Clock}
                    label="Shadow"
                    value={evidence?.shadow?.challenger_version ?? challenger?.version ?? '—'}
                    detail={formatPercent(evidence?.shadow?.recall)}
                    tone="purple"
                />
                <WorkflowStep
                    icon={Database}
                    label="Rows"
                    value={formatInteger(evidence?.benchmark_metrics?.rows_eval)}
                    detail={evidence?.dataset_id ?? 'FreshRetailNet'}
                    tone="neutral"
                />
                <WorkflowStep
                    icon={CheckCircle2}
                    label="Feedback"
                    value={formatInteger(evidence?.feedback?.outcomes_recorded)}
                    detail={evidence?.feedback?.feedback_provenance ?? 'not measured yet'}
                    tone="neutral"
                />
            </div>

            <div className="grid gap-4 xl:grid-cols-[0.95fr,1.05fr]">
                <div className="rounded-lg border border-black/[0.04] bg-[#f5f5f7] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#86868b]">Shadow Decision</p>
                    <p className="mt-2 text-sm font-medium text-[#1d1d1f]">{decisionReason}</p>
                    <p className="mt-3 text-xs leading-5 text-[#6e6e73]">
                        {evidence?.claim_boundary ?? 'Benchmark anomaly evidence only. Buyer outcomes require real cycle-count feedback.'}
                    </p>
                    <div className="mt-4 grid gap-2 text-xs text-[#6e6e73] sm:grid-cols-3">
                        <div>
                            <span className="block font-mono text-sm text-[#1d1d1f]">
                                {formatInteger(evidence?.feedback?.shadow_predictions)}
                            </span>
                            <span>shadow predictions</span>
                        </div>
                        <div>
                            <span className="block font-mono text-sm text-[#1d1d1f]">
                                {formatPercent(evidence?.feedback?.disagreement_rate)}
                            </span>
                            <span>disagreement rate</span>
                        </div>
                        <div>
                            <span className="block font-mono text-sm text-[#1d1d1f]">
                                {formatPercent(evidence?.feedback?.measured_precision)}
                            </span>
                            <span>measured precision</span>
                        </div>
                    </div>
                </div>

                <div className="overflow-hidden rounded-lg border border-black/[0.04]">
                    <table className="w-full text-left text-xs">
                        <thead className="bg-[#f5f5f7] text-[#86868b]">
                            <tr>
                                <th className="px-3 py-2 font-medium">Profile</th>
                                <th className="px-3 py-2 font-medium">Precision</th>
                                <th className="px-3 py-2 font-medium">Recall</th>
                                <th className="px-3 py-2 font-medium">Review</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-black/[0.04] bg-white">
                            {(evidence?.benchmark_rows ?? []).slice(0, 3).map(row => (
                                <tr key={row.label}>
                                    <td className="px-3 py-2 font-medium text-[#1d1d1f]">{row.label}</td>
                                    <td className="px-3 py-2 font-mono text-[#1d1d1f]">{formatPercent(row.precision)}</td>
                                    <td className="px-3 py-2 font-mono text-[#1d1d1f]">{formatPercent(row.recall)}</td>
                                    <td className="px-3 py-2 font-mono text-[#1d1d1f]">{formatPercent(row.review_rate)}</td>
                                </tr>
                            ))}
                            {(evidence?.benchmark_rows ?? []).length === 0 && (
                                <tr>
                                    <td className="px-3 py-6 text-center text-[#86868b]" colSpan={4}>
                                        No anomaly benchmark rows available.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
    )
}

function WorkflowStep({
    icon: Icon,
    label,
    value,
    detail,
    tone,
}: {
    icon: typeof FlaskConical
    label: string
    value: string
    detail: string
    tone: 'neutral' | 'good' | 'blue' | 'warn' | 'purple'
}) {
    const toneClass = tone === 'good'
        ? 'bg-[#34c759]/10 text-[#1f8f45]'
        : tone === 'blue'
            ? 'bg-[#0071e3]/10 text-[#0071e3]'
            : tone === 'warn'
                ? 'bg-[#ffcc00]/20 text-[#8a6a00]'
                : tone === 'purple'
                    ? 'bg-[#5856d6]/10 text-[#5856d6]'
                    : 'bg-[#f5f5f7] text-[#1d1d1f]'

    return (
        <div className="rounded-[18px] border border-black/[0.04] bg-white px-4 py-4">
            <div className={`flex h-9 w-9 items-center justify-center rounded-2xl ${toneClass}`}>
                <Icon className="h-4 w-4" />
            </div>
            <p className="mt-4 text-xs font-medium uppercase tracking-[0.16em] text-[#86868b]">{label}</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <p className="mt-1 text-xs text-[#6e6e73]">{detail}</p>
        </div>
    )
}

function countStatus(experiments: ExperimentLedgerEntry[], status: string) {
    return experiments.filter(experiment => experiment.status === status).length
}

function formatPercent(value: number | null | undefined) {
    if (value === null || value === undefined) {
        return '—'
    }
    return `${(value * 100).toFixed(1)}%`
}

function formatInteger(value: number | null | undefined) {
    if (value === null || value === undefined) {
        return '—'
    }
    return Math.round(value).toLocaleString()
}

function HeroStat({
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
        <div className="hero-stat-card">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                <Icon className="h-5 w-5 text-[#1d1d1f]" />
            </div>
            <p className="mt-4 text-sm font-medium text-[#86868b]">{label}</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <p className="mt-2 text-xs text-[#6e6e73]">{detail}</p>
        </div>
    )
}
