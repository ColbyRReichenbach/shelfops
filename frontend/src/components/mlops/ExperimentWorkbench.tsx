import { useEffect, useState } from 'react'
import type React from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { CheckCircle2, ClipboardList, FlaskConical, Loader2, PlusCircle, Sparkles } from 'lucide-react'

import {
    useApproveExperiment,
    useExperimentLedger,
    useInterpretExperiment,
    useProposeExperiment,
    useRunExperiment,
} from '@/hooks/useShelfOps'
import type {
    ExperimentLedgerEntry,
    ExperimentResults,
    ExperimentRun,
    ExperimentRunExecution,
    ExperimentType,
    ProposeExperimentPayload,
} from '@/lib/types'
import ExperimentHistory from '@/components/mlops/ExperimentHistory'

const EXPERIMENT_TYPES: Array<{ value: ExperimentType; label: string }> = [
    { value: 'feature_set', label: 'Feature Set' },
    { value: 'segmentation', label: 'Segmentation' },
    { value: 'hyperparameter_tuning', label: 'Hyperparameter Tuning' },
    { value: 'objective_function', label: 'Objective Function' },
    { value: 'post_processing', label: 'Post Processing' },
    { value: 'data_window', label: 'Data Window' },
    { value: 'data_contract', label: 'Data Contract' },
    { value: 'architecture', label: 'Architecture' },
    { value: 'baseline_refresh', label: 'Baseline Refresh' },
    { value: 'promotion_decision', label: 'Promotion Decision' },
    { value: 'rollback', label: 'Rollback' },
]

type ExperimentFormState = {
    experiment_name: string
    hypothesis: string
    experiment_type: ExperimentType
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
    notes: string
}

function initialFormState(defaultModelName: string): ExperimentFormState {
    return {
        experiment_name: '',
        hypothesis: '',
        experiment_type: 'feature_set',
        model_name: defaultModelName,
        dataset_id: 'm5_walmart',
        forecast_grain: 'dataset_specific',
        architecture: 'lightgbm',
        objective: 'poisson',
        feature_set_id: 'm5_replenishment_baseline_v1',
        segment_strategy: 'global',
        trigger_source: 'manual_hypothesis',
        baseline_version: '',
        success_criteria: 'Reduce overstock and stockout opportunity cost without regressing MASE or WAPE.',
        notes: '',
    }
}

export default function ExperimentWorkbench({
    modelNames,
    defaultModelName,
    runHistory,
    runsLoading,
    runsError,
    runsErrorMessage,
}: {
    modelNames: string[]
    defaultModelName: string
    runHistory: ExperimentRun[]
    runsLoading: boolean
    runsError: boolean
    runsErrorMessage: string
}) {
    const { user } = useAuth0()
    const defaultAuthor = user?.email ?? ''
    const [form, setForm] = useState<ExperimentFormState>(() => initialFormState(defaultModelName))
    const [submitMessage, setSubmitMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
    const [approvalMessage, setApprovalMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
    const [runMessage, setRunMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
    const [latestExecution, setLatestExecution] = useState<ExperimentRunExecution | null>(null)
    const [draftExperimentId, setDraftExperimentId] = useState<string | null>(null)
    const [draftSignature, setDraftSignature] = useState<string | null>(null)

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
    const {
        data: ledger = [],
        isLoading: ledgerLoading,
        isError: ledgerError,
        error: ledgerErrorDetail,
    } = useExperimentLedger({
        modelName: form.model_name || undefined,
        limit: 12,
    })

    const {
        data: completedTrials = [],
        isLoading: completedLoading,
    } = useExperimentLedger({
        modelName: form.model_name || undefined,
        status: 'completed',
        limit: 20,
    })

    function buildPayload(): ProposeExperimentPayload {
        return {
            experiment_name: form.experiment_name.trim(),
            hypothesis: form.hypothesis.trim(),
            experiment_type: form.experiment_type,
            model_name: form.model_name.trim() || defaultModelName,
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
                notes: form.notes.trim() || null,
            },
        }
    }

    function payloadSignature(payload: ProposeExperimentPayload): string {
        return JSON.stringify(payload)
    }

    function resetDraft(modelName: string) {
        setDraftExperimentId(null)
        setDraftSignature(null)
        setLatestExecution(null)
        setRunMessage(null)
        setSubmitMessage(null)
        setApprovalMessage(null)
        setForm(current => ({
            ...initialFormState(modelName),
            model_name: modelName,
            dataset_id: current.dataset_id,
            forecast_grain: current.forecast_grain,
            architecture: current.architecture,
            objective: current.objective,
            feature_set_id: current.feature_set_id,
            segment_strategy: current.segment_strategy,
            trigger_source: current.trigger_source,
        }))
    }

    async function ensureExperiment(payload: ProposeExperimentPayload): Promise<string> {
        const signature = payloadSignature(payload)
        if (draftExperimentId && draftSignature === signature) {
            return draftExperimentId
        }
        const response = await proposeExperiment.mutateAsync(payload)
        setDraftExperimentId(response.experiment_id)
        setDraftSignature(signature)
        return response.experiment_id
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
            setDraftExperimentId(response.experiment_id)
            setDraftSignature(payloadSignature(payload))
            setSubmitMessage({
                tone: 'success',
                text: `Hypothesis logged${defaultAuthor ? ` as ${defaultAuthor}` : ''}. Baseline version: ${response.baseline_version ?? 'none detected yet'}.`,
            })
        } catch (error) {
            const detail = error instanceof Error ? error.message : 'Unable to log experiment.'
            setSubmitMessage({ tone: 'error', text: detail })
        }
    }

    async function handleRun(event: React.MouseEvent<HTMLButtonElement>) {
        event.preventDefault()
        setRunMessage(null)
        setSubmitMessage(null)
        const payload = buildPayload()

        if (!payload.experiment_name || !payload.hypothesis) {
            setRunMessage({
                tone: 'error',
                text: 'Experiment name and hypothesis are required before running.',
            })
            return
        }

        try {
            const experimentId = await ensureExperiment(payload)
            const result = await runExperiment.mutateAsync({
                experimentId,
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

    const actorLabel = defaultAuthor || 'the authenticated account'

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 xl:grid-cols-[1.2fr,0.8fr] gap-6">
                <section className="card border border-black/[0.02] shadow-sm p-5 space-y-4">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <h2 className="text-lg font-semibold text-[#0071e3]">Log New Hypothesis</h2>
                            <p className="text-sm text-[#86868b] mt-1">
                                This logs the proposed change before a training run starts.
                            </p>
                            <p className="text-xs text-[#86868b] mt-2">
                                The submitting account is pulled from {actorLabel}; it is no longer entered manually.
                            </p>
                        </div>
                        <div className="inline-flex items-center gap-2 rounded-full bg-[#0071e3]/10 px-3 py-1 text-xs font-medium text-[#0071e3]">
                            <PlusCircle className="h-3.5 w-3.5" />
                            Experiment Intake
                        </div>
                    </div>

                    <form className="space-y-4" onSubmit={handleSubmit}>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <Field label="Experiment Name">
                                <input
                                    value={form.experiment_name}
                                    onChange={event => setForm(current => ({ ...current, experiment_name: event.target.value }))}
                                    className="input"
                                    placeholder="m5_replenishment_feature_set_v2"
                                />
                            </Field>
                            <Field label="Experiment Type">
                                <select
                                    value={form.experiment_type}
                                    onChange={event => {
                                        const nextType = event.target.value as ExperimentType
                                        setForm(current => ({
                                            ...current,
                                            experiment_type: nextType,
                                            segment_strategy: nextType === 'segmentation'
                                                ? 'sku_velocity_terciles_with_global_fallback'
                                                : current.segment_strategy,
                                            feature_set_id: nextType === 'segmentation'
                                                ? 'm5_segmented_candidate_v1'
                                                : current.feature_set_id,
                                            success_criteria: nextType === 'segmentation'
                                                ? 'Reduce lost sales quantity and stockout opportunity cost without regressing WAPE, MASE, or overstock rate.'
                                                : current.success_criteria,
                                        }))
                                    }}
                                    className="input"
                                >
                                    {EXPERIMENT_TYPES.map(option => (
                                        <option key={option.value} value={option.value}>{option.label}</option>
                                    ))}
                                </select>
                            </Field>
                        </div>

                        <Field label="Hypothesis">
                            <textarea
                                value={form.hypothesis}
                                onChange={event => setForm(current => ({ ...current, hypothesis: event.target.value }))}
                                className="input min-h-24 resize-y"
                                placeholder="Promo interactions and recent-demand velocity features will reduce overstock and stockout opportunity cost without regressing MASE or WAPE."
                            />
                        </Field>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <Field label="Model Name">
                                <select
                                    value={form.model_name}
                                    onChange={event => setForm(current => ({ ...current, model_name: event.target.value }))}
                                    className="input"
                                >
                                    {[...new Set([defaultModelName, ...modelNames].filter(Boolean))].map(name => (
                                        <option key={name} value={name}>{name}</option>
                                    ))}
                                </select>
                            </Field>
                            <Field label="Baseline Version">
                                <input
                                    value={form.baseline_version}
                                    onChange={event => setForm(current => ({ ...current, baseline_version: event.target.value }))}
                                    className="input"
                                    placeholder="Auto-detected if blank"
                                />
                            </Field>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                            <Field label="Dataset ID">
                                <input
                                    value={form.dataset_id}
                                    onChange={event => setForm(current => ({ ...current, dataset_id: event.target.value }))}
                                    className="input"
                                />
                            </Field>
                            <Field label="Forecast Grain">
                                <input
                                    value={form.forecast_grain}
                                    onChange={event => setForm(current => ({ ...current, forecast_grain: event.target.value }))}
                                    className="input"
                                />
                            </Field>
                            <Field label="Architecture">
                                <input
                                    value={form.architecture}
                                    onChange={event => setForm(current => ({ ...current, architecture: event.target.value }))}
                                    className="input"
                                />
                            </Field>
                            <Field label="Objective">
                                <input
                                    value={form.objective}
                                    onChange={event => setForm(current => ({ ...current, objective: event.target.value }))}
                                    className="input"
                                />
                            </Field>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <Field label="Feature Set ID">
                                <input
                                    value={form.feature_set_id}
                                    onChange={event => setForm(current => ({ ...current, feature_set_id: event.target.value }))}
                                    className="input"
                                />
                            </Field>
                            <Field label="Segment Strategy">
                                <input
                                    value={form.segment_strategy}
                                    onChange={event => setForm(current => ({ ...current, segment_strategy: event.target.value }))}
                                    className="input"
                                />
                            </Field>
                            <Field label="Trigger Source">
                                <input
                                    value={form.trigger_source}
                                    onChange={event => setForm(current => ({ ...current, trigger_source: event.target.value }))}
                                    className="input"
                                />
                            </Field>
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            <Field label="Success Criteria">
                                <textarea
                                    value={form.success_criteria}
                                    onChange={event => setForm(current => ({ ...current, success_criteria: event.target.value }))}
                                    className="input min-h-20 resize-y"
                                    placeholder="Reduce overstock dollars and stockout opportunity cost while keeping MASE/WAPE flat or better."
                                />
                            </Field>
                            <Field label="Notes">
                                <textarea
                                    value={form.notes}
                                    onChange={event => setForm(current => ({ ...current, notes: event.target.value }))}
                                    className="input min-h-20 resize-y"
                                    placeholder="Optional implementation notes, segment focus, or rollback concerns."
                                />
                            </Field>
                        </div>

                        {submitMessage && (
                            <StatusMessage tone={submitMessage.tone} text={submitMessage.text} />
                        )}
                        {runMessage && (
                            <StatusMessage tone={runMessage.tone} text={runMessage.text} />
                        )}

                        <div className="flex items-center justify-between gap-3">
                            <p className="text-xs text-[#86868b]">
                                `Run Hypothesis` logs the entry if needed, executes the bounded test cycle, and returns the release-check summary.
                            </p>
                            <div className="flex items-center gap-2">
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
                                    className="inline-flex items-center gap-2 rounded-lg border border-[#0071e3]/20 bg-white px-4 py-2 text-sm font-medium text-[#0071e3] shadow-sm transition hover:border-[#0071e3]/35 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {proposeExperiment.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlusCircle className="h-4 w-4" />}
                                    Log Hypothesis
                                </button>
                                <button
                                    type="button"
                                    onClick={handleRun}
                                    disabled={proposeExperiment.isPending || runExperiment.isPending}
                                    className="inline-flex items-center gap-2 rounded-lg bg-[#0071e3] px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {runExperiment.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
                                    Run Hypothesis
                                </button>
                            </div>
                        </div>
                    </form>
                </section>

                <section className="card border border-black/[0.02] shadow-sm p-5 space-y-4">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <h2 className="text-lg font-semibold text-[#0071e3]">Experiment Ledger</h2>
                            <p className="text-sm text-[#86868b] mt-1">
                                Human-reviewed hypothesis queue for the active model.
                            </p>
                        </div>
                        <div className="inline-flex items-center gap-2 rounded-full bg-[#ff9500]/10 px-3 py-1 text-xs font-medium text-[#ff9500]">
                            <ClipboardList className="h-3.5 w-3.5" />
                            {form.model_name}
                        </div>
                    </div>

                    {approvalMessage && (
                        <StatusMessage tone={approvalMessage.tone} text={approvalMessage.text} />
                    )}

                    <ExperimentLedgerList
                        experiments={ledger}
                        isLoading={ledgerLoading}
                        isError={ledgerError}
                        errorMessage={ledgerErrorDetail instanceof Error ? ledgerErrorDetail.message : 'Unable to load experiment ledger.'}
                        onApprove={handleApprove}
                        approvingId={approveExperiment.variables?.experimentId ?? null}
                        approvePending={approveExperiment.isPending}
                    />
                </section>
            </div>

            <section className="space-y-3">
                {latestExecution && (
                    <ExperimentExecutionSummary execution={latestExecution} />
                )}
                <div>
                    <h2 className="text-lg font-semibold text-[#0071e3]">Training Run History</h2>
                    <p className="text-sm text-[#86868b] mt-1">
                        Runtime training and evaluation logs from the local report history.
                    </p>
                </div>
                <ExperimentHistory
                    experiments={runHistory}
                    isLoading={runsLoading}
                    isError={runsError}
                    errorMessage={runsErrorMessage}
                />
            </section>

            <section className="space-y-3">
                <div>
                    <h2 className="text-lg font-semibold text-[#0071e3]">Completed Trials</h2>
                    <p className="text-sm text-[#86868b] mt-1">
                        Finished model comparisons with final release-check outcomes.
                    </p>
                </div>
                <CompletedTrialsLog experiments={completedTrials} isLoading={completedLoading} />
            </section>
        </div>
    )
}

function ExperimentLedgerList({
    experiments,
    isLoading,
    isError,
    errorMessage,
    onApprove,
    approvingId,
    approvePending,
}: {
    experiments: ExperimentLedgerEntry[]
    isLoading: boolean
    isError: boolean
    errorMessage: string
    onApprove: (experiment: ExperimentLedgerEntry) => Promise<void>
    approvingId: string | null
    approvePending: boolean
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
                const isApproving = approvePending && approvingId === experiment.experiment_id

                return (
                    <article key={experiment.experiment_id} className="rounded-xl border border-black/5 bg-white/80 p-4 space-y-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <p className="font-semibold text-[#1d1d1f]">{experiment.experiment_name}</p>
                                    <StatusPill status={experiment.status} />
                                </div>
                                <p className="mt-1 text-sm text-[#86868b]">{experiment.hypothesis}</p>
                            </div>
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
                        </div>

                        <div className="grid grid-cols-2 gap-3 text-xs text-[#86868b] md:grid-cols-3">
                            <Meta label="Type" value={experiment.experiment_type} />
                            <Meta label="Model" value={experiment.model_name} />
                            <Meta label="Baseline" value={experiment.baseline_version ?? '—'} />
                            <Meta label="Dataset" value={stringValue(meta.dataset_id)} />
                            <Meta label="Feature Set" value={stringValue(meta.feature_set_id)} />
                            <Meta label="Segment Strategy" value={stringValue(meta.segment_strategy)} />
                        </div>

                        <div className="rounded-lg bg-[#f5f5f7] px-3 py-2 text-xs text-[#86868b]">
                            <span className="font-medium text-[#86868b]">Success criteria:</span>{' '}
                            {stringValue(meta.success_criteria) || 'Not provided'}
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[#86868b]">
                            <span>Proposed by {experiment.proposed_by}</span>
                            <span>{new Date(experiment.created_at).toLocaleString()}</span>
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

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <DecisionMetric
                    label="WAPE"
                    baseline={numberMetric(baselineMetrics.wape, 'percent')}
                    challenger={numberMetric(challengerMetrics.wape, 'percent')}
                />
                <DecisionMetric
                    label="MASE"
                    baseline={numberMetric(baselineMetrics.mase)}
                    challenger={numberMetric(challengerMetrics.mase)}
                />
                <DecisionMetric
                    label="Opportunity Cost Stockout"
                    baseline={numberMetric(baselineMetrics.opportunity_cost_stockout, 'currency')}
                    challenger={numberMetric(challengerMetrics.opportunity_cost_stockout, 'currency')}
                />
            </div>

            <div className="rounded-xl border border-black/5 bg-[#f5f5f7] p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#86868b]">Decision rationale</p>
                <p className="mt-2 text-sm text-[#86868b]">{execution.comparison.reason}</p>
            </div>

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
                        <div className="text-xs mt-1">{passed ? 'Passed' : 'Failed'}</div>
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

function Meta({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <p className="uppercase tracking-wider text-[10px] text-[#86868b]">{label}</p>
            <p className="mt-1 font-medium text-[#86868b]">{value || '—'}</p>
        </div>
    )
}

function stringValue(value: unknown): string {
    if (typeof value === 'string') return value
    if (typeof value === 'number') return String(value)
    return ''
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
                <p className="mt-2 text-sm text-[#86868b]">No completed trials yet.</p>
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
    const maseDelta = r.baseline_mase != null && r.experimental_mase != null
        ? (((r.baseline_mase - r.experimental_mase) / r.baseline_mase) * 100)
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

            {(r.baseline_mase != null || r.baseline_mae != null) && (
                <div className="grid grid-cols-3 gap-3">
                    <TrialMetricDelta label="MAE" baseline={r.baseline_mae} experimental={r.experimental_mae} lowerIsBetter />
                    <TrialMetricDelta label="WAPE" baseline={r.baseline_wape} experimental={r.experimental_wape} lowerIsBetter isPercent />
                    <TrialMetricDelta label="MASE" baseline={r.baseline_mase} experimental={r.experimental_mase} lowerIsBetter />
                </div>
            )}

            {maseDelta != null && (
                <div className="rounded-lg bg-[#f5f5f7] px-3 py-2 text-xs text-[#86868b]">
                    MASE improved <span className="font-semibold text-[#0071e3]">{maseDelta.toFixed(1)}%</span>
                    {' '}· {String(r.decision_rationale ?? r.promotion_comparison?.reason ?? exp.decision_rationale ?? '')}
                    {failedGates.length > 0 && (
                        <span className="ml-2 text-[#ff9500]">Failed: {failedGates.map(g => g.replace('_gate', '')).join(', ')}</span>
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
