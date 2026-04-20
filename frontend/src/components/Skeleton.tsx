/**
 * Skeleton — Loading placeholder with shimmer animation.
 * Agent: full-stack-engineer | Skill: react-dashboard
 */

export function Skeleton({ className = '', style }: { className?: string; style?: React.CSSProperties }) {
    return (
        <div
            className={`animate-pulse rounded-lg bg-[#f5f5f7] ${className}`}
            style={style}
        />
    )
}

export function KpiSkeleton() {
    return (
        <div className="card border border-black/[0.02] rounded-[24px] shadow-sm p-4 space-y-3">
            <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-8 rounded-full" />
            </div>
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-3 w-32" />
        </div>
    )
}

export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
    return (
        <tr>
            {Array.from({ length: columns }).map((_, i) => (
                <td key={i} className="px-4 py-3">
                    <Skeleton className="h-4 w-full" />
                </td>
            ))}
        </tr>
    )
}

export function ChartSkeleton() {
    const heights = ['32%', '45%', '38%', '52%', '61%', '49%', '56%', '63%', '58%', '67%', '54%', '70%']
    return (
        <div className="card border border-black/[0.02] rounded-[24px] shadow-sm p-6 h-[350px] flex items-end gap-2">
            {heights.map((height, i) => (
                <Skeleton
                    key={i}
                    className="flex-1"
                    style={{ height }}
                />
            ))}
        </div>
    )
}
