/**
 * DataHealthDashboard — compact integration freshness summary for the model evidence rail.
 */

import {
    CheckCircle2,
    Database,
    Loader2,
    AlertTriangle,
    Clock3,
    Activity,
    Wifi,
    WifiOff,
} from 'lucide-react'

import type { SyncHealth } from '@/lib/types'

const INTEGRATION_ACCENTS: Record<string, string> = {
    CSV: 'bg-[#0071e3]/10 text-[#0071e3]',
    POS: 'bg-[#34c759]/10 text-[#1f8f45]',
    EDI: 'bg-[#5856d6]/10 text-[#5856d6]',
    SFTP: 'bg-[#ff9500]/10 text-[#b36a00]',
    Kafka: 'bg-[#ff9500]/10 text-[#b36a00]',
}

export default function DataHealthDashboard({
    syncData,
    isLoading,
}: {
    syncData: SyncHealth[]
    isLoading: boolean
}) {
    if (isLoading) {
        return (
            <div className="rounded-[20px] border border-black/[0.04] bg-[#fbfbfd] px-5 py-14 text-center">
                <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-[#0071e3]" />
                <p className="text-sm text-[#86868b]">Loading data health...</p>
            </div>
        )
    }

    if (syncData.length === 0) {
        return (
            <div className="rounded-[20px] border border-black/[0.04] bg-[#fbfbfd] px-5 py-14 text-center">
                <Database className="mx-auto mb-3 h-8 w-8 text-[#86868b]" />
                <p className="text-sm text-[#86868b]">No integration data available.</p>
            </div>
        )
    }

    const totalSyncs = syncData.reduce((sum, source) => sum + source.syncs_24h, 0)
    const latestRecords = syncData.reduce((sum, source) => sum + source.records_24h, 0)
    const slaOkCount = syncData.filter(source => source.sla_status === 'ok').length
    const slaRate = syncData.length > 0 ? (slaOkCount / syncData.length) * 100 : 100

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <SummaryTile label="Sources" value={String(syncData.length)} detail="active feeds" icon={Database} />
                <SummaryTile label="24h Syncs" value={totalSyncs.toLocaleString()} detail={`${latestRecords.toLocaleString()} records`} icon={Activity} />
                <SummaryTile
                    label="SLA" value={`${slaRate.toFixed(1)}%`}
                    detail={slaOkCount === syncData.length ? 'all sources in window' : `${slaOkCount}/${syncData.length} sources in window`}
                    icon={Clock3}
                    tone={slaRate >= 99 ? 'good' : slaRate >= 95 ? 'warn' : 'bad'}
                />
            </div>

            <div className="space-y-3">
                {syncData.map(source => {
                    const accent = INTEGRATION_ACCENTS[source.integration_type] ?? 'bg-[#f5f5f7] text-[#86868b]'
                    const failRate = source.syncs_24h > 0 ? (source.failures_24h / source.syncs_24h) * 100 : 0
                    const healthTone = source.sla_status === 'ok' ? 'text-[#1f8f45]' : 'text-[#c9342a]'
                    const HealthIcon = source.sla_status === 'ok' ? Wifi : WifiOff

                    return (
                        <div
                            key={`${source.integration_type}-${source.integration_name}`}
                            className="rounded-[20px] border border-black/[0.04] bg-[#fbfbfd] p-4"
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                    <div className="flex items-center gap-3">
                                        <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${accent}`}>
                                            {source.integration_type}
                                        </span>
                                        <p className="truncate text-sm font-semibold text-[#1d1d1f]">{source.integration_name}</p>
                                    </div>
                                    <p className="mt-2 text-xs text-[#6e6e73]">
                                        Last sync {formatLastSync(source.last_sync)} · SLA window {source.sla_hours}h
                                    </p>
                                </div>

                                <div className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
                                    source.sla_status === 'ok' ? 'bg-[#34c759]/10 text-[#1f8f45]' : 'bg-[#ff3b30]/10 text-[#c9342a]'
                                }`}>
                                    <HealthIcon className={`h-3.5 w-3.5 ${healthTone}`} />
                                    {source.sla_status === 'ok' ? 'Healthy' : 'Attention'}
                                </div>
                            </div>

                            <div className="mt-4 grid grid-cols-2 gap-3">
                                <SourceMetric label="Syncs 24h" value={source.syncs_24h.toLocaleString()} />
                                <SourceMetric label="Records 24h" value={source.records_24h.toLocaleString()} />
                                <SourceMetric label="Failures" value={source.failures_24h.toLocaleString()} tone={source.failures_24h > 0 ? 'warn' : 'neutral'} />
                                <SourceMetric
                                    label="Fail rate"
                                    value={`${failRate.toFixed(1)}%`}
                                    tone={failRate > 5 ? 'bad' : failRate > 0 ? 'warn' : 'good'}
                                />
                            </div>

                            {(source.mapping_confirmed !== undefined || source.unmapped_location_ids?.length || source.unmapped_catalog_ids?.length) && (
                                <div className="mt-4 flex flex-wrap gap-2">
                                    {source.mapping_confirmed !== undefined && (
                                        <StatusPill
                                            tone={source.mapping_confirmed ? 'good' : 'warn'}
                                            label={source.mapping_confirmed ? 'Mapping confirmed' : 'Mapping review needed'}
                                        />
                                    )}
                                    {(source.unmapped_location_ids?.length ?? 0) > 0 && (
                                        <StatusPill tone="warn" label={`${source.unmapped_location_ids?.length} unmapped locations`} />
                                    )}
                                    {(source.unmapped_catalog_ids?.length ?? 0) > 0 && (
                                        <StatusPill tone="warn" label={`${source.unmapped_catalog_ids?.length} unmapped catalog ids`} />
                                    )}
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

function SummaryTile({
    label,
    value,
    detail,
    icon: Icon,
    tone = 'neutral',
}: {
    label: string
    value: string
    detail: string
    icon: typeof Database
    tone?: 'neutral' | 'good' | 'warn' | 'bad'
}) {
    const toneClass = tone === 'good'
        ? 'text-[#1f8f45]'
        : tone === 'warn'
            ? 'text-[#b36a00]'
            : tone === 'bad'
                ? 'text-[#c9342a]'
                : 'text-[#1d1d1f]'

    return (
        <div className="rounded-[20px] border border-black/[0.04] bg-[#fbfbfd] p-4">
            <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-white shadow-[0_2px_10px_rgba(0,0,0,0.04)]">
                    <Icon className="h-4 w-4 text-[#0071e3]" />
                </div>
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#86868b]">{label}</p>
            </div>
            <p className={`mt-4 text-2xl font-semibold tracking-tight ${toneClass}`}>{value}</p>
            <p className="mt-1 text-xs text-[#86868b]">{detail}</p>
        </div>
    )
}

function SourceMetric({
    label,
    value,
    tone = 'neutral',
}: {
    label: string
    value: string
    tone?: 'neutral' | 'good' | 'warn' | 'bad'
}) {
    const toneClass = tone === 'good'
        ? 'text-[#1f8f45]'
        : tone === 'warn'
            ? 'text-[#b36a00]'
            : tone === 'bad'
                ? 'text-[#c9342a]'
                : 'text-[#1d1d1f]'

    return (
        <div className="rounded-[16px] bg-white px-3 py-3 shadow-[0_2px_10px_rgba(0,0,0,0.03)]">
            <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[#86868b]">{label}</p>
            <p className={`mt-2 text-sm font-semibold ${toneClass}`}>{value}</p>
        </div>
    )
}

function StatusPill({
    label,
    tone,
}: {
    label: string
    tone: 'good' | 'warn'
}) {
    return (
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${
            tone === 'good' ? 'bg-[#34c759]/10 text-[#1f8f45]' : 'bg-[#ff9500]/10 text-[#b36a00]'
        }`}>
            {tone === 'good' ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
            {label}
        </span>
    )
}

function formatLastSync(value: string | null) {
    if (!value) return 'unknown'
    return new Date(value).toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    })
}
