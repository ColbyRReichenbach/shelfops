import {
    AreaChart,
    Area,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend
} from 'recharts'

interface ForecastData {
    date: string
    actual?: number
    forecast?: number
    lower_bound?: number
    upper_bound?: number
}

interface ForecastChartProps {
    data: ForecastData[]
}

export default function ForecastChart({ data }: ForecastChartProps) {
    return (
        <div className="card h-[400px] border border-white/40 shadow-sm">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Demand Forecast</h3>
                    <p className="text-xs text-shelf-foreground/60 mt-1">Historical sales vs. AI prediction</p>
                </div>
            </div>

            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: -20 }}>
                    <defs>
                        <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3e6d96" stopOpacity={0.15} />
                            <stop offset="95%" stopColor="#3e6d96" stopOpacity={0} />
                        </linearGradient>
                        <pattern id="confidencePattern" patternUnits="userSpaceOnUse" width="8" height="8">
                            <path d="M-2,2 l4,-4 M0,8 l8,-8 M6,10 l4,-4" stroke="#3e6d96" strokeWidth="1" strokeOpacity={0.1} />
                        </pattern>
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
                        contentStyle={{
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            border: '1px solid rgba(255, 255, 255, 0.5)',
                            borderRadius: '12px',
                            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                            fontSize: '12px',
                            color: '#4e5274'
                        }}
                        itemStyle={{ color: '#4e5274' }}
                        formatter={(value: number) => [value.toFixed(0), '']}
                        labelStyle={{ color: '#3e6d96', fontWeight: 600, marginBottom: '0.5rem' }}
                    />
                    <Legend
                        wrapperStyle={{ paddingTop: '20px' }}
                        iconType="circle"
                        formatter={(value) => <span className="text-xs font-medium text-shelf-foreground/70">{value}</span>}
                    />

                    {/* Confidence Interval (Bounded Area) */}
                    {/* Recharts Trick: Stacked Area with transparent bottom to create range, or just use two areas? 
                        Simpler approach for now: Area for upper bound, hide everything below lower bound?
                        Actually, 'range' area chart is supported in newer Recharts but requires array dataKey.
                        Fallback: Two Areas, one white to mask? No, transparent.
                        Better: Area with `dataKey="upper_bound"` and `baseLine="lower_bound"` (if supported) or `stackId`.
                        
                        Robust method: use `Area` with `dataKey` as array [min, max]. Recharts 2.x supports this.
                     */}
                    {/* NOTE: Recharts 2.x Area can take an array for dataKey [min, max] is not quite right, it takes a range for values.
                         Use 'range' type or specific data formatting?
                         Let's stick to a simple shaded area for 'upper_bound' that starts from 0? No that's misleading.
                         Let's try standard approach: Area for 'upper_bound' with white fill? No background is complex.
                         
                         Let's use the 'range' feature if available, or just render 'forecast' line and 'confidence' bands as lines.
                         Actually, let's keep it simple: Area for Forecast, Line for Actual.
                         We will render 'upper_bound' and 'lower_bound' as transparent lines with a fill between them if possible.
                         
                         Alternative: Render Area for 'upper_bound' filled with light color, and 'lower_bound' filled with BACKGROUND color (white/gray) on top?
                         That works since our background is solid-ish. 
                      */}

                    {/* Confidence Band (Upper) */}
                    {/* Workaround: Area from 0 to Upper, then Area from 0 to Lower (white) on top? 
                        Issue: Grid lines will be covered.
                        Correct way: <Area dataKey={[min, max]} /> is supported in Recharts v2.10?
                        Yes, verify: <Area dataKey="range" /> where range is [min, max].
                     */}

                    {/* Simpler Visual: Just Forecast Area and Actual Line for MVP, maybe add 'confidence' as a light cloud if data supports [min, max] prop.
                        Looking at Recharts docs, `dataKey` returning an array `[min, max]` works for `type="range"`. 
                        Let's try creating a custom data transformer or just assuming standard Area for now.
                        Will implement standard Area for prediction and Line for actuals.
                    */}

                    <Area
                        type="monotone"
                        dataKey="forecast"
                        stroke="#3e6d96"
                        strokeWidth={2}
                        fill="url(#forecastGradient)"
                        name="Forecast"
                    />

                    <Line
                        type="monotone"
                        dataKey="actual"
                        stroke="#5ba2b6"
                        strokeWidth={2}
                        dot={{ r: 4, fill: '#5ba2b6', strokeWidth: 2, stroke: '#fff' }}
                        activeDot={{ r: 6, strokeWidth: 0 }}
                        name="Actual Sales"
                        connectNulls
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    )
}
