import {
    AreaChart,
    Area,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer
} from 'recharts'

interface RevenueData {
    date: string
    actual: number | null
    predicted: number
    at_risk: number | null
}

interface RevenueChartProps {
    data: RevenueData[]
}

export default function RevenueChart({ data }: RevenueChartProps) {
    const currency = (value: number | null | undefined) => {
        if (value == null || Number.isNaN(value)) return 'N/A'
        return `$${Math.round(value).toLocaleString()}`
    }

    const hasActualSeries = data.some((point) => point.actual != null)
    const hasRiskSeries = data.some((point) => point.at_risk != null)

    return (
        <div className="card h-[350px] border border-white/40 shadow-sm">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Revenue Forecast & Risk</h3>
                <div className="flex gap-4 text-xs font-medium">
                    <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-shelf-primary"></span>
                        <span className="text-shelf-foreground/70">Predicted</span>
                    </div>
                    {hasActualSeries && (
                        <div className="flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-shelf-secondary"></span>
                            <span className="text-shelf-foreground/70">Actual</span>
                        </div>
                    )}
                    {hasRiskSeries && (
                        <div className="flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-shelf-accent"></span>
                            <span className="text-shelf-foreground/70">At Risk</span>
                        </div>
                    )}
                </div>
            </div>

            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data} margin={{ top: 10, right: 0, bottom: 20, left: -20 }}>
                    <defs>
                        <linearGradient id="predictedGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3e6d96" stopOpacity={0.15} />
                            <stop offset="95%" stopColor="#3e6d96" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#934c4e" stopOpacity={0.15} />
                            <stop offset="95%" stopColor="#934c4e" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#000000" strokeOpacity={0.05} vertical={false} />
                    <XAxis
                        dataKey="date"
                        tick={{ fill: '#4e5274', fontSize: 11, opacity: 0.6 }}
                        axisLine={false}
                        tickLine={false}
                        dy={10}
                    />
                    <YAxis
                        tick={{ fill: '#4e5274', fontSize: 11, opacity: 0.6 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(value) => `$${(Number(value) / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                        cursor={{ stroke: 'rgba(62,109,150,0.22)', strokeWidth: 1.5, strokeDasharray: '4 4' }}
                        labelFormatter={(label) => `Date: ${label}`}
                        contentStyle={{
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            border: '1px solid rgba(255, 255, 255, 0.5)',
                            borderRadius: '12px',
                            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                            fontSize: '12px',
                            color: '#4e5274'
                        }}
                        itemStyle={{ color: '#4e5274' }}
                        formatter={(value: number | string, name: string) => {
                            const numeric = typeof value === 'number' ? value : Number(value)
                            return [currency(Number.isNaN(numeric) ? null : numeric), name]
                        }}
                    />

                    {hasRiskSeries && (
                        <Area
                            type="monotone"
                            dataKey="at_risk"
                            stroke="#934c4e"
                            strokeWidth={2}
                            fill="url(#riskGradient)"
                            name="At Risk"
                            isAnimationActive
                            animationDuration={450}
                            animationEasing="ease-out"
                        />
                    )}

                    {/* Predicted Line/Area */}
                    <Area
                        type="monotone"
                        dataKey="predicted"
                        stroke="#3e6d96"
                        strokeWidth={2}
                        fill="url(#predictedGradient)"
                        name="Predicted"
                        isAnimationActive
                        animationDuration={450}
                        animationEasing="ease-out"
                    />

                    {/* Actual Line */}
                    {hasActualSeries && (
                        <Line
                            type="monotone"
                            dataKey="actual"
                            stroke="#5ba2b6"
                            strokeWidth={2}
                            dot={false}
                            activeDot={{ r: 4, fill: '#5ba2b6', strokeWidth: 1, stroke: '#fff' }}
                            name="Actual"
                            connectNulls
                            isAnimationActive
                            animationDuration={450}
                            animationEasing="ease-out"
                        />
                    )}
                </AreaChart>
            </ResponsiveContainer>
        </div>
    )
}
