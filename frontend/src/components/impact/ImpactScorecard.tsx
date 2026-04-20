import { CircleDollarSign, LineChart, ShieldAlert, ShoppingBag } from 'lucide-react'

import MetricProvenanceBadge from '@/components/impact/MetricProvenanceBadge'
import type { RecommendationImpact } from '@/lib/types'

interface ImpactScorecardProps {
    impact: RecommendationImpact | undefined
}

export default function ImpactScorecard({ impact }: ImpactScorecardProps) {
    const forecastCloseout = impact?.forecast_closeout
    const recommendationPolicy = impact?.recommendation_policy

    return (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <ImpactCard
                icon={CircleDollarSign}
                label="Estimated policy value"
                value={formatCurrency(recommendationPolicy?.net_policy_value ?? null)}
                provenance={recommendationPolicy?.net_policy_value_confidence ?? 'unavailable'}
            />
            <ImpactCard
                icon={LineChart}
                label="Forecast vs observed sales proxy"
                value={forecastCloseout?.average_forecast_error_abs !== null && forecastCloseout?.average_forecast_error_abs !== undefined
                    ? forecastCloseout.average_forecast_error_abs.toFixed(2)
                    : '—'}
                provenance={forecastCloseout?.average_forecast_error_abs_confidence ?? 'unavailable'}
            />
            <ImpactCard
                icon={ShieldAlert}
                label="Stockout events"
                value={String(forecastCloseout?.stockout_events ?? 0)}
                provenance={forecastCloseout?.stockout_events_confidence ?? 'unavailable'}
            />
            <ImpactCard
                icon={ShoppingBag}
                label="Overstock events"
                value={String(forecastCloseout?.overstock_events ?? 0)}
                provenance={forecastCloseout?.overstock_events_confidence ?? 'unavailable'}
            />
        </section>
    )
}

function ImpactCard({
    icon: Icon,
    label,
    value,
    provenance,
}: {
    icon: typeof CircleDollarSign
    label: string
    value: string
    provenance: string
}) {
    return (
        <div className="hero-stat-card">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                <Icon className="h-5 w-5 text-[#1d1d1f]" />
            </div>
            <p className="mt-4 text-sm font-medium text-[#86868b]">{label}</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <div className="mt-3">
                <MetricProvenanceBadge label={provenance} tone={mapTone(provenance)} />
            </div>
        </div>
    )
}

function formatCurrency(value: number | null) {
    if (value === null) {
        return '—'
    }
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
    }).format(value)
}

function mapTone(label: string) {
    if (label === 'measured') {
        return 'measured'
    }
    if (label === 'estimated') {
        return 'estimated'
    }
    if (label === 'provisional') {
        return 'provisional'
    }
    return 'neutral'
}
