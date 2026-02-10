/**
 * KPI Stat Card component with trend indicator.
 */

import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { KpiData } from '@/lib/types'

const trendConfig = {
    up: { icon: TrendingUp, color: 'text-green-600', bg: 'bg-green-100' },
    down: { icon: TrendingDown, color: 'text-red-600', bg: 'bg-red-100' },
    flat: { icon: Minus, color: 'text-shelf-foreground/50', bg: 'bg-shelf-foreground/5' },
}

export default function KpiCard({ label, value, change, trend = 'flat' }: KpiData) {
    const { icon: TrendIcon, color, bg } = trendConfig[trend]

    return (
        <div className="card group animate-fade-in">
            <div className="flex items-start justify-between">
                <div>
                    <p className="stat-label">{label}</p>
                    <p className="stat-value mt-1">{value}</p>
                </div>
                {change !== undefined && (
                    <div className={`flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${bg} ${color}`}>
                        <TrendIcon className="h-3 w-3" />
                        {Math.abs(change)}%
                    </div>
                )}
            </div>
        </div>
    )
}
