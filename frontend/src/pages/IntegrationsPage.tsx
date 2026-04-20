/**
 * Integrations Page — Manage POS connections (Square, Shopify, etc.)
 * Agent: full-stack-engineer | Skill: react-dashboard
 */

import { useState } from 'react'
import { motion } from 'framer-motion'
import {
    Link2, Loader2, AlertCircle, CheckCircle2,
    XCircle, Clock, Plug, ExternalLink, Trash2,
} from 'lucide-react'
import { useIntegrations, useDisconnectIntegration } from '@/hooks/useShelfOps'
import type { Integration } from '@/lib/types'

const PROVIDER_META: Record<string, { label: string; color: string; description: string }> = {
    square: {
        label: 'Square POS',
        color: 'bg-[#0071e3]',
        description: 'Real-time inventory counts, transaction sync, and catalog management.',
    },
    shopify: {
        label: 'Shopify',
        color: 'bg-[#34c759]',
        description: 'E-commerce inventory and order synchronization.',
    },
    lightspeed: {
        label: 'Lightspeed',
        color: 'bg-[#ff9500]',
        description: 'Retail POS inventory and sales data integration.',
    },
    clover: {
        label: 'Clover',
        color: 'bg-[#5856d6]',
        description: 'POS transaction and inventory tracking.',
    },
}

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
    connected: { icon: CheckCircle2, color: 'text-[#34c759]', label: 'Connected' },
    disconnected: { icon: XCircle, color: 'text-[#86868b]', label: 'Disconnected' },
    error: { icon: AlertCircle, color: 'text-[#ff3b30]', label: 'Error' },
    pending: { icon: Clock, color: 'text-[#ff9500]', label: 'Pending' },
}

const LIVE_PROVIDER_KEYS = new Set(['square'])

function IntegrationCard({ integration }: { integration: Integration }) {
    const disconnect = useDisconnectIntegration()
    const [showConfirm, setShowConfirm] = useState(false)

    const provider = PROVIDER_META[integration.provider] ?? {
        label: integration.provider,
        color: 'bg-[#86868b]',
        description: 'POS integration.',
    }
    const status = STATUS_CONFIG[integration.status] ?? { icon: XCircle, color: 'text-[#86868b]', label: 'Unknown' }
    const StatusIcon = status.icon

    return (
        <motion.div
            whileHover={{ y: -2 }}
            className="card p-5"
        >
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                    <div className={`h-11 w-11 rounded-[12px] ${provider.color} flex items-center justify-center shadow-sm`}>
                        <Link2 className="h-5 w-5 text-white" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-[#1d1d1f]">{provider.label}</h3>
                        <p className="text-xs text-[#86868b] mt-0.5 max-w-sm">{provider.description}</p>
                        <div className="flex items-center gap-3 mt-3 text-xs text-[#86868b]">
                            <span className={`flex items-center gap-1 font-medium ${status.color}`}>
                                <StatusIcon className="h-3.5 w-3.5" />
                                {status.label}
                            </span>
                            {integration.merchant_id && (
                                <>
                                    <span>·</span>
                                    <span className="font-mono bg-[#f5f5f7] px-1.5 py-0.5 rounded">
                                        {integration.merchant_id}
                                    </span>
                                </>
                            )}
                            {integration.last_sync_at && (
                                <>
                                    <span>·</span>
                                    <span>Last sync: {new Date(integration.last_sync_at).toLocaleString()}</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {integration.status === 'connected' && !showConfirm && (
                        <button
                            onClick={() => setShowConfirm(true)}
                            className="btn-secondary text-xs h-8 px-3 gap-1 text-[#ff3b30] hover:bg-[#ff3b30]/10"
                        >
                            <Trash2 className="h-3 w-3" />
                            Disconnect
                        </button>
                    )}
                    {showConfirm && (
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => {
                                    disconnect.mutate(integration.integration_id)
                                    setShowConfirm(false)
                                }}
                                className="btn-secondary text-xs h-8 px-3 bg-[#ff3b30]/10 text-[#ff3b30] hover:bg-[#ff3b30]/20"
                                disabled={disconnect.isPending}
                            >
                                {disconnect.isPending ? 'Disconnecting...' : 'Confirm'}
                            </button>
                            <button
                                onClick={() => setShowConfirm(false)}
                                className="btn-secondary text-xs h-8 px-3"
                            >
                                Cancel
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    )
}

function AvailableProviderCard({ provider, providerKey }: { provider: typeof PROVIDER_META[string]; providerKey: string }) {
    const connectUrl = providerKey === 'square' ? '/api/v1/integrations/square/connect' : '#'
    const isLiveProvider = LIVE_PROVIDER_KEYS.has(providerKey)

    return (
        <motion.div
            whileHover={{ y: -2 }}
            className={`card p-5 ${
                isLiveProvider
                    ? 'border-dashed border-black/10 hover:border-[#0071e3]/30'
                    : 'border-black/5 bg-[#f5f5f7]/50'
            }`}
        >
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                    <div className={`h-11 w-11 rounded-[12px] ${provider.color}/20 flex items-center justify-center`}>
                        <Plug className={`h-5 w-5 ${provider.color.replace('bg-', 'text-')}`} />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-[#1d1d1f]">{provider.label}</h3>
                        <p className="text-xs text-[#86868b] mt-0.5 max-w-sm">{provider.description}</p>
                    </div>
                </div>
                {isLiveProvider ? (
                    <a
                        href={connectUrl}
                        className="btn-secondary text-xs h-8 px-3 gap-1"
                    >
                        Connect
                        <ExternalLink className="h-3 w-3" />
                    </a>
                ) : (
                    <span className="rounded-full bg-[#86868b]/10 px-3 py-1.5 text-xs font-medium text-[#86868b]">
                        Roadmap only
                    </span>
                )}
            </div>
        </motion.div>
    )
}

export default function IntegrationsPage() {
    const { data: integrations = [], isLoading, isError } = useIntegrations()

    const connectedProviders = new Set<string>(integrations.map((i) => i.provider))
    const availableProviders = Object.entries(PROVIDER_META).filter(
        ([key]) => !connectedProviders.has(key)
    )
    const connectableProviders = availableProviders.filter(([key]) => LIVE_PROVIDER_KEYS.has(key))
    const roadmapProviders = availableProviders.filter(([key]) => !LIVE_PROVIDER_KEYS.has(key))

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-[#1d1d1f]">Integrations</h1>
                <p className="text-sm text-[#86868b] mt-1">
                    Connect your POS systems for automatic inventory and sales sync.
                </p>
            </div>

            {isLoading && (
                <div className="card text-center py-16">
                    <Loader2 className="h-8 w-8 mx-auto mb-3 text-[#0071e3] animate-spin" />
                    <p className="text-sm text-[#86868b]">Loading integrations...</p>
                </div>
            )}

            {isError && (
                <div className="card text-center py-16 bg-[#ff3b30]/5">
                    <AlertCircle className="h-8 w-8 mx-auto mb-3 text-[#ff3b30]" />
                    <p className="text-sm text-[#ff3b30]">Failed to load integrations</p>
                </div>
            )}

            {!isLoading && !isError && (
                <>
                    {integrations.length > 0 && (
                        <div className="space-y-3">
                            <h2 className="text-xs font-semibold text-[#86868b] uppercase tracking-wider">
                                Connected ({integrations.length})
                            </h2>
                            {integrations.map((integration) => (
                                <IntegrationCard key={integration.integration_id} integration={integration} />
                            ))}
                        </div>
                    )}

                    {connectableProviders.length > 0 && (
                        <div className="space-y-3">
                            <h2 className="text-xs font-semibold text-[#86868b] uppercase tracking-wider">
                                Available to Connect
                            </h2>
                            {connectableProviders.map(([key, provider]) => (
                                <AvailableProviderCard key={key} providerKey={key} provider={provider} />
                            ))}
                        </div>
                    )}

                    {roadmapProviders.length > 0 && (
                        <div className="space-y-3">
                            <h2 className="text-xs font-semibold text-[#86868b] uppercase tracking-wider">
                                Roadmap Providers
                            </h2>
                            <p className="text-xs text-[#86868b]">
                                These providers are visible for planning only and are not interactive in production until OAuth and sync flows exist end to end.
                            </p>
                            {roadmapProviders.map(([key, provider]) => (
                                <AvailableProviderCard key={key} providerKey={key} provider={provider} />
                            ))}
                        </div>
                    )}
                </>
            )}
        </div>
    )
}
