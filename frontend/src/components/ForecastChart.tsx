/**
 * Demand Forecast Chart — Area chart with confidence bands.
 * Agent: full-stack-engineer | Skill: react-dashboard (Recharts pattern)
 */

import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from 'recharts'
import type { Forecast } from '@/lib/types'

interface ForecastChartProps {
    data: Forecast[]
    title?: string
}

export default function ForecastChart({ data, title = 'Demand Forecast' }: ForecastChartProps) {
    const chartData = data.map((f) => ({
        date: new Date(f.forecast_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        demand: f.forecasted_demand,
        lower: f.lower_bound,
        upper: f.upper_bound,
    }))

    return (
        <div className="card">
            <h3 className="text-sm font-semibold text-surface-50 mb-4">{title}</h3>
            <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                    <defs>
                        <linearGradient id="demandGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                            <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="bandGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#818cf8" stopOpacity={0.1} />
                            <stop offset="100%" stopColor="#818cf8" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                        dataKey="date"
                        tick={{ fill: '#94a3b8', fontSize: 11 }}
                        axisLine={{ stroke: '#334155' }}
                        tickLine={false}
                    />
                    <YAxis
                        tick={{ fill: '#94a3b8', fontSize: 11 }}
                        axisLine={{ stroke: '#334155' }}
                        tickLine={false}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: '#0f172a',
                            border: '1px solid #334155',
                            borderRadius: '8px',
                            color: '#f1f5f9',
                            fontSize: '13px',
                        }}
                    />
                    <Area
                        type="monotone"
                        dataKey="upper"
                        stroke="none"
                        fill="url(#bandGradient)"
                        fillOpacity={1}
                    />
                    <Area
                        type="monotone"
                        dataKey="lower"
                        stroke="none"
                        fill="#020617"
                        fillOpacity={1}
                    />
                    <Area
                        type="monotone"
                        dataKey="demand"
                        stroke="#6366f1"
                        strokeWidth={2}
                        fill="url(#demandGradient)"
                        fillOpacity={1}
                        dot={false}
                        activeDot={{ r: 4, fill: '#6366f1', stroke: '#fff', strokeWidth: 2 }}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    )
}
