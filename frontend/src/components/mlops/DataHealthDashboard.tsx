/**
 * DataHealthDashboard — Integration sync status + SLA badges.
 */

import { Database, Wifi, WifiOff, Loader2, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react'
import type { SyncHealth } from '@/lib/types'

const INTEGRATION_ICONS: Record<string, { icon: string; color: string }> = {
    POS: { icon: 'POS', color: 'bg-[#34c759]/10 text-[#34c759]' },
    EDI: { icon: 'EDI', color: 'bg-[#0071e3]/10 text-[#0071e3]' },
    SFTP: { icon: 'SFTP', color: 'bg-[#5856d6]/10 text-[#5856d6]' },
    Kafka: { icon: 'KFK', color: 'bg-[#ff9500]/10 text-[#ff9500]' },
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
            <div className="card border border-black/[0.02] shadow-sm text-center py-16">
                <Loader2 className="h-8 w-8 mx-auto mb-3 text-[#0071e3] animate-spin" />
                <p className="text-sm text-[#86868b]">Loading data health...</p>
            </div>
        )
    }

    if (syncData.length === 0) {
        return (
            <div className="card border border-black/[0.02] shadow-sm text-center py-16">
                <Database className="h-8 w-8 mx-auto mb-3 text-[#86868b]" />
                <p className="text-sm text-[#86868b]">No integration data available</p>
                <p className="text-xs text-[#86868b] mt-1">Run seed_integration_history.py to populate</p>
            </div>
        )
    }

    const totalSyncs = syncData.reduce((sum, s) => sum + s.syncs_24h, 0)
    const slaOkCount = syncData.filter((s) => s.sla_status === 'ok').length
    const slaRate = syncData.length > 0 ? (slaOkCount / syncData.length) * 100 : 100

    return (
        <div className="space-y-4">
            {/* Overview KPIs */}
            <div className="grid grid-cols-3 gap-4">
                <div className="card border border-black/[0.02] shadow-sm p-4">
                    <p className="text-xs font-medium text-[#86868b] uppercase tracking-wider">Data Sources</p>
                    <p className="text-2xl font-bold text-[#0071e3] mt-1">{syncData.length}</p>
                </div>
                <div className="card border border-black/[0.02] shadow-sm p-4">
                    <p className="text-xs font-medium text-[#86868b] uppercase tracking-wider">24h Syncs</p>
                    <p className="text-2xl font-bold text-[#1d1d1f] mt-1">{totalSyncs.toLocaleString()}</p>
                </div>
                <div className="card border border-black/[0.02] shadow-sm p-4">
                    <p className="text-xs font-medium text-[#86868b] uppercase tracking-wider">SLA Rate</p>
                    <p className={`text-2xl font-bold mt-1 ${slaRate >= 99 ? 'text-[#34c759]' : slaRate >= 95 ? 'text-[#b38f00]' : 'text-[#ff3b30]'}`}>
                        {slaRate.toFixed(1)}%
                    </p>
                </div>
            </div>

            {/* Per-source cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {syncData.map((source) => {
                    const config = INTEGRATION_ICONS[source.integration_type] ?? { icon: '?', color: 'bg-[#f5f5f7] text-[#86868b]' }
                    const isOnline = source.sla_status === 'ok'
                    const failRate = source.syncs_24h > 0
                        ? (source.failures_24h / source.syncs_24h * 100)
                        : 0

                    return (
                        <div key={`${source.integration_type}-${source.integration_name}`} className="card border border-black/[0.02] shadow-sm p-4">
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-3">
                                    <div className={`h-10 w-10 rounded-lg ${config.color} flex items-center justify-center text-xs font-bold`}>
                                        {config.icon}
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-[#1d1d1f]">{source.integration_name}</p>
                                        <p className="text-xs text-[#86868b]">{source.integration_type}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    {isOnline
                                        ? <Wifi className="h-4 w-4 text-[#34c759]" />
                                        : <WifiOff className="h-4 w-4 text-[#ff3b30]" />
                                    }
                                    {source.sla_status === 'ok'
                                        ? <CheckCircle2 className="h-4 w-4 text-[#34c759]" />
                                        : <AlertTriangle className="h-4 w-4 text-[#ffcc00]" />
                                    }
                                </div>
                            </div>

                            <div className="grid grid-cols-3 gap-2 text-xs">
                                <div>
                                    <p className="text-[#86868b]">Last Sync</p>
                                    <p className="font-mono text-[#1d1d1f]">
                                        {source.last_sync
                                            ? new Date(source.last_sync).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                                            : '—'
                                        }
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[#86868b]">Records</p>
                                    <p className="font-mono font-semibold text-[#1d1d1f]">{source.records_24h.toLocaleString()}</p>
                                </div>
                                <div>
                                    <p className="text-[#86868b]">Fail Rate</p>
                                    <p className={`font-mono font-semibold ${failRate > 5 ? 'text-[#ff3b30]' : failRate > 2 ? 'text-[#b38f00]' : 'text-[#34c759]'}`}>
                                        {failRate.toFixed(1)}%
                                    </p>
                                </div>
                            </div>

                            {/* SLA badge */}
                            <div className="mt-3 pt-3 border-t border-black/5">
                                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                                    source.sla_status === 'ok'
                                        ? 'bg-[#34c759]/10 text-[#34c759]'
                                        : 'bg-[#ffcc00]/10 text-[#b38f00]'
                                }`}>
                                    {source.sla_status === 'ok' ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                                    {source.sla_status === 'ok' ? 'SLA Met' : 'SLA Breach'}
                                </span>
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
