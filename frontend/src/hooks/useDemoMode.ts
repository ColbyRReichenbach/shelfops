/**
 * Hook to detect the current demo tour mode from the URL search param.
 * Used by WS-4 components to switch between buyer and technical presentations.
 */

type DemoMode = 'buyer' | 'technical' | null

export function useDemoMode(): {
    mode: DemoMode
    isBuyer: boolean
    isTechnical: boolean
} {
    const searchParams = new URLSearchParams(window.location.search)
    const tour = searchParams.get('tour')
    const mode: DemoMode =
        tour === 'buyer' ? 'buyer' : tour === 'technical' ? 'technical' : null
    return {
        mode,
        isBuyer: mode === 'buyer',
        isTechnical: mode === 'technical',
    }
}
