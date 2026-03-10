import ExecutiveDashboard from '@/components/dashboard/ExecutiveDashboard'
import ActivityFeed from '@/components/dashboard/ActivityFeed'
import ModelTimeline from '@/components/dashboard/ModelTimeline'
import SystemEventsPanel from '@/components/dashboard/SystemEventsPanel'
import { useDemoMode } from '@/hooks/useDemoMode'

export default function DemoPage() {
    const { isTechnical } = useDemoMode()

    return (
        <div className="mx-auto max-w-7xl p-6 lg:p-8 space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">ShelfOps Demo</h1>
                <p className="mt-1 text-sm text-shelf-foreground/60">
                    Guided storytelling environment with demo-only overlays and narrative widgets.
                </p>
            </div>

            <ExecutiveDashboard />
            <ModelTimeline />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <ActivityFeed />
                <SystemEventsPanel demoMode={isTechnical ? 'technical' : 'buyer'} isOpen={isTechnical} />
            </div>
        </div>
    )
}
