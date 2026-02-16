import type { PurchaseOrder } from '@/lib/types'

const STATUS_OPTIONS = ['all', 'suggested', 'approved', 'ordered', 'received', 'cancelled'] as const

interface PurchaseOrderTableProps {
    orders: PurchaseOrder[]
    isLoading?: boolean
    highlightedPoId?: string | null
    statusFilter: (typeof STATUS_OPTIONS)[number]
    onStatusFilterChange: (status: (typeof STATUS_OPTIONS)[number]) => void
    productNameById: Record<string, string>
    storeNameById: Record<string, string>
}

export default function PurchaseOrderTable({
    orders,
    isLoading = false,
    highlightedPoId = null,
    statusFilter,
    onStatusFilterChange,
    productNameById,
    storeNameById,
}: PurchaseOrderTableProps) {
    return (
        <div className="card border border-white/40 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-shelf-foreground/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">PO Pipeline</h3>
                <select
                    value={statusFilter}
                    onChange={(e) => onStatusFilterChange(e.target.value as (typeof STATUS_OPTIONS)[number])}
                    className="rounded-lg border border-shelf-foreground/10 bg-white px-3 py-1.5 text-sm"
                >
                    {STATUS_OPTIONS.map((status) => (
                        <option key={status} value={status}>
                            Status: {status}
                        </option>
                    ))}
                </select>
            </div>

            {isLoading ? (
                <div className="p-8 text-sm text-shelf-foreground/50">Loading purchase orders...</div>
            ) : orders.length === 0 ? (
                <div className="p-8 text-sm text-shelf-foreground/50">No purchase orders in this view.</div>
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-shelf-foreground/10 text-left text-xs uppercase tracking-wider text-shelf-foreground/50">
                                <th className="px-4 py-3">PO</th>
                                <th className="px-4 py-3">Product</th>
                                <th className="px-4 py-3">Store</th>
                                <th className="px-4 py-3 text-right">Qty</th>
                                <th className="px-4 py-3 text-right">Est Cost</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Ordered</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-shelf-foreground/5">
                            {orders.map((po) => (
                                <tr
                                    key={po.po_id}
                                    className={`hover:bg-shelf-foreground/[0.02] transition-colors ${
                                        highlightedPoId === po.po_id ? 'bg-shelf-primary/5' : ''
                                    }`}
                                >
                                    <td className="px-4 py-3 font-mono text-xs">{po.po_id.slice(0, 8)}</td>
                                    <td className="px-4 py-3">{productNameById[po.product_id] ?? po.product_id.slice(0, 8)}</td>
                                    <td className="px-4 py-3">{storeNameById[po.store_id] ?? po.store_id.slice(0, 8)}</td>
                                    <td className="px-4 py-3 text-right font-semibold">{po.quantity}</td>
                                    <td className="px-4 py-3 text-right">
                                        {po.estimated_cost != null ? `$${po.estimated_cost.toFixed(2)}` : '—'}
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="badge bg-shelf-secondary/10 text-shelf-foreground border-shelf-foreground/10">
                                            {po.status}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3">
                                        {po.ordered_at ? new Date(po.ordered_at).toLocaleDateString() : '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    )
}
