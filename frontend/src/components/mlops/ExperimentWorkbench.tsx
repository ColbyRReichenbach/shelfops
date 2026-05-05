import { useEffect, useState } from 'react'
import type React from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { Bot, CheckCircle2, ClipboardList, FileText, FlaskConical, Loader2, PlusCircle, Sparkles } from 'lucide-react'

import {
    useApproveExperiment,
    useCreateExperimentContextPackage,
    useCreateExperimentHypothesis,
    useExperimentComparisonReport,
    useExperimentContextPackages,
    useExperimentHypotheses,
    useExperimentLedger,
    useExperiments,
    useExperimentSpecs,
    useExperimentSpecTemplates,
    useInterpretExperiment,
    useProposeExperiment,
    useReviewExperimentHypothesis,
    useRunExperiment,
} from '@/hooks/useShelfOps'
import type {
    ExperimentComparisonReport,
    ExperimentContextPackage,
    ExperimentHypothesis,
    ExperimentLedgerEntry,
    ExperimentResults,
    ExperimentRunExecution,
    ExperimentSource,
    ExperimentType,
    ProposeExperimentPayload,
} from '@/lib/types'
import ExperimentHistory from '@/components/mlops/ExperimentHistory'

const EXPERIMENT_SOURCES: Array<{ value: ExperimentSource; label: string }> = [
    { value: 'manual', label: 'Manual DS' },
    { value: 'ai_assisted', label: 'AI Assisted' },
    { value: 'ai_agent', label: 'AI Agent' },
]

type ValidationMode = 'quick_screen' | 'extended_backtest' | 'promotion_gate'

const MODEL_FAMILY_LABELS: Record<string, { label: string; detail: string }> = {
    demand_forecast: {
        label: 'Forecasting',
        detail: 'Demand, uncertainty, and replenishment replay',
    },
    anomaly_detector: {
        label: 'Anomaly Detection',
        detail: 'Stockout and shelf-availability sentinel',
    },
}

const VALIDATION_MODES: Array<{
    value: ValidationMode
    label: string
    description: string
}> = [
    {
        value: 'quick_screen',
        label: 'Quick Screen',
        description: 'Single recent holdout for fast hypothesis feedback.',
    },
    {
        value: 'extended_backtest',
        label: 'Extended Backtest',
        description: 'Rolling windows for temporal robustness before a stronger claim.',
    },
    {
        value: 'promotion_gate',
        label: 'Promotion Gate',
        description: 'Stricter rolling validation before treating a challenger as promotion-worthy.',
    },
]

type ExperimentFormState = {
    experiment_name: string
    hypothesis: string
    experiment_type: ExperimentType
    experiment_source: ExperimentSource
    context_package_id: string
    experiment_spec_id: string
    spec_template_id: string
    model_name: string
    dataset_id: string
    forecast_grain: string
    architecture: string
    objective: string
    feature_set_id: string
    segment_strategy: string
    trigger_source: string
    baseline_version: string
    success_criteria: string
    domain_rationale: string
    risk_notes: string
    notes: string
    validation_mode: ValidationMode
    holdout_days: number
    calibration_days: number
    rolling_window_count: number
    rolling_window_days: number
    rolling_stride_days: number
    max_rows: number
    max_series: number
}

function defaultSpecTemplateId(modelName: string) {
    return modelName === 'anomaly_detector' ? 'freshretailnet_balanced_context_v1' : 'm5_lag_price_calendar_v1'
}

function defaultDatasetId(modelName: string) {
    return modelName === 'anomaly_detector' ? 'freshretailnet_50k' : 'm5_walmart'
}

function defaultGrain(modelName: string) {
    return modelName === 'anomaly_detector'
        ? 'store_id x product_id x date stockout context'
        : 'store_id x product_id x date'
}

function defaultArchitecture(modelName: string) {
    return modelName === 'anomaly_detector' ? 'deterministic_stockout_risk_score' : 'lightgbm'
}

function defaultObjective(modelName: string) {
    return modelName === 'anomaly_detector' ? 'balanced_stockout_detection' : 'poisson'
}

function defaultFeatureSet(modelName: string) {
    return modelName === 'anomaly_detector' ? 'freshretailnet_balanced_context_v1' : 'm5_replenishment_baseline_v1'
}

function defaultSuccessCriteria(modelName: string) {
    return modelName === 'anomaly_detector'
        ? 'Increase stockout-anomaly recall without breaching false-positive-rate or review-rate gates; promotion requires measured cycle-count feedback.'
        : 'Reduce overstock and stockout opportunity cost without regressing MASE or WAPE.'
}

function validationDefaults(mode: ValidationMode) {
    if (mode === 'promotion_gate') {
        return {
            holdout_days: 56,
            calibration_days: 56,
            rolling_window_count: 6,
            rolling_window_days: 28,
            rolling_stride_days: 28,
            max_rows: 120000,
            max_series: 120,
        }
    }
    if (mode === 'extended_backtest') {
        return {
            holdout_days: 28,
            calibration_days: 28,
            rolling_window_count: 3,
            rolling_window_days: 28,
            rolling_stride_days: 28,
            max_rows: 80000,
            max_series: 80,
        }
    }
    return {
        holdout_days: 28,
        calibration_days: 28,
        rolling_window_count: 0,
        rolling_window_days: 28,
        rolling_stride_days: 28,
        max_rows: 50000,
        max_series: 60,
    }
}

function experimentNamePlaceholder(modelName: string) {
    return modelName === 'anomaly_detector'
        ? 'freshretailnet_stockout_review_rate_v2'
        : 'm5_replenishment_feature_set_v2'
}

function hypothesisPlaceholder(modelName: string) {
    return modelName === 'anomaly_detector'
        ? 'A calibrated stockout-risk threshold should increase recall while keeping false-positive and review-rate gates within operating limits.'
        : 'Promo interactions and recent-demand velocity features should reduce overstock and stockout opportunity cost without regressing MASE or WAPE.'
}

function successCriteriaPlaceholder(modelName: string) {
    return modelName === 'anomaly_detector'
        ? 'Improve recall while keeping false-positive rate and review rate within release gates.'
        : 'Reduce overstock dollars and stockout opportunity cost while keeping MASE/WAPE flat or better.'
}

function initialFormState(defaultModelName: string): ExperimentFormState {
    const validation = validationDefaults('quick_screen')
    return {
        experiment_name: '',
        hypothesis: '',
        experiment_type: defaultModelName === 'anomaly_detector' ? 'post_processing' : 'feature_set',
        experiment_source: 'manual',
        context_package_id: '',
        experiment_spec_id: '',
        spec_template_id: defaultSpecTemplateId(defaultModelName),
        model_name: defaultModelName,
        dataset_id: defaultDatasetId(defaultModelName),
        forecast_grain: defaultGrain(defaultModelName),
        architecture: defaultArchitecture(defaultModelName),
        objective: defaultObjective(defaultModelName),
        feature_set_id: defaultFeatureSet(defaultModelName),
        segment_strategy: 'global',
        trigger_source: 'manual_hypothesis',
        baseline_version: '',
        success_criteria: defaultSuccessCriteria(defaultModelName),
        domain_rationale: '',
        risk_notes: '',
        notes: '',
        validation_mode: 'quick_screen',
        ...validation,
    }
}

export default function ExperimentWorkbench({
    modelNames,
    defaultModelName,
    showModelSwitcher = true,
}: {
    modelNames: string[]
    defaultModelName: string
    showModelSwitcher?: boolean
}) {
    const { user } = useAuth0()
    const defaultAuthor = user?.email ?? ''
    const [form, setForm] = useState<ExperimentFormState>(() => initialFormState(defaultModelName))
    const [submitMessage, setSubmitMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
    const [approvalMessage, setApprovalMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
    const [runMessage, setRunMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
    const [governanceMessage, setGovernanceMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
    const [latestExecution, setLatestExecution] = useState<ExperimentRunExecution | null>(null)

    useEffect(() => {
        setForm(current => {
            const next = { ...current }
            if (!current.model_name && defaultModelName) next.model_name = defaultModelName
            return next
        })
    }, [defaultAuthor, defaultModelName])

    const proposeExperiment = useProposeExperiment()
    const approveExperiment = useApproveExperiment()
    const runExperiment = useRunExperiment()
    const createContextPackage = useCreateExperimentContextPackage()
    const createHypothesis = useCreateExperimentHypothesis()
    const reviewHypothesis = useReviewExperimentHypothesis()
    const {
        data: contextPackages = [],
        isLoading: contextPackagesLoading,
    } = useExperimentContextPackages(form.model_name || defaultModelName)
    const {
        data: specTemplates = [],
        isLoading: specTemplatesLoading,
    } = useExperimentSpecTemplates(form.model_name || defaultModelName)
    const {
        data: experimentSpecs = [],
        isLoading: experimentSpecsLoading,
    } = useExperimentSpecs({
        modelName: form.model_name || undefined,
        contextPackageId: form.context_package_id || undefined,
        limit: 20,
    })
    const {
        data: ledger = [],
        isLoading: ledgerLoading,
        isError: ledgerError,
        error: ledgerErrorDetail,
    } = useExperimentLedger({
        modelName: form.model_name || undefined,
        limit: 12,
    })

    const selectedTemplate = specTemplates.find(template => template.template_id === form.spec_template_id)
    const selectedSpec = experimentSpecs.find(spec => spec.experiment_spec_id === form.experiment_spec_id)
    const selectedValidationMode = VALIDATION_MODES.find(mode => mode.value === form.validation_mode) ?? {
        value: 'quick_screen',
        label: 'Quick Screen',
        description: 'Single recent holdout for fast hypothesis feedback.',
    }
    const validationControlsEnabled = form.model_name !== 'anomaly_detector'
    const {
        data: hypotheses = [],
        isLoading: hypothesesLoading,
    } = useExperimentHypotheses({
        modelName: form.model_name || undefined,
        contextPackageId: form.context_package_id || undefined,
        limit: 10,
    })
    const {
        data: comparisonReport,
        isLoading: comparisonLoading,
    } = useExperimentComparisonReport(form.context_package_id || undefined, form.model_name || defaultModelName)

    const {
        data: completedTrials = [],
        isLoading: completedLoading,
    } = useExperimentLedger({
        modelName: form.model_name || undefined,
        status: 'completed',
        limit: 20,
    })
    const {
        data: runHistory = [],
        isLoading: runsLoading,
        isError: runsError,
        error: runsErrorDetail,
    } = useExperiments(form.model_name || defaultModelName)
    const runsErrorMessage = runsErrorDetail instanceof Error
        ? runsErrorDetail.message
        : 'Unable to load experiment evidence.'
    const activeModelName = form.model_name || defaultModelName
    const modelFamilyOptions = [...new Set((modelNames.length > 0 ? modelNames : ['demand_forecast', 'anomaly_detector']).filter(Boolean))]
        .filter(name => MODEL_FAMILY_LABELS[name])
    const selectedSpecBody = selectedSpec?.spec ?? selectedTemplate?.spec ?? {}
    const selectedModelConfig = selectedSpecBody.model_config as Record<string, unknown> | undefined
    const selectedFeatureConfig = selectedSpecBody.feature_config as Record<string, unknown> | undefined
    const selectedDatasetConfig = selectedSpecBody.dataset_config as Record<string, unknown> | undefined
    const selectedClaimBoundary = String(selectedSpecBody.claim_boundary ?? selectedSpec?.spec_metadata?.claim_boundary ?? selectedTemplate?.claim_boundary ?? '')

    useEffect(() => {
        if (specTemplates.length === 0) return
        if (!specTemplates.some(template => template.template_id === form.spec_template_id)) {
            const nextTemplate = specTemplates[0]
            const nextSpec = nextTemplate?.spec ?? {}
            setForm(current => ({
                ...current,
                spec_template_id: nextTemplate?.template_id ?? '',
                experiment_spec_id: '',
                experiment_type: nextTemplate?.experiment_type ?? current.experiment_type,
                dataset_id: nextTemplate?.dataset_id ?? defaultDatasetId(current.model_name),
                forecast_grain: String(nextSpec.forecast_grain ?? defaultGrain(current.model_name)),
                feature_set_id: nextTemplate?.feature_set_id ?? defaultFeatureSet(current.model_name),
                objective: nextTemplate?.objective ?? defaultObjective(current.model_name),
                architecture: String((nextSpec.model_config as Record<string, unknown> | undefined)?.architecture ?? defaultArchitecture(current.model_name)),
                segment_strategy: String((nextSpec.segmentation_config as Record<string, unknown> | undefined)?.strategy ?? 'global'),
                success_criteria: defaultSuccessCriteria(current.model_name),
            }))
        }
    }, [form.spec_template_id, specTemplates])

    function buildPayload(): ProposeExperimentPayload {
        return {
            experiment_name: form.experiment_name.trim(),
            hypothesis: form.hypothesis.trim(),
            experiment_type: form.experiment_type,
            model_name: form.model_name.trim() || defaultModelName,
            experiment_source: form.experiment_source,
            context_package_id: form.context_package_id || null,
            experiment_spec_id: form.experiment_spec_id || null,
            spec_template_id: form.experiment_spec_id ? null : (form.spec_template_id || null),
            lineage_metadata: {
                dataset_id: form.dataset_id.trim() || null,
                forecast_grain: form.forecast_grain.trim() || null,
                architecture: form.architecture.trim() || null,
                objective: form.objective.trim() || null,
                feature_set_id: form.feature_set_id.trim() || null,
                segment_strategy: form.segment_strategy.trim() || null,
                trigger_source: form.trigger_source.trim() || null,
                baseline_version: form.baseline_version.trim() || null,
                success_criteria: form.success_criteria.trim() || null,
                domain_rationale: form.domain_rationale.trim() || null,
                risk_notes: form.risk_notes.trim() || null,
                notes: form.notes.trim() || null,
                experiment_source: form.experiment_source,
                context_package_id: form.context_package_id || null,
                experiment_spec_id: form.experiment_spec_id || null,
                spec_template_id: form.spec_template_id || null,
            },
        }
    }

    function resetDraft(modelName: string) {
        setLatestExecution(null)
        setRunMessage(null)
        setSubmitMessage(null)
        setApprovalMessage(null)
        setForm(current => ({
            ...initialFormState(modelName),
            model_name: modelName,
            context_package_id: current.context_package_id,
        }))
    }

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setSubmitMessage(null)
        setRunMessage(null)

        const payload = buildPayload()

        if (!payload.experiment_name || !payload.hypothesis) {
            setSubmitMessage({
                tone: 'error',
                text: 'Experiment name and hypothesis are required.',
            })
            return
        }

        try {
            const response = await proposeExperiment.mutateAsync(payload)
            setSubmitMessage({
                tone: 'success',
                text: `Hypothesis submitted for review${defaultAuthor ? ` by ${defaultAuthor}` : ''}. Baseline version: ${response.baseline_version ?? 'none detected yet'}.`,
            })
        } catch (error) {
            const detail = error instanceof Error ? error.message : 'Unable to log experiment.'
            setSubmitMessage({ tone: 'error', text: detail })
        }
    }

    async function handleCreateContextPackage() {
        setGovernanceMessage(null)
        try {
            const created = await createContextPackage.mutateAsync({
                package_name: `${form.model_name || defaultModelName}_manual_vs_ai_context`,
                model_name: form.model_name || defaultModelName,
                dataset_id: form.dataset_id || defaultDatasetId(form.model_name || defaultModelName),
                package_type: 'manual_vs_ai',
            })
            setForm(current => ({ ...current, context_package_id: created.context_package_id }))
            setGovernanceMessage({
                tone: 'success',
                text: `Context package created for ${created.baseline_version ?? 'the current baseline'}.`,
            })
        } catch (error) {
            const detail = error instanceof Error ? error.message : 'Unable to create context package.'
            setGovernanceMessage({ tone: 'error', text: detail })
        }
    }

    async function handleSaveHypothesis() {
        setGovernanceMessage(null)
        if (!form.experiment_name.trim() || !form.hypothesis.trim()) {
            setGovernanceMessage({ tone: 'error', text: 'Experiment name and hypothesis are required.' })
            return
        }

        try {
            await createHypothesis.mutateAsync({
                title: form.experiment_name.trim(),
                hypothesis: form.hypothesis.trim(),
                experiment_type: form.experiment_type,
                model_name: form.model_name.trim() || defaultModelName,
                experiment_source: form.experiment_source,
                context_package_id: form.context_package_id || null,
                experiment_spec_id: form.experiment_spec_id || null,
                spec_template_id: form.experiment_spec_id ? null : (form.spec_template_id || null),
                domain_rationale: form.domain_rationale.trim() || null,
                risk_notes: form.risk_notes.trim() || null,
                expected_metric_movement: {
                    success_criteria: form.success_criteria.trim() || null,
                    forecast_grain: form.forecast_grain.trim() || null,
                    segment_strategy: form.segment_strategy.trim() || null,
                },
                hypothesis_metadata: {
                    dataset_id: form.dataset_id.trim() || null,
                    feature_set_id: form.feature_set_id.trim() || null,
                    trigger_source: form.trigger_source.trim() || null,
                    spec_template_id: form.spec_template_id || null,
                },
            })
            setGovernanceMessage({
                tone: 'success',
                text: `Hypothesis saved to the ${form.experiment_source.replace('_', ' ')} backlog.`,
            })
        } catch (error) {
            const detail = error instanceof Error ? error.message : 'Unable to save hypothesis.'
            setGovernanceMessage({ tone: 'error', text: detail })
        }
    }

    async function handleConvertHypothesis(hypothesis: ExperimentHypothesis) {
        setGovernanceMessage(null)
        try {
            await reviewHypothesis.mutateAsync({
                hypothesisId: hypothesis.hypothesis_id,
                decision: 'approve',
                rationale: 'Approved from experiment governance workbench.',
                convertToExperiment: true,
            })
            setGovernanceMessage({
                tone: 'success',
                text: `${hypothesis.title} was approved and converted into an experiment.`,
            })
        } catch (error) {
            const detail = error instanceof Error ? error.message : 'Unable to convert hypothesis.'
            setGovernanceMessage({ tone: 'error', text: detail })
        }
    }

    async function handleRun(experiment: ExperimentLedgerEntry) {
        setRunMessage(null)
        setSubmitMessage(null)

        try {
            const result = await runExperiment.mutateAsync({
                experimentId: experiment.experiment_id,
                experimentSpecId: experiment.experiment_spec_id,
                validationMode: form.validation_mode,
                holdoutDays: form.holdout_days,
                calibrationDays: form.calibration_days,
                rollingWindowCount: form.rolling_window_count,
                rollingWindowDays: form.rolling_window_days,
                rollingStrideDays: form.rolling_stride_days,
                maxRows: form.max_rows,
                maxSeries: form.max_series,
            })
            setLatestExecution(result)
            setRunMessage({
                tone: 'success',
                text: result.comparison.promoted
                    ? `Experiment ran successfully and set ${result.experimental_version} as the active version.`
                    : `Experiment ran successfully. ${result.experimental_version} stays in review because ${result.comparison.reason}.`,
            })
        } catch (error) {
            const detail = error instanceof Error ? error.message : 'Unable to run experiment.'
            setRunMessage({ tone: 'error', text: detail })
        }
    }

    function handleClear() {
        resetDraft(form.model_name || defaultModelName)
    }

    function handleModelChange(modelName: string) {
        setLatestExecution(null)
        setRunMessage(null)
        setSubmitMessage(null)
        setApprovalMessage(null)
        setGovernanceMessage(null)
        setForm({
            ...initialFormState(modelName),
            model_name: modelName,
        })
    }

    async function handleApprove(experiment: ExperimentLedgerEntry) {
        setApprovalMessage(null)
        try {
            await approveExperiment.mutateAsync({
                experimentId: experiment.experiment_id,
                rationale: 'Approved from ML Ops workbench for implementation.',
            })
            setApprovalMessage({
                tone: 'success',
                text: `Approved ${experiment.experiment_name}${defaultAuthor ? ` as ${defaultAuthor}` : ''}.`,
            })
        } catch (error) {
            const detail = error instanceof Error ? error.message : 'Unable to approve experiment.'
            setApprovalMessage({ tone: 'error', text: detail })
        }
    }

    const actorLabel = defaultAuthor || 'current user'

    return (
        <div className="min-w-0 space-y-5">
            <section className="card border border-black/[0.02] p-4 shadow-sm">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                    <div className="min-w-0">
                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Experiment Workbench</h2>
                        <p className="mt-1 text-sm text-[#6e6e73]">
                            Draft a hypothesis, bind it to an executable spec, approve it, then run the bounded validation.
                        </p>
                    </div>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                        {showModelSwitcher && (
                            <div className="inline-grid rounded-lg bg-[#f5f5f7] p-1 sm:grid-flow-col">
                                {modelFamilyOptions.map(modelName => {
                                    const modelLabel = MODEL_FAMILY_LABELS[modelName] ?? { label: modelName, detail: '' }
                                    const active = activeModelName === modelName
                                    return (
                                        <button
                                            key={modelName}
                                            type="button"
                                            onClick={() => handleModelChange(modelName)}
                                            className={`rounded-md px-3 py-2 text-left text-sm transition ${
                                                active
                                                    ? 'bg-white text-[#0071e3] shadow-sm'
                                                    : 'text-[#6e6e73] hover:text-[#1d1d1f]'
                                            }`}
                                        >
                                            <span className="block font-semibold">{modelLabel.label}</span>
                                            <span className="block max-w-[220px] truncate text-[11px] font-normal">{modelLabel.detail}</span>
                                        </button>
                                    )
                                })}
                            </div>
                        )}
                        <Field label="Source">
                            <select
                                value={form.experiment_source}
                                onChange={event => setForm(current => ({ ...current, experiment_source: event.target.value as ExperimentSource }))}
                                className="input min-w-[150px]"
                            >
                                {EXPERIMENT_SOURCES.map(option => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                            </select>
                        </Field>
                    </div>
                </div>
            </section>

            {latestExecution && (
                <ExperimentExecutionSummary execution={latestExecution} />
            )}

            <div className="grid min-w-0 grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.48fr)]">
                <section className="card min-w-0 border border-black/[0.02] p-5 shadow-sm">
                    <form className="space-y-5" onSubmit={handleSubmit}>
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                                <div className="flex items-center gap-2">
                                    <PlusCircle className="h-4 w-4 text-[#0071e3]" />
                                    <h3 className="text-base font-semibold text-[#1d1d1f]">Hypothesis Intake</h3>
                                </div>
                                <p className="mt-1 text-xs text-[#6e6e73]">
                                    Submitted as {actorLabel}; spec-controlled settings are summarized below.
                                </p>
                            </div>
                            <span className="rounded-full bg-[#0071e3]/10 px-3 py-1 text-xs font-semibold text-[#0071e3]">
                                {MODEL_FAMILY_LABELS[activeModelName]?.label ?? activeModelName}
                            </span>
                        </div>

                        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[0.8fr,0.45fr]">
                            <Field label="Experiment Name">
                                <input
                                    value={form.experiment_name}
                                    onChange={event => setForm(current => ({ ...current, experiment_name: event.target.value }))}
                                    className="input"
                                    placeholder={experimentNamePlaceholder(activeModelName)}
                                />
                            </Field>
                            <Meta label="Experiment Type" value={humanizeGateName(form.experiment_type)} />
                        </div>

                        <Field label="Hypothesis">
                            <textarea
                                value={form.hypothesis}
                                onChange={event => setForm(current => ({ ...current, hypothesis: event.target.value }))}
                                className="input min-h-24 resize-y"
                                placeholder={hypothesisPlaceholder(activeModelName)}
                            />
                        </Field>

                        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                            <Field label="Success Criteria">
                                <textarea
                                    value={form.success_criteria}
                                    onChange={event => setForm(current => ({ ...current, success_criteria: event.target.value }))}
                                    className="input min-h-20 resize-y"
                                    placeholder={successCriteriaPlaceholder(activeModelName)}
                                />
                            </Field>
                            <Field label="Domain Rationale">
                                <textarea
                                    value={form.domain_rationale}
                                    onChange={event => setForm(current => ({ ...current, domain_rationale: event.target.value }))}
                                    className="input min-h-20 resize-y"
                                    placeholder="Retail reason this should work: demand pattern, shelf availability, promotion proxy, perishability, region, or buying policy."
                                />
                            </Field>
                        </div>

                        <Field label="Risk Notes">
                            <textarea
                                value={form.risk_notes}
                                onChange={event => setForm(current => ({ ...current, risk_notes: event.target.value }))}
                                className="input min-h-16 resize-y"
                                placeholder="Expected tradeoffs, such as overstock exposure, lost-sales risk, false positives, review workload, or interval coverage risk."
                            />
                        </Field>

                        <section className="rounded-lg border border-[#0071e3]/10 bg-[#f5f9ff] p-4">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                    <p className="text-sm font-semibold text-[#1d1d1f]">Executable Spec</p>
                                    <p className="mt-1 text-xs text-[#5f6673]">
                                        The selected spec controls the dataset, objective, architecture, and feature flags for this run.
                                    </p>
                                </div>
                                <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-[#0071e3]">
                                    Set by spec
                                </span>
                            </div>

                            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
                                <Field label="Spec Template">
                                    <select
                                        value={form.spec_template_id}
                                        onChange={event => {
                                            const nextTemplate = specTemplates.find(template => template.template_id === event.target.value)
                                            const nextSpec = nextTemplate?.spec ?? {}
                                            setForm(current => ({
                                                ...current,
                                                spec_template_id: event.target.value,
                                                experiment_spec_id: '',
                                                experiment_type: nextTemplate?.experiment_type ?? current.experiment_type,
                                                dataset_id: nextTemplate?.dataset_id ?? current.dataset_id,
                                                forecast_grain: String(nextSpec.forecast_grain ?? current.forecast_grain),
                                                feature_set_id: nextTemplate?.feature_set_id ?? current.feature_set_id,
                                                objective: nextTemplate?.objective ?? current.objective,
                                                architecture: String((nextSpec.model_config as Record<string, unknown> | undefined)?.architecture ?? defaultArchitecture(current.model_name)),
                                                segment_strategy: String((nextSpec.segmentation_config as Record<string, unknown> | undefined)?.strategy ?? current.segment_strategy),
                                                success_criteria: current.success_criteria || defaultSuccessCriteria(current.model_name),
                                            }))
                                        }}
                                        className="input"
                                        disabled={specTemplatesLoading}
                                    >
                                        {specTemplates.map(template => (
                                            <option key={template.template_id} value={template.template_id}>
                                                {template.spec_name}
                                            </option>
                                        ))}
                                    </select>
                                </Field>
                                <Field label="Saved Spec">
                                    <select
                                        value={form.experiment_spec_id}
                                        onChange={event => {
                                            const nextSpec = experimentSpecs.find(spec => spec.experiment_spec_id === event.target.value)
                                            const specBody = nextSpec?.spec ?? {}
                                            setForm(current => ({
                                                ...current,
                                                experiment_spec_id: event.target.value,
                                                spec_template_id: nextSpec?.template_id ?? current.spec_template_id,
                                                dataset_id: nextSpec?.dataset_id ?? current.dataset_id,
                                                forecast_grain: String(specBody.forecast_grain ?? current.forecast_grain),
                                                feature_set_id: String(specBody.feature_set_id ?? current.feature_set_id),
                                                objective: String((specBody.model_config as Record<string, unknown> | undefined)?.objective ?? current.objective),
                                                architecture: String((specBody.model_config as Record<string, unknown> | undefined)?.architecture ?? current.architecture),
                                                segment_strategy: String((specBody.segmentation_config as Record<string, unknown> | undefined)?.strategy ?? current.segment_strategy),
                                            }))
                                        }}
                                        className="input"
                                        disabled={experimentSpecsLoading}
                                    >
                                        <option value="">Use selected template</option>
                                        {experimentSpecs.map(spec => (
                                            <option key={spec.experiment_spec_id} value={spec.experiment_spec_id}>
                                                {spec.spec_name} · {spec.spec_hash.slice(0, 8)}
                                            </option>
                                        ))}
                                    </select>
                                </Field>
                            </div>

                            <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                                <Meta label="Dataset" value={selectedSpec?.dataset_id ?? selectedTemplate?.dataset_id ?? form.dataset_id} />
                                <Meta label="Objective" value={String(selectedModelConfig?.objective ?? selectedTemplate?.objective ?? form.objective)} />
                                <Meta label="Feature Set" value={String(selectedSpecBody.feature_set_id ?? selectedTemplate?.feature_set_id ?? form.feature_set_id)} />
                                <Meta label="Spec Hash" value={(selectedSpec?.spec_hash ?? selectedTemplate?.spec_hash ?? 'template only').slice(0, 12)} />
                            </div>

                            <details className="mt-3 rounded-lg border border-[#0071e3]/10 bg-white/70 px-3 py-2">
                                <summary className="cursor-pointer text-xs font-semibold text-[#0071e3]">Spec details and claim boundary</summary>
                                <div className="mt-3 grid grid-cols-1 gap-3 text-xs text-[#6e6e73] lg:grid-cols-3">
                                    <Meta label="Grain" value={String(selectedSpecBody.forecast_grain ?? form.forecast_grain)} />
                                    <Meta label="Architecture" value={String(selectedModelConfig?.architecture ?? form.architecture)} />
                                    <Meta label="Segmentation" value={String((selectedSpecBody.segmentation_config as Record<string, unknown> | undefined)?.strategy ?? form.segment_strategy)} />
                                    <Meta label="Features" value={compactFeatureFlags(selectedFeatureConfig)} />
                                    <Meta label="Dataset Policy" value={String(selectedDatasetConfig?.activation_policy ?? 'canonical')} />
                                    <Meta label="Provenance" value={String(selectedSpecBody.provenance ?? selectedTemplate?.provenance ?? 'benchmark')} />
                                    <p className="lg:col-span-3 rounded-md bg-[#f5f5f7] px-3 py-2">
                                        {selectedClaimBoundary || 'No claim boundary available for this spec.'}
                                    </p>
                                </div>
                            </details>
                        </section>

                        <details className="rounded-lg border border-black/5 bg-white px-4 py-3">
                            <summary className="cursor-pointer text-sm font-semibold text-[#1d1d1f]">
                                Run controls · {selectedValidationMode.label}
                            </summary>
                            <div className="mt-4 space-y-4">
                                <p className="text-xs text-[#6e6e73]">
                                    {validationControlsEnabled
                                        ? selectedValidationMode.description
                                        : 'Anomaly experiments use the FreshRetailNet benchmark split; only row cap is sent to the run.'}
                                </p>
                                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                                    <Field label="Mode">
                                        <select
                                            value={form.validation_mode}
                                            disabled={!validationControlsEnabled}
                                            onChange={event => {
                                                const validation_mode = event.target.value as ValidationMode
                                                setForm(current => ({
                                                    ...current,
                                                    validation_mode,
                                                    ...validationDefaults(validation_mode),
                                                }))
                                            }}
                                            className="input"
                                        >
                                            {VALIDATION_MODES.map(option => (
                                                <option key={option.value} value={option.value}>{option.label}</option>
                                            ))}
                                        </select>
                                    </Field>
                                    <Field label="Calibration Days">
                                        <input
                                            type="number"
                                            min={7}
                                            max={180}
                                            value={form.calibration_days}
                                            disabled={!validationControlsEnabled}
                                            onChange={event => setForm(current => ({ ...current, calibration_days: Number(event.target.value) }))}
                                            className="input"
                                        />
                                    </Field>
                                    <Field label="Holdout Days">
                                        <input
                                            type="number"
                                            min={7}
                                            max={365}
                                            value={form.holdout_days}
                                            disabled={!validationControlsEnabled}
                                            onChange={event => setForm(current => ({ ...current, holdout_days: Number(event.target.value) }))}
                                            className="input"
                                        />
                                    </Field>
                                </div>

                                {form.validation_mode !== 'quick_screen' && validationControlsEnabled && (
                                    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                                        <Field label="Rolling Windows">
                                            <input
                                                type="number"
                                                min={1}
                                                max={12}
                                                value={form.rolling_window_count}
                                                onChange={event => setForm(current => ({ ...current, rolling_window_count: Number(event.target.value) }))}
                                                className="input"
                                            />
                                        </Field>
                                        <Field label="Window Days">
                                            <input
                                                type="number"
                                                min={7}
                                                max={90}
                                                value={form.rolling_window_days}
                                                onChange={event => setForm(current => ({ ...current, rolling_window_days: Number(event.target.value) }))}
                                                className="input"
                                            />
                                        </Field>
                                        <Field label="Stride Days">
                                            <input
                                                type="number"
                                                min={7}
                                                max={90}
                                                value={form.rolling_stride_days}
                                                onChange={event => setForm(current => ({ ...current, rolling_stride_days: Number(event.target.value) }))}
                                                className="input"
                                            />
                                        </Field>
                                    </div>
                                )}

                                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                    <Field label="Max Rows">
                                        <input
                                            type="number"
                                            min={10000}
                                            max={250000}
                                            step={10000}
                                            value={form.max_rows}
                                            onChange={event => setForm(current => ({ ...current, max_rows: Number(event.target.value) }))}
                                            className="input"
                                        />
                                    </Field>
                                    <Field label="Max Series">
                                        <input
                                            type="number"
                                            min={2}
                                            max={250}
                                            value={form.max_series}
                                            disabled={!validationControlsEnabled}
                                            onChange={event => setForm(current => ({ ...current, max_series: Number(event.target.value) }))}
                                            className="input"
                                        />
                                    </Field>
                                </div>
                            </div>
                        </details>

                        <details className="rounded-lg border border-black/5 bg-white px-4 py-3">
                            <summary className="cursor-pointer text-sm font-semibold text-[#1d1d1f]">Collaboration context</summary>
                            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
                                <Field label="Context Package">
                                    <select
                                        value={form.context_package_id}
                                        onChange={event => setForm(current => ({ ...current, context_package_id: event.target.value }))}
                                        className="input"
                                        disabled={contextPackagesLoading}
                                    >
                                        <option value="">No package selected</option>
                                        {contextPackages.map(pkg => (
                                            <option key={pkg.context_package_id} value={pkg.context_package_id}>
                                                {pkg.package_name}
                                            </option>
                                        ))}
                                    </select>
                                </Field>
                                <Field label="Notes">
                                    <input
                                        value={form.notes}
                                        onChange={event => setForm(current => ({ ...current, notes: event.target.value }))}
                                        className="input"
                                        placeholder="Optional operating note or rollback concern"
                                    />
                                </Field>
                                <div className="lg:col-span-2">
                                    <button
                                        type="button"
                                        onClick={() => void handleCreateContextPackage()}
                                        disabled={createContextPackage.isPending}
                                        className="inline-flex items-center gap-2 rounded-lg border border-black/5 bg-white px-4 py-2 text-sm font-medium text-[#1d1d1f] shadow-sm transition hover:border-[#0071e3]/30 hover:text-[#0071e3] disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        {createContextPackage.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                                        Create context package
                                    </button>
                                </div>
                            </div>
                        </details>

                        {submitMessage && <StatusMessage tone={submitMessage.tone} text={submitMessage.text} />}
                        {runMessage && <StatusMessage tone={runMessage.tone} text={runMessage.text} />}
                        {governanceMessage && <StatusMessage tone={governanceMessage.tone} text={governanceMessage.text} />}

                        <div className="flex flex-col gap-3 border-t border-black/5 pt-4 lg:flex-row lg:items-center lg:justify-between">
                            <p className="text-xs text-[#86868b]">
                                Approve a proposal before launching a validation run. Run controls are applied at launch.
                            </p>
                            <div className="flex flex-wrap items-center justify-end gap-2">
                                <button
                                    type="button"
                                    onClick={() => void handleSaveHypothesis()}
                                    disabled={createHypothesis.isPending}
                                    className="inline-flex items-center gap-2 rounded-lg border border-[#5856d6]/20 bg-white px-4 py-2 text-sm font-medium text-[#5856d6] shadow-sm transition hover:border-[#5856d6]/35 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {createHypothesis.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
                                    Save backlog
                                </button>
                                <button
                                    type="button"
                                    onClick={handleClear}
                                    className="inline-flex items-center gap-2 rounded-lg border border-black/5 bg-white px-4 py-2 text-sm font-medium text-[#86868b] shadow-sm transition hover:border-[#0071e3]/30 hover:text-[#0071e3]"
                                >
                                    Clear
                                </button>
                                <button
                                    type="submit"
                                    disabled={proposeExperiment.isPending || runExperiment.isPending}
                                    className="inline-flex items-center gap-2 rounded-lg bg-[#0071e3] px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-[#0068d1] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {proposeExperiment.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlusCircle className="h-4 w-4" />}
                                    Submit for review
                                </button>
                            </div>
                        </div>
                    </form>
                </section>

                <section className="card min-w-0 border border-black/[0.02] p-5 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                            <div className="flex items-center gap-2">
                                <ClipboardList className="h-4 w-4 text-[#0071e3]" />
                                <h3 className="text-base font-semibold text-[#1d1d1f]">Review Queue</h3>
                            </div>
                            <p className="mt-1 text-sm text-[#86868b]">
                                Approve a proposal, then run it with the active validation controls.
                            </p>
                        </div>
                        <span className="rounded-full bg-[#ff9500]/10 px-3 py-1 text-xs font-medium text-[#ff9500]">
                            {MODEL_FAMILY_LABELS[activeModelName]?.label ?? activeModelName}
                        </span>
                    </div>

                    {approvalMessage && <StatusMessage tone={approvalMessage.tone} text={approvalMessage.text} />}

                    <div className="mt-4 max-h-[760px] overflow-y-auto pr-1">
                        <ExperimentLedgerList
                            experiments={ledger}
                            isLoading={ledgerLoading}
                            isError={ledgerError}
                            errorMessage={ledgerErrorDetail instanceof Error ? ledgerErrorDetail.message : 'Unable to load experiment ledger.'}
                            onApprove={handleApprove}
                            onRun={handleRun}
                            approvingId={approveExperiment.variables?.experimentId ?? null}
                            approvePending={approveExperiment.isPending}
                            runningId={runExperiment.variables?.experimentId ?? null}
                            runPending={runExperiment.isPending}
                        />
                    </div>
                </section>
            </div>

            <details className="border-t border-black/5 pt-4">
                <summary className="cursor-pointer text-sm font-semibold text-[#1d1d1f]">Governance backlog and manual-vs-AI lanes</summary>
                <div className="mt-4">
                    <ExperimentGovernancePanel
                        contextPackages={contextPackages}
                        contextPackagesLoading={contextPackagesLoading}
                        hypotheses={hypotheses}
                        hypothesesLoading={hypothesesLoading}
                        comparisonReport={comparisonReport}
                        comparisonLoading={comparisonLoading}
                        selectedContextPackageId={form.context_package_id}
                        onSelectContextPackage={contextPackageId => setForm(current => ({ ...current, context_package_id: contextPackageId }))}
                        onConvertHypothesis={handleConvertHypothesis}
                        convertingHypothesisId={reviewHypothesis.variables?.hypothesisId ?? null}
                        convertPending={reviewHypothesis.isPending}
                    />
                </div>
            </details>

            <details className="border-t border-black/5 pt-4">
                <summary className="cursor-pointer text-sm font-semibold text-[#1d1d1f]">Training run history</summary>
                <div className="mt-4">
                    <ExperimentHistory
                        experiments={runHistory}
                        isLoading={runsLoading}
                        isError={runsError}
                        errorMessage={runsErrorMessage}
                    />
                </div>
            </details>

            <details className="border-t border-black/5 pt-4">
                <summary className="cursor-pointer text-sm font-semibold text-[#1d1d1f]">
                    Release reports ({completedTrials.length})
                </summary>
                <div className="mt-4">
                    <CompletedTrialsLog experiments={completedTrials} isLoading={completedLoading} />
                </div>
            </details>
        </div>
    )
}

function ExperimentGovernancePanel({
    contextPackages,
    contextPackagesLoading,
    hypotheses,
    hypothesesLoading,
    comparisonReport,
    comparisonLoading,
    selectedContextPackageId,
    onSelectContextPackage,
    onConvertHypothesis,
    convertingHypothesisId,
    convertPending,
}: {
    contextPackages: ExperimentContextPackage[]
    contextPackagesLoading: boolean
    hypotheses: ExperimentHypothesis[]
    hypothesesLoading: boolean
    comparisonReport?: ExperimentComparisonReport
    comparisonLoading: boolean
    selectedContextPackageId: string
    onSelectContextPackage: (contextPackageId: string) => void
    onConvertHypothesis: (hypothesis: ExperimentHypothesis) => Promise<void>
    convertingHypothesisId: string | null
    convertPending: boolean
}) {
    const selectedPackage = contextPackages.find(pkg => pkg.context_package_id === selectedContextPackageId)

    return (
        <section className="space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-lg font-semibold text-[#0071e3]">Experiment Governance</h2>
                    <p className="text-sm text-[#86868b] mt-1">
                        Context packages, hypothesis backlog, and manual-vs-agent comparison for auditable DS iteration.
                    </p>
                </div>
                <div className="inline-flex items-center gap-2 rounded-full bg-[#5856d6]/10 px-3 py-1 text-xs font-medium text-[#5856d6]">
                    <Bot className="h-3.5 w-3.5" />
                    Human Reviewed
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-[0.8fr,1.2fr] gap-4">
                <article className="rounded-xl border border-black/5 bg-white/80 p-4 space-y-4">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <p className="font-semibold text-[#1d1d1f]">Context Package</p>
                            <p className="text-xs text-[#86868b] mt-1">Shared inputs for manual and AI experiment runs.</p>
                        </div>
                        <FileText className="h-4 w-4 text-[#0071e3]" />
                    </div>

                    {contextPackagesLoading ? (
                        <div className="rounded-lg bg-[#f5f5f7] p-4 text-sm text-[#86868b]">Loading packages...</div>
                    ) : (
                        <select
                            value={selectedContextPackageId}
                            onChange={event => onSelectContextPackage(event.target.value)}
                            className="input"
                        >
                            <option value="">Compare all current model work</option>
                            {contextPackages.map(pkg => (
                                <option key={pkg.context_package_id} value={pkg.context_package_id}>
                                    {pkg.package_name}
                                </option>
                            ))}
                        </select>
                    )}

                    <div className="grid grid-cols-2 gap-3 text-xs text-[#86868b]">
                        <Meta label="Baseline" value={selectedPackage?.baseline_version ?? 'current model'} />
                        <Meta label="Dataset" value={selectedPackage?.dataset_id ?? 'selected model'} />
                        <Meta label="Snapshot" value={selectedPackage?.dataset_snapshot_id ?? '—'} />
                        <Meta label="Evidence" value={selectedPackage?.artifact_uri ? 'attached' : 'not recorded'} />
                    </div>
                </article>

                <article className="rounded-xl border border-black/5 bg-white/80 p-4 space-y-4">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <p className="font-semibold text-[#1d1d1f]">Manual vs AI Lanes</p>
                            <p className="text-xs text-[#86868b] mt-1">
                                Counts stay separate so agent output remains auditable before any run.
                            </p>
                        </div>
                        <SourcePill source="ai_agent" />
                    </div>

                    {comparisonLoading ? (
                        <div className="rounded-lg bg-[#f5f5f7] p-4 text-sm text-[#86868b]">Loading comparison...</div>
                    ) : comparisonReport ? (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            {comparisonReport.lanes.map(lane => (
                                <div key={lane.source} className="rounded-lg border border-black/5 bg-[#f5f5f7] p-3">
                                    <SourcePill source={lane.source} />
                                    <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-[#86868b]">
                                        <Meta label="Ideas" value={String(lane.hypotheses)} />
                                        <Meta label="Runs" value={String(lane.experiments)} />
                                        <Meta label="Traces" value={String(lane.agent_traces)} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="rounded-lg bg-[#f5f5f7] p-4 text-sm text-[#86868b]">No comparison report available.</div>
                    )}
                </article>
            </div>

            <article className="rounded-xl border border-black/5 bg-white/80 p-4 space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <p className="font-semibold text-[#1d1d1f]">Hypothesis Backlog</p>
                        <p className="text-xs text-[#86868b] mt-1">
                            Approve and convert backlog items into the experiment ledger before running.
                        </p>
                    </div>
                    <ClipboardList className="h-4 w-4 text-[#ff9500]" />
                </div>

                {hypothesesLoading ? (
                    <div className="rounded-lg bg-[#f5f5f7] p-4 text-sm text-[#86868b]">Loading hypotheses...</div>
                ) : hypotheses.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-black/5 bg-[#f5f5f7] p-4 text-sm text-[#86868b]">
                        No hypotheses are waiting in this lane.
                    </div>
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                        {hypotheses.map(hypothesis => {
                            const canConvert = hypothesis.status === 'proposed' || hypothesis.status === 'approved'
                            const isConverting = convertPending && convertingHypothesisId === hypothesis.hypothesis_id
                            return (
                                <div key={hypothesis.hypothesis_id} className="rounded-lg border border-black/5 bg-[#f5f5f7] p-3 space-y-3">
                                    <div className="flex flex-wrap items-start justify-between gap-2">
                                        <div>
                                            <div className="flex flex-wrap items-center gap-2">
                                                <p className="font-medium text-[#1d1d1f]">{hypothesis.title}</p>
                                                <SourcePill source={hypothesis.experiment_source} />
                                                <StatusPill status={hypothesis.status} />
                                            </div>
                                            <p className="mt-1 text-sm text-[#86868b]">{hypothesis.hypothesis}</p>
                                        </div>
                                        {canConvert && (
                                            <button
                                                type="button"
                                                onClick={() => void onConvertHypothesis(hypothesis)}
                                                disabled={isConverting}
                                                className="inline-flex items-center gap-1.5 rounded-[8px] bg-[#0071e3] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
                                            >
                                                {isConverting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                                                Convert
                                            </button>
                                        )}
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 text-xs text-[#86868b]">
                                        <Meta label="Type" value={hypothesis.experiment_type} />
                                        <Meta label="Author" value={hypothesis.generated_by} />
                                        <Meta label="Spec" value={hypothesis.experiment_spec_id ? hypothesis.experiment_spec_id.slice(0, 8) : stringValue(hypothesis.hypothesis_metadata?.spec_template_id)} />
                                        <Meta label="Spec Hash" value={stringValue(hypothesis.hypothesis_metadata?.experiment_spec_hash).slice(0, 12)} />
                                    </div>
                                    {hypothesis.domain_rationale && (
                                        <p className="rounded-md bg-white/70 px-3 py-2 text-xs text-[#86868b]">
                                            {hypothesis.domain_rationale}
                                        </p>
                                    )}
                                </div>
                            )
                        })}
                    </div>
                )}
            </article>
        </section>
    )
}

function ExperimentLedgerList({
    experiments,
    isLoading,
    isError,
    errorMessage,
    onApprove,
    onRun,
    approvingId,
    approvePending,
    runningId,
    runPending,
}: {
    experiments: ExperimentLedgerEntry[]
    isLoading: boolean
    isError: boolean
    errorMessage: string
    onApprove: (experiment: ExperimentLedgerEntry) => Promise<void>
    onRun: (experiment: ExperimentLedgerEntry) => Promise<void>
    approvingId: string | null
    approvePending: boolean
    runningId: string | null
    runPending: boolean
}) {
    if (isLoading) {
        return (
            <div className="rounded-xl border border-black/5 bg-[#f5f5f7] p-6 text-center">
                <Loader2 className="mx-auto h-5 w-5 animate-spin text-[#0071e3]" />
                <p className="mt-2 text-sm text-[#86868b]">Loading experiment ledger...</p>
            </div>
        )
    }

    if (isError) {
        return (
            <div className="rounded-xl border border-[#ff3b30]/20 bg-[#ff3b30]/5 px-4 py-5 text-sm text-[#ff3b30]">
                {errorMessage}
            </div>
        )
    }

    if (experiments.length === 0) {
        return (
            <div className="rounded-xl border border-dashed border-black/5 bg-[#f5f5f7] p-6 text-center">
                <FlaskConical className="mx-auto h-6 w-6 text-[#86868b]" />
                <p className="mt-2 text-sm text-[#86868b]">No hypotheses logged for this model yet.</p>
            </div>
        )
    }

    return (
        <div className="space-y-3">
            {experiments.map(experiment => {
                const meta = experiment.lineage_metadata ?? {}
                const canApprove = experiment.status === 'proposed'
                const canRun = experiment.status === 'approved'
                const isApproving = approvePending && approvingId === experiment.experiment_id
                const isRunning = runPending && runningId === experiment.experiment_id

                return (
                    <article key={experiment.experiment_id} className="rounded-xl border border-black/5 bg-white/80 p-4 space-y-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <p className="font-semibold text-[#1d1d1f]">{experiment.experiment_name}</p>
                                    <StatusPill status={experiment.status} />
                                    <SourcePill source={experiment.experiment_source} />
                                </div>
                                <p className="mt-1 text-sm text-[#86868b]">{experiment.hypothesis}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                {canApprove && (
                                    <button
                                        type="button"
                                        onClick={() => void onApprove(experiment)}
                                        disabled={isApproving}
                                        className="inline-flex items-center gap-2 rounded-lg border border-[#34c759]/20 bg-[#34c759]/10 px-3 py-1.5 text-xs font-medium text-[#34c759] transition hover:bg-[#34c759]/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        {isApproving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                                        Approve
                                    </button>
                                )}
                                {canRun && (
                                    <button
                                        type="button"
                                        onClick={() => void onRun(experiment)}
                                        disabled={isRunning}
                                        className="inline-flex items-center gap-2 rounded-lg bg-[#0071e3] px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        {isRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FlaskConical className="h-3.5 w-3.5" />}
                                        Run
                                    </button>
                                )}
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3 text-xs text-[#86868b] md:grid-cols-3">
                            <Meta label="Type" value={experiment.experiment_type} />
                            <Meta label="Model" value={experiment.model_name} />
                            <Meta label="Baseline" value={experiment.baseline_version ?? '—'} />
                            <Meta label="Source" value={sourceLabel(experiment.experiment_source)} />
                            <Meta label="Dataset" value={stringValue(meta.dataset_id)} />
                            <Meta label="Feature Set" value={stringValue(meta.feature_set_id)} />
                            <Meta label="Spec" value={experiment.experiment_spec_id ? experiment.experiment_spec_id.slice(0, 8) : stringValue(meta.spec_template_id)} />
                            <Meta label="Spec Hash" value={stringValue(meta.experiment_spec_hash).slice(0, 12)} />
                            <Meta label="Segment Strategy" value={stringValue(meta.segment_strategy)} />
                        </div>

                        <div className="rounded-lg bg-[#f5f5f7] px-3 py-2 text-xs text-[#86868b]">
                            <span className="font-medium text-[#86868b]">Success criteria:</span>{' '}
                            {stringValue(meta.success_criteria) || 'No criteria recorded'}
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[#86868b]">
                            <span>Proposed by {experiment.proposed_by}</span>
                            <span>
                                {experiment.approved_at
                                    ? `Approved ${new Date(experiment.approved_at).toLocaleString()}`
                                    : new Date(experiment.created_at).toLocaleString()}
                            </span>
                        </div>
                    </article>
                )
            })}
        </div>
    )
}

function Field({
    label,
    children,
}: {
    label: string
    children: React.ReactNode
}) {
    return (
        <label className="space-y-1.5 block">
            <span className="text-xs font-medium uppercase tracking-wider text-[#86868b]">{label}</span>
            {children}
        </label>
    )
}

function ExperimentExecutionSummary({ execution }: { execution: ExperimentRunExecution }) {
    const baselineMetrics = execution.report.baseline.holdout_metrics
    const challengerMetrics = execution.report.challenger.holdout_metrics
    const gateChecks = Object.entries(execution.comparison.gate_checks ?? {})
    const isAnomaly = execution.report.experiment.model_name === 'anomaly_detector'
    const validation = execution.report.validation
    const rollingValidation = execution.report.rolling_validation
    const metricCards = isAnomaly
        ? [
            ['Precision', 'precision', 'percent'] as const,
            ['Recall', 'recall', 'percent'] as const,
            ['False Positive Rate', 'false_positive_rate', 'percent'] as const,
            ['Review Rate', 'review_rate', 'percent'] as const,
        ]
        : [
            ['WAPE', 'wape', 'percent'] as const,
            ['MASE', 'mase', 'number'] as const,
            ['Opportunity Cost Stockout', 'opportunity_cost_stockout', 'currency'] as const,
        ]

    return (
        <section className="card border border-black/[0.02] shadow-sm p-5 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h2 className="text-lg font-semibold text-[#0071e3]">Latest Arena Decision</h2>
                    <p className="text-sm text-[#86868b] mt-1">
                        {execution.report.experiment.experiment_name} · {execution.experimental_version}
                    </p>
                </div>
                <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
                    execution.comparison.promoted
                        ? 'bg-[#34c759]/10 text-[#34c759]'
                        : 'bg-[#ff9500]/10 text-[#ff9500]'
                }`}>
                    {execution.comparison.promoted ? 'Promoted to Champion' : 'Shadow Review Required'}
                </div>
            </div>

            <div className={`grid grid-cols-1 gap-4 ${isAnomaly ? 'md:grid-cols-2 xl:grid-cols-4' : 'md:grid-cols-3'}`}>
                {metricCards.map(([label, key, mode]) => (
                    <DecisionMetric
                        key={key}
                        label={label}
                        baseline={numberMetric(baselineMetrics[key], mode)}
                        challenger={numberMetric(challengerMetrics[key], mode)}
                    />
                ))}
            </div>

            <div className="rounded-xl border border-black/5 bg-[#f5f5f7] p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#86868b]">Decision rationale</p>
                <p className="mt-2 text-sm text-[#86868b]">{execution.comparison.reason}</p>
            </div>

            {validation && (
                <div className="rounded-xl border border-[#0071e3]/10 bg-[#f5f9ff] p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#0071e3]">Validation Plan</p>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                        <Meta label="Mode" value={humanizeGateName(String(validation.mode ?? 'quick_screen'))} />
                        <Meta label="Calibration" value={`${validation.calibration_days ?? 28} days`} />
                        <Meta label="Holdout" value={`${validation.holdout_days ?? 28} days`} />
                        <Meta
                            label="Rolling"
                            value={rollingValidation ? `${rollingValidation.completed_windows}/${rollingValidation.requested_windows} windows` : 'not run'}
                        />
                    </div>
                </div>
            )}

            {rollingValidation && (
                <div className="rounded-xl border border-black/5 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="text-xs font-semibold uppercase tracking-wider text-[#86868b]">Rolling Validation</p>
                        <span className={`rounded-full px-3 py-1 text-xs font-medium ${
                            rollingValidation.gate_checks?.temporal_validation_gate
                                ? 'bg-[#34c759]/10 text-[#34c759]'
                                : 'bg-[#ff3b30]/10 text-[#ff3b30]'
                        }`}>
                            {rollingValidation.gate_checks?.temporal_validation_gate ? 'Temporal Gate Passed' : 'Temporal Gate Needs Review'}
                        </span>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                        <Meta label="Avg WAPE" value={`${numberMetric(rollingValidation.summary_metrics?.baseline_avg_wape, 'percent')} -> ${numberMetric(rollingValidation.summary_metrics?.challenger_avg_wape, 'percent')}`} />
                        <Meta label="Worst WAPE" value={`${numberMetric(rollingValidation.summary_metrics?.baseline_worst_wape, 'percent')} -> ${numberMetric(rollingValidation.summary_metrics?.challenger_worst_wape, 'percent')}`} />
                        <Meta label="Avg Cost" value={`${numberMetric(rollingValidation.summary_metrics?.baseline_avg_combined_cost_proxy, 'currency')} -> ${numberMetric(rollingValidation.summary_metrics?.challenger_avg_combined_cost_proxy, 'currency')}`} />
                        <Meta label="Avg Service" value={`${numberMetric(rollingValidation.summary_metrics?.baseline_avg_service_level, 'percent')} -> ${numberMetric(rollingValidation.summary_metrics?.challenger_avg_service_level, 'percent')}`} />
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
                {gateChecks.map(([gateName, passed]) => (
                    <div
                        key={gateName}
                        className={`rounded-lg border px-3 py-2 text-sm ${
                            passed
                                ? 'border-[#34c759]/20 bg-[#34c759]/10 text-[#34c759]'
                                : 'border-[#ff3b30]/20 bg-[#ff3b30]/10 text-[#ff3b30]'
                        }`}
                    >
                        <div className="font-medium">{humanizeGateName(gateName)}</div>
                        <div className="text-xs mt-1">{passed ? 'Passed' : 'Needs review'}</div>
                    </div>
                ))}
            </div>
        </section>
    )
}

function DecisionMetric({
    label,
    baseline,
    challenger,
}: {
    label: string
    baseline: string
    challenger: string
}) {
    return (
        <div className="rounded-xl border border-black/5 bg-white/80 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#86868b]">{label}</p>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div>
                    <p className="text-[#86868b]">Baseline</p>
                    <p className="font-semibold text-[#1d1d1f]">{baseline}</p>
                </div>
                <div>
                    <p className="text-[#86868b]">Challenger</p>
                    <p className="font-semibold text-[#0071e3]">{challenger}</p>
                </div>
            </div>
        </div>
    )
}

function humanizeGateName(value: string) {
    return value
        .replace(/_gate$/g, '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, char => char.toUpperCase())
}

function numberMetric(value: unknown, mode: 'number' | 'percent' | 'currency' = 'number') {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return '—'
    }
    if (mode === 'percent') {
        return `${(value * 100).toFixed(1)}%`
    }
    if (mode === 'currency') {
        return `$${Math.round(value).toLocaleString()}`
    }
    return value.toFixed(3)
}

function StatusMessage({ tone, text }: { tone: 'success' | 'error'; text: string }) {
    return (
        <div className={`rounded-lg px-3 py-2 text-sm ${
            tone === 'success'
                ? 'bg-[#34c759]/10 text-[#34c759] border border-[#34c759]/20'
                : 'bg-[#ff3b30]/10 text-[#ff3b30] border border-[#ff3b30]/20'
        }`}>
            {text}
        </div>
    )
}

function StatusPill({ status }: { status: string }) {
    const styles: Record<string, string> = {
        proposed: 'bg-[#86868b]/10 text-[#86868b]',
        approved: 'bg-[#34c759]/10 text-[#34c759]',
        in_progress: 'bg-[#0071e3]/10 text-[#0071e3]',
        shadow_testing: 'bg-[#ff9500]/10 text-[#ff9500]',
        completed: 'bg-[#5856d6]/10 text-[#5856d6]',
        rejected: 'bg-[#ff3b30]/10 text-[#ff3b30]',
    }

    return (
        <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${styles[status] ?? 'bg-[#86868b]/10 text-[#86868b]'}`}>
            {status.replace(/_/g, ' ')}
        </span>
    )
}

function SourcePill({ source }: { source: ExperimentSource }) {
    const styles: Record<ExperimentSource, string> = {
        manual: 'bg-[#0071e3]/10 text-[#0071e3]',
        ai_assisted: 'bg-[#5856d6]/10 text-[#5856d6]',
        ai_agent: 'bg-[#ff9500]/10 text-[#ff9500]',
    }

    return (
        <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${styles[source]}`}>
            {sourceLabel(source)}
        </span>
    )
}

function sourceLabel(source: ExperimentSource) {
    const labels: Record<ExperimentSource, string> = {
        manual: 'Manual DS',
        ai_assisted: 'AI Assisted',
        ai_agent: 'AI Agent',
    }
    return labels[source]
}

function Meta({ label, value }: { label: string; value: string }) {
    return (
        <div className="min-w-0">
            <p className="uppercase tracking-wider text-[10px] text-[#86868b]">{label}</p>
            <p className="mt-1 truncate font-medium text-[#86868b]" title={value || '—'}>{value || '—'}</p>
        </div>
    )
}

function stringValue(value: unknown): string {
    if (typeof value === 'string') return value
    if (typeof value === 'number') return String(value)
    return ''
}

function compactFeatureFlags(featureConfig: Record<string, unknown> | undefined): string {
    if (!featureConfig) return '—'
    const activeFlags = Object.entries(featureConfig)
        .filter(([key, value]) => key.startsWith('include_') && value === true)
        .map(([key]) => key.replace(/^include_/, '').replace(/_/g, ' '))
    return activeFlags.length > 0 ? activeFlags.join(', ') : 'none'
}

function CompletedTrialsLog({
    experiments,
    isLoading,
}: {
    experiments: ExperimentLedgerEntry[]
    isLoading: boolean
}) {
    if (isLoading) {
        return (
            <div className="card border border-black/[0.02] shadow-sm text-center py-10">
                <Loader2 className="h-5 w-5 mx-auto text-[#0071e3] animate-spin" />
            </div>
        )
    }

    if (experiments.length === 0) {
        return (
            <div className="card border border-dashed border-black/5 bg-[#f5f5f7] text-center py-10">
                <FlaskConical className="h-6 w-6 mx-auto text-[#86868b]" />
                <p className="mt-2 text-sm text-[#86868b]">No completed release reports yet.</p>
                <p className="mt-1 text-xs text-[#86868b]">
                    Comparison appears after a finished experiment records validation results.
                </p>
            </div>
        )
    }

    return (
        <div className="space-y-3">
            {experiments.map(exp => (
                <CompletedTrialCard key={exp.experiment_id} exp={exp} />
            ))}
        </div>
    )
}

function CompletedTrialCard({ exp }: { exp: ExperimentLedgerEntry }) {
    const interpret = useInterpretExperiment()
    const [interpretation, setInterpretation] = useState<{
        results_summary: string
        why_it_worked: string
        next_hypothesis: string
    } | null>(() => {
        const cached = (exp.results as ExperimentResults | null)?.llm_interpretation as {
            results_summary: string
            why_it_worked: string
            next_hypothesis: string
        } | undefined
        return cached ?? null
    })

    const r = (exp.results ?? {}) as ExperimentResults
    const promoted = r.promotion_comparison?.promoted ?? r.overall_business_safe
    const gateChecks = r.promotion_comparison?.gate_checks ?? {}
    const failedGates = Object.entries(gateChecks).filter(([, passed]) => !passed).map(([k]) => k)
    const isAnomaly = exp.model_name === 'anomaly_detector'
    const maseDelta = r.baseline_mase != null && r.experimental_mase != null
        ? (((r.baseline_mase - r.experimental_mase) / r.baseline_mase) * 100)
        : null
    const precisionDelta = r.baseline_precision != null && r.experimental_precision != null
        ? ((r.experimental_precision - r.baseline_precision) * 100)
        : null

    async function handleInterpret() {
        try {
            const result = await interpret.mutateAsync(exp.experiment_id)
            setInterpretation({
                results_summary: result.results_summary,
                why_it_worked: result.why_it_worked,
                next_hypothesis: result.next_hypothesis,
            })
        } catch {
            // error surfaced via interpret.isError
        }
    }

    return (
        <article className="card border border-black/[0.02] shadow-sm p-5 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-[#1d1d1f]">{exp.experiment_name}</p>
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            promoted ? 'bg-[#34c759]/10 text-[#34c759]' : 'bg-[#ff9500]/10 text-[#ff9500]'
                        }`}>
                            {promoted ? 'Promoted' : 'Shadow only'}
                        </span>
                        <SourcePill source={exp.experiment_source} />
                    </div>
                    <p className="mt-1 text-sm text-[#86868b]">{exp.hypothesis}</p>
                </div>
                <div className="flex items-start gap-3">
                    <div className="text-right text-xs text-[#86868b]">
                        <p>{exp.baseline_version ?? '—'} → {exp.experimental_version ?? '—'}</p>
                        {exp.completed_at && <p className="mt-0.5">{new Date(exp.completed_at).toLocaleDateString()}</p>}
                    </div>
                    {!interpretation && (
                        <button
                            type="button"
                            onClick={() => void handleInterpret()}
                            disabled={interpret.isPending}
                            className="inline-flex items-center gap-1.5 rounded-[8px] border border-[#5856d6]/20 bg-[#5856d6]/10 px-3 py-1.5 text-xs font-medium text-[#5856d6] transition hover:bg-[#5856d6]/15 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {interpret.isPending
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <Sparkles className="h-3.5 w-3.5" />
                            }
                            Interpret Results
                        </button>
                    )}
                </div>
            </div>

            {!isAnomaly && (r.baseline_mase != null || r.baseline_mae != null) && (
                <div className="grid grid-cols-3 gap-3">
                    <TrialMetricDelta label="MAE" baseline={r.baseline_mae} experimental={r.experimental_mae} lowerIsBetter />
                    <TrialMetricDelta label="WAPE" baseline={r.baseline_wape} experimental={r.experimental_wape} lowerIsBetter isPercent />
                    <TrialMetricDelta label="MASE" baseline={r.baseline_mase} experimental={r.experimental_mase} lowerIsBetter />
                </div>
            )}

            {isAnomaly && (r.baseline_precision != null || r.experimental_precision != null) && (
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                    <TrialMetricDelta label="Precision" baseline={r.baseline_precision} experimental={r.experimental_precision} lowerIsBetter={false} isPercent />
                    <TrialMetricDelta label="Recall" baseline={r.baseline_recall} experimental={r.experimental_recall} lowerIsBetter={false} isPercent />
                    <TrialMetricDelta label="False Positive" baseline={r.baseline_false_positive_rate} experimental={r.experimental_false_positive_rate} lowerIsBetter isPercent />
                    <TrialMetricDelta label="Review Rate" baseline={r.baseline_review_rate} experimental={r.experimental_review_rate} lowerIsBetter isPercent />
                </div>
            )}

            {!isAnomaly && maseDelta != null && (
                <div className="rounded-lg bg-[#f5f5f7] px-3 py-2 text-xs text-[#86868b]">
                    MASE improved <span className="font-semibold text-[#0071e3]">{maseDelta.toFixed(1)}%</span>
                    {' '}· {String(r.decision_rationale ?? r.promotion_comparison?.reason ?? exp.decision_rationale ?? '')}
                    {failedGates.length > 0 && (
                        <span className="ml-2 text-[#ff9500]">Needs review: {failedGates.map(g => g.replace('_gate', '')).join(', ')}</span>
                    )}
                </div>
            )}

            {isAnomaly && precisionDelta != null && (
                <div className="rounded-lg bg-[#f5f5f7] px-3 py-2 text-xs text-[#86868b]">
                    Precision moved <span className="font-semibold text-[#0071e3]">{precisionDelta.toFixed(1)} pts</span>
                    {' '}· {String(r.decision_rationale ?? r.promotion_comparison?.reason ?? exp.decision_rationale ?? '')}
                    {failedGates.length > 0 && (
                        <span className="ml-2 text-[#ff9500]">Needs review: {failedGates.map(g => g.replace('_gate', '')).join(', ')}</span>
                    )}
                </div>
            )}

            {interpret.isError && (
                <div className="rounded-lg border border-[#ff3b30]/20 bg-[#ff3b30]/10 px-3 py-2 text-xs text-[#ff3b30]">
                    {interpret.error instanceof Error ? interpret.error.message : 'Interpretation failed.'}
                </div>
            )}

            {interpretation && (
                <div className="rounded-xl border border-[#5856d6]/10 bg-[#5856d6]/5 p-4 space-y-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-[#5856d6]">
                        <Sparkles className="h-3.5 w-3.5" />
                        AI Interpretation
                        <button
                            type="button"
                            onClick={() => setInterpretation(null)}
                            className="ml-auto text-[#5856d6]/40 hover:text-[#5856d6] text-[10px]"
                        >
                            dismiss
                        </button>
                    </div>
                    {interpretation.results_summary && (
                        <InterpretSection label="Results Summary" text={interpretation.results_summary} />
                    )}
                    {interpretation.why_it_worked && (
                        <InterpretSection label="Why It Worked" text={interpretation.why_it_worked} />
                    )}
                    {interpretation.next_hypothesis && (
                        <InterpretSection label="Next Hypothesis" text={interpretation.next_hypothesis} accent />
                    )}
                </div>
            )}
        </article>
    )
}

function InterpretSection({ label, text, accent = false }: { label: string; text: string; accent?: boolean }) {
    return (
        <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#5856d6]/70">{label}</p>
            <p className={`mt-1 text-sm ${accent ? 'font-medium text-[#5856d6]' : 'text-[#1d1d1f]/80'}`}>{text}</p>
        </div>
    )
}

function TrialMetricDelta({
    label,
    baseline,
    experimental,
    lowerIsBetter = true,
    isPercent = false,
}: {
    label: string
    baseline?: number | null
    experimental?: number | null
    lowerIsBetter?: boolean
    isPercent?: boolean
}) {
    const fmt = (v: number) => isPercent ? `${(v * 100).toFixed(1)}%` : v.toFixed(3)
    const improved = baseline != null && experimental != null
        ? (lowerIsBetter ? experimental < baseline : experimental > baseline)
        : null

    return (
        <div className="rounded-lg border border-black/5 bg-white/80 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#86868b]">{label}</p>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <div>
                    <p className="text-[#86868b]">Baseline</p>
                    <p className="font-medium text-[#1d1d1f]">{baseline != null ? fmt(baseline) : '—'}</p>
                </div>
                <div>
                    <p className="text-[#86868b]">Challenger</p>
                    <p className={`font-semibold ${improved === true ? 'text-[#34c759]' : improved === false ? 'text-[#ff3b30]' : 'text-[#1d1d1f]'}`}>
                        {experimental != null ? fmt(experimental) : '—'}
                    </p>
                </div>
            </div>
        </div>
    )
}
