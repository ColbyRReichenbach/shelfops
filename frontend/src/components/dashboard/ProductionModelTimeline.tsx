import { Loader2, TrendingUp } from 'lucide-react'
import {
    CartesianGrid,
    Legend,
    Line,
    LineChart,
    ReferenceDot,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts'

import { useModelHistory } from '@/hooks/useShelfOps'

export default function ProductionModelTimeline() {
    const { data: history = [], isLoading } = useModelHistory(12)

    if (isLoading) {
        return (
            <div className="card border border-white/40 shadow-sm p-8 text-center">
                <Loader2 className="mx-auto h-6 w-6 animate-spin text-shelf-primary" />
                <p className="mt-2 text-sm text-shelf-foreground/60">Loading model history...</p>
            </div>
        )
    }

    const chartData = [...history]
        .reverse()
        .map((entry, index) => ({
            point: index + 1,
            version: entry.version,
            mase: entry.mase,
            wape: entry.wape != null ? entry.wape * 100 : null,
            status: entry.status,
        }))

    if (chartData.length === 0) {
        return null
    }

    return (
        <div className="card border border-white/40 shadow-sm">
            <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                    <h3 className="text-sm font-semibold uppercase tracking-wider text-shelf-primary">
                        Model Performance Timeline
                    </h3>
                    <p className="mt-1 text-xs text-shelf-foreground/55">
                        Runtime model-history view from champion, challenger, and archived versions.
                    </p>
                </div>
                <div className="inline-flex items-center gap-2 rounded-full bg-shelf-primary/10 px-3 py-1 text-xs font-medium text-shelf-primary">
                    <TrendingUp className="h-3.5 w-3.5" />
                    {chartData.length} recorded versions
                </div>
            </div>

            <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 12, right: 16, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#000" strokeOpacity={0.05} vertical={false} />
                        <XAxis
                            dataKey="version"
                            tick={{ fill: '#4e5274', fontSize: 10, opacity: 0.7 }}
                            axisLine={false}
                            tickLine={false}
                            dy={8}
                        />
                        <YAxis
                            yAxisId="mase"
                            tick={{ fill: '#4e5274', fontSize: 10, opacity: 0.7 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis
                            yAxisId="wape"
                            orientation="right"
                            tick={{ fill: '#4e5274', fontSize: 10, opacity: 0.45 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'rgba(255,255,255,0.95)',
                                border: '1px solid rgba(255,255,255,0.5)',
                                borderRadius: '12px',
                                boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                                fontSize: '12px',
                                color: '#4e5274',
                            }}
                        />
                        <Legend
                            wrapperStyle={{ paddingTop: '18px' }}
                            formatter={(value) => <span className="text-xs font-medium text-shelf-foreground/70">{value}</span>}
                        />
                        <Line
                            yAxisId="mase"
                            type="monotone"
                            dataKey="mase"
                            stroke="#3e6d96"
                            strokeWidth={2}
                            dot={{ r: 3, fill: '#3e6d96' }}
                            connectNulls={false}
                            name="MASE"
                        />
                        <Line
                            yAxisId="wape"
                            type="monotone"
                            dataKey="wape"
                            stroke="#5ba2b6"
                            strokeWidth={2}
                            strokeDasharray="5 4"
                            dot={{ r: 3, fill: '#5ba2b6' }}
                            connectNulls={false}
                            name="WAPE %"
                        />
                        {chartData.map((entry) =>
                            entry.status === 'champion' ? (
                                <ReferenceDot
                                    key={`${entry.version}-champion`}
                                    yAxisId="mase"
                                    x={entry.version}
                                    y={entry.mase ?? undefined}
                                    r={5}
                                    fill="#22c55e"
                                    stroke="#fff"
                                />
                            ) : null
                        )}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    )
}
