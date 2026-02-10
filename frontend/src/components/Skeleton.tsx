/**
 * Skeleton — Loading placeholder with shimmer animation.
 * Agent: full-stack-engineer | Skill: react-dashboard
 */

export function Skeleton({ className = '', style }: { className?: string; style?: React.CSSProperties }) {
    return (
        <div
            className={`animate-pulse rounded-lg bg-shelf-foreground/[0.06] ${className}`}
            style={style}
        />
    )
}

export function KpiSkeleton() {
    return (
        <div className="card border border-white/40 shadow-sm p-4 space-y-3">
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
    return (
        <div className="card border border-white/40 shadow-sm p-6 h-[350px] flex items-end gap-2">
            {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton
                    key={i}
                    className="flex-1"
                    style={{ height: `${30 + Math.random() * 60}%` }}
                />
            ))}
        </div>
    )
}
