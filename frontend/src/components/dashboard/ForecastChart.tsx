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

interface ForecastData {
    date: string
    actual?: number | null
    forecast?: number | null
    lower?: number
    upper?: number
}

interface ForecastChartProps {
    data: ForecastData[]
}

export default function ForecastChart({ data }: ForecastChartProps) {
    const formatUnits = (value: number | null | undefined) => {
        if (value == null || Number.isNaN(value)) return 'N/A'
        return `${Math.round(value).toLocaleString()} units`
    }

    const hasActualSeries = data.some((point) => point.actual != null)

    return (
        <div className="card border border-white/40 shadow-sm">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Demand Forecast</h3>
                    <p className="text-xs text-shelf-foreground/60 mt-1">Historical sales vs. AI prediction</p>
                </div>
                <div className="flex flex-wrap gap-4 text-xs font-medium">
                    <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-shelf-primary"></span>
                        <span className="text-shelf-foreground/70">AI Forecast</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-shelf-secondary"></span>
                        <span className="text-shelf-foreground/70">Actual Sales</span>
                    </div>
                </div>
            </div>

            <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: -20 }}>
                        <defs>
                            <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#3e6d96" stopOpacity={0.15} />
                                <stop offset="95%" stopColor="#3e6d96" stopOpacity={0} />
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
                                return [formatUnits(Number.isNaN(numeric) ? null : numeric), name]
                            }}
                            labelStyle={{ color: '#3e6d96', fontWeight: 600, marginBottom: '0.5rem' }}
                        />

                        <Area
                            type="monotone"
                            dataKey="forecast"
                            stroke="#3e6d96"
                            strokeWidth={2}
                            fill="url(#forecastGradient)"
                            name="AI Forecast"
                            isAnimationActive
                            animationDuration={450}
                            animationEasing="ease-out"
                        />

                        {hasActualSeries && (
                            <Line
                                type="monotone"
                                dataKey="actual"
                                stroke="#5ba2b6"
                                strokeWidth={2}
                                dot={false}
                                activeDot={{ r: 4, strokeWidth: 0 }}
                                name="Actual Sales"
                                connectNulls
                                isAnimationActive
                                animationDuration={450}
                                animationEasing="ease-out"
                            />
                        )}
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    )
}
