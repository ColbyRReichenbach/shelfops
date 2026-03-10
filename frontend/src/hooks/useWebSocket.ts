/**
 * WebSocket hook for real-time alert updates.
 * Agent: full-stack-engineer | Skill: react-dashboard (WebSocket pattern)
 */

import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { getWebSocketBaseUrl } from '@/lib/api'

export interface WsMessage {
    type:
        | 'alert'
        | 'inventory_update'
        | 'forecast_ready'
        | 'heartbeat'
        | 'feedback_loop'
        | 'po_decision'
    payload: unknown
}

export function useWebSocket(onMessage: (msg: WsMessage) => void) {
    const { getAccessTokenSilently } = useAuth0()
    const wsRef = useRef<WebSocket | null>(null)
    const [connected, setConnected] = useState(false)
    const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>()
    const retryCount = useRef(0)
    const onMessageRef = useRef(onMessage)

    // Keep callback ref current without triggering reconnects
    useEffect(() => {
        onMessageRef.current = onMessage
    }, [onMessage])

    const connect = useCallback(async () => {
        try {
            const token = import.meta.env.DEV ? null : await getAccessTokenSilently()
            const wsBase = getWebSocketBaseUrl()
            const wsUrl = token
                ? `${wsBase}/ws/alerts?token=${encodeURIComponent(token)}`
                : `${wsBase}/ws/alerts`
            const ws = new WebSocket(wsUrl)

            ws.onopen = () => {
                setConnected(true)
                retryCount.current = 0
            }

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data) as WsMessage
                    onMessageRef.current(data)
                } catch {
                    console.warn('Invalid WebSocket message:', event.data)
                }
            }

            ws.onclose = () => {
                setConnected(false)
                const delay = Math.min(3000 * Math.pow(2, retryCount.current), 60000)
                retryCount.current += 1
                reconnectTimeout.current = setTimeout(connect, delay)
            }

            ws.onerror = () => ws.close()

            wsRef.current = ws
        } catch {
            const delay = Math.min(3000 * Math.pow(2, retryCount.current), 60000)
            retryCount.current += 1
            reconnectTimeout.current = setTimeout(connect, delay)
        }
    }, [getAccessTokenSilently])

    useEffect(() => {
        connect()
        return () => {
            clearTimeout(reconnectTimeout.current)
            wsRef.current?.close()
        }
    }, [connect])

    return { connected }
}
