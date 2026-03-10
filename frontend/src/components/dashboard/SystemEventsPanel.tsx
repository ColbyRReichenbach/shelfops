/**
 * SystemEventsPanel — Live WebSocket event feed, collapsible side drawer.
 */

import { useState, useCallback, useRef } from 'react'
import { X, Radio, ChevronDown, ChevronUp } from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WsMessage } from '@/hooks/useWebSocket'

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

function summarizeProductionMessage(msg: WsMessage): Pick<SystemEvent, 'message' | 'detail'> {
    if (msg.payload && typeof msg.payload === 'object') {
        const payload = msg.payload as Record<string, unknown>
        const message =
            (typeof payload.message === 'string' && payload.message) ||
            (typeof payload.summary === 'string' && payload.summary) ||
            `${msg.type.replace(/_/g, ' ')} received`
        const fragments = [
            typeof payload.version === 'string' ? `version ${payload.version}` : null,
            typeof payload.model_version === 'string' ? `model ${payload.model_version}` : null,
            typeof payload.store_id === 'string' ? `store ${payload.store_id.slice(0, 8)}` : null,
            typeof payload.product_id === 'string' ? `product ${payload.product_id.slice(0, 8)}` : null,
            typeof payload.status === 'string' ? `status ${payload.status}` : null,
        ].filter(Boolean)

        return {
            message,
            detail: fragments.length > 0 ? fragments.join(' · ') : undefined,
        }
    }

    return {
        message: `${msg.type.replace(/_/g, ' ')} received`,
        detail: undefined,
    }
}

function eventToSystemEvent(msg: WsMessage, demoMode: 'buyer' | 'technical' | null): SystemEvent {
    const ts = formatTimestamp()
    const id = `${msg.type}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const productionSummary = summarizeProductionMessage(msg)

    return {
        id,
        timestamp: ts,
        type: msg.type,
        message: demoMode ? BUYER_LABELS[msg.type] ?? msg.type : productionSummary.message,
        technical: demoMode ? TECHNICAL_LABELS[msg.type] ?? msg.type : productionSummary.message,
        detail:
            demoMode === 'technical' && msg.type === 'po_decision'
                ? 'Feature matrix update scheduled for next retrain'
                : productionSummary.detail,
    }
}

interface SystemEventsPanelProps {
    isOpen?: boolean
    demoMode?: 'buyer' | 'technical' | null
}

export default function SystemEventsPanel({
    isOpen: initialOpen = false,
    demoMode = null,
}: SystemEventsPanelProps) {
    const [isOpen, setIsOpen] = useState(initialOpen || demoMode === 'technical')
    const [events, setEvents] = useState<SystemEvent[]>([])
    const listRef = useRef<HTMLDivElement>(null)

    const handleMessage = useCallback((msg: WsMessage) => {
        // Skip heartbeats — don't pollute the feed
        if (msg.type === 'heartbeat') return

        if (demoMode) {
            window.__demoEventReceived = true
        }

        const systemEvent = eventToSystemEvent(msg, demoMode)
        setEvents(prev => [systemEvent, ...prev].slice(0, 50))
    }, [demoMode])

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
                                            {demoMode === 'technical'
                                                ? (event.technical ?? event.message)
                                                : event.message}
                                        </p>
                                        {event.detail && (
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
