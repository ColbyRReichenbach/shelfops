import {
    AreaChart,
    Area,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from 'recharts'

interface ForecastData {
    date: string
    actual?: number
    forecast?: number
    lower_bound?: number
    upper_bound?: number
    range?: [number, number]
}

interface ForecastChartProps {
    data: ForecastData[]
}

interface TooltipPayloadItem {
    dataKey?: string
    color?: string
    value?: number | [number, number]
    payload: ForecastData
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

function formatUnits(value: number | undefined) {
    return value == null ? '—' : `${Math.round(value).toLocaleString()} units`
}

function DemandTooltip({
    active,
    label,
    payload,
}: {
    active?: boolean
    label?: string
    payload?: TooltipPayloadItem[]
}) {
    if (!active || !payload?.length || !label) return null
    const point = payload[0]?.payload
    if (!point) return null

    return (
        <div className="rounded-[10px] border border-white/10 bg-[#1d1d1f]/90 px-3 py-2 text-xs text-white shadow-lg backdrop-blur">
            <p className="mb-2 font-semibold">{formatLongDate(label)}</p>
            <div className="space-y-1.5">
                {point.actual != null && (
                    <div className="flex min-w-[180px] items-center justify-between gap-4">
                        <span className="flex items-center gap-2 text-white/75">
                            <span className="h-2 w-2 rounded-full bg-[#34c759]" />
                            Historical sales
                        </span>
                        <span className="font-semibold">{formatUnits(point.actual)}</span>
                    </div>
                )}
                {point.forecast != null && (
                    <div className="flex min-w-[180px] items-center justify-between gap-4">
                        <span className="flex items-center gap-2 text-white/75">
                            <span className="h-2 w-2 rounded-full bg-[#0071e3]" />
                            Forecast
                        </span>
                        <span className="font-semibold">{formatUnits(point.forecast)}</span>
                    </div>
                )}
                {point.lower_bound != null && point.upper_bound != null && (
                    <div className="flex min-w-[180px] items-center justify-between gap-4">
                        <span className="flex items-center gap-2 text-white/75">
                            <span className="h-2 w-2 rounded-full bg-[#8bbcff]" />
                            Forecast range
                        </span>
                        <span className="font-semibold">
                            {Math.round(point.lower_bound).toLocaleString()}-{Math.round(point.upper_bound).toLocaleString()}
                        </span>
                    </div>
                )}
            </div>
        </div>
    )
}

export default function ForecastChart({ data }: ForecastChartProps) {
    const chartData = data
        .map(point => ({
            ...point,
            range: point.lower_bound != null && point.upper_bound != null
                ? [point.lower_bound, point.upper_bound] as [number, number]
                : undefined,
        }))
        .sort((left, right) => left.date.localeCompare(right.date))

    return (
        <div className="card">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h3 className="text-lg font-semibold tracking-tight text-[#1d1d1f]">Demand Forecast</h3>
                    <p className="text-xs text-[#86868b] mt-1">Historical sales vs. forecast</p>
                </div>
            </div>

            <div className="h-[330px]">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 18, bottom: 20, left: 0 }}>
                    <defs>
                        <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#0071e3" stopOpacity={0.15} />
                            <stop offset="95%" stopColor="#0071e3" stopOpacity={0} />
                        </linearGradient>
                        <pattern id="confidencePattern" patternUnits="userSpaceOnUse" width="8" height="8">
                            <path d="M-2,2 l4,-4 M0,8 l8,-8 M6,10 l4,-4" stroke="#0071e3" strokeWidth="1" strokeOpacity={0.1} />
                        </pattern>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e5ea" vertical={false} />
                    <XAxis
                        dataKey="date"
                        tick={{ fill: '#86868b', fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={formatShortDate}
                        interval="preserveStartEnd"
                        minTickGap={42}
                        dy={8}
                    />
                    <YAxis
                        tick={{ fill: '#86868b', fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        width={44}
                    />
                    <Tooltip
                        content={<DemandTooltip />}
                        cursor={{ stroke: '#c7c7cc', strokeWidth: 1 }}
                    />

                    <Area
                        type="monotone"
                        dataKey="range"
                        stroke="none"
                        fill="#0071e3"
                        fillOpacity={0.1}
                        name="Forecast range"
                        connectNulls={false}
                        activeDot={false}
                    />

                    <Line
                        type="monotone"
                        dataKey="actual"
                        stroke="#34c759"
                        strokeWidth={2}
                        dot={false}
                        activeDot={{ r: 5, strokeWidth: 0, fill: '#34c759' }}
                        name="Historical sales"
                        connectNulls={false}
                    />

                    <Line
                        type="monotone"
                        dataKey="forecast"
                        stroke="#0071e3"
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{ r: 5, strokeWidth: 0, fill: '#0071e3' }}
                        name="Forecast"
                        connectNulls={false}
                    />
                </AreaChart>
            </ResponsiveContainer>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-center gap-5 text-xs font-medium text-[#6e6e73]">
                <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#34c759]" />Historical sales</span>
                <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#0071e3]" />Forecast</span>
                <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#8bbcff]" />Forecast range</span>
            </div>
        </div>
    )
}
