/**
 * KPI Stat Card component with Apple-style hover animation.
 */

import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { KpiData } from '@/lib/types'

const trendConfig = {
    up: { icon: TrendingUp, color: 'text-[#34c759]', bg: 'bg-[#34c759]/10' },
    down: { icon: TrendingDown, color: 'text-[#ff3b30]', bg: 'bg-[#ff3b30]/10' },
    flat: { icon: Minus, color: 'text-[#86868b]', bg: 'bg-[#86868b]/10' },
}

export default function KpiCard({ label, value, change, trend = 'flat', icon }: KpiData) {
    const { icon: TrendIcon, color, bg } = trendConfig[trend]

    return (
        <motion.div
            whileHover={{ y: -4, scale: 1.01 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            className="bg-white rounded-[24px] p-6 shadow-[0_4px_20px_rgba(0,0,0,0.03)] border border-black/[0.02]"
        >
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                    {icon && (
                        <div className="w-10 h-10 rounded-full bg-[#f5f5f7] flex items-center justify-center">
                            {icon}
                        </div>
                    )}
                </div>
                {change !== undefined && (
                    <div className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${bg} ${color}`}>
                        <TrendIcon className="h-3 w-3" />
                        {Math.abs(change)}%
                    </div>
                )}
            </div>
            <div className="mt-3">
                <p className="stat-label">{label}</p>
                <p className="stat-value mt-1">{value}</p>
            </div>
        </motion.div>
    )
}
