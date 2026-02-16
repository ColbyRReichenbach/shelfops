interface PurchaseOrderSummaryCardsProps {
    openRecommendations: number
    approvedToday: number
    suggestedSpend: number
    receivedThisWeek: number
}

export default function PurchaseOrderSummaryCards({
    openRecommendations,
    approvedToday,
    suggestedSpend,
    receivedThisWeek,
}: PurchaseOrderSummaryCardsProps) {
    return (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <SummaryCard label="Open Reorder Recs" value={String(openRecommendations)} />
            <SummaryCard label="Approved Today" value={String(approvedToday)} />
            <SummaryCard label="Suggested Spend" value={`$${suggestedSpend.toFixed(2)}`} />
            <SummaryCard label="Received (7d)" value={String(receivedThisWeek)} />
        </div>
    )
}

function SummaryCard({ label, value }: { label: string; value: string }) {
    return (
        <div className="card border border-white/40 shadow-sm p-4">
            <p className="text-xs uppercase tracking-wider text-shelf-foreground/50">{label}</p>
            <p className="text-2xl font-bold text-shelf-primary mt-2">{value}</p>
        </div>
    )
}
