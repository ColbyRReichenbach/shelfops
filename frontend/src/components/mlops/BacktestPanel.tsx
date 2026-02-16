import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts'
import type { BacktestPoint, ModelHistoryItem } from '@/lib/types'

interface BacktestPanelProps {
    history: ModelHistoryItem[]
    backtest: BacktestPoint[]
    selectedVersion: string | null
    onSelectVersion: (version: string) => void
    isLoadingHistory?: boolean
    isLoadingBacktest?: boolean
}

function fmtDate(value: string) {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return value
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function BacktestPanel({
    history,
    backtest,
    selectedVersion,
    onSelectVersion,
    isLoadingHistory = false,
    isLoadingBacktest = false,
}: BacktestPanelProps) {
    return (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div className="xl:col-span-2 card border border-white/40 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">Backtest Trend</h3>
                    <select
                        value={selectedVersion ?? ''}
                        onChange={(e) => onSelectVersion(e.target.value)}
                        className="rounded-lg border border-shelf-foreground/10 bg-white px-3 py-1.5 text-sm text-shelf-foreground"
                        disabled={isLoadingHistory || history.length === 0}
                    >
                        {history.length === 0 && <option value="">No versions</option>}
                        {history.map((h) => (
                            <option key={h.version} value={h.version}>
                                {h.version} ({h.status})
                            </option>
                        ))}
                    </select>
                </div>
                <div className="h-[280px]">
                    {isLoadingBacktest ? (
                        <div className="h-full flex items-center justify-center text-sm text-shelf-foreground/50">
                            Loading backtest...
                        </div>
                    ) : backtest.length > 0 ? (
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={backtest}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#000000" strokeOpacity={0.05} />
                                <XAxis
                                    dataKey="forecast_date"
                                    tickFormatter={fmtDate}
                                    tick={{ fill: '#4e5274', fontSize: 11, opacity: 0.7 }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <YAxis
                                    tick={{ fill: '#4e5274', fontSize: 11, opacity: 0.7 }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <Tooltip
                                    cursor={{ stroke: 'rgba(62,109,150,0.22)', strokeWidth: 1.5, strokeDasharray: '4 4' }}
                                    labelFormatter={(v) => fmtDate(String(v))}
                                    formatter={(value: number | string, key: string) => {
                                        const numeric = typeof value === 'number' ? value : Number(value)
                                        if (key === 'mape') return [`${((Number.isNaN(numeric) ? 0 : numeric) * 100).toFixed(2)}%`, 'MAPE']
                                        return [Number.isNaN(numeric) ? value : numeric.toFixed(3), 'MAE']
                                    }}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="mae"
                                    stroke="#3e6d96"
                                    strokeWidth={2}
                                    dot={false}
                                    isAnimationActive
                                    animationDuration={450}
                                    animationEasing="ease-out"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="mape"
                                    stroke="#5ba2b6"
                                    strokeWidth={2}
                                    dot={false}
                                    isAnimationActive
                                    animationDuration={450}
                                    animationEasing="ease-out"
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-full flex items-center justify-center text-sm text-shelf-foreground/40">
                            No backtest data available for selected version.
                        </div>
                    )}
                </div>
            </div>

            <div className="card border border-white/40 shadow-sm">
                <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider mb-4">Version History</h3>
                {isLoadingHistory ? (
                    <p className="text-sm text-shelf-foreground/50">Loading model history...</p>
                ) : history.length === 0 ? (
                    <p className="text-sm text-shelf-foreground/50">No model versions registered yet.</p>
                ) : (
                    <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                        {history.map((item) => (
                            <div
                                key={item.version}
                                className={`rounded-lg border px-3 py-2 cursor-pointer transition-colors ${
                                    selectedVersion === item.version
                                        ? 'border-shelf-primary/40 bg-shelf-primary/5'
                                        : 'border-shelf-foreground/10 hover:bg-shelf-secondary/10'
                                }`}
                                onClick={() => onSelectVersion(item.version)}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <span className="font-mono text-xs">{item.version}</span>
                                    <span className="text-[11px] text-shelf-foreground/60 uppercase">{item.status}</span>
                                </div>
                                <div className="text-xs text-shelf-foreground/60 mt-1">
                                    MAE {item.mae ?? '—'} · MAPE {item.mape ?? '—'}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
