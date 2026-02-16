import { useMemo } from 'react'
import { DollarSign, TrendingDown, Target, Zap } from 'lucide-react'
import KpiCard from '@/components/KpiCard'
import RevenueChart from './RevenueChart'
import { KpiSkeleton, ChartSkeleton, Skeleton } from '@/components/Skeleton'
import {
    useAlertSummary,
    useForecasts,
    useStores,
    useForecastAccuracy,
    useForecastAccuracyTrend,
    useInventorySummary,
    useProducts,
} from '@/hooks/useShelfOps'

export default function ExecutiveDashboard() {
    const { data: alertSummary, isLoading: alertsLoading } = useAlertSummary()
    const { data: forecasts = [], isLoading: forecastsLoading } = useForecasts({
        limit: 5000,
    })
    const { data: forecastTrend = [] } = useForecastAccuracyTrend({ limit: 30 })
    const { data: products = [] } = useProducts()
    const { data: stores = [], isLoading: storesLoading } = useStores()
    const { data: accuracyData = [] } = useForecastAccuracy()
    const { data: inventorySummary } = useInventorySummary()

    const isLoading = alertsLoading || forecastsLoading || storesLoading

    // Compute KPIs directly from real API data — no fabricated multipliers
    const kpis = useMemo(() => {
        const totalAlerts = alertSummary?.total ?? 0
        const criticalAlerts = alertSummary?.critical ?? 0
        const openAlerts = alertSummary?.open ?? 0

        // Stockout rate: percentage of alerts that are critical severity
        const stockoutRate = totalAlerts > 0
            ? Number(((criticalAlerts / totalAlerts) * 100).toFixed(1))
            : 0

        // Forecast accuracy from MAPE.
        // Backend stores MAPE as ratio in [0, 1] (occasionally percentage in [0, 100] for legacy rows),
        // so normalize before converting to accuracy%.
        const avgAccuracy = accuracyData.length > 0
            ? Number(
                (
                    accuracyData.reduce((sum, a) => {
                        const mapeRatio = a.avg_mape > 1 ? a.avg_mape / 100 : a.avg_mape
                        const accuracyPct = (1 - mapeRatio) * 100
                        return sum + Math.max(0, Math.min(100, accuracyPct))
                    }, 0) / accuracyData.length
                ).toFixed(1)
            )
            : null

        const stockHealthValue = inventorySummary
            ? `${Math.round((inventorySummary.in_stock / Math.max(1, inventorySummary.total_items)) * 100)}%`
            : '—'
        const stockHealthChange = inventorySummary
            ? inventorySummary.low_stock + inventorySummary.critical + inventorySummary.out_of_stock
            : 0
        const stockHealthTrend = inventorySummary
            ? (inventorySummary.out_of_stock > 0 ? ('down' as const) : inventorySummary.critical > 0 ? ('flat' as const) : ('up' as const))
            : ('flat' as const)
        const stockHealthDescription = inventorySummary
            ? `${inventorySummary.low_stock} low, ${inventorySummary.critical} critical, ${inventorySummary.out_of_stock} out`
            : 'Inventory summary unavailable'

        return [
            {
                label: 'Open Alerts',
                value: openAlerts.toString(),
                change: criticalAlerts,
                trend: openAlerts > 0 ? ('up' as const) : ('flat' as const),
                icon: <TrendingDown className="h-4 w-4 text-red-500" />,
                description: `${criticalAlerts} critical, ${alertSummary?.high ?? 0} high severity`
            },
            {
                label: 'Stock Health',
                value: stockHealthValue,
                change: stockHealthChange,
                trend: stockHealthTrend,
                icon: <DollarSign className="h-4 w-4 text-green-500" />,
                description: stockHealthDescription,
            },
            {
                label: 'Stockout Rate',
                value: `${stockoutRate}%`,
                change: stockoutRate,
                trend: stockoutRate > 10 ? ('up' as const) : stockoutRate > 0 ? ('down' as const) : ('flat' as const),
                icon: <Zap className="h-4 w-4 text-yellow-500" />,
                description: 'Critical alerts as % of total'
            },
            {
                label: 'Forecast Accuracy',
                value: avgAccuracy != null ? `${avgAccuracy}%` : '—',
                change: avgAccuracy != null ? avgAccuracy : 0,
                trend: (avgAccuracy ?? 0) >= 90 ? ('up' as const) : (avgAccuracy ?? 0) >= 70 ? ('flat' as const) : ('down' as const),
                icon: <Target className="h-4 w-4 text-shelf-primary" />,
                description: accuracyData.length > 0 ? `Based on ${accuracyData.length} product forecasts` : 'No accuracy data yet'
            }
        ]
    }, [alertSummary, accuracyData, inventorySummary])

    // Build chart data from real forecast/accuracy records only.
    const chartData = useMemo(() => {
        if (forecastTrend.length > 0) {
            return forecastTrend.map((point) => {
                const predicted = Math.round(point.forecasted_revenue)
                const actual = point.actual_revenue == null ? null : Math.round(point.actual_revenue)
                const atRisk = actual == null ? null : Math.max(predicted - actual, 0)
                return {
                    date: new Date(point.forecast_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                    predicted,
                    actual,
                    at_risk: atRisk,
                }
            })
        }

        const priceByProduct = new Map<string, number>()
        products.forEach((p) => {
            priceByProduct.set(p.product_id, p.unit_price ?? p.unit_cost ?? 0)
        })

        const byDate = new Map<string, { predictedRevenue: number }>()
        forecasts.forEach(f => {
            const dateKey = f.forecast_date
            const existing = byDate.get(dateKey) ?? { predictedRevenue: 0 }
            existing.predictedRevenue += f.forecasted_demand * (priceByProduct.get(f.product_id) ?? 0)
            byDate.set(dateKey, existing)
        })
        return Array.from(byDate.entries())
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([date, vals]) => ({
                date: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                predicted: Math.round(vals.predictedRevenue),
                actual: null,
                at_risk: null,
            }))
    }, [forecasts, products, forecastTrend])

    // Top at-risk stores: use alert counts per store from the alerts data
    const atRiskStores = useMemo(() => {
        return stores
            .filter(s => s.status === 'active')
            .map(s => ({
                name: `${s.name}${s.city ? ` (${s.city})` : ''}`,
                storeId: s.store_id,
            }))
            .slice(0, 5)
    }, [stores])

    if (isLoading) {
        return (
            <div className="space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => <KpiSkeleton key={i} />)}
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2"><ChartSkeleton /></div>
                    <div className="card border border-white/40 shadow-sm p-4 space-y-4">
                        <Skeleton className="h-4 w-24" />
                        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* KPI Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {kpis.map((kpi) => (
                    <KpiCard key={kpi.label} {...kpi} />
                ))}
            </div>

            {/* Main Content Area */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Revenue Chart (2 cols) */}
                <div className="lg:col-span-2">
                    {chartData.length > 0 ? (
                        <RevenueChart data={chartData} />
                    ) : (
                        <div className="card h-[350px] border border-white/40 shadow-sm flex items-center justify-center">
                            <p className="text-sm text-shelf-foreground/40">No forecast data available for chart</p>
                        </div>
                    )}
                </div>

                {/* Active Stores List (1 col) */}
                <div className="card">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Active Stores</h3>
                        <span className="text-xs text-shelf-foreground/50">{stores.filter(s => s.status === 'active').length} active</span>
                    </div>
                    <div className="space-y-3">
                        {atRiskStores.map((store, i) => (
                            <div key={i} className="flex items-center justify-between p-2 rounded-lg hover:bg-shelf-secondary/10 transition-colors">
                                <div>
                                    <p className="text-sm font-medium text-shelf-foreground">{store.name}</p>
                                    <p className="text-xs text-shelf-foreground/60 font-mono">{store.storeId.slice(0, 8)}</p>
                                </div>
                            </div>
                        ))}
                        {atRiskStores.length === 0 && (
                            <p className="text-sm text-shelf-foreground/40 text-center py-4">No store data available</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
