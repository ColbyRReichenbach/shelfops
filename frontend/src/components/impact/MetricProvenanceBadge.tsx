interface MetricProvenanceBadgeProps {
    label: string
    tone?: 'measured' | 'estimated' | 'provisional' | 'simulated' | 'neutral'
}

export default function MetricProvenanceBadge({
    label,
    tone = 'neutral',
}: MetricProvenanceBadgeProps) {
    const classes = tone === 'measured'
        ? 'bg-[#34c759]/10 text-[#1f8f45]'
        : tone === 'estimated'
            ? 'bg-[#0071e3]/10 text-[#0071e3]'
            : tone === 'provisional'
                ? 'bg-[#ffcc00]/20 text-[#8a6a00]'
                : tone === 'simulated'
                    ? 'bg-[#1d1d1f] text-white'
                    : 'bg-[#f5f5f7] text-[#1d1d1f]'

    return (
        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${classes}`}>
            {label}
        </span>
    )
}
