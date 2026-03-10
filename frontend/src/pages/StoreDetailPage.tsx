import { ArrowLeft, AlertCircle, Loader2, MapPin, Package } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAlertSummary, useInventory, useInventorySummary, useStore } from '@/hooks/useShelfOps'

export default function StoreDetailPage() {
    const { storeId } = useParams()
    const navigate = useNavigate()
    const { data: store, isLoading, isError } = useStore(storeId)
    const { data: summary } = useInventorySummary(storeId)
    const { data: items = [] } = useInventory({ store_id: storeId })
    const { data: alertSummary } = useAlertSummary(storeId)

    if (isLoading) {
        return (
            <div className="p-6 lg:p-8 flex min-h-[400px] items-center justify-center">
                <div className="text-center">
                    <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-shelf-primary" />
                    <p className="text-sm text-shelf-foreground/60">Loading store details...</p>
                </div>
            </div>
        )
    }

    if (isError || !store) {
        return (
            <div className="p-6 lg:p-8">
                <div className="card border border-red-200 bg-red-50/50 p-12 text-center shadow-sm">
                    <AlertCircle className="mx-auto mb-3 h-8 w-8 text-red-500" />
                    <p className="text-sm text-red-600">Store not found</p>
                    <button onClick={() => navigate(-1)} className="btn-secondary mt-4 text-sm">Go Back</button>
                </div>
            </div>
        )
    }

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex items-center gap-4">
                <button
                    onClick={() => navigate(-1)}
                    className="rounded-lg p-2 text-shelf-foreground/60 transition-colors hover:bg-shelf-secondary/10 hover:text-shelf-foreground"
                >
                    <ArrowLeft className="h-5 w-5" />
                </button>
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">{store.name}</h1>
                    <p className="mt-1 text-sm text-shelf-foreground/60">
                        {[store.city, store.state].filter(Boolean).join(', ') || 'Location unavailable'} · {store.timezone}
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                <StatCard label="Tracked Items" value={summary?.total_items ?? items.length} detail="Inventory positions at this location" icon={Package} />
                <StatCard label="Open Alerts" value={alertSummary?.open ?? 0} detail={`${alertSummary?.critical ?? 0} critical alerts`} icon={AlertCircle} />
                <StatCard label="Address" value={store.address ?? '—'} detail={store.zip_code ?? 'No ZIP code on file'} icon={MapPin} />
            </div>

            <div className="card border border-white/40 shadow-sm">
                <h2 className="text-lg font-semibold text-shelf-primary">Store Details</h2>
                <div className="mt-4 grid grid-cols-1 gap-4 text-sm md:grid-cols-2 lg:grid-cols-4">
                    <Detail label="Name" value={store.name} />
                    <Detail label="Status" value={store.status} />
                    <Detail label="Timezone" value={store.timezone} />
                    <Detail label="Address" value={store.address ?? '—'} />
                    <Detail label="City" value={store.city ?? '—'} />
                    <Detail label="State" value={store.state ?? '—'} />
                    <Detail label="ZIP Code" value={store.zip_code ?? '—'} />
                    <Detail label="Updated" value={new Date(store.updated_at).toLocaleString()} />
                </div>
            </div>

            <div className="card border border-white/40 shadow-sm">
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-shelf-primary">Inventory Snapshot</h2>
                    <Link to="/inventory" className="text-sm text-shelf-primary/70 transition-colors hover:text-shelf-primary">
                        Open Inventory Workspace
                    </Link>
                </div>
                <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-left text-sm">
                        <thead>
                            <tr className="border-b border-shelf-foreground/5 text-xs font-semibold uppercase tracking-wider text-shelf-foreground/55">
                                <th className="px-4 py-3">Product</th>
                                <th className="px-4 py-3">SKU</th>
                                <th className="px-4 py-3 text-right">On Hand</th>
                                <th className="px-4 py-3 text-right">Reorder Point</th>
                                <th className="px-4 py-3">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-shelf-foreground/5">
                            {items.slice(0, 12).map((item) => (
                                <tr key={`${item.store_id}-${item.product_id}`}>
                                    <td className="px-4 py-3 font-medium text-shelf-foreground">{item.product_name}</td>
                                    <td className="px-4 py-3 font-mono text-xs text-shelf-foreground/60">{item.sku}</td>
                                    <td className="px-4 py-3 text-right font-mono">{item.quantity_on_hand}</td>
                                    <td className="px-4 py-3 text-right font-mono text-shelf-foreground/60">{item.reorder_point ?? '—'}</td>
                                    <td className="px-4 py-3 text-shelf-foreground/70">{item.status.replace('_', ' ')}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {items.length === 0 && (
                        <div className="p-8 text-center text-sm text-shelf-foreground/40">No inventory records for this store yet.</div>
                    )}
                </div>
            </div>
        </div>
    )
}

function StatCard({
    label,
    value,
    detail,
    icon: Icon,
}: {
    label: string
    value: string | number
    detail: string
    icon: typeof Package
}) {
    return (
        <div className="card border border-white/40 shadow-sm">
            <div className="mb-2 flex items-center gap-2">
                <Icon className="h-4 w-4 text-shelf-primary" />
                <p className="text-xs font-medium uppercase tracking-wider text-shelf-foreground/50">{label}</p>
            </div>
            <p className="text-xl font-semibold text-shelf-foreground">{value}</p>
            <p className="mt-1 text-xs text-shelf-foreground/55">{detail}</p>
        </div>
    )
}

function Detail({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <p className="mb-1 text-shelf-foreground/60">{label}</p>
            <p className="font-medium text-shelf-foreground">{value}</p>
        </div>
    )
}
