/**
 * SHAPWaterfall — Collapsible SHAP feature importance panel.
 * Forecast explanation panel. Fetches from /api/v1/forecasts/{forecastId}/explain.
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
    Cell,
    ResponsiveContainer,
} from 'recharts'
import { ChevronDown, ChevronUp, HelpCircle, Loader2, AlertCircle } from 'lucide-react'
import { useApi } from '@/lib/api'

// ─── Types ─────────────────────────────────────────────────────────────────

interface SHAPFeatureEntry {
    name: string
    shap_value: number
    friendly_label?: string
}

interface SHAPExplainResponse {
    forecast_id: string
    base_value: number
    predicted_value: number
    features: SHAPFeatureEntry[]
    plain_summary?: string
}

export interface SHAPWaterfallProps {
    forecastId: string
    predictedValue: number
    isLoading?: boolean
}

// ─── Local hook ─────────────────────────────────────────────────────────────

function useSHAPExplanation(forecastId: string | undefined) {
    const api = useApi()
    return useQuery({
        queryKey: ['shap', forecastId],
        queryFn: () =>
            api.get<SHAPExplainResponse>(
                `/api/v1/forecasts/${forecastId}/explain`
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
        shap_value: number
    }
}

function SHAPTooltip({
    active,
    payload,
}: {
    active?: boolean
    payload?: TooltipPayloadItem[]
}) {
    if (!active || !payload?.length) return null
    const item = payload[0]
    if (!item) return null
    const val = item.payload.shap_value
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
            <p style={{ color: val >= 0 ? '#34c759' : '#ff3b30' }}>
                SHAP: {val >= 0 ? '+' : ''}{val.toFixed(3)}
            </p>
        </div>
    )
}

// ─── Plain-language summary builder ─────────────────────────────────────────

function buildSummary(data: SHAPExplainResponse): string {
    if (data.plain_summary) return data.plain_summary
    const top = [...data.features]
        .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
        .slice(0, 2)
    const labels = top.map(
        f => f.friendly_label ?? f.name.replace(/_/g, ' ')
    )
    return `The ${labels[0] ?? 'primary feature'}${labels[1] ? ` and ${labels[1]}` : ''} had the largest impact on this forecast.`
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function SHAPWaterfall({
    forecastId,
    predictedValue,
}: SHAPWaterfallProps) {
    const [isOpen, setIsOpen] = useState(false)
    const { data, isLoading, isError, isFetching } = useSHAPExplanation(
        isOpen ? forecastId : undefined
    )

    // Build chart data — top 8 features by absolute SHAP value
    const chartData = data
        ? [...data.features]
              .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
              .slice(0, 8)
              .map(f => ({
                  label: f.friendly_label ?? f.name.replace(/_/g, ' '),
                  shap_value: f.shap_value,
                  abs: Math.abs(f.shap_value),
              }))
        : []

    return (
        <div className="mt-3 border-t border-black/5 pt-3">
            {/* Trigger button — id required for Shepherd.js step */}
            <button
                id="shap-explain-btn"
                onClick={() => setIsOpen(prev => !prev)}
                className="flex items-center gap-1.5 text-xs font-medium text-[#0071e3] hover:text-[#0071e3]/80 transition-colors"
            >
                <HelpCircle className="h-3.5 w-3.5" />
                Why this forecast?
                {isOpen ? (
                    <ChevronUp className="h-3 w-3 ml-0.5" />
                ) : (
                    <ChevronDown className="h-3 w-3 ml-0.5" />
                )}
            </button>

            {isOpen && (
                <div className="mt-3 space-y-3">
                    {/* Predicted value summary */}
                    <div className="flex items-baseline gap-2">
                        <span className="text-lg font-bold text-[#1d1d1f]">
                            {predictedValue.toLocaleString()}
                        </span>
                        <span className="text-xs text-[#86868b]">units forecast</span>
                        {data?.base_value != null && (
                            <span className="text-xs text-[#86868b]">
                                (base: {data.base_value.toFixed(1)})
                            </span>
                        )}
                    </div>

                    {/* Loading */}
                    {(isLoading || isFetching) && (
                        <div className="flex items-center gap-2 py-4 text-[#86868b]">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-xs">Loading explanation&hellip;</span>
                        </div>
                    )}

                    {/* Error */}
                    {isError && !isFetching && (
                        <div className="flex items-center gap-2 py-3 text-[#ff3b30]">
                            <AlertCircle className="h-4 w-4" />
                            <span className="text-xs">Could not load SHAP explanation.</span>
                        </div>
                    )}

                    {/* Chart */}
                    {data && !isFetching && (
                        <>
                            {/* Plain-language summary */}
                            <p className="text-xs text-[#86868b] bg-[#f5f5f7] rounded-lg px-3 py-2">
                                {buildSummary(data)}
                            </p>
                            <p className="text-[11px] text-[#86868b]">
                                Demo explanation view: deterministic per-forecast contribution estimates for a repeatable walkthrough.
                            </p>

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
                                            tickFormatter={v =>
                                                v >= 0 ? `+${v.toFixed(2)}` : v.toFixed(2)
                                            }
                                        />
                                        <YAxis
                                            dataKey="label"
                                            type="category"
                                            width={110}
                                            tick={{ fill: '#86868b', fontSize: 10 }}
                                            axisLine={false}
                                            tickLine={false}
                                        />
                                        <Tooltip content={<SHAPTooltip />} />
                                        <Bar dataKey="shap_value" barSize={20} radius={[0, 3, 3, 0]}>
                                            {chartData.map((entry, index) => (
                                                <Cell
                                                    key={`cell-${index}`}
                                                    fill={
                                                        entry.shap_value >= 0
                                                            ? '#34c759'
                                                            : '#ff3b30'
                                                    }
                                                    fillOpacity={0.8}
                                                />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>

                            <div className="flex items-center gap-4 text-[10px] text-[#86868b]">
                                <span className="flex items-center gap-1">
                                    <span className="inline-block h-2 w-3 rounded" style={{ backgroundColor: '#34c759', opacity: 0.8 }} />
                                    Increases forecast
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="inline-block h-2 w-3 rounded" style={{ backgroundColor: '#ff3b30', opacity: 0.8 }} />
                                    Decreases forecast
                                </span>
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    )
}
