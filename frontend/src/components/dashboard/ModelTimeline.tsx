/**
 * ModelTimeline — Sparkline chart showing MASE improvement over time.
 * WS-4 demo component. Uses hardcoded Summit Outdoor Supply data.
 */

import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceLine,
    ResponsiveContainer,
} from 'recharts'

interface MaseDataPoint {
    day: number
    label: string
    mase: number | null
    challenger: number | null
}

const MODEL_DATA: MaseDataPoint[] = [
    { day: 1, label: 'Day 1', mase: 0.95, challenger: null },
    { day: 30, label: 'Day 30', mase: 0.88, challenger: null },
    { day: 44, label: 'Day 44', mase: 0.71, challenger: null },
    { day: 52, label: 'Day 52', mase: 0.71, challenger: null },
    { day: 57, label: 'Day 57', mase: 0.71, challenger: 0.64 },
    { day: 95, label: 'Today', mase: 0.71, challenger: 0.64 },
]

interface CustomDotProps {
    cx?: number
    cy?: number
    payload?: MaseDataPoint
}

function ChampionDot({ cx = 0, cy = 0, payload }: CustomDotProps) {
    if (payload?.day === 44) {
        return (
            <g>
                <circle cx={cx} cy={cy} r={5} fill="#22c55e" stroke="#fff" strokeWidth={2} />
                <text x={cx} y={cy - 10} textAnchor="middle" fontSize={10} fill="#22c55e">
                    ★
                </text>
            </g>
        )
    }
    return <circle cx={cx} cy={cy} r={3} fill="#3e6d96" stroke="#fff" strokeWidth={1.5} />
}

function ChallengerDot({ cx = 0, cy = 0, payload }: CustomDotProps) {
    if (payload?.day === 57) {
        return (
            <g>
                <circle cx={cx} cy={cy} r={5} fill="#f97316" stroke="#fff" strokeWidth={2} />
                <text x={cx} y={cy - 10} textAnchor="middle" fontSize={10} fill="#f97316">
                    ●
                </text>
            </g>
        )
    }
    return <circle cx={cx} cy={cy} r={3} fill="#f97316" stroke="#fff" strokeWidth={1.5} />
}

export default function ModelTimeline() {
    return (
        <div className="card border border-white/40 shadow-sm">
            <div className="flex items-start justify-between mb-1">
                <div>
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">
                        Model Accuracy Over Time
                    </h3>
                    <p className="text-xs text-shelf-foreground/50 mt-0.5">
                        MASE improvement — lower is better
                    </p>
                </div>
                <div className="flex items-center gap-3 text-xs text-shelf-foreground/60">
                    <span className="flex items-center gap-1">
                        <span className="inline-block h-2 w-4 rounded" style={{ backgroundColor: '#3e6d96' }} />
                        Champion
                    </span>
                    <span className="flex items-center gap-1">
                        <span className="inline-block h-2 w-4 rounded" style={{ backgroundColor: '#f97316' }} />
                        Challenger
                    </span>
                </div>
            </div>

            <div className="h-[160px] mt-4">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={MODEL_DATA} margin={{ top: 16, right: 16, left: -20, bottom: 0 }}>
                        <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="#000"
                            strokeOpacity={0.05}
                            vertical={false}
                        />
                        <XAxis
                            dataKey="label"
                            tick={{ fill: '#4e5274', fontSize: 10, opacity: 0.6 }}
                            axisLine={false}
                            tickLine={false}
                            dy={6}
                        />
                        <YAxis
                            domain={[0.55, 1.0]}
                            tick={{ fill: '#4e5274', fontSize: 10, opacity: 0.6 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'rgba(255,255,255,0.95)',
                                border: '1px solid rgba(255,255,255,0.5)',
                                borderRadius: '8px',
                                fontSize: '11px',
                                color: '#4e5274',
                            }}
                            formatter={(value: number, name: string) => [
                                value.toFixed(2),
                                name === 'mase' ? 'Champion MASE' : 'Challenger MASE',
                            ]}
                        />
                        {/* Graduation milestone line */}
                        <ReferenceLine x="Day 44" stroke="#22c55e" strokeDasharray="4 2" strokeOpacity={0.5} />
                        {/* Shadow start line */}
                        <ReferenceLine x="Day 57" stroke="#f97316" strokeDasharray="4 2" strokeOpacity={0.5} />

                        <Line
                            type="monotone"
                            dataKey="mase"
                            stroke="#3e6d96"
                            strokeWidth={2}
                            dot={<ChampionDot />}
                            connectNulls={false}
                            name="mase"
                        />
                        <Line
                            type="monotone"
                            dataKey="challenger"
                            stroke="#f97316"
                            strokeWidth={2}
                            strokeDasharray="5 3"
                            dot={<ChallengerDot />}
                            connectNulls={false}
                            name="challenger"
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>

            <div className="mt-3 flex items-center gap-4 text-xs text-shelf-foreground/60 border-t border-shelf-foreground/5 pt-3">
                <span>
                    <span className="text-green-600 font-medium">★ Day 44</span> — Champion promoted
                </span>
                <span>
                    <span className="text-orange-500 font-medium">● Day 57</span> — Shadow phase started
                </span>
            </div>
        </div>
    )
}
