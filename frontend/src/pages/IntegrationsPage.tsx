import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
    AlertCircle,
    CheckCircle2,
    Clock,
    ExternalLink,
    Link2,
    Loader2,
    Plug,
    RefreshCcw,
    ShieldCheck,
    Trash2,
    UploadCloud,
    XCircle,
} from 'lucide-react'

import {
    useConfirmSquareMapping,
    useDeadLetterWebhooks,
    useDisconnectIntegration,
    useIntegrations,
    useProducts,
    useReplayWebhookEvent,
    useSquareMappingPreview,
    useStores,
} from '@/hooks/useShelfOps'
import { getApiErrorDetail } from '@/lib/api'
import type { Integration } from '@/lib/types'

const PROVIDER_META: Record<string, { label: string; color: string; description: string }> = {
    csv: {
        label: 'CSV Onboarding',
        color: 'bg-[#34c759]',
        description: 'Structured file uploads used for pilot backfill and manual refresh when a live connector is not ready.',
    },
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

const CONNECTABLE_PROVIDER_KEYS = new Set(['square'])
const ROADMAP_PROVIDER_KEYS = new Set(['shopify', 'lightspeed', 'clover'])
const MANAGED_PROVIDER_KEYS = new Set([...CONNECTABLE_PROVIDER_KEYS, ...ROADMAP_PROVIDER_KEYS])

function IntegrationCard({ integration }: { integration: Integration }) {
    const disconnect = useDisconnectIntegration()
    const [showConfirm, setShowConfirm] = useState(false)
    const disconnectable = integration.provider === 'square'

    const provider = PROVIDER_META[integration.provider] ?? {
        label: integration.provider,
        color: 'bg-[#86868b]',
        description: 'POS integration.',
    }
    const status = STATUS_CONFIG[integration.status] ?? { icon: XCircle, color: 'text-[#86868b]', label: 'Unknown' }
    const StatusIcon = status.icon

    return (
        <motion.div whileHover={{ y: -2 }} className="card p-5">
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                    <div className={`flex h-11 w-11 items-center justify-center rounded-[12px] ${provider.color} shadow-sm`}>
                        <Link2 className="h-5 w-5 text-white" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-[#1d1d1f]">{provider.label}</h3>
                        <p className="mt-0.5 max-w-sm text-xs text-[#86868b]">{provider.description}</p>
                        <div className="mt-3 flex items-center gap-3 text-xs text-[#86868b]">
                            <span className={`flex items-center gap-1 font-medium ${status.color}`}>
                                <StatusIcon className="h-3.5 w-3.5" />
                                {status.label}
                            </span>
                            {integration.merchant_id ? (
                                <>
                                    <span>·</span>
                                    <span className="rounded bg-[#f5f5f7] px-1.5 py-0.5 font-mono">
                                        {integration.merchant_id}
                                    </span>
                                </>
                            ) : null}
                            {integration.last_sync_at ? (
                                <>
                                    <span>·</span>
                                    <span>Last sync: {new Date(integration.last_sync_at).toLocaleString()}</span>
                                </>
                            ) : null}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {!disconnectable ? (
                        <span className="rounded-full bg-[#34c759]/10 px-3 py-1.5 text-xs font-medium text-[#1f8f45]">
                            File-backed source
                        </span>
                    ) : null}
                    {disconnectable && integration.status === 'connected' && !showConfirm ? (
                        <button
                            onClick={() => setShowConfirm(true)}
                            className="btn-secondary h-8 gap-1 px-3 text-xs text-[#ff3b30] hover:bg-[#ff3b30]/10"
                        >
                            <Trash2 className="h-3 w-3" />
                            Disconnect
                        </button>
                    ) : null}
                    {showConfirm ? (
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => {
                                    disconnect.mutate(integration.integration_id)
                                    setShowConfirm(false)
                                }}
                                className="btn-secondary h-8 bg-[#ff3b30]/10 px-3 text-xs text-[#ff3b30] hover:bg-[#ff3b30]/20"
                                disabled={disconnect.isPending}
                            >
                                {disconnect.isPending ? 'Disconnecting...' : 'Confirm'}
                            </button>
                            <button onClick={() => setShowConfirm(false)} className="btn-secondary h-8 px-3 text-xs">
                                Cancel
                            </button>
                        </div>
                    ) : null}
                </div>
            </div>
        </motion.div>
    )
}

function AvailableProviderCard({ provider, providerKey }: { provider: typeof PROVIDER_META[string]; providerKey: string }) {
    const connectUrl = providerKey === 'square' ? '/api/v1/integrations/square/connect' : '#'
    const isLiveProvider = CONNECTABLE_PROVIDER_KEYS.has(providerKey)

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
                    <div className={`flex h-11 w-11 items-center justify-center rounded-[12px] ${provider.color}/20`}>
                        <Plug className={`h-5 w-5 ${provider.color.replace('bg-', 'text-')}`} />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-[#1d1d1f]">{provider.label}</h3>
                        <p className="mt-0.5 max-w-sm text-xs text-[#86868b]">{provider.description}</p>
                    </div>
                </div>
                {isLiveProvider ? (
                    <a href={connectUrl} className="btn-secondary h-8 gap-1 px-3 text-xs">
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
    const { data: integrations = [], isLoading, isError, error } = useIntegrations()
    const squareIntegration = integrations.find(integration => integration.provider === 'square' && integration.status === 'connected')
    const squareConnected = Boolean(squareIntegration)

    const { data: stores = [] } = useStores()
    const { data: products = [] } = useProducts()
    const {
        data: mappingPreview,
        isLoading: mappingLoading,
        isError: mappingError,
        error: mappingErrorDetail,
        refetch: refetchMappingPreview,
    } = useSquareMappingPreview(squareConnected)
    const confirmSquareMapping = useConfirmSquareMapping()
    const { data: deadLetters = [], isLoading: deadLettersLoading } = useDeadLetterWebhooks()
    const replayWebhookEvent = useReplayWebhookEvent()

    const [locationMappings, setLocationMappings] = useState<Record<string, string>>({})
    const [catalogMappings, setCatalogMappings] = useState<Record<string, string>>({})
    const [mappingBanner, setMappingBanner] = useState<string | null>(null)

    useEffect(() => {
        if (!mappingPreview) {
            return
        }
        setLocationMappings(
            Object.fromEntries(
                mappingPreview.locations
                    .filter(location => Boolean(location.mapped_store_id))
                    .map(location => [location.external_id, location.mapped_store_id as string]),
            ),
        )
        setCatalogMappings(
            Object.fromEntries(
                mappingPreview.catalog_items
                    .filter(item => Boolean(item.mapped_product_id))
                    .map(item => [item.external_id, item.mapped_product_id as string]),
            ),
        )
    }, [mappingPreview])

    const connectedProviders = new Set<string>(integrations.map(integration => integration.provider))
    const availableProviders = Object.entries(PROVIDER_META).filter(
        ([key]) => MANAGED_PROVIDER_KEYS.has(key) && !connectedProviders.has(key),
    )
    const connectableProviders = availableProviders.filter(([key]) => CONNECTABLE_PROVIDER_KEYS.has(key))
    const roadmapProviders = availableProviders.filter(([key]) => ROADMAP_PROVIDER_KEYS.has(key))

    const unmappedLocationCount = mappingPreview
        ? mappingPreview.locations.filter(location => !locationMappings[location.external_id]).length
        : 0
    const unmappedCatalogCount = mappingPreview
        ? mappingPreview.catalog_items.filter(item => !catalogMappings[item.external_id]).length
        : 0

    const mappingReadyToConfirm = squareConnected && unmappedLocationCount === 0 && unmappedCatalogCount === 0
    const mappingChanged = useMemo(() => {
        if (!mappingPreview) {
            return false
        }
        const existingLocationMap = Object.fromEntries(
            mappingPreview.locations
                .filter(location => Boolean(location.mapped_store_id))
                .map(location => [location.external_id, location.mapped_store_id as string]),
        )
        const existingCatalogMap = Object.fromEntries(
            mappingPreview.catalog_items
                .filter(item => Boolean(item.mapped_product_id))
                .map(item => [item.external_id, item.mapped_product_id as string]),
        )
        return JSON.stringify(existingLocationMap) !== JSON.stringify(locationMappings)
            || JSON.stringify(existingCatalogMap) !== JSON.stringify(catalogMappings)
    }, [catalogMappings, locationMappings, mappingPreview])

    async function persistMappings(squareMappingConfirmed: boolean) {
        const result = await confirmSquareMapping.mutateAsync({
            square_location_to_store: Object.fromEntries(
                Object.entries(locationMappings).filter(([, value]) => Boolean(value)),
            ),
            square_catalog_to_product: Object.fromEntries(
                Object.entries(catalogMappings).filter(([, value]) => Boolean(value)),
            ),
            square_mapping_confirmed: squareMappingConfirmed,
        })
        setMappingBanner(
            squareMappingConfirmed
                ? `Saved and confirmed mappings for ${result.provider}.`
                : `Saved mapping draft for ${result.provider}.`,
        )
        await refetchMappingPreview()
    }

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-[#1d1d1f]">Integrations</h1>
                <p className="mt-1 text-sm text-[#86868b]">
                    Choose how ShelfOps will receive catalog, sales, and inventory data for day-to-day planning.
                </p>
            </div>

            <section className="grid gap-4 xl:grid-cols-2">
                <div className="card p-5 space-y-3">
                    <div className="flex items-center gap-2">
                        <Plug className="h-4 w-4 text-[#0071e3]" />
                        <h2 className="text-sm font-semibold text-[#1d1d1f]">Live POS Connection</h2>
                    </div>
                    <p className="text-sm text-[#6e6e73]">
                        Use a live integration when you want recurring syncs for products, transactions, and inventory without manual uploads.
                    </p>
                    <p className="text-xs text-[#86868b]">
                        Square is available today. Additional providers remain visible here for roadmap planning.
                    </p>
                </div>

                <div className="card p-5 space-y-3">
                    <div className="flex items-center gap-2">
                        <UploadCloud className="h-4 w-4 text-[#34c759]" />
                        <h2 className="text-sm font-semibold text-[#1d1d1f]">Structured File Onboarding</h2>
                    </div>
                    <p className="text-sm text-[#6e6e73]">
                        CSV onboarding is the fastest route for pilot evaluation, historical backfill, and first-pass setup when a live connector is not ready.
                    </p>
                    <Link
                        to="/data-readiness"
                        className="inline-flex items-center gap-1 text-xs font-medium text-[#0071e3] hover:text-[#005bb5]"
                    >
                        Open CSV onboarding
                        <ExternalLink className="h-3 w-3" />
                    </Link>
                </div>
            </section>

            {isLoading ? (
                <div className="card py-16 text-center">
                    <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-[#0071e3]" />
                    <p className="text-sm text-[#86868b]">Loading integrations...</p>
                </div>
            ) : isError ? (
                <div className="card py-16 text-center bg-[#ff3b30]/5">
                    <AlertCircle className="mx-auto mb-3 h-8 w-8 text-[#ff3b30]" />
                    <p className="text-sm text-[#ff3b30]">{getApiErrorDetail(error, 'Failed to load integrations')}</p>
                </div>
            ) : (
                <>
                    {integrations.length > 0 ? (
                        <div className="space-y-3">
                            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#86868b]">
                                Connected ({integrations.length})
                            </h2>
                            {integrations.map(integration => (
                                <IntegrationCard key={integration.integration_id} integration={integration} />
                            ))}
                        </div>
                    ) : null}

                    {connectableProviders.length > 0 ? (
                        <div className="space-y-3">
                            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#86868b]">
                                Available to Connect
                            </h2>
                            {connectableProviders.map(([key, provider]) => (
                                <AvailableProviderCard key={key} providerKey={key} provider={provider} />
                            ))}
                        </div>
                    ) : null}

                    {squareConnected ? (
                        <section className="card space-y-5">
                            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <ShieldCheck className="h-4 w-4 text-[#0071e3]" />
                                        <h2 className="text-lg font-semibold text-[#1d1d1f]">Square Mapping Review</h2>
                                    </div>
                                    <p className="mt-2 text-sm text-[#6e6e73]">
                                        Review location and catalog mappings before trusting synced records in planning and replenishment workflows.
                                    </p>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <button
                                        type="button"
                                        onClick={() => void refetchMappingPreview()}
                                        className="btn-secondary px-4 py-2 text-sm"
                                    >
                                        <RefreshCcw className="h-4 w-4" />
                                        Refresh Preview
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => void persistMappings(false)}
                                        disabled={!mappingChanged || confirmSquareMapping.isPending}
                                        className="btn-secondary px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        Save Draft
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => void persistMappings(true)}
                                        disabled={!mappingReadyToConfirm || confirmSquareMapping.isPending}
                                        className="btn-primary px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        Confirm Mappings
                                    </button>
                                </div>
                            </div>

                            {mappingBanner ? (
                                <div className="rounded-[20px] border border-[#34c759]/20 bg-[#34c759]/10 px-4 py-4 text-sm text-[#1f8f45]">
                                    {mappingBanner}
                                </div>
                            ) : null}

                            {mappingError ? (
                                <div className="rounded-[20px] border border-[#ff3b30]/20 bg-[#ff3b30]/5 px-4 py-4 text-sm text-[#c9342a]">
                                    {getApiErrorDetail(mappingErrorDetail, 'Failed to load Square mapping preview.')}
                                </div>
                            ) : null}

                            {confirmSquareMapping.isError ? (
                                <div className="rounded-[20px] border border-[#ff3b30]/20 bg-[#ff3b30]/5 px-4 py-4 text-sm text-[#c9342a]">
                                    {getApiErrorDetail(confirmSquareMapping.error, 'Failed to persist Square mappings.')}
                                </div>
                            ) : null}

                            {mappingLoading ? (
                                <div className="rounded-[20px] bg-[#f5f5f7] px-4 py-10 text-center text-sm text-[#86868b]">
                                    Loading Square mapping preview…
                                </div>
                            ) : mappingPreview ? (
                                <>
                                    <div className="grid gap-4 md:grid-cols-4">
                                        <SummaryTile label="Locations mapped" value={`${mappingPreview.mapping_coverage.locations_mapped}/${mappingPreview.mapping_coverage.locations_total}`} />
                                        <SummaryTile label="Catalog mapped" value={`${mappingPreview.mapping_coverage.catalog_mapped}/${mappingPreview.mapping_coverage.catalog_total}`} />
                                        <SummaryTile label="Unmapped locations" value={String(unmappedLocationCount)} />
                                        <SummaryTile label="Unmapped products" value={String(unmappedCatalogCount)} />
                                    </div>

                                    <div className="grid gap-6 xl:grid-cols-2">
                                        <MappingTable
                                            title="Location mappings"
                                            rows={mappingPreview.locations.map(location => ({
                                                external_id: location.external_id,
                                                name: location.name ?? location.external_id,
                                                extra: location.timezone ?? 'timezone unavailable',
                                                selected_value: locationMappings[location.external_id] ?? '',
                                            }))}
                                            options={stores.map(store => ({ value: store.store_id, label: store.name }))}
                                            placeholder="Select a store"
                                            onChange={(externalId, value) => {
                                                setLocationMappings(current => ({ ...current, [externalId]: value }))
                                                setMappingBanner(null)
                                            }}
                                        />

                                        <MappingTable
                                            title="Catalog mappings"
                                            rows={mappingPreview.catalog_items.map(item => ({
                                                external_id: item.external_id,
                                                name: item.name ?? item.external_id,
                                                extra: item.variation_ids?.length ? `Variations: ${item.variation_ids.join(', ')}` : 'No variation ids',
                                                selected_value: catalogMappings[item.external_id] ?? '',
                                            }))}
                                            options={products.map(product => ({ value: product.product_id, label: `${product.name} · ${product.sku}` }))}
                                            placeholder="Select a product"
                                            onChange={(externalId, value) => {
                                                setCatalogMappings(current => ({ ...current, [externalId]: value }))
                                                setMappingBanner(null)
                                            }}
                                        />
                                    </div>
                                </>
                            ) : (
                                <div className="rounded-[20px] bg-[#f5f5f7] px-4 py-10 text-center text-sm text-[#86868b]">
                                    Square preview unavailable.
                                </div>
                            )}
                        </section>
                    ) : null}

                    <section className="card space-y-5">
                        <div className="flex items-center gap-2">
                            <AlertCircle className="h-4 w-4 text-[#0071e3]" />
                            <h2 className="text-lg font-semibold text-[#1d1d1f]">Webhook Recovery</h2>
                        </div>
                        <p className="text-sm text-[#6e6e73]">
                            Failed Square webhook deliveries are held here for operator review and replay instead of disappearing into backend-only logs.
                        </p>

                        {deadLettersLoading ? (
                            <div className="rounded-[20px] bg-[#f5f5f7] px-4 py-10 text-center text-sm text-[#86868b]">
                                Loading replay queue…
                            </div>
                        ) : deadLetters.length === 0 ? (
                            <div className="rounded-[20px] bg-[#34c759]/10 px-4 py-4 text-sm text-[#1f8f45]">
                                No dead-letter webhook events are waiting for replay.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {deadLetters.map(event => (
                                    <div key={event.webhook_event_id} className="rounded-[18px] border border-black/[0.05] bg-[#fbfbfd] px-4 py-4">
                                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                            <div>
                                                <p className="text-sm font-semibold text-[#1d1d1f]">{event.event_type}</p>
                                                <p className="mt-1 text-xs text-[#86868b]">
                                                    {event.provider} · {event.merchant_id ?? 'merchant unavailable'} · {new Date(event.received_at).toLocaleString()}
                                                </p>
                                                <p className="mt-2 text-sm text-[#6e6e73]">
                                                    Attempts: {event.delivery_attempts} · Last error: {event.last_error ?? 'unknown'}
                                                </p>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => replayWebhookEvent.mutate(event.webhook_event_id)}
                                                disabled={replayWebhookEvent.isPending}
                                                className="btn-secondary px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                                            >
                                                {replayWebhookEvent.isPending ? 'Replaying…' : 'Replay Event'}
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {replayWebhookEvent.isError ? (
                            <div className="rounded-[20px] border border-[#ff3b30]/20 bg-[#ff3b30]/5 px-4 py-4 text-sm text-[#c9342a]">
                                {getApiErrorDetail(replayWebhookEvent.error, 'Failed to replay webhook event.')}
                            </div>
                        ) : null}
                    </section>

                    {roadmapProviders.length > 0 ? (
                        <div className="space-y-3">
                            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#86868b]">
                                Roadmap Providers
                            </h2>
                            <p className="text-xs text-[#86868b]">
                                These providers are visible for planning only and are not interactive in production until OAuth and sync flows exist end to end.
                            </p>
                            {roadmapProviders.map(([key, provider]) => (
                                <AvailableProviderCard key={key} providerKey={key} provider={provider} />
                            ))}
                        </div>
                    ) : null}
                </>
            )}
        </div>
    )
}

function SummaryTile({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-[18px] bg-[#f5f5f7] px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-[#86868b]">{label}</p>
            <p className="mt-2 text-xl font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
        </div>
    )
}

function MappingTable({
    title,
    rows,
    options,
    placeholder,
    onChange,
}: {
    title: string
    rows: Array<{ external_id: string; name: string; extra: string; selected_value: string }>
    options: Array<{ value: string; label: string }>
    placeholder: string
    onChange: (externalId: string, value: string) => void
}) {
    return (
        <div className="space-y-3">
            <h3 className="text-sm font-semibold text-[#1d1d1f]">{title}</h3>
            <div className="max-h-[420px] space-y-3 overflow-y-auto rounded-[20px] border border-black/[0.05] bg-[#fbfbfd] p-4">
                {rows.length === 0 ? (
                    <div className="rounded-[16px] bg-white px-4 py-4 text-sm text-[#86868b]">No rows in this preview.</div>
                ) : rows.map(row => (
                    <div key={row.external_id} className="rounded-[16px] bg-white px-4 py-4">
                        <p className="text-sm font-semibold text-[#1d1d1f]">{row.name}</p>
                        <p className="mt-1 text-xs text-[#86868b]">
                            {row.external_id} · {row.extra}
                        </p>
                        <select
                            value={row.selected_value}
                            onChange={event => onChange(row.external_id, event.target.value)}
                            className="mt-3 w-full rounded-[14px] border border-black/[0.08] bg-[#fbfbfd] px-3 py-2 text-sm text-[#1d1d1f] outline-none transition focus:border-[#0071e3]/35"
                        >
                            <option value="">{placeholder}</option>
                            {options.map(option => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>
                ))}
            </div>
        </div>
    )
}
