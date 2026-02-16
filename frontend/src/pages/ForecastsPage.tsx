import { useState, useMemo } from 'react'
import { AreaChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { ArrowUpRight, ArrowDownRight, Filter, Loader2, AlertCircle } from 'lucide-react'
import { useForecasts, useProducts, useForecastAccuracyTrend, useForecastAccuracyByCategory } from '@/hooks/useShelfOps'

export default function ForecastsPage() {
    const [activeCategory, setActiveCategory] = useState('All')

    const { data: forecasts = [], isLoading: forecastsLoading, isError } = useForecasts({
        limit: 5000,
    })
    const { data: products = [] } = useProducts()
    const { data: trendAccuracy = [], isLoading: trendLoading } = useForecastAccuracyTrend({
        limit: 90,
        category: activeCategory !== 'All' ? activeCategory : undefined,
    })
    const { data: categoryAccuracy = [], isLoading: byCategoryLoading } = useForecastAccuracyByCategory({ limit: 8 })
    const isLoading = forecastsLoading || trendLoading || byCategoryLoading

    // Build a product lookup
    const productMap = useMemo(() => {
        const map = new Map<string, { name: string; category: string | null }>()
        products.forEach(p => map.set(p.product_id, { name: p.name, category: p.category }))
        return map
    }, [products])

    // Aggregate forecasts by date for trend chart
    const trendData = useMemo(() => {
        if (trendAccuracy.length > 0) {
            return trendAccuracy.map((row) => ({
                date: new Date(row.forecast_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                forecast: Math.round(row.forecasted_demand),
                actual: row.actual_demand == null ? null : Math.round(row.actual_demand),
            }))
        }

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
                forecast: Math.round(demand),
                actual: null,
            }))
    }, [trendAccuracy, forecasts, productMap, activeCategory])

    // Aggregate forecasts by product category for bar chart
    const categoryData = useMemo(() => {
        if (categoryAccuracy.length > 0) {
            return categoryAccuracy
                .map((row) => ({
                    name: row.category || 'Unknown',
                    forecast: Math.round(row.forecasted_demand),
                    actual: row.actual_demand == null ? null : Math.round(row.actual_demand),
                }))
                .sort((a, b) => b.forecast - a.forecast)
                .slice(0, 8)
        }

        const byCategory = new Map<string, number>()
        forecasts.forEach(f => {
            const product = productMap.get(f.product_id)
            const cat = product?.category ?? 'Unknown'
            byCategory.set(cat, (byCategory.get(cat) ?? 0) + f.forecasted_demand)
        })
        return Array.from(byCategory.entries())
            .sort(([, a], [, b]) => b - a)
            .slice(0, 8)
            .map(([name, value]) => ({ name, forecast: Math.round(value), actual: null }))
    }, [categoryAccuracy, forecasts, productMap])

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
    const hasTrendActual = trendData.some((point) => point.actual != null)
    const hasCategoryActual = categoryData.some((point) => point.actual != null)

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Forecast Analysis</h1>
                    <p className="text-sm text-shelf-foreground/60 mt-1">
                        Aggregate demand planning and trend analysis
                        {forecasts.length > 0 && ` · ${forecasts.length} forecasts loaded`}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button className="btn-secondary text-xs px-3 h-8 gap-2">
                        <Filter className="h-3 w-3" />
                        Last 7 Days
                    </button>
                    <button className="btn-primary text-xs px-3 h-8">
                        Export Report
                    </button>
                </div>
            </div>

            {/* Category Filter */}
            <div className="flex flex-wrap gap-2">
                {categories.map((cat) => (
                    <button
                        key={cat}
                        onClick={() => setActiveCategory(cat)}
                        className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${activeCategory === cat
                            ? 'bg-shelf-primary text-white shadow-md shadow-shelf-primary/20'
                            : 'bg-white text-shelf-foreground/60 hover:text-shelf-primary hover:bg-white/80 border border-transparent hover:border-shelf-foreground/5'
                            }`}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Loading state */}
            {isLoading && (
                <div className="card p-12 text-center border border-white/40 shadow-sm">
                    <Loader2 className="h-8 w-8 mx-auto mb-3 text-shelf-primary animate-spin" />
                    <p className="text-sm text-shelf-foreground/60">Loading forecasts...</p>
                </div>
            )}

            {/* Error state */}
            {isError && (
                <div className="card p-12 text-center border border-red-200 bg-red-50/50 shadow-sm">
                    <AlertCircle className="h-8 w-8 mx-auto mb-3 text-red-500" />
                    <p className="text-sm text-red-600">Failed to load forecasts</p>
                </div>
            )}

            {!isLoading && !isError && (
                <>
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Main Trend Chart */}
                        <div className="lg:col-span-2 card border border-white/40 shadow-sm">
                            <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider mb-6">Total Demand Trend</h3>
                            <div className="h-[300px]">
                                {trendData.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                            <defs>
                                                <linearGradient id="colorDemand" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#3e6d96" stopOpacity={0.2} />
                                                    <stop offset="95%" stopColor="#3e6d96" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#000000" strokeOpacity={0.05} vertical={false} />
                                            <XAxis dataKey="date" tick={{ fill: '#4e5274', fontSize: 11, opacity: 0.6 }} axisLine={false} tickLine={false} dy={10} />
                                            <YAxis tick={{ fill: '#4e5274', fontSize: 11, opacity: 0.6 }} axisLine={false} tickLine={false} />
                                            <Tooltip
                                                cursor={{ stroke: 'rgba(62,109,150,0.22)', strokeWidth: 1.5, strokeDasharray: '4 4' }}
                                                labelFormatter={(label) => `Date: ${label}`}
                                                formatter={(value: number | string, name: string) => {
                                                    if (value === null || value === undefined) return ['N/A', name]
                                                    const numeric = typeof value === 'number' ? value : Number(value)
                                                    if (Number.isNaN(numeric)) return ['N/A', name]
                                                    return [`${Math.round(numeric).toLocaleString()} units`, name]
                                                }}
                                                contentStyle={{
                                                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                                    border: '1px solid rgba(255, 255, 255, 0.5)',
                                                    borderRadius: '12px',
                                                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                                                    fontSize: '12px',
                                                    color: '#4e5274'
                                                }}
                                            />
                                            <Area
                                                type="monotone"
                                                dataKey="forecast"
                                                stroke="#3e6d96"
                                                fill="url(#colorDemand)"
                                                name="Forecast"
                                                isAnimationActive
                                                animationDuration={450}
                                                animationEasing="ease-out"
                                            />
                                            {hasTrendActual && (
                                                <Line
                                                    type="monotone"
                                                    dataKey="actual"
                                                    stroke="#5ba2b6"
                                                    strokeWidth={2}
                                                    dot={false}
                                                    connectNulls
                                                    name="Actual"
                                                    isAnimationActive
                                                    animationDuration={450}
                                                    animationEasing="ease-out"
                                                />
                                            )}
                                        </AreaChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-shelf-foreground/40 text-sm">
                                        No forecast data available
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Category Distribution */}
                        <div className="card border border-white/40 shadow-sm">
                            <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider mb-6">Forecast by Category</h3>
                            <div className="h-[300px]">
                                {categoryData.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={categoryData} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 20 }}>
                                            <XAxis type="number" hide />
                                            <YAxis dataKey="name" type="category" width={80} tick={{ fill: '#4e5274', fontSize: 11 }} axisLine={false} tickLine={false} />
                                            <Tooltip
                                                cursor={{ fill: 'rgba(0,0,0,0.02)' }}
                                                labelFormatter={(label) => `Category: ${label}`}
                                                formatter={(value: number | string, name: string) => {
                                                    if (value === null || value === undefined) return ['N/A', name]
                                                    const numeric = typeof value === 'number' ? value : Number(value)
                                                    if (Number.isNaN(numeric)) return ['N/A', name]
                                                    return [`${Math.round(numeric).toLocaleString()} units`, name]
                                                }}
                                                contentStyle={{ borderRadius: '8px' }}
                                            />
                                            <Bar
                                                dataKey="forecast"
                                                name="Forecast"
                                                barSize={10}
                                                radius={[3, 3, 0, 0]}
                                                fill="#3e6d96"
                                                isAnimationActive
                                                animationDuration={450}
                                                animationEasing="ease-out"
                                            />
                                            {hasCategoryActual && (
                                                <Bar
                                                    dataKey="actual"
                                                    name="Actual"
                                                    barSize={10}
                                                    radius={[3, 3, 0, 0]}
                                                    fill="#5ba2b6"
                                                    isAnimationActive
                                                    animationDuration={450}
                                                    animationEasing="ease-out"
                                                />
                                            )}
                                        </BarChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-shelf-foreground/40 text-sm">
                                        No category data
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Movers and Shakers */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="card p-0 overflow-hidden border border-white/40 shadow-sm">
                            <div className="p-4 border-b border-shelf-foreground/5 bg-shelf-secondary/5">
                                <h3 className="text-sm font-semibold text-shelf-foreground flex items-center gap-2">
                                    <ArrowUpRight className="h-4 w-4 text-green-600" />
                                    Top Demand Products
                                </h3>
                            </div>
                            <div className="divide-y divide-shelf-foreground/5">
                                {topMovers.length > 0 ? topMovers.map((item, i) => (
                                    <div key={i} className="p-4 flex items-center justify-between hover:bg-shelf-primary/5 transition-colors">
                                        <div>
                                            <p className="text-sm font-medium text-shelf-foreground">{item.name}</p>
                                            <p className="text-xs text-shelf-foreground/60">{item.total.toLocaleString()} units forecast</p>
                                        </div>
                                        <span className="badge bg-green-100 text-green-700 border-green-200">#{i + 1}</span>
                                    </div>
                                )) : (
                                    <div className="p-8 text-center text-shelf-foreground/40 text-sm">No forecast data</div>
                                )}
                            </div>
                        </div>

                        <div className="card p-0 overflow-hidden border border-white/40 shadow-sm">
                            <div className="p-4 border-b border-shelf-foreground/5 bg-shelf-secondary/5">
                                <h3 className="text-sm font-semibold text-shelf-foreground flex items-center gap-2">
                                    <ArrowDownRight className="h-4 w-4 text-red-600" />
                                    Lowest Demand Products
                                </h3>
                            </div>
                            <div className="divide-y divide-shelf-foreground/5">
                                {bottomMovers.length > 0 ? bottomMovers.map((item, i) => (
                                    <div key={i} className="p-4 flex items-center justify-between hover:bg-shelf-primary/5 transition-colors">
                                        <div>
                                            <p className="text-sm font-medium text-shelf-foreground">{item.name}</p>
                                            <p className="text-xs text-shelf-foreground/60">{item.total.toLocaleString()} units forecast</p>
                                        </div>
                                        <span className="badge bg-red-100 text-red-700 border-red-200">Low</span>
                                    </div>
                                )) : (
                                    <div className="p-8 text-center text-shelf-foreground/40 text-sm">No forecast data</div>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
