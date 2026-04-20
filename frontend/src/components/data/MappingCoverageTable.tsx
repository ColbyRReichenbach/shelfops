import { Link2, MapPinned } from 'lucide-react'

import type { SyncHealth } from '@/lib/types'

interface MappingCoverageTableProps {
    sources: SyncHealth[]
}

export default function MappingCoverageTable({ sources }: MappingCoverageTableProps) {
    const mappedSources = sources.filter(source => source.integration_name === 'Square POS')

    return (
        <section className="card overflow-hidden border border-black/[0.02] p-0 shadow-sm">
            <div className="border-b border-black/[0.04] px-6 py-5">
                <div className="flex items-center gap-2">
                    <MapPinned className="h-4 w-4 text-[#0071e3]" />
                    <h2 className="text-lg font-semibold text-[#1d1d1f]">Connection Mapping</h2>
                </div>
                <p className="mt-2 text-sm text-[#6e6e73]">
                    Confirm store and catalog mappings so incoming sales and inventory records land in the right places.
                </p>
            </div>

            {mappedSources.length === 0 ? (
                <div className="px-6 py-14 text-center">
                    <p className="text-sm font-medium text-[#1d1d1f]">No mapped connection found</p>
                    <p className="mt-1 text-sm text-[#86868b]">Connect Square or confirm mappings to populate this table.</p>
                </div>
            ) : (
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-black/[0.04]">
                        <thead className="bg-[#fbfbfd] text-left text-xs uppercase tracking-[0.18em] text-[#86868b]">
                            <tr>
                                <th className="px-6 py-4 font-medium">Source</th>
                                <th className="px-4 py-4 font-medium">Confirmation</th>
                                <th className="px-4 py-4 font-medium">Location coverage</th>
                                <th className="px-4 py-4 font-medium">Catalog coverage</th>
                                <th className="px-6 py-4 font-medium">Unmapped IDs</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-black/[0.04] bg-white">
                            {mappedSources.map(source => {
                                const coverage = source.mapping_coverage ?? {}
                                const unmappedCount = (source.unmapped_location_ids?.length ?? 0) + (source.unmapped_catalog_ids?.length ?? 0)

                                return (
                                    <tr key={`${source.integration_name}-${source.last_sync ?? 'none'}`}>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                                                    <Link2 className="h-4 w-4 text-[#1d1d1f]" />
                                                </div>
                                                <div>
                                                    <p className="text-sm font-semibold text-[#1d1d1f]">{source.integration_name}</p>
                                                    <p className="mt-1 text-xs text-[#86868b]">{source.integration_type}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${source.mapping_confirmed ? 'bg-[#34c759]/10 text-[#1f8f45]' : 'bg-[#ffcc00]/20 text-[#8a6a00]'}`}>
                                                {source.mapping_confirmed ? 'confirmed' : 'pending'}
                                            </span>
                                        </td>
                                        <td className="px-4 py-4 text-sm text-[#1d1d1f]">
                                            {coverage.locations_mapped ?? 0} mapped / {coverage.locations_total ?? 0} total
                                        </td>
                                        <td className="px-4 py-4 text-sm text-[#1d1d1f]">
                                            {coverage.catalog_mapped ?? 0} mapped / {coverage.catalog_total ?? 0} total
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="space-y-2 text-sm text-[#1d1d1f]">
                                                <p>{unmappedCount} remaining</p>
                                                <p className="text-xs text-[#86868b]">
                                                    Locations: {source.unmapped_location_ids?.join(', ') || 'none'}
                                                </p>
                                                <p className="text-xs text-[#86868b]">
                                                    Catalog: {source.unmapped_catalog_ids?.join(', ') || 'none'}
                                                </p>
                                            </div>
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </section>
    )
}
