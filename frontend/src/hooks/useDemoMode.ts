/**
 * Hook to detect the current demo tour mode from the URL search param.
 * Used by demo-only components to switch between buyer and technical presentations.
 */

type DemoMode = 'buyer' | 'technical' | null

export function useDemoMode(): {
    mode: DemoMode
    isBuyer: boolean
    isTechnical: boolean
} {
    const searchParams = new URLSearchParams(window.location.search)
    const track = searchParams.get('track') ?? searchParams.get('tour')
    const mode: DemoMode =
        track === 'buyer' ? 'buyer' : track === 'technical' ? 'technical' : null
    return {
        mode,
        isBuyer: mode === 'buyer',
        isTechnical: mode === 'technical',
    }
}
