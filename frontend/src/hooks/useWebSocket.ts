/**
 * WebSocket hook for real-time alert updates.
 * Agent: full-stack-engineer | Skill: react-dashboard (WebSocket pattern)
 */

import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuth0 } from '@auth0/auth0-react'

export interface WsMessage {
    type: 'alert' | 'inventory_update' | 'forecast_ready' | 'heartbeat'
    payload: unknown
}

export function useWebSocket(onMessage: (msg: WsMessage) => void) {
    const { getAccessTokenSilently } = useAuth0()
    const wsRef = useRef<WebSocket | null>(null)
    const [connected, setConnected] = useState(false)
    const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>()

    const connect = useCallback(async () => {
        try {
            const token = import.meta.env.DEV
                ? 'mock-token'
                : await getAccessTokenSilently()
            const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
            const ws = new WebSocket(`${protocol}://${window.location.host}/ws/alerts?token=${token}`)

            ws.onopen = () => setConnected(true)

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data) as WsMessage
                    onMessage(data)
                } catch {
                    console.warn('Invalid WebSocket message:', event.data)
                }
            }

            ws.onclose = () => {
                setConnected(false)
                reconnectTimeout.current = setTimeout(connect, 3000)
            }

            ws.onerror = () => ws.close()

            wsRef.current = ws
        } catch {
            reconnectTimeout.current = setTimeout(connect, 5000)
        }
    }, [getAccessTokenSilently, onMessage])

    useEffect(() => {
        connect()
        return () => {
            clearTimeout(reconnectTimeout.current)
            wsRef.current?.close()
        }
    }, [connect])

    return { connected }
}
