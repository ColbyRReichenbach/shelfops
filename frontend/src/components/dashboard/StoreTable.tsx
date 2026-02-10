import type { Store } from '@/lib/types'
import { MoreHorizontal, ExternalLink, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react'

interface StoreTableProps {
    stores: Store[]
}

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; bg: string; label: string }> = {
    active: { icon: CheckCircle2, color: 'text-green-700', bg: 'bg-green-100', label: 'Active' },
    onboarding: { icon: AlertTriangle, color: 'text-yellow-700', bg: 'bg-yellow-100', label: 'Onboarding' },
    inactive: { icon: XCircle, color: 'text-shelf-foreground/50', bg: 'bg-shelf-foreground/10', label: 'Inactive' },
}

export default function StoreTable({ stores }: StoreTableProps) {
    return (
        <div className="card overflow-hidden p-0 border border-white/40 shadow-sm">
            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                    <thead>
                        <tr className="border-b border-shelf-foreground/5 bg-shelf-secondary/5 text-shelf-foreground/70">
                            <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs">Store Name</th>
                            <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs">Location</th>
                            <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs">Status</th>
                            <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs">Health Score</th>
                            <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs">Last Sync</th>
                            <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-shelf-foreground/5">
                        {stores.map((store) => {
                            const status = statusConfig[store.status] ?? { icon: AlertTriangle, color: 'text-gray-700', bg: 'bg-gray-100', label: store.status }
                            const StatusIcon = status.icon

                            // Health Score Color Logic
                            const healthColor = (store.health_score ?? 0) >= 90 ? 'text-green-600'
                                : (store.health_score ?? 0) >= 70 ? 'text-yellow-600'
                                    : 'text-red-600'

                            const healthBg = (store.health_score ?? 0) >= 90 ? 'bg-green-600'
                                : (store.health_score ?? 0) >= 70 ? 'bg-yellow-600'
                                    : 'bg-red-600'

                            return (
                                <tr key={store.store_id} className="group hover:bg-shelf-primary/5 transition-colors duration-200">
                                    <td className="px-6 py-4 font-medium text-shelf-foreground">
                                        <div className="flex items-center gap-3">
                                            <div className="h-8 w-8 rounded-lg bg-white border border-shelf-foreground/10 flex items-center justify-center text-xs font-bold text-shelf-primary shadow-sm">
                                                {store.store_id.slice(-3)}
                                            </div>
                                            {store.name}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-shelf-foreground/80">
                                        {[store.city, store.state].filter(Boolean).join(', ') || '—'}
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${status.bg} ${status.color} border border-transparent`}>
                                            <StatusIcon className="h-3 w-3" />
                                            {status.label}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-3">
                                            <div className="flex-1 h-1.5 w-16 bg-shelf-foreground/10 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full rounded-full ${healthBg}`}
                                                    style={{ width: `${store.health_score}%` }}
                                                />
                                            </div>
                                            <span className={`text-xs font-bold ${healthColor}`}>{store.health_score}%</span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-shelf-foreground/60 font-mono text-xs">
                                        {store.last_sync ?? (store.updated_at ? new Date(store.updated_at).toLocaleDateString() : 'N/A')}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-all duration-200 transform translate-x-2 group-hover:translate-x-0">
                                            <a
                                                href={`/stores`}
                                                className="p-1.5 rounded-md hover:bg-white hover:shadow-sm text-shelf-foreground/50 hover:text-shelf-primary transition-all border border-transparent hover:border-shelf-foreground/5"
                                                title="View Store"
                                            >
                                                <ExternalLink className="h-4 w-4" />
                                            </a>
                                            <button className="p-1.5 rounded-md hover:bg-white hover:shadow-sm text-shelf-foreground/50 hover:text-shelf-primary transition-all border border-transparent hover:border-shelf-foreground/5">
                                                <MoreHorizontal className="h-4 w-4" />
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
                <div className="p-8 text-center text-surface-400 text-sm">
                    No stores found.
                </div>
            )}
        </div>
    )
}
