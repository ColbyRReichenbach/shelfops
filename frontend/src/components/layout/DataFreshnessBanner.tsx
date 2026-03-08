/**
 * DataFreshnessBanner — Dismissible banner for stale data warning.
 * WS-4 demo component. Shown when hoursSinceSync > 48.
 */

import { AlertTriangle, X } from 'lucide-react'

export interface DataFreshnessBannerProps {
    hoursSinceSync: number
    onDismiss: () => void
}

export default function DataFreshnessBanner({
    hoursSinceSync,
    onDismiss,
}: DataFreshnessBannerProps) {
    if (hoursSinceSync <= 48) return null

    const hoursDisplay = Math.round(hoursSinceSync)

    return (
        <div
            role="alert"
            className="
                flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50
                px-4 py-3 text-amber-800 shadow-sm
            "
        >
            <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5 text-amber-500" />

            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">
                    Data last synced {hoursDisplay} hours ago.
                </p>
                <p className="text-xs text-amber-700 mt-0.5">
                    Forecast confidence is reduced until the next successful sync.
                    Check the{' '}
                    <a
                        href="/integrations"
                        className="underline underline-offset-2 hover:text-amber-900 transition-colors"
                    >
                        Integrations
                    </a>
                    {' '}page for sync status.
                </p>
            </div>

            <button
                onClick={onDismiss}
                className="flex-shrink-0 rounded-md p-1 text-amber-500 hover:bg-amber-100 hover:text-amber-700 transition-colors"
                aria-label="Dismiss data freshness warning"
            >
                <X className="h-4 w-4" />
            </button>
        </div>
    )
}
