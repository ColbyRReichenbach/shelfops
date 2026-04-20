import { AlertTriangle, Clock3, DatabaseBackup, ShieldX } from 'lucide-react'

import type { DataReadiness, SyncHealth } from '@/lib/types'

interface DataQualityEventsProps {
    readiness: DataReadiness | undefined
    sources: SyncHealth[]
}

export default function DataQualityEvents({ readiness, sources }: DataQualityEventsProps) {
    const issues = buildIssues(readiness, sources)

    return (
        <section className="card space-y-4">
            <div>
                <h2 className="text-lg font-semibold text-[#1d1d1f]">Data Health Alerts</h2>
                <p className="mt-2 text-sm text-[#6e6e73]">
                    These issues can limit forecast quality, replenishment accuracy, or integration reliability.
                </p>
            </div>

            {issues.length === 0 ? (
                <div className="rounded-[20px] bg-[#34c759]/10 px-4 py-4 text-sm text-[#1f8f45]">
                    No active data-readiness or integration issues were returned by the current API responses.
                </div>
            ) : (
                <div className="space-y-3">
                    {issues.map(issue => (
                        <div
                            key={issue.title}
                            className={`rounded-[20px] border px-4 py-4 ${
                                issue.severity === 'high'
                                    ? 'border-[#ff3b30]/20 bg-[#ff3b30]/5'
                                    : issue.severity === 'medium'
                                        ? 'border-[#ffcc00]/30 bg-[#ffcc00]/10'
                                        : 'border-black/[0.04] bg-[#f5f5f7]'
                            }`}
                        >
                            <div className="flex items-start gap-3">
                                <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-2xl bg-white">
                                    <issue.icon className="h-4 w-4 text-[#1d1d1f]" />
                                </div>
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <p className="text-sm font-semibold text-[#1d1d1f]">{issue.title}</p>
                                        <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#86868b]">
                                            {issue.severity}
                                        </span>
                                    </div>
                                    <p className="mt-2 text-sm text-[#6e6e73]">{issue.body}</p>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </section>
    )
}

function buildIssues(readiness: DataReadiness | undefined, sources: SyncHealth[]) {
    const issues: Array<{
        title: string
        body: string
        severity: 'high' | 'medium' | 'low'
        icon: typeof AlertTriangle
    }> = []

    if (readiness?.state === 'cold_start') {
        issues.push({
            title: 'Limited history available',
            body: 'The account is still below the minimum history or catalog thresholds, so forecasts and recommendations may be less stable.',
            severity: 'high',
            icon: DatabaseBackup,
        })
    } else if (readiness?.state === 'warming') {
        issues.push({
            title: 'Recent validation still building',
            body: 'There is enough source history to forecast, but recent performance checks are still limited.',
            severity: 'medium',
            icon: AlertTriangle,
        })
    }

    for (const source of sources) {
        if (source.sla_status === 'breach') {
            issues.push({
                title: `${source.integration_name} freshness breach`,
                body: `This source is beyond its freshness target (${source.sla_hours}h), which can weaken recommendation quality and delay timely decisions.`,
                severity: 'medium',
                icon: Clock3,
            })
        }

        if (source.integration_name === 'Square POS' && !source.mapping_confirmed) {
            issues.push({
                title: 'Square mapping not confirmed',
                body: 'Square mappings still need review before sales and catalog records can be trusted end to end.',
                severity: 'high',
                icon: ShieldX,
            })
        }

        const unmappedCount = (source.unmapped_location_ids?.length ?? 0) + (source.unmapped_catalog_ids?.length ?? 0)
        if (unmappedCount > 0) {
            issues.push({
                title: `${source.integration_name} unmapped IDs`,
                body: `${unmappedCount} external IDs are still unmapped. They will stay out of planning and replenishment views until mapping is complete.`,
                severity: 'medium',
                icon: ShieldX,
            })
        }
    }

    return issues
}
