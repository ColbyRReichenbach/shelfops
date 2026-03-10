import { useEffect, useState } from 'react'
import type React from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { CheckCircle2, ClipboardList, FlaskConical, Loader2, PlusCircle } from 'lucide-react'

import {
    useApproveExperiment,
    useExperimentLedger,
    useProposeExperiment,
} from '@/hooks/useShelfOps'
import type {
    ExperimentLedgerEntry,
    ExperimentRun,
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
        dataset_id: 'favorita',
        forecast_grain: 'store_nbr_family_date',
        architecture: 'lightgbm',
        objective: 'poisson',
        feature_set_id: 'favorita_baseline_v1',
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
}: {
    modelNames: string[]
    defaultModelName: string
    runHistory: ExperimentRun[]
    runsLoading: boolean
}) {
    const { user } = useAuth0()
    const defaultAuthor = user?.email ?? ''
    const [form, setForm] = useState<ExperimentFormState>(() => initialFormState(defaultModelName))
    const [submitMessage, setSubmitMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
    const [approvalMessage, setApprovalMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)

    useEffect(() => {
        setForm(current => {
            const next = { ...current }
            if (!current.model_name && defaultModelName) next.model_name = defaultModelName
            return next
        })
    }, [defaultAuthor, defaultModelName])

    const proposeExperiment = useProposeExperiment()
    const approveExperiment = useApproveExperiment()
    const { data: ledger = [], isLoading: ledgerLoading } = useExperimentLedger({
        modelName: form.model_name || undefined,
        limit: 12,
    })

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setSubmitMessage(null)

        const payload: ProposeExperimentPayload = {
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
                text: `Hypothesis logged${defaultAuthor ? ` as ${defaultAuthor}` : ''}. Baseline version: ${response.baseline_version ?? 'none detected yet'}.`,
            })
            setForm(current => ({
                ...initialFormState(payload.model_name),
                model_name: payload.model_name,
                dataset_id: current.dataset_id,
                forecast_grain: current.forecast_grain,
                architecture: current.architecture,
                objective: current.objective,
                feature_set_id: current.feature_set_id,
                segment_strategy: current.segment_strategy,
                trigger_source: current.trigger_source,
            }))
        } catch (error) {
            const detail = error instanceof Error ? error.message : 'Unable to log experiment.'
            setSubmitMessage({ tone: 'error', text: detail })
        }
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
                <section className="card border border-white/40 shadow-sm p-5 space-y-4">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <h2 className="text-lg font-semibold text-shelf-primary">Log New Hypothesis</h2>
                            <p className="text-sm text-shelf-foreground/60 mt-1">
                                This writes directly to the experiments API and anchors the audit trail before training starts.
                            </p>
                            <p className="text-xs text-shelf-foreground/45 mt-2">
                                Audit actor is derived from {actorLabel}; it is no longer entered manually.
                            </p>
                        </div>
                        <div className="inline-flex items-center gap-2 rounded-full bg-shelf-primary/10 px-3 py-1 text-xs font-medium text-shelf-primary">
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
                                    placeholder="favorita_lgbm_feature_set_v2_promo_velocity"
                                />
                            </Field>
                            <Field label="Experiment Type">
                                <select
                                    value={form.experiment_type}
                                    onChange={event => setForm(current => ({ ...current, experiment_type: event.target.value as ExperimentType }))}
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

                        <div className="flex items-center justify-between gap-3">
                            <p className="text-xs text-shelf-foreground/50">
                                Baseline version is still auto-detected by the backend from the current champion.
                            </p>
                            <button
                                type="submit"
                                disabled={proposeExperiment.isPending}
                                className="inline-flex items-center gap-2 rounded-lg bg-shelf-primary px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {proposeExperiment.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlusCircle className="h-4 w-4" />}
                                Log Hypothesis
                            </button>
                        </div>
                    </form>
                </section>

                <section className="card border border-white/40 shadow-sm p-5 space-y-4">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <h2 className="text-lg font-semibold text-shelf-primary">Experiment Ledger</h2>
                            <p className="text-sm text-shelf-foreground/60 mt-1">
                                Human-reviewed hypothesis queue for the active model.
                            </p>
                        </div>
                        <div className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
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
                        onApprove={handleApprove}
                        approvingId={approveExperiment.variables?.experimentId ?? null}
                        approvePending={approveExperiment.isPending}
                    />
                </section>
            </div>

            <section className="space-y-3">
                <div>
                    <h2 className="text-lg font-semibold text-shelf-primary">Training Run Evidence</h2>
                    <p className="text-sm text-shelf-foreground/60 mt-1">
                        Runtime training and evaluation logs from the local report history.
                    </p>
                </div>
                <ExperimentHistory experiments={runHistory} isLoading={runsLoading} />
            </section>
        </div>
    )
}

function ExperimentLedgerList({
    experiments,
    isLoading,
    onApprove,
    approvingId,
    approvePending,
}: {
    experiments: ExperimentLedgerEntry[]
    isLoading: boolean
    onApprove: (experiment: ExperimentLedgerEntry) => Promise<void>
    approvingId: string | null
    approvePending: boolean
}) {
    if (isLoading) {
        return (
            <div className="rounded-xl border border-shelf-foreground/10 bg-shelf-secondary/5 p-6 text-center">
                <Loader2 className="mx-auto h-5 w-5 animate-spin text-shelf-primary" />
                <p className="mt-2 text-sm text-shelf-foreground/60">Loading experiment ledger...</p>
            </div>
        )
    }

    if (experiments.length === 0) {
        return (
            <div className="rounded-xl border border-dashed border-shelf-foreground/15 bg-shelf-secondary/5 p-6 text-center">
                <FlaskConical className="mx-auto h-6 w-6 text-shelf-foreground/35" />
                <p className="mt-2 text-sm text-shelf-foreground/55">No hypotheses logged for this model yet.</p>
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
                    <article key={experiment.experiment_id} className="rounded-xl border border-shelf-foreground/10 bg-white/80 p-4 space-y-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <p className="font-semibold text-shelf-foreground">{experiment.experiment_name}</p>
                                    <StatusPill status={experiment.status} />
                                </div>
                                <p className="mt-1 text-sm text-shelf-foreground/65">{experiment.hypothesis}</p>
                            </div>
                            {canApprove && (
                                <button
                                    type="button"
                                    onClick={() => void onApprove(experiment)}
                                    disabled={isApproving}
                                    className="inline-flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-1.5 text-xs font-medium text-green-700 transition hover:bg-green-100 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {isApproving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                                    Approve
                                </button>
                            )}
                        </div>

                        <div className="grid grid-cols-2 gap-3 text-xs text-shelf-foreground/60 md:grid-cols-3">
                            <Meta label="Type" value={experiment.experiment_type} />
                            <Meta label="Model" value={experiment.model_name} />
                            <Meta label="Baseline" value={experiment.baseline_version ?? '—'} />
                            <Meta label="Dataset" value={stringValue(meta.dataset_id)} />
                            <Meta label="Feature Set" value={stringValue(meta.feature_set_id)} />
                            <Meta label="Segment Strategy" value={stringValue(meta.segment_strategy)} />
                        </div>

                        <div className="rounded-lg bg-shelf-secondary/5 px-3 py-2 text-xs text-shelf-foreground/60">
                            <span className="font-medium text-shelf-foreground/70">Success criteria:</span>{' '}
                            {stringValue(meta.success_criteria) || 'Not provided'}
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-shelf-foreground/50">
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
            <span className="text-xs font-medium uppercase tracking-wider text-shelf-foreground/55">{label}</span>
            {children}
        </label>
    )
}

function StatusMessage({ tone, text }: { tone: 'success' | 'error'; text: string }) {
    return (
        <div className={`rounded-lg px-3 py-2 text-sm ${
            tone === 'success'
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
            {text}
        </div>
    )
}

function StatusPill({ status }: { status: string }) {
    const styles: Record<string, string> = {
        proposed: 'bg-slate-100 text-slate-700',
        approved: 'bg-green-100 text-green-700',
        in_progress: 'bg-blue-100 text-blue-700',
        shadow_testing: 'bg-amber-100 text-amber-700',
        completed: 'bg-violet-100 text-violet-700',
        rejected: 'bg-rose-100 text-rose-700',
    }

    return (
        <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${styles[status] ?? 'bg-slate-100 text-slate-700'}`}>
            {status.replace(/_/g, ' ')}
        </span>
    )
}

function Meta({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <p className="uppercase tracking-wider text-[10px] text-shelf-foreground/40">{label}</p>
            <p className="mt-1 font-medium text-shelf-foreground/70">{value || '—'}</p>
        </div>
    )
}

function stringValue(value: unknown): string {
    if (typeof value === 'string') return value
    if (typeof value === 'number') return String(value)
    return ''
}
