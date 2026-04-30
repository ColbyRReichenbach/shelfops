import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Loader2, Sparkles } from 'lucide-react'
import type { ModelDriverFeature } from '@/lib/types'

function formatFeatureName(name: string): string {
    return name
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase())
        .replace('Lag ', 'Lag-')
        .replace('Rolling ', 'Roll-')
}

interface DriverTooltipPayload {
    payload: {
        name: string
        importance: number
    }
}

function DriverTooltip({
    active,
    payload,
}: {
    active?: boolean
    payload?: DriverTooltipPayload[]
}) {
    if (!active || !payload?.length) return null
    const point = payload[0]?.payload
    if (!point) return null

    return (
        <div className="rounded-[10px] border border-white/10 bg-[#1d1d1f]/90 px-3 py-2 text-xs text-white shadow-lg backdrop-blur">
            <p className="mb-2 font-semibold">{point.name}</p>
            <div className="flex min-w-[160px] items-center justify-between gap-4">
                <span className="text-white/75">Importance</span>
                <span className="font-semibold">{point.importance.toFixed(1)}%</span>
            </div>
        </div>
    )
}

export default function FeatureImportance({
    features,
    isLoading,
    version,
}: {
    features: ModelDriverFeature[]
    isLoading: boolean
    version: string
}) {
    if (isLoading) {
        return (
            <div className="card border border-black/[0.02] shadow-sm text-center py-16">
                <Loader2 className="h-8 w-8 mx-auto mb-3 text-[#0071e3] animate-spin" />
                <p className="text-sm text-[#86868b]">Loading feature importance...</p>
            </div>
        )
    }

    if (features.length === 0) {
        return (
            <div className="card border border-black/[0.02] shadow-sm text-center py-16">
                <Sparkles className="h-8 w-8 mx-auto mb-3 text-[#86868b]" />
                <p className="text-sm text-[#86868b]">No model-driver data available</p>
                <p className="text-xs text-[#86868b] mt-1">Model-driver evidence will appear after a registered run stores the artifact metadata.</p>
            </div>
        )
    }

    const chartData = features.slice(0, 12).map(f => ({
        name: formatFeatureName(f.name),
        importance: Number((f.importance * 100).toFixed(1)),
    }))

    return (
        <div className="card border border-black/[0.02] shadow-sm p-4">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-[#1d1d1f]">Model Drivers</h3>
                <span className="text-xs text-[#86868b] font-mono">{version}</span>
            </div>
            <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 32)}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 100 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e5ea" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: '#86868b' }} stroke="rgba(0,0,0,0.3)" />
                    <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 11, fill: '#86868b' }}
                        stroke="rgba(0,0,0,0.3)"
                        width={100}
                    />
                    <Tooltip content={<DriverTooltip />} cursor={{ fill: 'rgba(0,0,0,0.02)' }} />
                    <Bar dataKey="importance" fill="#0071e3" radius={[0, 4, 4, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    )
}
