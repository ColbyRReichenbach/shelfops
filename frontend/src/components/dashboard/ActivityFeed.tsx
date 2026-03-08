/**
 * ActivityFeed — Collapsible ML pipeline history timeline.
 * WS-4 demo component. Shows the Summit Outdoor Supply 95-day learning arc.
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

interface ActivityEvent {
    day: number
    label: string
    detail: string
    status: 'past' | 'milestone' | 'active' | 'pending'
}

const SUMMIT_EVENTS: ActivityEvent[] = [
    {
        day: 1,
        label: 'Day 1',
        detail: 'Tenant onboarded. Cold-start model activated. First forecasts: 50 SKUs',
        status: 'past',
    },
    {
        day: 30,
        label: 'Day 30',
        detail: 'Milestone: 30d data accumulated. Challenger trained. Arena: Gates 1\u20136 \u2713',
        status: 'milestone',
    },
    {
        day: 44,
        label: 'Day 44',
        detail: 'Champion promoted: MASE 0.95 \u2192 0.71. Accuracy +25%',
        status: 'milestone',
    },
    {
        day: 52,
        label: 'Day 52',
        detail: 'Demand spike detected. Auto-retrain triggered.',
        status: 'past',
    },
    {
        day: 57,
        label: 'Day 57',
        detail: 'New challenger: MASE 0.64. Shadow phase started \u25cf active',
        status: 'active',
    },
    {
        day: 95,
        label: 'Today',
        detail: 'Shadow challenger: Day 6 of 14. Auto-promotes in 8 days if holds.',
        status: 'active',
    },
]

const STATUS_DOT: Record<ActivityEvent['status'], string> = {
    past: 'bg-gray-300',
    milestone: 'bg-green-500',
    active: 'bg-orange-400',
    pending: 'bg-gray-200 border border-gray-300',
}

const STATUS_TEXT: Record<ActivityEvent['status'], string> = {
    past: 'text-shelf-foreground/50',
    milestone: 'text-green-700',
    active: 'text-orange-600 font-medium',
    pending: 'text-shelf-foreground/30',
}

interface ActivityFeedProps {
    useDemoMode?: boolean
}

export default function ActivityFeed({ useDemoMode = true }: ActivityFeedProps) {
    const [isExpanded, setIsExpanded] = useState(true)

    // For the demo we always show the hardcoded Summit events.
    // In a real implementation this would come from ModelVersion retrain logs.
    const events: ActivityEvent[] = useDemoMode ? SUMMIT_EVENTS : SUMMIT_EVENTS

    return (
        <div className="card border border-white/40 shadow-sm">
            {/* Header */}
            <div className="flex items-center justify-between mb-0">
                <div>
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">
                        Platform Activity
                    </h3>
                    <p className="text-xs text-shelf-foreground/50 mt-0.5">
                        95-day ML pipeline history — Summit Outdoor Supply
                    </p>
                </div>
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="p-1.5 rounded-lg text-shelf-foreground/40 hover:bg-shelf-secondary/10 hover:text-shelf-primary transition-colors"
                    aria-label={isExpanded ? 'Collapse activity feed' : 'Expand activity feed'}
                >
                    {isExpanded ? (
                        <ChevronUp className="h-4 w-4" />
                    ) : (
                        <ChevronDown className="h-4 w-4" />
                    )}
                </button>
            </div>

            {isExpanded && (
                <div className="mt-4 relative pl-6">
                    {/* Vertical line */}
                    <div className="absolute left-2.5 top-1 bottom-1 w-px bg-shelf-foreground/10" />

                    <div className="space-y-4">
                        {events.map((event, i) => (
                            <div key={i} className="relative flex items-start gap-3">
                                {/* Status dot */}
                                <div
                                    className={`absolute -left-4 mt-1 h-3 w-3 rounded-full flex-shrink-0 ${STATUS_DOT[event.status]}`}
                                />

                                <div className="min-w-0 flex-1">
                                    <div className="flex items-baseline gap-2 flex-wrap">
                                        <span className="text-xs font-semibold text-shelf-foreground/70 w-14 flex-shrink-0">
                                            {event.label}
                                        </span>
                                        <span
                                            className={`text-xs leading-relaxed ${STATUS_TEXT[event.status]}`}
                                        >
                                            {event.detail}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
