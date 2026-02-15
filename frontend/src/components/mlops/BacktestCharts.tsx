/**
 * BacktestCharts — 90-day walk-forward MAE/MAPE time-series chart.
 */

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { TrendingDown, Loader2 } from 'lucide-react'
import type { BacktestEntry } from '@/lib/types'

export default function BacktestCharts({ backtests, isLoading }: { backtests: BacktestEntry[]; isLoading: boolean }) {
    if (isLoading) {
        return (
            <div className="card border border-white/40 shadow-sm text-center py-16">
                <Loader2 className="h-8 w-8 mx-auto mb-3 text-shelf-primary animate-spin" />
                <p className="text-sm text-shelf-foreground/60">Loading backtest data...</p>
            </div>
        )
    }

    if (backtests.length === 0) {
        return (
            <div className="card border border-white/40 shadow-sm text-center py-16">
                <TrendingDown className="h-8 w-8 mx-auto mb-3 text-shelf-foreground/30" />
                <p className="text-sm text-shelf-foreground/50">No backtest results yet</p>
                <p className="text-xs text-shelf-foreground/40 mt-1">Backtests run daily at 6:00 AM UTC</p>
            </div>
        )
    }

    const chartData = backtests
        .filter(b => b.forecast_date && b.mae !== null)
        .map(b => ({
            date: new Date(b.forecast_date!).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
            mae: Number(b.mae?.toFixed(2)),
            mape: b.mape !== null ? Number(b.mape.toFixed(1)) : null,
            stockoutMissRate: b.stockout_miss_rate !== null ? Number((b.stockout_miss_rate * 100).toFixed(1)) : null,
            version: b.model_version,
        }))

    // Summary stats
    const avgMae = chartData.reduce((sum, d) => sum + (d.mae ?? 0), 0) / chartData.length
    const latestMae = chartData[chartData.length - 1]?.mae ?? 0
    const trend = chartData.length > 7
        ? (chartData.slice(-7).reduce((s, d) => s + (d.mae ?? 0), 0) / 7) - (chartData.slice(0, 7).reduce((s, d) => s + (d.mae ?? 0), 0) / 7)
        : 0

    return (
        <div className="space-y-4">
            {/* KPI row */}
            <div className="grid grid-cols-3 gap-4">
                <div className="card border border-white/40 shadow-sm p-4">
                    <p className="text-xs font-medium text-shelf-foreground/50 uppercase tracking-wider">Avg MAE</p>
                    <p className="text-2xl font-bold text-shelf-primary mt-1">{avgMae.toFixed(2)}</p>
                </div>
                <div className="card border border-white/40 shadow-sm p-4">
                    <p className="text-xs font-medium text-shelf-foreground/50 uppercase tracking-wider">Latest MAE</p>
                    <p className="text-2xl font-bold text-shelf-foreground mt-1">{latestMae.toFixed(2)}</p>
                </div>
                <div className="card border border-white/40 shadow-sm p-4">
                    <p className="text-xs font-medium text-shelf-foreground/50 uppercase tracking-wider">7d Trend</p>
                    <p className={`text-2xl font-bold mt-1 ${trend < 0 ? 'text-green-600' : trend > 0 ? 'text-red-600' : 'text-shelf-foreground'}`}>
                        {trend > 0 ? '+' : ''}{trend.toFixed(2)}
                    </p>
                </div>
            </div>

            {/* Chart */}
            <div className="card border border-white/40 shadow-sm p-4">
                <h3 className="text-sm font-semibold text-shelf-foreground mb-4">Walk-Forward MAE Over Time</h3>
                <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" />
                        <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="rgba(0,0,0,0.3)" />
                        <YAxis tick={{ fontSize: 11 }} stroke="rgba(0,0,0,0.3)" />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'white',
                                borderRadius: '8px',
                                border: '1px solid rgba(0,0,0,0.1)',
                                fontSize: '12px',
                            }}
                        />
                        <Legend />
                        <Line type="monotone" dataKey="mae" name="MAE" stroke="#6366f1" strokeWidth={2} dot={false} />
                        {chartData.some(d => d.mape !== null) && (
                            <Line type="monotone" dataKey="mape" name="MAPE %" stroke="#f59e0b" strokeWidth={2} dot={false} />
                        )}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    )
}
