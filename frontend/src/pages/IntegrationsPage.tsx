/**
 * Integrations Page — Manage POS connections (Square, Shopify, etc.)
 * Agent: full-stack-engineer | Skill: react-dashboard
 */

import { useState } from 'react'
import {
    Link2, Loader2, AlertCircle, CheckCircle2,
    XCircle, Clock, Plug, ExternalLink, Trash2,
} from 'lucide-react'
import { useIntegrations, useDisconnectIntegration } from '@/hooks/useShelfOps'
import type { Integration } from '@/lib/types'

const PROVIDER_META: Record<string, { label: string; color: string; description: string }> = {
    square: {
        label: 'Square POS',
        color: 'bg-blue-500',
        description: 'Real-time inventory counts, transaction sync, and catalog management.',
    },
    shopify: {
        label: 'Shopify',
        color: 'bg-green-500',
        description: 'E-commerce inventory and order synchronization.',
    },
    lightspeed: {
        label: 'Lightspeed',
        color: 'bg-orange-500',
        description: 'Retail POS inventory and sales data integration.',
    },
    clover: {
        label: 'Clover',
        color: 'bg-purple-500',
        description: 'POS transaction and inventory tracking.',
    },
}

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
    connected: { icon: CheckCircle2, color: 'text-green-600', label: 'Connected' },
    disconnected: { icon: XCircle, color: 'text-gray-400', label: 'Disconnected' },
    error: { icon: AlertCircle, color: 'text-red-500', label: 'Error' },
    pending: { icon: Clock, color: 'text-yellow-500', label: 'Pending' },
}

function IntegrationCard({ integration }: { integration: Integration }) {
    const disconnect = useDisconnectIntegration()
    const [showConfirm, setShowConfirm] = useState(false)

    const provider = PROVIDER_META[integration.provider] ?? {
        label: integration.provider,
        color: 'bg-gray-500',
        description: 'POS integration.',
    }
    const status = STATUS_CONFIG[integration.status] ?? { icon: XCircle, color: 'text-gray-400', label: 'Unknown' }
    const StatusIcon = status.icon

    return (
        <div className="card border border-white/40 shadow-sm hover:shadow-md transition-all p-5">
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                    <div className={`h-11 w-11 rounded-xl ${provider.color} flex items-center justify-center shadow-sm`}>
                        <Link2 className="h-5 w-5 text-white" />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-shelf-foreground">{provider.label}</h3>
                        <p className="text-xs text-shelf-foreground/60 mt-0.5 max-w-sm">{provider.description}</p>
                        <div className="flex items-center gap-3 mt-3 text-xs text-shelf-foreground/50">
                            <span className={`flex items-center gap-1 font-medium ${status.color}`}>
                                <StatusIcon className="h-3.5 w-3.5" />
                                {status.label}
                            </span>
                            {integration.merchant_id && (
                                <>
                                    <span>·</span>
                                    <span className="font-mono bg-shelf-foreground/5 px-1.5 py-0.5 rounded">
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
                            className="btn-secondary text-xs h-8 px-3 gap-1 text-red-500 hover:bg-red-50"
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
                                className="btn-secondary text-xs h-8 px-3 bg-red-50 text-red-600 hover:bg-red-100"
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
        </div>
    )
}

function AvailableProviderCard({ provider, providerKey }: { provider: typeof PROVIDER_META[string]; providerKey: string }) {
    const connectUrl = providerKey === 'square' ? '/api/v1/integrations/square/connect' : '#'
    const isSquare = providerKey === 'square'

    return (
        <div className="card border border-dashed border-shelf-foreground/15 shadow-sm p-5 hover:border-shelf-primary/30 transition-all">
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                    <div className={`h-11 w-11 rounded-xl ${provider.color}/20 flex items-center justify-center`}>
                        <Plug className={`h-5 w-5 ${provider.color.replace('bg-', 'text-')}`} />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-shelf-foreground">{provider.label}</h3>
                        <p className="text-xs text-shelf-foreground/60 mt-0.5 max-w-sm">{provider.description}</p>
                    </div>
                </div>
                {isSquare ? (
                    <a
                        href={connectUrl}
                        className="btn-secondary text-xs h-8 px-3 gap-1"
                    >
                        Connect
                        <ExternalLink className="h-3 w-3" />
                    </a>
                ) : (
                    <span className="text-xs text-shelf-foreground/40 font-medium px-3 py-1.5">Coming soon</span>
                )}
            </div>
        </div>
    )
}

export default function IntegrationsPage() {
    const { data: integrations = [], isLoading, isError } = useIntegrations()

    const connectedProviders = new Set<string>(integrations.map((i) => i.provider))
    const availableProviders = Object.entries(PROVIDER_META).filter(
        ([key]) => !connectedProviders.has(key)
    )

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div>
                <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Integrations</h1>
                <p className="text-sm text-shelf-foreground/60 mt-1">
                    Connect your POS systems for automatic inventory and sales sync.
                </p>
            </div>

            {/* Connected Integrations */}
            {isLoading && (
                <div className="card text-center py-16 border border-white/40 shadow-sm">
                    <Loader2 className="h-8 w-8 mx-auto mb-3 text-shelf-primary animate-spin" />
                    <p className="text-sm text-shelf-foreground/60">Loading integrations...</p>
                </div>
            )}

            {isError && (
                <div className="card text-center py-16 border border-red-200 bg-red-50/50 shadow-sm">
                    <AlertCircle className="h-8 w-8 mx-auto mb-3 text-red-500" />
                    <p className="text-sm text-red-600">Failed to load integrations</p>
                </div>
            )}

            {!isLoading && !isError && (
                <>
                    {integrations.length > 0 && (
                        <div className="space-y-3">
                            <h2 className="text-sm font-semibold text-shelf-foreground/70 uppercase tracking-wider">
                                Connected ({integrations.length})
                            </h2>
                            {integrations.map((integration) => (
                                <IntegrationCard key={integration.integration_id} integration={integration} />
                            ))}
                        </div>
                    )}

                    {availableProviders.length > 0 && (
                        <div className="space-y-3">
                            <h2 className="text-sm font-semibold text-shelf-foreground/70 uppercase tracking-wider">
                                Available
                            </h2>
                            {availableProviders.map(([key, provider]) => (
                                <AvailableProviderCard key={key} providerKey={key} provider={provider} />
                            ))}
                        </div>
                    )}
                </>
            )}
        </div>
    )
}
