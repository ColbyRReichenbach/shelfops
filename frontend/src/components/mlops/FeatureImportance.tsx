/**
 * FeatureImportance — SHAP bar chart showing top features.
 */

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Loader2, Sparkles } from 'lucide-react'
import type { SHAPFeature } from '@/lib/types'

function formatFeatureName(name: string): string {
    return name
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase())
        .replace('Lag ', 'Lag-')
        .replace('Rolling ', 'Roll-')
}

export default function FeatureImportance({
    features,
    isLoading,
    version,
}: {
    features: SHAPFeature[]
    isLoading: boolean
    version: string
}) {
    if (isLoading) {
        return (
            <div className="card border border-white/40 shadow-sm text-center py-16">
                <Loader2 className="h-8 w-8 mx-auto mb-3 text-shelf-primary animate-spin" />
                <p className="text-sm text-shelf-foreground/60">Loading feature importance...</p>
            </div>
        )
    }

    if (features.length === 0) {
        return (
            <div className="card border border-white/40 shadow-sm text-center py-16">
                <Sparkles className="h-8 w-8 mx-auto mb-3 text-shelf-foreground/30" />
                <p className="text-sm text-shelf-foreground/50">No SHAP data available</p>
                <p className="text-xs text-shelf-foreground/40 mt-1">Train a model to generate feature importance</p>
            </div>
        )
    }

    const chartData = features.slice(0, 12).map(f => ({
        name: formatFeatureName(f.name),
        importance: Number((f.importance * 100).toFixed(1)),
    }))

    return (
        <div className="card border border-white/40 shadow-sm p-4">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-shelf-foreground">SHAP Feature Importance</h3>
                <span className="text-xs text-shelf-foreground/50 font-mono">{version}</span>
            </div>
            <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 32)}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 100 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11 }} stroke="rgba(0,0,0,0.3)" />
                    <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 11 }}
                        stroke="rgba(0,0,0,0.3)"
                        width={100}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: 'white',
                            borderRadius: '8px',
                            border: '1px solid rgba(0,0,0,0.1)',
                            fontSize: '12px',
                        }}
                        formatter={(value: number) => [`${value}%`, 'Importance']}
                    />
                    <Bar dataKey="importance" fill="#6366f1" radius={[0, 4, 4, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    )
}
