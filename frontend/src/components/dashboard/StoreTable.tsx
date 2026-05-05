import { CheckCircle2, AlertTriangle, XCircle, ExternalLink, Pencil, Trash2 } from 'lucide-react'

import type { Store } from '@/lib/types'

interface StoreTableProps {
    stores: Store[]
    onView: (store: Store) => void
    onEdit: (store: Store) => void
    onDelete: (store: Store) => void
}

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; bg: string; label: string }> = {
    active: { icon: CheckCircle2, color: 'text-[#34c759]', bg: 'bg-[#34c759]/10', label: 'Active' },
    onboarding: { icon: AlertTriangle, color: 'text-[#b38f00]', bg: 'bg-[#ffcc00]/10', label: 'Onboarding' },
    inactive: { icon: XCircle, color: 'text-[#86868b]', bg: 'bg-[#86868b]/10', label: 'Inactive' },
}

export default function StoreTable({ stores, onView, onEdit, onDelete }: StoreTableProps) {
    return (
        <div className="card overflow-hidden p-0">
            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                    <thead>
                        <tr className="border-b border-black/5 text-[#86868b]">
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Store Name</th>
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Location</th>
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Status</th>
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Timezone</th>
                            <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider">Last Updated</th>
                            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-black/5">
                        {stores.map((store) => {
                            const status =
                                statusConfig[store.status] ??
                                { icon: AlertTriangle, color: 'text-[#86868b]', bg: 'bg-[#86868b]/10', label: store.status }
                            const StatusIcon = status.icon

                            return (
                                <tr key={store.store_id} className="group transition-colors duration-200 hover:bg-[#0071e3]/5">
                                    <td className="px-6 py-4 font-medium text-[#1d1d1f]">
                                        <div className="flex items-center gap-3">
                                            <div className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-black/5 bg-white text-xs font-bold text-[#0071e3]">
                                                {store.store_id.slice(-3)}
                                            </div>
                                            {store.name}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-[#86868b]">
                                        {[store.city, store.state].filter(Boolean).join(', ') || '—'}
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${status.bg} ${status.color}`}>
                                            <StatusIcon className="h-3 w-3" />
                                            {status.label}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-[#86868b]">{store.timezone || '—'}</td>
                                    <td className="px-6 py-4 font-mono text-xs text-[#86868b]">
                                        {store.updated_at ? new Date(store.updated_at).toLocaleDateString() : 'N/A'}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex items-center justify-end gap-2 opacity-0 transition-all duration-200 group-hover:opacity-100">
                                            <button
                                                onClick={() => onView(store)}
                                                className="inline-flex items-center gap-1 rounded-[8px] border border-black/5 px-2 py-1 text-xs text-[#86868b] transition-colors hover:text-[#0071e3]"
                                                title="View store"
                                            >
                                                <ExternalLink className="h-3.5 w-3.5" />
                                                View
                                            </button>
                                            <button
                                                onClick={() => onEdit(store)}
                                                className="inline-flex items-center gap-1 rounded-[8px] border border-black/5 px-2 py-1 text-xs text-[#86868b] transition-colors hover:text-[#0071e3]"
                                            >
                                                <Pencil className="h-3.5 w-3.5" />
                                                Edit
                                            </button>
                                            <button
                                                onClick={() => onDelete(store)}
                                                className="inline-flex items-center gap-1 rounded-[8px] border border-[#ff3b30]/20 px-2 py-1 text-xs text-[#ff3b30] transition-colors hover:bg-[#ff3b30]/5"
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
