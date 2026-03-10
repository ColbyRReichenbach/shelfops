import { CheckCircle2, AlertTriangle, XCircle, ExternalLink, Pencil, Trash2 } from 'lucide-react'

import type { Store } from '@/lib/types'

interface StoreTableProps {
    stores: Store[]
    onView: (store: Store) => void
    onEdit: (store: Store) => void
    onDelete: (store: Store) => void
}

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; bg: string; label: string }> = {
    active: { icon: CheckCircle2, color: 'text-green-700', bg: 'bg-green-100', label: 'Active' },
    onboarding: { icon: AlertTriangle, color: 'text-yellow-700', bg: 'bg-yellow-100', label: 'Onboarding' },
    inactive: { icon: XCircle, color: 'text-shelf-foreground/50', bg: 'bg-shelf-foreground/10', label: 'Inactive' },
}

export default function StoreTable({ stores, onView, onEdit, onDelete }: StoreTableProps) {
    return (
        <div className="card overflow-hidden border border-white/40 p-0 shadow-sm">
            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                    <thead>
                        <tr className="border-b border-shelf-foreground/5 bg-shelf-secondary/5 text-shelf-foreground/70">
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Store Name</th>
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Location</th>
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Status</th>
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Timezone</th>
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Last Updated</th>
                            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-shelf-foreground/5">
                        {stores.map((store) => {
                            const status =
                                statusConfig[store.status] ??
                                { icon: AlertTriangle, color: 'text-gray-700', bg: 'bg-gray-100', label: store.status }
                            const StatusIcon = status.icon

                            return (
                                <tr key={store.store_id} className="group transition-colors duration-200 hover:bg-shelf-primary/5">
                                    <td className="px-6 py-4 font-medium text-shelf-foreground">
                                        <div className="flex items-center gap-3">
                                            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-shelf-foreground/10 bg-white text-xs font-bold text-shelf-primary shadow-sm">
                                                {store.store_id.slice(-3)}
                                            </div>
                                            {store.name}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-shelf-foreground/80">
                                        {[store.city, store.state].filter(Boolean).join(', ') || '—'}
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${status.bg} ${status.color}`}>
                                            <StatusIcon className="h-3 w-3" />
                                            {status.label}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-shelf-foreground/70">{store.timezone || '—'}</td>
                                    <td className="px-6 py-4 font-mono text-xs text-shelf-foreground/60">
                                        {store.updated_at ? new Date(store.updated_at).toLocaleDateString() : 'N/A'}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex items-center justify-end gap-2 opacity-0 transition-all duration-200 group-hover:opacity-100">
                                            <button
                                                onClick={() => onView(store)}
                                                className="inline-flex items-center gap-1 rounded-lg border border-shelf-foreground/10 px-2 py-1 text-xs text-shelf-foreground/70 transition-colors hover:text-shelf-primary"
                                                title="View store"
                                            >
                                                <ExternalLink className="h-3.5 w-3.5" />
                                                View
                                            </button>
                                            <button
                                                onClick={() => onEdit(store)}
                                                className="inline-flex items-center gap-1 rounded-lg border border-shelf-foreground/10 px-2 py-1 text-xs text-shelf-foreground/70 transition-colors hover:text-shelf-primary"
                                            >
                                                <Pencil className="h-3.5 w-3.5" />
                                                Edit
                                            </button>
                                            <button
                                                onClick={() => onDelete(store)}
                                                className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-2 py-1 text-xs text-red-600 transition-colors hover:bg-red-50"
                                            >
                                                <Trash2 className="h-3.5 w-3.5" />
                                                Delete
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>
            {stores.length === 0 && (
                <div className="p-8 text-center text-sm text-surface-400">
                    No stores found.
                </div>
            )}
        </div>
    )
}
