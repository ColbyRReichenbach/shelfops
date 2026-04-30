import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { TrendingDown, Loader2 } from 'lucide-react'
import type { BacktestEntry } from '@/lib/types'

interface BacktestTooltipPayload {
    payload: {
        date: string
        mae: number
        mape: number | null
        version: string
    }
}

function formatShortDate(value: string) {
    return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatLongDate(value: string) {
    return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    })
}

function BacktestTooltip({
    active,
    label,
    payload,
}: {
    active?: boolean
    label?: string
    payload?: BacktestTooltipPayload[]
}) {
    if (!active || !payload?.length || !label) return null
    const point = payload[0]?.payload
    if (!point) return null

    return (
        <div className="rounded-[10px] border border-white/10 bg-[#1d1d1f]/90 px-3 py-2 text-xs text-white shadow-lg backdrop-blur">
            <p className="mb-2 font-semibold">{formatLongDate(label)}</p>
            <div className="space-y-1.5">
                <div className="flex min-w-[160px] items-center justify-between gap-4">
                    <span className="flex items-center gap-2 text-white/75">
                        <span className="h-2 w-2 rounded-full bg-[#0071e3]" />
                        MAE
                    </span>
                    <span className="font-semibold">{point.mae.toFixed(2)}</span>
                </div>
                {point.mape !== null && (
                    <div className="flex min-w-[160px] items-center justify-between gap-4">
                        <span className="flex items-center gap-2 text-white/75">
                            <span className="h-2 w-2 rounded-full bg-[#34c759]" />
                            MAPE
                        </span>
                        <span className="font-semibold">{point.mape.toFixed(1)}%</span>
                    </div>
                )}
                <p className="pt-1 text-[11px] text-white/55">Model {point.version}</p>
            </div>
        </div>
    )
}

export default function BacktestCharts({ backtests, isLoading }: { backtests: BacktestEntry[]; isLoading: boolean }) {
    if (isLoading) {
        return (
            <div className="card border border-black/[0.02] shadow-sm text-center py-16">
                <Loader2 className="h-8 w-8 mx-auto mb-3 text-[#0071e3] animate-spin" />
                <p className="text-sm text-[#86868b]">Loading backtest data...</p>
            </div>
        )
    }

    if (backtests.length === 0) {
        return (
            <div className="card border border-black/[0.02] shadow-sm text-center py-16">
                <TrendingDown className="h-8 w-8 mx-auto mb-3 text-[#86868b]" />
                <p className="text-sm text-[#86868b]">No backtest results yet</p>
                <p className="text-xs text-[#86868b] mt-1">Backtests run daily at 6:00 AM UTC</p>
            </div>
        )
    }

    const chartData = backtests
        .filter(b => b.forecast_date && b.mae !== null)
        .map(b => ({
            date: b.forecast_date!,
            mae: Number(b.mae?.toFixed(2)),
            mape: b.mape !== null ? Number(b.mape.toFixed(1)) : null,
            stockoutMissRate: b.stockout_miss_rate !== null ? Number((b.stockout_miss_rate * 100).toFixed(1)) : null,
            version: b.model_version,
        }))
        .sort((left, right) => left.date.localeCompare(right.date))

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
                <div className="card border border-black/[0.02] shadow-sm p-4">
                    <p className="text-xs font-medium text-[#86868b] uppercase tracking-wider">Avg MAE</p>
                    <p className="text-2xl font-bold text-[#0071e3] mt-1">{avgMae.toFixed(2)}</p>
                </div>
                <div className="card border border-black/[0.02] shadow-sm p-4">
                    <p className="text-xs font-medium text-[#86868b] uppercase tracking-wider">Latest MAE</p>
                    <p className="text-2xl font-bold text-[#1d1d1f] mt-1">{latestMae.toFixed(2)}</p>
                </div>
                <div className="card border border-black/[0.02] shadow-sm p-4">
                    <p className="text-xs font-medium text-[#86868b] uppercase tracking-wider">7d Trend</p>
                    <p className={`text-2xl font-bold mt-1 ${trend < 0 ? 'text-[#34c759]' : trend > 0 ? 'text-[#ff3b30]' : 'text-[#1d1d1f]'}`}>
                        {trend > 0 ? '+' : ''}{trend.toFixed(2)}
                    </p>
                </div>
            </div>

            {/* Chart */}
            <div className="card border border-black/[0.02] shadow-sm p-4">
                <h3 className="text-sm font-semibold text-[#1d1d1f] mb-4">Walk-Forward MAE Over Time</h3>
                <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 14, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5ea" />
                        <XAxis
                            dataKey="date"
                            tick={{ fontSize: 11, fill: '#86868b' }}
                            tickFormatter={formatShortDate}
                            interval="preserveStartEnd"
                            minTickGap={40}
                            stroke="rgba(0,0,0,0.3)"
                        />
                        <YAxis tick={{ fontSize: 11, fill: '#86868b' }} stroke="rgba(0,0,0,0.3)" width={44} />
                        <Tooltip
                            content={<BacktestTooltip />}
                            cursor={{ stroke: '#c7c7cc', strokeWidth: 1 }}
                        />
                        <Legend />
                        <Line type="monotone" dataKey="mae" name="MAE" stroke="#0071e3" strokeWidth={2} dot={false} />
                        {chartData.some(d => d.mape !== null) && (
                            <Line type="monotone" dataKey="mape" name="MAPE %" stroke="#34c759" strokeWidth={2} dot={false} />
                        )}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    )
}
