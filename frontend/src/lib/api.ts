/**
 * API Client — Wraps fetch with auth token injection and error handling.
 * Agent: full-stack-engineer | Skill: react-dashboard
 */

import { useAuth0 } from '@auth0/auth0-react'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export interface ApiError {
    status: number
    detail: string
}

export function getApiBaseUrl(): string {
    if (!API_BASE) {
        return window.location.origin
    }
    return new URL(API_BASE, window.location.origin).toString().replace(/\/$/, '')
}

export function getWebSocketBaseUrl(): string {
    const apiUrl = new URL(getApiBaseUrl())
    apiUrl.protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    return apiUrl.toString().replace(/\/$/, '')
}

export function getApiErrorDetail(error: unknown, fallback = 'Unknown error'): string {
    if (error && typeof error === 'object' && 'detail' in error && typeof error.detail === 'string') {
        return error.detail
    }
    if (error instanceof Error && error.message) {
        return error.message
    }
    return fallback
}

async function request<T>(
    path: string,
    token: string | null,
    options: RequestInit = {},
): Promise<T> {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string> | undefined),
    }
    if (token) {
        headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
    })

    if (!response.ok) {
        const body = await response.json().catch(() => ({ detail: response.statusText }))
        throw { status: response.status, detail: body.detail ?? 'Unknown error' } as ApiError
    }

    if (response.status === 204) {
        return undefined as T
    }

    const contentLength = response.headers.get('content-length')
    if (contentLength === '0') {
        return undefined as T
    }

    return response.json()
}

export function useApi() {
    const { getAccessTokenSilently } = useAuth0()

    const getToken = async () => {
        if (import.meta.env.DEV) {
            return null
        }
        return await getAccessTokenSilently()
    }

    return {
        get: async <T>(path: string) => {
            const token = await getToken()
            return request<T>(path, token)
        },
        post: async <T>(path: string, body: unknown) => {
            const token = await getToken()
            return request<T>(path, token, { method: 'POST', body: JSON.stringify(body) })
        },
        patch: async <T>(path: string, body: unknown) => {
            const token = await getToken()
            return request<T>(path, token, { method: 'PATCH', body: JSON.stringify(body) })
        },
        delete: async <T>(path: string) => {
            const token = await getToken()
            return request<T>(path, token, { method: 'DELETE' })
        },
    }
}
