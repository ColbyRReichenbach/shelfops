/**
 * ModelDriversPanel — Collapsible global model-driver evidence panel.
 * Fetches artifact-backed evidence from /api/v1/forecasts/{forecastId}/drivers.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from 'recharts'
import { ChevronDown, ChevronUp, HelpCircle, Loader2, AlertCircle } from 'lucide-react'
import { useApi } from '@/lib/api'

// ─── Types ─────────────────────────────────────────────────────────────────

interface ModelDriverFeatureEntry {
    name: string
    importance: number
    friendly_label?: string
}

interface ForecastDriversResponse {
    forecast_id: string
    forecast_model_version: string
    artifact_model_version: string | null
    driver_scope: 'global' | 'unavailable'
    evidence_type: 'artifact' | 'unavailable'
    source_artifact: string | null
    features: ModelDriverFeatureEntry[]
    plain_summary: string
    limitations: string[]
}

export interface ModelDriversPanelProps {
    forecastId: string
    predictedValue: number
    isLoading?: boolean
}

// ─── Local hook ─────────────────────────────────────────────────────────────

function useForecastDrivers(forecastId: string | undefined) {
    const api = useApi()
    return useQuery({
        queryKey: ['forecast-drivers', forecastId],
        queryFn: () =>
            api.get<ForecastDriversResponse>(
                `/api/v1/forecasts/${forecastId}/drivers`
            ),
        enabled: !!forecastId,
        staleTime: 60 * 60 * 1000, // 1 hour — matches Redis TTL
    })
}

// ─── Custom tooltip ─────────────────────────────────────────────────────────

interface TooltipPayloadItem {
    value: number
    payload: {
        label: string
        importance: number
    }
}

function DriversTooltip({
    active,
    payload,
}: {
    active?: boolean
    payload?: TooltipPayloadItem[]
}) {
    if (!active || !payload?.length) return null
    const item = payload[0]
    if (!item) return null
    const val = item.payload.importance
    return (
        <div
            style={{
                backgroundColor: 'rgba(29,29,31,0.8)',
                backdropFilter: 'blur(12px)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '16px',
                padding: '8px 12px',
                fontSize: '12px',
                color: '#ffffff',
                boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
            }}
        >
            <p className="font-medium">{item.payload.label}</p>
            <p style={{ color: '#0071e3' }}>Importance: {(val * 100).toFixed(2)}%</p>
        </div>
    )
}

// ─── Plain-language summary builder ─────────────────────────────────────────

function buildSummary(data: ForecastDriversResponse): string {
    if (data.plain_summary) return data.plain_summary
    const top = [...data.features]
        .sort((a, b) => b.importance - a.importance)
        .slice(0, 2)
    const labels = top.map(
        f => f.friendly_label ?? f.name.replace(/_/g, ' ')
    )
    return `These are global model drivers. ${labels[0] ?? 'The top feature'}${labels[1] ? ` and ${labels[1]}` : ''} carry the highest overall importance in the current model artifact.`
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function ModelDriversPanel({
    forecastId,
    predictedValue,
}: ModelDriversPanelProps) {
    const [isOpen, setIsOpen] = useState(false)
    const { data, isLoading, isError, isFetching } = useForecastDrivers(
        isOpen ? forecastId : undefined
    )

    // Build chart data from top global model-driver weights
    const chartData = data
        ? [...data.features]
              .sort((a, b) => b.importance - a.importance)
              .slice(0, 8)
              .map(f => ({
                  label: f.friendly_label ?? f.name.replace(/_/g, ' '),
                  importance: f.importance,
              }))
        : []

    return (
        <div className="mt-3 border-t border-black/5 pt-3">
            <button
                id="forecast-drivers-btn"
                onClick={() => setIsOpen(prev => !prev)}
                className="flex items-center gap-1.5 text-xs font-medium text-[#0071e3] hover:text-[#0071e3]/80 transition-colors"
            >
                <HelpCircle className="h-3.5 w-3.5" />
                Model drivers
                {isOpen ? (
                    <ChevronUp className="h-3 w-3 ml-0.5" />
                ) : (
                    <ChevronDown className="h-3 w-3 ml-0.5" />
                )}
            </button>

            {isOpen && (
                <div className="mt-3 space-y-3">
                    <div className="flex items-baseline gap-2">
                        <span className="text-lg font-bold text-[#1d1d1f]">
                            {predictedValue.toLocaleString()}
                        </span>
                        <span className="text-xs text-[#86868b]">units forecast</span>
                        {data?.artifact_model_version && (
                            <span className="text-xs text-[#86868b]">
                                artifact: {data.artifact_model_version}
                            </span>
                        )}
                    </div>

                    {(isLoading || isFetching) && (
                        <div className="flex items-center gap-2 py-4 text-[#86868b]">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-xs">Loading model drivers&hellip;</span>
                        </div>
                    )}

                    {isError && !isFetching && (
                        <div className="flex items-center gap-2 py-3 text-[#ff3b30]">
                            <AlertCircle className="h-4 w-4" />
                            <span className="text-xs">Could not load model-driver evidence.</span>
                        </div>
                    )}

                    {data && !isFetching && (
                        <>
                            <p className="text-xs text-[#86868b] bg-[#f5f5f7] rounded-lg px-3 py-2">
                                {buildSummary(data)}
                            </p>
                            <p className="text-[11px] text-[#86868b]">
                                Scope: {data.driver_scope}. Source: {data.evidence_type === 'artifact' ? 'saved model artifact' : 'unavailable'}.
                                This is not a local explanation for this specific forecast row.
                            </p>
                            {data.source_artifact && (
                                <p className="text-[11px] text-[#86868b]">
                                    Source artifact: {data.source_artifact}
                                    {data.artifact_model_version && ` (${data.artifact_model_version})`}
                                </p>
                            )}

                            {chartData.length > 0 ? (
                                <div className="h-[200px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart
                                            data={chartData}
                                            layout="vertical"
                                            margin={{ top: 0, right: 24, bottom: 0, left: 8 }}
                                        >
                                            <CartesianGrid
                                                strokeDasharray="3 3"
                                                stroke="#e5e5ea"
                                                strokeOpacity={1}
                                                horizontal={false}
                                            />
                                            <XAxis
                                                type="number"
                                                tick={{ fill: '#86868b', fontSize: 10, opacity: 0.6 }}
                                                axisLine={false}
                                                tickLine={false}
                                                tickFormatter={v => `${(v * 100).toFixed(1)}%`}
                                            />
                                            <YAxis
                                                dataKey="label"
                                                type="category"
                                                width={128}
                                                tick={{ fill: '#86868b', fontSize: 10 }}
                                                axisLine={false}
                                                tickLine={false}
                                            />
                                            <Tooltip content={<DriversTooltip />} />
                                            <Bar dataKey="importance" barSize={20} radius={[0, 3, 3, 0]} fill="#0071e3" fillOpacity={0.8} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                <div className="rounded-lg border border-dashed border-black/10 bg-[#f5f5f7] px-3 py-4 text-xs text-[#86868b]">
                                    Model-driver evidence is unavailable for this forecast version.
                                </div>
                            )}

                            <div className="space-y-1 text-[10px] text-[#86868b]">
                                {data.limitations.map(limit => (
                                    <p key={limit}>{limit}</p>
                                ))}
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    )
}
