import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell, LabelList } from 'recharts'
import { ArrowUpRight, ArrowDownRight, Filter, Loader2, AlertCircle, BarChart3, CalendarRange, Layers3, Sparkles, Store as StoreIcon } from 'lucide-react'
import { useForecasts, useProducts, useStores } from '@/hooks/useShelfOps'
import ModelDriversPanel from '@/components/forecasts/ModelDriversPanel'

export default function ForecastsPage() {
    const [activeCategory, setActiveCategory] = useState('All')
    const [windowDays, setWindowDays] = useState<14 | 30 | 60>(14)

    const dateFilter = useMemo(() => {
        const start = new Date()
        const end = new Date()
        end.setDate(start.getDate() + windowDays - 1)
        const toIsoDate = (d: Date) => d.toISOString().slice(0, 10)
        return {
            start_date: toIsoDate(start),
            end_date: toIsoDate(end),
            limit: 1000,
        }
    }, [windowDays])

    const { data: forecasts = [], isLoading, isError } = useForecasts(dateFilter)
    const { data: products = [] } = useProducts()
    const { data: stores = [] } = useStores()

    // Build a product lookup
    const productMap = useMemo(() => {
        const map = new Map<string, { name: string; category: string | null }>()
        products.forEach(p => map.set(p.product_id, { name: p.name, category: p.category }))
        return map
    }, [products])

    // Aggregate forecasts by date for trend chart
    const trendData = useMemo(() => {
        const byDate = new Map<string, { demand: number; lower: number; upper: number; count: number }>()
        forecasts.forEach(f => {
            const product = productMap.get(f.product_id)
            if (activeCategory !== 'All' && product?.category !== activeCategory) return
            const dateKey = f.forecast_date
            const existing = byDate.get(dateKey) ?? { demand: 0, lower: 0, upper: 0, count: 0 }
            existing.demand += f.forecasted_demand
            existing.lower += f.lower_bound ?? f.forecasted_demand
            existing.upper += f.upper_bound ?? f.forecasted_demand
            existing.count += 1
            byDate.set(dateKey, existing)
        })
        return Array.from(byDate.entries())
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([date, totals]) => ({
                date: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                demand: Math.round(totals.demand),
                lower: Math.round(totals.lower),
                upper: Math.round(totals.upper),
                lines: totals.count,
            }))
    }, [forecasts, productMap, activeCategory])

    // Aggregate forecasts by product category for bar chart
    const categoryData = useMemo(() => {
        const byCategory = new Map<string, number>()
        forecasts.forEach(f => {
            const product = productMap.get(f.product_id)
            const cat = product?.category ?? 'Unknown'
            if (activeCategory !== 'All' && cat !== activeCategory) return
            byCategory.set(cat, (byCategory.get(cat) ?? 0) + f.forecasted_demand)
        })
        const grandTotal = Array.from(byCategory.values()).reduce((sum, value) => sum + value, 0)
        return Array.from(byCategory.entries())
            .sort(([, a], [, b]) => b - a)
            .slice(0, 8)
            .map(([name, value]) => ({
                name,
                value: Math.round(value),
                share: grandTotal > 0 ? Math.round((value / grandTotal) * 100) : 0,
            }))
    }, [forecasts, productMap, activeCategory])

    // Get unique categories from products
    const categories = useMemo(() => {
        const cats = new Set(products.map(p => p.category).filter(Boolean))
        return ['All', ...Array.from(cats) as string[]]
    }, [products])

    // Top movers by forecast demand (product-level aggregation)
    const productForecasts = useMemo(() => {
        const byProduct = new Map<string, number>()
        forecasts.forEach(f => {
            const product = productMap.get(f.product_id)
            if (activeCategory !== 'All' && product?.category !== activeCategory) return
            byProduct.set(f.product_id, (byProduct.get(f.product_id) ?? 0) + f.forecasted_demand)
        })
        return Array.from(byProduct.entries())
            .map(([productId, total]) => ({
                productId,
                name: productMap.get(productId)?.name ?? productId.slice(0, 8),
                total: Math.round(total),
            }))
            .sort((a, b) => b.total - a.total)
    }, [forecasts, productMap, activeCategory])

    const topMovers = productForecasts.slice(0, 3)
    const bottomMovers = productForecasts.slice(-3).reverse()

    // Latest forecast record per product — used to supply forecastId to the model-driver panel
    const latestForecastByProduct = useMemo(() => {
        const map = new Map<string, { id: string; demand: number; date: string }>()
        forecasts.forEach(f => {
            const product = productMap.get(f.product_id)
            if (activeCategory !== 'All' && product?.category !== activeCategory) return
            const existing = map.get(f.product_id)
            if (!existing || f.forecast_date > existing.date) {
                map.set(f.product_id, { id: f.forecast_id, demand: f.forecasted_demand, date: f.forecast_date })
            }
        })
        return map
    }, [forecasts, productMap, activeCategory])

    const summary = useMemo(() => {
        const visibleForecasts = forecasts.filter(f => {
            const category = productMap.get(f.product_id)?.category ?? 'Unknown'
            return activeCategory === 'All' || category === activeCategory
        })
        const totalDemand = visibleForecasts.reduce((sum, forecast) => sum + forecast.forecasted_demand, 0)
        const totalLower = visibleForecasts.reduce((sum, forecast) => sum + (forecast.lower_bound ?? forecast.forecasted_demand), 0)
        const totalUpper = visibleForecasts.reduce((sum, forecast) => sum + (forecast.upper_bound ?? forecast.forecasted_demand), 0)
        const productCount = new Set(visibleForecasts.map(f => f.product_id)).size
        const storeCount = new Set(visibleForecasts.map(f => f.store_id)).size
        const avgConfidence = visibleForecasts.length > 0
            ? visibleForecasts.reduce((sum, forecast) => sum + (forecast.confidence ?? 0), 0) / visibleForecasts.length
            : 0

        return {
            totalDemand: Math.round(totalDemand),
            averageDailyDemand: trendData.length > 0 ? Math.round(totalDemand / trendData.length) : 0,
            totalLower: Math.round(totalLower),
            totalUpper: Math.round(totalUpper),
            productCount,
            storeCount,
            avgConfidence,
            visibleForecasts: visibleForecasts.length,
            visibleDays: new Set(visibleForecasts.map(f => f.forecast_date)).size,
        }
    }, [forecasts, productMap, activeCategory, trendData])

    return (
        <div className="page-shell animate-fade-in">
            <div className="hero-panel hero-panel-blue">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                    <div className="max-w-3xl">
                        <div className="hero-chip text-[#0071e3]">
                            <BarChart3 className="h-3.5 w-3.5" />
                            Forecasts
                        </div>
                        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">Review demand patterns before placing orders.</h1>
                        <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                        Explore forward demand by date, category, store, and product before you commit inventory.
                        {summary.visibleForecasts > 0 && ` · ${summary.visibleForecasts} forecast rows across ${summary.visibleDays} forecast days`}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setWindowDays(14)}
                            className={`text-xs px-3 h-8 gap-2 ${windowDays === 14 ? 'btn-primary' : 'btn-secondary'}`}
                        >
                            <Filter className="h-3 w-3" />
                            Next 14 Days
                        </button>
                        <button
                            onClick={() => setWindowDays(30)}
                            className={`text-xs px-3 h-8 ${windowDays === 30 ? 'btn-primary' : 'btn-secondary'}`}
                        >
                            Next 30 Days
                        </button>
                        <button
                            onClick={() => setWindowDays(60)}
                            className={`text-xs px-3 h-8 ${windowDays === 60 ? 'btn-primary' : 'btn-secondary'}`}
                        >
                            Next 60 Days
                        </button>
                    </div>
                </div>
            </div>

            {!isLoading && !isError && (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <div className="hero-stat-card">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                            <CalendarRange className="h-5 w-5 text-[#1d1d1f]" />
                        </div>
                        <p className="mt-4 text-sm font-medium text-[#86868b]">Forecast horizon</p>
                        <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f]">{summary.totalDemand.toLocaleString()}</p>
                        <p className="mt-2 text-xs text-[#6e6e73]">{summary.totalLower.toLocaleString()} to {summary.totalUpper.toLocaleString()} units across {summary.visibleDays} forecast days</p>
                    </div>
                    <div className="hero-stat-card">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                            <Sparkles className="h-5 w-5 text-[#1d1d1f]" />
                        </div>
                        <p className="mt-4 text-sm font-medium text-[#86868b]">Average day</p>
                        <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f]">{summary.averageDailyDemand.toLocaleString()}</p>
                        <p className="mt-2 text-xs text-[#6e6e73]">Expected units per covered day in the current horizon</p>
                    </div>
                    <div className="hero-stat-card">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                            <Layers3 className="h-5 w-5 text-[#1d1d1f]" />
                        </div>
                        <p className="mt-4 text-sm font-medium text-[#86868b]">Covered products</p>
                        <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f]">{summary.productCount}</p>
                        <p className="mt-2 text-xs text-[#6e6e73]">{categories.length - 1} categories in current view</p>
                    </div>
                    <div className="hero-stat-card">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                            <StoreIcon className="h-5 w-5 text-[#1d1d1f]" />
                        </div>
                        <p className="mt-4 text-sm font-medium text-[#86868b]">Store coverage</p>
                        <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f]">{summary.storeCount}</p>
                        <p className="mt-2 text-xs text-[#6e6e73]">{Math.round(summary.avgConfidence * 100)}% average confidence across {stores.length || summary.storeCount} stores</p>
                    </div>
                </div>
            )}

            {!isLoading && !isError && summary.visibleDays < windowDays && (
                <div className="surface-muted border border-[#0071e3]/10 bg-[#0071e3]/[0.04] px-4 py-3 text-sm text-[#275ea3]">
                    Showing {summary.visibleDays} forecast days from the current model run. Extend the generated forecast horizon to fill the full next {windowDays} day view.
                </div>
            )}

            {/* Category Filter */}
            <div className="flex flex-wrap gap-2">
                {categories.map((cat) => (
                    <button
                        key={cat}
                        onClick={() => setActiveCategory(cat)}
                        className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${activeCategory === cat
                            ? 'bg-[#0071e3] text-white shadow-md shadow-[0_2px_10px_rgba(0,113,227,0.2)]'
                            : 'bg-white text-[#86868b] hover:text-[#0071e3] hover:bg-white/80 border border-transparent hover:border-black/5'
                            }`}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Loading state */}
            {isLoading && (
                <div className="card p-12 text-center border border-black/[0.02] shadow-sm">
                    <Loader2 className="h-8 w-8 mx-auto mb-3 text-[#0071e3] animate-spin" />
                    <p className="text-sm text-[#86868b]">Loading forecasts…</p>
                </div>
            )}

            {/* Error state */}
            {isError && (
                <div className="card p-12 text-center bg-[#ff3b30]/5">
                    <AlertCircle className="h-8 w-8 mx-auto mb-3 text-[#ff3b30]" />
                    <p className="text-sm text-[#ff3b30]">Failed to load forecasts.</p>
                </div>
            )}

            {!isLoading && !isError && (
                <>
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Main Trend Chart */}
                        <motion.div
                            className="lg:col-span-2 card border border-black/[0.02] shadow-sm"
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4, ease: 'easeOut' }}
                        >
                            <h3 className="text-sm font-semibold text-[#0071e3] uppercase tracking-wider mb-6">Total Demand Trend</h3>
                            <div className="h-[300px]">
                                {trendData.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                            <defs>
                                                <linearGradient id="colorDemand" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#0071e3" stopOpacity={0.2} />
                                                    <stop offset="95%" stopColor="#0071e3" stopOpacity={0} />
                                                </linearGradient>
                                                <linearGradient id="colorRange" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#34c759" stopOpacity={0.16} />
                                                    <stop offset="95%" stopColor="#34c759" stopOpacity={0.02} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e5ea" strokeOpacity={0.05} vertical={false} />
                                            <XAxis dataKey="date" tick={{ fill: '#86868b', fontSize: 11, opacity: 0.6 }} axisLine={false} tickLine={false} dy={10} />
                                            <YAxis tick={{ fill: '#86868b', fontSize: 11, opacity: 0.6 }} axisLine={false} tickLine={false} />
                                            <Tooltip
                                                contentStyle={{
                                                    backgroundColor: 'rgba(29,29,31,0.8)',
                                                    backdropFilter: 'blur(12px)',
                                                    border: '1px solid rgba(255,255,255,0.1)',
                                                    borderRadius: '16px',
                                                    boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                                                    fontSize: '12px',
                                                    color: '#ffffff'
                                                }}
                                            />
                                            <Area
                                                type="monotone"
                                                dataKey="upper"
                                                stroke="#34c759"
                                                strokeOpacity={0.28}
                                                strokeWidth={1.5}
                                                fill="url(#colorRange)"
                                                name="Upper range"
                                            />
                                            <Area
                                                type="monotone"
                                                dataKey="lower"
                                                stroke="#34c759"
                                                strokeOpacity={0.18}
                                                strokeWidth={1}
                                                fill="#f8f8fb"
                                                name="Lower range"
                                            />
                                            <Area
                                                type="monotone"
                                                dataKey="demand"
                                                stroke="#0071e3"
                                                strokeWidth={3}
                                                fill="url(#colorDemand)"
                                                name="Demand"
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-[#86868b] text-sm">
                                        No forecast data available
                                    </div>
                                )}
                            </div>
                        </motion.div>

                        {/* Category Distribution */}
                        <motion.div
                            className="card border border-black/[0.02] shadow-sm"
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4, ease: 'easeOut', delay: 0.08 }}
                        >
                            <h3 className="text-sm font-semibold text-[#0071e3] uppercase tracking-wider mb-6">Forecast by Category</h3>
                            <div className="h-[300px]">
                                {categoryData.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={categoryData} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 20 }}>
                                            <XAxis type="number" hide />
                                            <YAxis dataKey="name" type="category" width={80} tick={{ fill: '#86868b', fontSize: 11 }} axisLine={false} tickLine={false} />
                                            <Tooltip
                                                cursor={{ fill: 'rgba(0,0,0,0.02)' }}
                                                contentStyle={{
                                                    backgroundColor: 'rgba(29,29,31,0.8)',
                                                    backdropFilter: 'blur(12px)',
                                                    border: '1px solid rgba(255,255,255,0.1)',
                                                    borderRadius: '16px',
                                                    boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                                                    fontSize: '12px',
                                                    color: '#ffffff'
                                                }}
                                                formatter={(value: number, _name, payload) => [`${value.toLocaleString()} units (${payload?.payload?.share ?? 0}%)`, 'Forecast']}
                                            />
                                            <Bar dataKey="value" barSize={24} radius={[0, 6, 6, 0]}>
                                                {categoryData.map((_, index) => (
                                                    <Cell key={`cell-${index}`} fill={index % 2 === 0 ? '#0071e3' : '#34c759'} />
                                                ))}
                                                <LabelList
                                                    dataKey="value"
                                                    position="right"
                                                    formatter={(value: number) => value.toLocaleString()}
                                                    style={{ fill: '#6e6e73', fontSize: 11, fontWeight: 600 }}
                                                />
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-[#86868b] text-sm">
                                        No category data
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </div>

                    {/* Movers and Shakers */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <motion.div
                            className="card p-0 overflow-hidden border border-black/[0.02] shadow-sm"
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4, ease: 'easeOut', delay: 0.12 }}
                        >
                            <div className="p-4 border-b border-black/5 bg-[#f5f5f7]">
                                <h3 className="text-sm font-semibold text-[#1d1d1f] flex items-center gap-2">
                                    <ArrowUpRight className="h-4 w-4 text-[#34c759]" />
                                    Top Demand Products
                                </h3>
                            </div>
                            <div className="divide-y divide-black/5">
                                {topMovers.length > 0 ? topMovers.map((item, i) => {
                                    const forecast = latestForecastByProduct.get(item.productId)
                                    return (
                                        <div key={i} className="hover:bg-[#0071e3]/5 transition-colors">
                                            <div className="p-4 flex items-center justify-between">
                                                <div>
                                                    <p className="text-sm font-medium text-[#1d1d1f]">{item.name}</p>
                                                    <p className="text-xs text-[#86868b]">{item.total.toLocaleString()} units forecast</p>
                                                </div>
                                                <span className="badge bg-[#34c759]/10 text-[#34c759]">#{i + 1}</span>
                                            </div>
                                            {forecast && (
                                                <div className="px-4 pb-3">
                                                    <ModelDriversPanel forecastId={forecast.id} predictedValue={forecast.demand} />
                                                </div>
                                            )}
                                        </div>
                                    )
                                }) : (
                                    <div className="p-8 text-center text-[#86868b] text-sm">No forecast data</div>
                                )}
                            </div>
                        </motion.div>

                        <motion.div
                            className="card p-0 overflow-hidden border border-black/[0.02] shadow-sm"
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4, ease: 'easeOut', delay: 0.16 }}
                        >
                            <div className="p-4 border-b border-black/5 bg-[#f5f5f7]">
                                <h3 className="text-sm font-semibold text-[#1d1d1f] flex items-center gap-2">
                                    <ArrowDownRight className="h-4 w-4 text-[#ff3b30]" />
                                    Lowest Demand Products
                                </h3>
                            </div>
                            <div className="divide-y divide-black/5">
                                {bottomMovers.length > 0 ? bottomMovers.map((item, i) => (
                                    <div key={i} className="p-4 flex items-center justify-between hover:bg-[#0071e3]/5 transition-colors">
                                        <div>
                                            <p className="text-sm font-medium text-[#1d1d1f]">{item.name}</p>
                                            <p className="text-xs text-[#86868b]">{item.total.toLocaleString()} units forecast</p>
                                        </div>
                                        <span className="badge bg-[#ff3b30]/10 text-[#ff3b30]">Low</span>
                                    </div>
                                )) : (
                                    <div className="p-8 text-center text-[#86868b] text-sm">No forecast data</div>
                                )}
                            </div>
                        </motion.div>
                    </div>
                </>
            )}
        </div>
    )
}
