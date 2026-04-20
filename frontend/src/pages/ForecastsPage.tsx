import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts'
import { ArrowUpRight, ArrowDownRight, Filter, Loader2, AlertCircle, BarChart3 } from 'lucide-react'
import { useForecasts, useProducts } from '@/hooks/useShelfOps'
import SHAPWaterfall from '@/components/forecasts/SHAPWaterfall'

export default function ForecastsPage() {
    const [activeCategory, setActiveCategory] = useState('All')
    const [windowDays, setWindowDays] = useState<7 | 30>(7)

    const dateFilter = useMemo(() => {
        const end = new Date()
        const start = new Date()
        start.setDate(end.getDate() - windowDays + 1)
        const toIsoDate = (d: Date) => d.toISOString().slice(0, 10)
        return {
            start_date: toIsoDate(start),
            end_date: toIsoDate(end),
        }
    }, [windowDays])

    const { data: forecasts = [], isLoading, isError } = useForecasts(dateFilter)
    const { data: products = [] } = useProducts()

    // Build a product lookup
    const productMap = useMemo(() => {
        const map = new Map<string, { name: string; category: string | null }>()
        products.forEach(p => map.set(p.product_id, { name: p.name, category: p.category }))
        return map
    }, [products])

    // Aggregate forecasts by date for trend chart
    const trendData = useMemo(() => {
        const byDate = new Map<string, number>()
        forecasts.forEach(f => {
            const product = productMap.get(f.product_id)
            if (activeCategory !== 'All' && product?.category !== activeCategory) return
            const dateKey = f.forecast_date
            byDate.set(dateKey, (byDate.get(dateKey) ?? 0) + f.forecasted_demand)
        })
        return Array.from(byDate.entries())
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([date, demand]) => ({
                date: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                demand: Math.round(demand),
            }))
    }, [forecasts, productMap, activeCategory])

    // Aggregate forecasts by product category for bar chart
    const categoryData = useMemo(() => {
        const byCategory = new Map<string, number>()
        forecasts.forEach(f => {
            const product = productMap.get(f.product_id)
            const cat = product?.category ?? 'Unknown'
            byCategory.set(cat, (byCategory.get(cat) ?? 0) + f.forecasted_demand)
        })
        return Array.from(byCategory.entries())
            .sort(([, a], [, b]) => b - a)
            .slice(0, 8)
            .map(([name, value]) => ({ name, value: Math.round(value) }))
    }, [forecasts, productMap])

    // Get unique categories from products
    const categories = useMemo(() => {
        const cats = new Set(products.map(p => p.category).filter(Boolean))
        return ['All', ...Array.from(cats) as string[]]
    }, [products])

    // Top movers by forecast demand (product-level aggregation)
    const productForecasts = useMemo(() => {
        const byProduct = new Map<string, number>()
        forecasts.forEach(f => {
            byProduct.set(f.product_id, (byProduct.get(f.product_id) ?? 0) + f.forecasted_demand)
        })
        return Array.from(byProduct.entries())
            .map(([productId, total]) => ({
                productId,
                name: productMap.get(productId)?.name ?? productId.slice(0, 8),
                total: Math.round(total),
            }))
            .sort((a, b) => b.total - a.total)
    }, [forecasts, productMap])

    const topMovers = productForecasts.slice(0, 3)
    const bottomMovers = productForecasts.slice(-3).reverse()

    // Latest forecast record per product — used to supply forecastId to SHAPWaterfall
    const latestForecastByProduct = useMemo(() => {
        const map = new Map<string, { id: string; demand: number; date: string }>()
        forecasts.forEach(f => {
            const existing = map.get(f.product_id)
            if (!existing || f.forecast_date > existing.date) {
                map.set(f.product_id, { id: f.forecast_id, demand: f.forecasted_demand, date: f.forecast_date })
            }
        })
        return map
    }, [forecasts])

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
                        Explore forecast volume by date, category, and product.
                        {forecasts.length > 0 && ` · ${forecasts.length} forecasts loaded`}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setWindowDays(7)}
                            className={`text-xs px-3 h-8 gap-2 ${windowDays === 7 ? 'btn-primary' : 'btn-secondary'}`}
                        >
                            <Filter className="h-3 w-3" />
                            Last 7 Days
                        </button>
                        <button
                            onClick={() => setWindowDays(30)}
                            className={`text-xs px-3 h-8 ${windowDays === 30 ? 'btn-primary' : 'btn-secondary'}`}
                        >
                            Last 30 Days
                        </button>
                    </div>
                </div>
            </div>

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
                                            <Area type="monotone" dataKey="demand" stroke="#0071e3" fill="url(#colorDemand)" name="Demand" />
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
                                            />
                                            <Bar dataKey="value" barSize={20} radius={[0, 4, 4, 0]}>
                                                {categoryData.map((_, index) => (
                                                    <Cell key={`cell-${index}`} fill={index % 2 === 0 ? '#0071e3' : '#34c759'} />
                                                ))}
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
                                                    <SHAPWaterfall forecastId={forecast.id} predictedValue={forecast.demand} />
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
