import { Activity, Brain, Database, FlaskConical, ShieldCheck } from 'lucide-react'

import CalibrationPanel from '@/components/mlops/CalibrationPanel'
import DataHealthDashboard from '@/components/mlops/DataHealthDashboard'
import ExperimentWorkbench from '@/components/mlops/ExperimentWorkbench'
import ModelArena from '@/components/mlops/ModelArena'
import ModelCardPanel from '@/components/mlops/ModelCardPanel'
import SegmentMetricsTable from '@/components/mlops/SegmentMetricsTable'
import { useActiveModelEvidence, useExperiments, useMLEffectiveness, useMLHealth, useMLModels, useModelHistory, useSyncHealth } from '@/hooks/useShelfOps'

export default function MLOpsPage() {
    const { data: health, isLoading: healthLoading } = useMLHealth()
    const { data: evidence, isLoading: evidenceLoading } = useActiveModelEvidence()
    const { data: models = [] } = useMLModels('demand_forecast')
    const { data: experiments = [], isLoading: experimentsLoading, isError: experimentsError, error: experimentsErrorDetail } = useExperiments('demand_forecast')
    const { data: modelHistory = [] } = useModelHistory(12)
    const { data: syncData = [], isLoading: syncLoading } = useSyncHealth()
    const { data: effectiveness } = useMLEffectiveness(30, 'demand_forecast')

    const championModel = models.find(model => model.version === evidence?.version)
        ?? models.find(model => model.status === 'champion')
    const championHistory = modelHistory.find(model => model.version === evidence?.version)
        ?? modelHistory.find(model => model.status === 'champion')
    const modelNames = [...new Set(models.map(model => model.model_name))]

    return (
        <div className="page-shell">
            <div className="hero-panel hero-panel-blue">
                <div className="max-w-3xl">
                    <div className="hero-chip text-[#0071e3]">
                        <Brain className="h-3.5 w-3.5" />
                        Model Performance
                    </div>
                    <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">
                        Understand model quality before it shapes inventory decisions.
                    </h1>
                    <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                        Review forecast accuracy, prediction ranges, segment performance, and recent experiments in one place.
                    </p>
                </div>

                <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <HeroStat
                        icon={ShieldCheck}
                        label="Active model"
                        value={evidenceLoading ? 'Loading' : (evidence?.version ?? 'unknown')}
                        detail={evidence?.dataset_id ?? 'artifact unavailable'}
                    />
                    <HeroStat
                        icon={Activity}
                        label="Holdout WAPE"
                        value={formatPercent(evidence?.holdout.wape)}
                        detail={evidence?.benchmark_rows?.[1]?.wape !== undefined
                            ? `vs baseline ${formatPercent(evidence.benchmark_rows[1].wape)}`
                            : 'baseline unavailable'}
                    />
                    <HeroStat
                        icon={Brain}
                        label="Interval coverage"
                        value={formatPercent(evidence?.interval_coverage)}
                        detail={evidence?.interval_method ?? 'artifact unavailable'}
                    />
                    <HeroStat
                        icon={Database}
                        label="Runtime status"
                        value={healthLoading ? 'Loading' : (health?.status ?? 'unknown')}
                        detail={`${health?.champions?.length ?? 0} active-model rows in runtime health`}
                    />
                </div>
            </div>

            <ModelCardPanel evidence={evidence} championModel={championModel} championHistory={championHistory} />
            <CalibrationPanel evidence={evidence} effectiveness={effectiveness} />
            <SegmentMetricsTable effectiveness={effectiveness} />

            <section className="grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
                <div className="space-y-6">
                    <div className="card space-y-4">
                        <div className="flex items-center gap-2">
                            <Brain className="h-4 w-4 text-[#0071e3]" />
                            <h2 className="text-lg font-semibold text-[#1d1d1f]">Runtime Registry</h2>
                        </div>
                        <p className="text-sm text-[#6e6e73]">
                            See which model versions are available and how they are currently staged in the runtime.
                        </p>
                        <ModelArena models={models} />
                    </div>

                    <div className="card space-y-4">
                        <div className="flex items-center gap-2">
                            <FlaskConical className="h-4 w-4 text-[#0071e3]" />
                            <h2 className="text-lg font-semibold text-[#1d1d1f]">Experiment Trail</h2>
                        </div>
                        <ExperimentWorkbench
                            modelNames={modelNames}
                            defaultModelName="demand_forecast"
                            runHistory={experiments}
                            runsLoading={experimentsLoading}
                            runsError={experimentsError}
                            runsErrorMessage={experimentsErrorDetail instanceof Error ? experimentsErrorDetail.message : 'Unable to load experiment evidence.'}
                        />
                    </div>
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

function formatPercent(value: number | null | undefined) {
    if (value === null || value === undefined) {
        return '—'
    }
    return `${(value * 100).toFixed(1)}%`
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
