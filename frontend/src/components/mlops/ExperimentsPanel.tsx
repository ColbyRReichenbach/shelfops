import { useMemo, useState } from 'react'
import { Beaker, Plus } from 'lucide-react'
import type { ExperimentItem, ProposeExperimentRequest } from '@/lib/types'

interface ExperimentsPanelProps {
    experiments: ExperimentItem[]
    isLoading?: boolean
    proposePending?: boolean
    onPropose: (payload: ProposeExperimentRequest) => Promise<unknown>
}

const STATUS_FILTERS = ['all', 'proposed', 'approved', 'in_progress', 'shadow_testing', 'completed', 'rejected'] as const

const defaultForm: ProposeExperimentRequest = {
    experiment_name: '',
    hypothesis: '',
    experiment_type: 'feature_engineering',
    model_name: 'demand_forecast',
    proposed_by: '',
}

export default function ExperimentsPanel({
    experiments,
    isLoading = false,
    proposePending = false,
    onPropose,
}: ExperimentsPanelProps) {
    const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>('all')
    const [showModal, setShowModal] = useState(false)
    const [form, setForm] = useState<ProposeExperimentRequest>(defaultForm)

    const filtered = useMemo(() => {
        if (statusFilter === 'all') return experiments
        return experiments.filter((exp) => exp.status === statusFilter)
    }, [experiments, statusFilter])

    async function submit() {
        if (!form.experiment_name.trim() || !form.hypothesis.trim() || !form.proposed_by.trim()) return
        await onPropose(form)
        setShowModal(false)
        setForm(defaultForm)
    }

    return (
        <div className="card border border-white/40 shadow-sm">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
                <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Experiments</h3>
                <div className="flex gap-2">
                    <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value as (typeof STATUS_FILTERS)[number])}
                        className="rounded-lg border border-shelf-foreground/10 bg-white px-3 py-1.5 text-sm"
                    >
                        {STATUS_FILTERS.map((status) => (
                            <option key={status} value={status}>
                                Status: {status}
                            </option>
                        ))}
                    </select>
                    <button
                        className="btn-primary text-xs h-8 px-3 gap-1"
                        onClick={() => setShowModal(true)}
                    >
                        <Plus className="h-3 w-3" />
                        Propose
                    </button>
                </div>
            </div>

            {isLoading ? (
                <p className="text-sm text-shelf-foreground/50">Loading experiments...</p>
            ) : filtered.length === 0 ? (
                <p className="text-sm text-shelf-foreground/50">No experiments found. Propose your first hypothesis test.</p>
            ) : (
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                    {filtered.map((exp) => (
                        <div key={exp.experiment_id} className="rounded-xl border border-shelf-foreground/10 p-3 bg-white">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <p className="font-medium text-sm">{exp.experiment_name}</p>
                                    <p className="text-xs text-shelf-foreground/70 mt-1">{exp.hypothesis}</p>
                                    <div className="flex items-center gap-2 mt-2 text-[11px] text-shelf-foreground/50">
                                        <span className="uppercase">{exp.status}</span>
                                        <span>•</span>
                                        <span className="uppercase">{exp.experiment_type}</span>
                                        <span>•</span>
                                        <span>by {exp.proposed_by}</span>
                                    </div>
                                    <div className="text-[11px] text-shelf-foreground/50 mt-1">
                                        Baseline {exp.baseline_version ?? '—'} · Experimental {exp.experimental_version ?? '—'}
                                    </div>
                                </div>
                                <Beaker className="h-4 w-4 text-shelf-primary/70 shrink-0 mt-0.5" />
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {showModal && (
                <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
                    <div className="w-full max-w-xl rounded-2xl bg-white shadow-xl border border-shelf-foreground/10 p-5 space-y-4">
                        <div className="flex items-center justify-between">
                            <h4 className="text-lg font-semibold text-shelf-primary">Propose Experiment</h4>
                            <button
                                className="text-sm text-shelf-foreground/50 hover:text-shelf-foreground"
                                onClick={() => setShowModal(false)}
                            >
                                Close
                            </button>
                        </div>
                        <div className="space-y-3">
                            <input
                                value={form.experiment_name}
                                onChange={(e) => setForm((prev) => ({ ...prev, experiment_name: e.target.value }))}
                                placeholder="Experiment name"
                                className="w-full rounded-lg border border-shelf-foreground/10 px-3 py-2 text-sm"
                            />
                            <textarea
                                value={form.hypothesis}
                                onChange={(e) => setForm((prev) => ({ ...prev, hypothesis: e.target.value }))}
                                placeholder="Hypothesis"
                                rows={3}
                                className="w-full rounded-lg border border-shelf-foreground/10 px-3 py-2 text-sm"
                            />
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <select
                                    value={form.experiment_type}
                                    onChange={(e) => setForm((prev) => ({ ...prev, experiment_type: e.target.value as ProposeExperimentRequest['experiment_type'] }))}
                                    className="rounded-lg border border-shelf-foreground/10 px-3 py-2 text-sm"
                                >
                                    <option value="feature_engineering">feature_engineering</option>
                                    <option value="model_architecture">model_architecture</option>
                                    <option value="data_source">data_source</option>
                                    <option value="segmentation">segmentation</option>
                                </select>
                                <input
                                    value={form.proposed_by}
                                    onChange={(e) => setForm((prev) => ({ ...prev, proposed_by: e.target.value }))}
                                    placeholder="Proposed by (email)"
                                    className="rounded-lg border border-shelf-foreground/10 px-3 py-2 text-sm"
                                />
                            </div>
                        </div>
                        <div className="flex justify-end gap-2">
                            <button className="btn-secondary text-xs h-8 px-3" onClick={() => setShowModal(false)}>Cancel</button>
                            <button className="btn-primary text-xs h-8 px-3" onClick={submit} disabled={proposePending}>
                                {proposePending ? 'Submitting...' : 'Submit'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
