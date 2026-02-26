/**
 * SystemEventsPanel — Live WebSocket event feed, collapsible side drawer.
 * WS-4 demo component. Sets window.__demoEventReceived for Shepherd.js steps.
 */

import { useState, useCallback, useRef } from 'react'
import { X, Radio, ChevronDown, ChevronUp } from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WsMessage } from '@/hooks/useWebSocket'
import { useDemoMode } from '@/hooks/useDemoMode'

// Extend window for Shepherd.js interop
declare global {
    interface Window {
        __demoEventReceived?: boolean
    }
}

interface SystemEvent {
    id: string
    timestamp: string
    type: string
    message: string
    detail?: string
    technical?: string
}

const BUYER_LABELS: Record<string, string> = {
    feedback_loop: 'Model updated from new sales data',
    po_decision: 'Purchase order decision recorded',
    forecast_ready: 'New forecasts are ready',
    alert: 'Inventory alert triggered',
    inventory_update: 'Inventory levels refreshed',
}

const TECHNICAL_LABELS: Record<string, string> = {
    feedback_loop: 'Celery task queued: feedback_loop_propagate',
    po_decision: 'PODecision written · rejection_rate_30d \u2191 · trust_score \u2193',
    forecast_ready: 'Forecast pipeline completed — feature matrix updated',
    alert: 'Alert event published to Redis pub/sub',
    inventory_update: 'Inventory snapshot ingested — next retrain scheduled',
}

function formatTimestamp(): string {
    return new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    })
}

function eventToSystemEvent(msg: WsMessage): SystemEvent {
    const ts = formatTimestamp()
    const id = `${msg.type}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`

    return {
        id,
        timestamp: ts,
        type: msg.type,
        message: BUYER_LABELS[msg.type] ?? msg.type,
        technical: TECHNICAL_LABELS[msg.type] ?? msg.type,
        detail:
            msg.type === 'po_decision'
                ? 'Feature matrix update scheduled for next retrain'
                : undefined,
    }
}

interface SystemEventsPanelProps {
    isOpen?: boolean
}

export default function SystemEventsPanel({ isOpen: initialOpen = false }: SystemEventsPanelProps) {
    const { isTechnical } = useDemoMode()
    const [isOpen, setIsOpen] = useState(initialOpen || isTechnical)
    const [events, setEvents] = useState<SystemEvent[]>([])
    const listRef = useRef<HTMLDivElement>(null)

    const handleMessage = useCallback((msg: WsMessage) => {
        // Skip heartbeats — don't pollute the feed
        if (msg.type === 'heartbeat') return

        // Signal Shepherd.js that a real event arrived
        window.__demoEventReceived = true

        const systemEvent = eventToSystemEvent(msg)
        setEvents(prev => [systemEvent, ...prev].slice(0, 50))
    }, [])

    const { connected } = useWebSocket(handleMessage)

    return (
        <div
            id="system-events-panel"
            className={`card border border-white/40 shadow-sm transition-all duration-200 ${
                isOpen ? '' : 'cursor-pointer hover:border-shelf-primary/30'
            }`}
        >
            {/* Header */}
            <div
                className="flex items-center justify-between"
                onClick={() => !isOpen && setIsOpen(true)}
                role="button"
                tabIndex={0}
                onKeyDown={e => {
                    if (!isOpen && (e.key === 'Enter' || e.key === ' ')) setIsOpen(true)
                }}
            >
                <div className="flex items-center gap-2">
                    <Radio
                        className={`h-4 w-4 ${connected ? 'text-green-500' : 'text-gray-400'}`}
                    />
                    <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider">
                        System Events
                    </h3>
                    {events.length > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-shelf-primary/10 text-shelf-primary text-[10px] font-semibold">
                            {events.length}
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <span
                        className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                            connected
                                ? 'bg-green-50 text-green-600'
                                : 'bg-gray-100 text-gray-400'
                        }`}
                    >
                        {connected ? 'Live' : 'Offline'}
                    </span>

                    <button
                        onClick={e => {
                            e.stopPropagation()
                            setIsOpen(prev => !prev)
                        }}
                        className="p-1 rounded text-shelf-foreground/40 hover:text-shelf-primary transition-colors"
                        aria-label={isOpen ? 'Collapse events panel' : 'Expand events panel'}
                    >
                        {isOpen ? (
                            <ChevronUp className="h-4 w-4" />
                        ) : (
                            <ChevronDown className="h-4 w-4" />
                        )}
                    </button>
                </div>
            </div>

            {isOpen && (
                <div className="mt-4">
                    {events.length === 0 ? (
                        <div className="py-8 text-center">
                            <Radio className="h-6 w-6 mx-auto mb-2 text-shelf-foreground/20 animate-pulse" />
                            <p className="text-xs text-shelf-foreground/40">
                                Waiting for live events&hellip;
                            </p>
                            <p className="text-[10px] text-shelf-foreground/30 mt-1">
                                Events appear when the backend publishes to Redis
                            </p>
                        </div>
                    ) : (
                        <div
                            ref={listRef}
                            className="space-y-2 max-h-64 overflow-y-auto pr-1"
                        >
                            {events.map(event => (
                                <div
                                    key={event.id}
                                    className="flex items-start gap-2 text-xs p-2 rounded-lg bg-shelf-secondary/5 hover:bg-shelf-secondary/10 transition-colors group"
                                >
                                    <span className="font-mono text-shelf-foreground/40 flex-shrink-0 mt-0.5">
                                        [{event.timestamp}]
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-shelf-foreground/80">
                                            {isTechnical
                                                ? (event.technical ?? event.message)
                                                : event.message}
                                        </p>
                                        {isTechnical && event.detail && (
                                            <p className="text-shelf-foreground/40 mt-0.5">
                                                {event.detail}
                                            </p>
                                        )}
                                    </div>
                                    <button
                                        onClick={() =>
                                            setEvents(prev =>
                                                prev.filter(e => e.id !== event.id)
                                            )
                                        }
                                        className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-shelf-foreground/30 hover:text-shelf-foreground/60 transition-all flex-shrink-0"
                                        aria-label="Dismiss event"
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {events.length > 0 && (
                        <button
                            onClick={() => setEvents([])}
                            className="mt-3 text-[10px] text-shelf-foreground/40 hover:text-shelf-primary transition-colors"
                        >
                            Clear all events
                        </button>
                    )}
                </div>
            )}
        </div>
    )
}
