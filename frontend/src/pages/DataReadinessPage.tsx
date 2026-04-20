import { DatabaseZap, ShieldCheck, TimerReset } from 'lucide-react'

import DataQualityEvents from '@/components/data/DataQualityEvents'
import DataReadinessSummary from '@/components/data/DataReadinessSummary'
import MappingCoverageTable from '@/components/data/MappingCoverageTable'
import { useDataReadiness, useSyncHealth } from '@/hooks/useShelfOps'
import { getApiErrorDetail } from '@/lib/api'

export default function DataReadinessPage() {
    const readinessQuery = useDataReadiness()
    const syncHealthQuery = useSyncHealth()

    const readiness = readinessQuery.data
    const sources = syncHealthQuery.data ?? []
    const snapshot = readiness?.snapshot ?? {}

    return (
        <div className="page-shell">
            <div className="hero-panel hero-panel-green">
                <div className="max-w-3xl">
                    <div className="hero-chip text-[#1f8f45]">
                        <DatabaseZap className="h-3.5 w-3.5" />
                        Data Readiness
                    </div>
                    <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">
                        Make sure your data is ready to support planning.
                    </h1>
                    <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                        Track history, catalog coverage, mappings, and freshness in one place so data issues are fixed before they affect forecasts or replenishment decisions.
                    </p>
                </div>

                <div className="mt-8 grid gap-4 md:grid-cols-3">
                    <HeroStat
                        icon={TimerReset}
                        label="History"
                        value={`${snapshot.history_days ?? 0}d`}
                        detail="Observed transaction span"
                    />
                    <HeroStat
                        icon={ShieldCheck}
                        label="State"
                        value={readiness?.state?.replace(/_/g, ' ') ?? 'not started'}
                        detail={readiness?.reason_code ?? 'no readiness state'}
                    />
                    <HeroStat
                        icon={DatabaseZap}
                        label="Sources"
                        value={String(sources.length)}
                        detail="Active sync sources monitored"
                    />
                </div>
            </div>

            {readinessQuery.isError ? (
                <div className="card border border-[#ff3b30]/20 bg-[#ff3b30]/5 p-12 text-center text-sm text-[#c9342a]">
                    {getApiErrorDetail(readinessQuery.error, 'Failed to load data readiness.')}
                </div>
            ) : readinessQuery.isLoading ? (
                <div className="card p-12 text-center text-sm text-[#86868b]">Loading data readiness…</div>
            ) : (
                <DataReadinessSummary readiness={readiness} />
            )}

            <MappingCoverageTable sources={sources} />
            <DataQualityEvents readiness={readiness} sources={sources} />
        </div>
    )
}

function HeroStat({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof TimerReset
    label: string
    value: string
    detail: string
}) {
    return (
        <div className="hero-stat-card">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                <Icon className="h-5 w-5 text-[#1d1d1f]" />
            </div>
            <p className="mt-4 text-sm font-medium text-[#86868b]">{label}</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f] capitalize">{value}</p>
            <p className="mt-2 text-xs text-[#6e6e73]">{detail}</p>
        </div>
    )
}
