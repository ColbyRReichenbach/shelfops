import { useState } from 'react'
import type React from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Download, Loader2, AlertCircle, X } from 'lucide-react'

import StoreTable from '@/components/dashboard/StoreTable'
import { getApiErrorDetail } from '@/lib/api'
import type { Store, StoreMutationPayload } from '@/lib/types'
import { useCreateStore, useDeleteStore, useStores, useUpdateStore } from '@/hooks/useShelfOps'

type StoreFormState = {
    name: string
    address: string
    city: string
    state: string
    zip_code: string
    lat: string
    lon: string
    timezone: string
    status: string
}

function emptyStoreForm(): StoreFormState {
    return {
        name: '',
        address: '',
        city: '',
        state: '',
        zip_code: '',
        lat: '',
        lon: '',
        timezone: 'America/New_York',
        status: 'active',
    }
}

function storeToForm(store: Store): StoreFormState {
    return {
        name: store.name,
        address: store.address ?? '',
        city: store.city ?? '',
        state: store.state ?? '',
        zip_code: store.zip_code ?? '',
        lat: store.lat != null ? String(store.lat) : '',
        lon: store.lon != null ? String(store.lon) : '',
        timezone: store.timezone,
        status: store.status,
    }
}

function buildStorePayload(form: StoreFormState): StoreMutationPayload {
    return {
        name: form.name.trim(),
        address: form.address.trim() || null,
        city: form.city.trim() || null,
        state: form.state.trim() || null,
        zip_code: form.zip_code.trim() || null,
        lat: form.lat ? Number(form.lat) : null,
        lon: form.lon ? Number(form.lon) : null,
        timezone: form.timezone.trim() || 'America/New_York',
        status: form.status,
    }
}

export default function StoreView() {
    const navigate = useNavigate()
    const { data: stores = [], isLoading, isError } = useStores()
    const createStore = useCreateStore()
    const updateStore = useUpdateStore()
    const deleteStore = useDeleteStore()

    const [isFormOpen, setIsFormOpen] = useState(false)
    const [editingStore, setEditingStore] = useState<Store | null>(null)
    const [form, setForm] = useState<StoreFormState>(emptyStoreForm)
    const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)

    const isSubmitting = createStore.isPending || updateStore.isPending

    function openCreateForm() {
        setEditingStore(null)
        setForm(emptyStoreForm())
        setIsFormOpen(true)
        setFeedback(null)
    }

    function openEditForm(store: Store) {
        setEditingStore(store)
        setForm(storeToForm(store))
        setIsFormOpen(true)
        setFeedback(null)
    }

    function closeForm() {
        setEditingStore(null)
        setForm(emptyStoreForm())
        setIsFormOpen(false)
    }

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setFeedback(null)

        try {
            if (editingStore) {
                await updateStore.mutateAsync({
                    storeId: editingStore.store_id,
                    payload: buildStorePayload(form),
                })
                setFeedback({ tone: 'success', text: `Updated ${form.name}.` })
            } else {
                const createPayload = buildStorePayload(form)
                delete createPayload.status
                await createStore.mutateAsync(createPayload)
                setFeedback({ tone: 'success', text: `Created ${form.name}.` })
            }
            closeForm()
        } catch (submitError) {
            setFeedback({
                tone: 'error',
                text: getApiErrorDetail(submitError, 'Unable to save store.'),
            })
        }
    }

    async function handleDelete(store: Store) {
        if (!window.confirm(`Delete ${store.name}? This cannot be undone.`)) {
            return
        }

        try {
            await deleteStore.mutateAsync(store.store_id)
            setFeedback({ tone: 'success', text: `Deleted ${store.name}.` })
        } catch (deleteError) {
            setFeedback({
                tone: 'error',
                text: getApiErrorDetail(deleteError, 'Unable to delete store.'),
            })
        }
    }

    function handleExport() {
        const header = ['store_id', 'name', 'city', 'state', 'timezone', 'status']
        const rows = stores.map((store) =>
            [store.store_id, store.name, store.city ?? '', store.state ?? '', store.timezone, store.status]
                .map((value) => `"${String(value).split('"').join('""')}"`)
                .join(','),
        )
        const blob = new Blob([[header.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = 'stores.csv'
        link.click()
        URL.revokeObjectURL(url)
    }

    return (
        <div className="p-6 lg:p-8 space-y-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Store Operations</h1>
                    <p className="mt-1 text-sm text-shelf-foreground/60">Manage store inventory and health status</p>
                </div>
                <div className="flex gap-3">
                    <button onClick={handleExport} className="btn-secondary gap-2">
                        <Download className="h-4 w-4" />
                        Export
                    </button>
                    <button onClick={openCreateForm} className="btn-primary gap-2 shadow-lg shadow-shelf-primary/20">
                        <Plus className="h-4 w-4" />
                        Add Store
                    </button>
                </div>
            </div>

            {feedback && (
                <div
                    className={`rounded-xl border px-4 py-3 text-sm ${
                        feedback.tone === 'success'
                            ? 'border-green-200 bg-green-50 text-green-700'
                            : 'border-red-200 bg-red-50 text-red-700'
                    }`}
                >
                    {feedback.text}
                </div>
            )}

            {isFormOpen && (
                <div className="card border border-white/40 shadow-sm">
                    <div className="mb-4 flex items-start justify-between gap-4">
                        <div>
                            <h2 className="text-lg font-semibold text-shelf-primary">
                                {editingStore ? 'Edit Store' : 'Create Store'}
                            </h2>
                            <p className="mt-1 text-sm text-shelf-foreground/55">Persist store metadata directly to the live API.</p>
                        </div>
                        <button
                            onClick={closeForm}
                            className="rounded-lg p-2 text-shelf-foreground/40 transition-colors hover:bg-shelf-secondary/10 hover:text-shelf-primary"
                            aria-label="Close store form"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>

                    <form className="space-y-4" onSubmit={handleSubmit}>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            <Field label="Name">
                                <input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} className="input" required />
                            </Field>
                            <Field label="Timezone">
                                <input value={form.timezone} onChange={(event) => setForm((current) => ({ ...current, timezone: event.target.value }))} className="input" />
                            </Field>
                            <Field label="Address">
                                <input value={form.address} onChange={(event) => setForm((current) => ({ ...current, address: event.target.value }))} className="input" />
                            </Field>
                            <Field label="City">
                                <input value={form.city} onChange={(event) => setForm((current) => ({ ...current, city: event.target.value }))} className="input" />
                            </Field>
                            <Field label="State">
                                <input value={form.state} onChange={(event) => setForm((current) => ({ ...current, state: event.target.value }))} className="input" maxLength={2} />
                            </Field>
                            <Field label="ZIP Code">
                                <input value={form.zip_code} onChange={(event) => setForm((current) => ({ ...current, zip_code: event.target.value }))} className="input" />
                            </Field>
                            <Field label="Latitude">
                                <input value={form.lat} onChange={(event) => setForm((current) => ({ ...current, lat: event.target.value }))} className="input" inputMode="decimal" />
                            </Field>
                            <Field label="Longitude">
                                <input value={form.lon} onChange={(event) => setForm((current) => ({ ...current, lon: event.target.value }))} className="input" inputMode="decimal" />
                            </Field>
                            <Field label="Status">
                                <select value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))} className="input">
                                    <option value="active">Active</option>
                                    <option value="onboarding">Onboarding</option>
                                    <option value="inactive">Inactive</option>
                                </select>
                            </Field>
                        </div>

                        <div className="flex items-center justify-end gap-3">
                            <button type="button" onClick={closeForm} className="btn-secondary text-sm">
                                Cancel
                            </button>
                            <button type="submit" disabled={isSubmitting} className="btn-primary text-sm disabled:opacity-60">
                                {isSubmitting ? 'Saving...' : editingStore ? 'Save Changes' : 'Create Store'}
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {isLoading && (
                <div className="card border border-white/40 p-12 text-center shadow-sm">
                    <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-shelf-primary" />
                    <p className="text-sm text-shelf-foreground/60">Loading stores...</p>
                </div>
            )}

            {isError && (
                <div className="card border border-red-200 bg-red-50/50 p-12 text-center shadow-sm">
                    <AlertCircle className="mx-auto mb-3 h-8 w-8 text-red-500" />
                    <p className="text-sm text-red-600">Failed to load stores</p>
                </div>
            )}

            {!isLoading && !isError && (
                <StoreTable
                    stores={stores}
                    onView={(store) => navigate(`/stores/${store.store_id}`)}
                    onEdit={openEditForm}
                    onDelete={(store) => {
                        void handleDelete(store)
                    }}
                />
            )}
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
        <label className="block space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-shelf-foreground/55">{label}</span>
            {children}
        </label>
    )
}
