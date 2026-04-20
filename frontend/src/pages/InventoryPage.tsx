/**
 * Inventory Page — Stock levels overview with status filtering.
 * Agent: full-stack-engineer | Skill: react-dashboard
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
    Package, Loader2, AlertCircle, ArrowRight,
    AlertTriangle, XCircle, CheckCircle2, Archive, Warehouse,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { useInventory, useInventorySummary, useStores } from '@/hooks/useShelfOps'

const STATUS_TABS = [
    { key: '', label: 'All' },
    { key: 'ok', label: 'In Stock' },
    { key: 'low', label: 'Low Stock' },
    { key: 'critical', label: 'Critical' },
    { key: 'out_of_stock', label: 'Out of Stock' },
] as const

const STATUS_BADGE: Record<string, { bg: string; text: string; icon: typeof CheckCircle2 }> = {
    ok: { bg: 'bg-[#34c759]/10', text: 'text-[#34c759]', icon: CheckCircle2 },
    low: { bg: 'bg-[#ff9500]/10', text: 'text-[#ff9500]', icon: AlertTriangle },
    critical: { bg: 'bg-[#ff3b30]/10', text: 'text-[#ff3b30]', icon: AlertCircle },
    out_of_stock: { bg: 'bg-[#86868b]/10', text: 'text-[#86868b]', icon: XCircle },
}

export default function InventoryPage() {
    const [statusFilter, setStatusFilter] = useState('')
    const [storeFilter, setStoreFilter] = useState('')
    const [categoryFilter, setCategoryFilter] = useState('')

    const { data: summary } = useInventorySummary(storeFilter || undefined)
    const { data: items = [], isLoading, isError } = useInventory({
        store_id: storeFilter || undefined,
        status: statusFilter || undefined,
        category: categoryFilter || undefined,
    })
    const { data: stores = [] } = useStores()

    // Derive unique categories from items
    const categories = [...new Set(items.map((i) => i.category).filter(Boolean))] as string[]

    return (
        <div className="page-shell animate-fade-in">
            <div className="hero-panel hero-panel-neutral">
                <div className="max-w-3xl">
                    <div className="hero-chip text-[#1d1d1f]">
                        <Warehouse className="h-3.5 w-3.5" />
                        Inventory
                    </div>
                    <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">See current stock exposure across stores and products.</h1>
                    <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                    {summary
                        ? `${summary.total_items} items tracked · ${summary.low_stock + summary.critical + summary.out_of_stock} need attention`
                        : 'Loading inventory status…'}
                    </p>
                </div>
            </div>

            {/* Summary KPI Cards */}
            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <SummaryCard label="In Stock" value={summary.in_stock} icon={CheckCircle2} color="text-[#34c759]" bg="bg-[#34c759]/10" />
                    <SummaryCard label="Low Stock" value={summary.low_stock} icon={AlertTriangle} color="text-[#ff9500]" bg="bg-[#ff9500]/10" />
                    <SummaryCard label="Critical" value={summary.critical} icon={AlertCircle} color="text-[#ff3b30]" bg="bg-[#ff3b30]/10" />
                    <SummaryCard label="Out of Stock" value={summary.out_of_stock} icon={XCircle} color="text-[#86868b]" bg="bg-[#86868b]/10" />
                </div>
            )}

            {/* Filters Row */}
            <div className="flex flex-wrap items-center gap-3">
                {/* Status tabs */}
                <div className="flex gap-1 rounded-lg bg-black/5 p-1">
                    {STATUS_TABS.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => setStatusFilter(tab.key)}
                            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-all ${
                                statusFilter === tab.key
                                    ? 'bg-white text-[#0071e3] shadow-sm'
                                    : 'text-[#86868b] hover:text-[#0071e3]'
                            }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Store filter */}
                <select
                    value={storeFilter}
                    onChange={(e) => setStoreFilter(e.target.value)}
                    className="rounded-lg border border-black/5 bg-white px-3 py-1.5 text-sm text-[#1d1d1f]"
                >
                    <option value="">All Stores</option>
                    {stores.map((s) => (
                        <option key={s.store_id} value={s.store_id}>{s.name}</option>
                    ))}
                </select>

                {/* Category filter */}
                {categories.length > 0 && (
                    <select
                        value={categoryFilter}
                        onChange={(e) => setCategoryFilter(e.target.value)}
                        className="rounded-lg border border-black/5 bg-white px-3 py-1.5 text-sm text-[#1d1d1f]"
                    >
                        <option value="">All Categories</option>
                        {categories.map((c) => (
                            <option key={c} value={c}>{c}</option>
                        ))}
                    </select>
                )}
            </div>

            {/* Loading */}
            {isLoading && (
                <div className="card text-center py-16 border border-black/[0.02] shadow-sm">
                    <Loader2 className="h-8 w-8 mx-auto mb-3 text-[#0071e3] animate-spin" />
                    <p className="text-sm text-[#86868b]">Loading inventory…</p>
                </div>
            )}

            {/* Error */}
            {isError && (
                <div className="card text-center py-16 bg-[#ff3b30]/5">
                    <AlertCircle className="h-8 w-8 mx-auto mb-3 text-[#ff3b30]" />
                    <p className="text-sm text-[#ff3b30]">Failed to load inventory.</p>
                </div>
            )}

            {/* Inventory Table */}
            {!isLoading && !isError && (
                <>
                    {items.length === 0 ? (
                        <div className="card text-center text-[#86868b] py-16 border border-black/[0.02] shadow-sm">
                            <Archive className="h-8 w-8 mx-auto mb-3" />
                            <p>No inventory items match your filters</p>
                        </div>
                    ) : (
                        <div className="card border border-black/[0.02] shadow-sm overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-black/5 text-left text-xs font-semibold uppercase tracking-wider text-[#86868b]">
                                            <th className="px-4 py-3">Product</th>
                                            <th className="px-4 py-3">Store</th>
                                            <th className="px-4 py-3 text-right">On Hand</th>
                                            <th className="px-4 py-3 text-right">Reorder Pt</th>
                                            <th className="px-4 py-3">Status</th>
                                            <th className="px-4 py-3"></th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-black/5">
                                        {items.map((item) => {
                                            const badge = STATUS_BADGE[item.status] ?? { bg: 'bg-[#34c759]/10', text: 'text-[#34c759]', icon: CheckCircle2 }
                                            const BadgeIcon = badge.icon
                                            const pct = item.reorder_point
                                                ? Math.min(100, Math.round((item.quantity_on_hand / item.reorder_point) * 100))
                                                : 100

                                            return (
                                                <tr key={`${item.store_id}-${item.product_id}`} className="hover:bg-[#0071e3]/5 transition-colors">
                                                    <td className="px-4 py-3">
                                                        <div className="flex items-center gap-3">
                                                            <div className="h-8 w-8 rounded-lg bg-[#0071e3]/10 flex items-center justify-center">
                                                                <Package className="h-4 w-4 text-[#0071e3]" />
                                                            </div>
                                                            <div>
                                                                <p className="font-medium text-[#1d1d1f]">{item.product_name}</p>
                                                                <p className="text-xs text-[#86868b]">{item.sku} · {item.category}</p>
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3 text-[#86868b]">{item.store_name}</td>
                                                    <td className="px-4 py-3 text-right">
                                                        <div className="flex flex-col items-end gap-1">
                                                            <span className="font-mono font-semibold">{item.quantity_on_hand}</span>
                                                            {item.reorder_point && (
                                                                <div className="w-16 h-1.5 rounded-full bg-black/5 overflow-hidden">
                                                                    <div
                                                                        className={`h-full rounded-full transition-all ${
                                                                            pct > 100 ? 'bg-[#34c759]' :
                                                                            pct > 50 ? 'bg-[#34c759]' :
                                                                            pct > 25 ? 'bg-[#ff9500]' :
                                                                            'bg-[#ff3b30]'
                                                                        }`}
                                                                        style={{ width: `${Math.min(pct, 100)}%` }}
                                                                    />
                                                                </div>
                                                            )}
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3 text-right font-mono text-[#86868b]">
                                                        {item.reorder_point ?? '—'}
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.bg} ${badge.text}`}>
                                                            <BadgeIcon className="h-3 w-3" />
                                                            {item.status.replace('_', ' ')}
                                                        </span>
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <Link
                                                            to={`/products/${item.product_id}`}
                                                            className="text-[#0071e3]/60 hover:text-[#0071e3] transition-colors"
                                                        >
                                                            <ArrowRight className="h-4 w-4" />
                                                        </Link>
                                                    </td>
                                                </tr>
                                            )
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    )
}

function SummaryCard({
    label, value, icon: Icon, color, bg,
}: {
    label: string
    value: number
    icon: typeof CheckCircle2
    color: string
    bg: string
}) {
    return (
        <motion.div whileHover={{ y: -2 }} className={`card border border-black/[0.02] shadow-sm p-4 ${bg}/30`}>
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-xs font-medium text-[#86868b] uppercase tracking-wider">{label}</p>
                    <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
                </div>
                <div className={`h-10 w-10 rounded-xl ${bg} flex items-center justify-center`}>
                    <Icon className={`h-5 w-5 ${color}`} />
                </div>
            </div>
        </motion.div>
    )
}
