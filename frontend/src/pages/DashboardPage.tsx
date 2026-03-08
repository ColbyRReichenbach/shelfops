/**
 * Dashboard Page — Wrapper for Executive Dashboard view.
 * Agent: full-stack-engineer | Skill: react-dashboard
 */

import ExecutiveDashboard from '@/components/dashboard/ExecutiveDashboard'
import ActivityFeed from '@/components/dashboard/ActivityFeed'
import ModelTimeline from '@/components/dashboard/ModelTimeline'
import SystemEventsPanel from '@/components/dashboard/SystemEventsPanel'

export default function DashboardPage() {
    return (
        <div className="p-6 lg:p-8 space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Executive Overview</h1>
                <p className="text-sm text-shelf-foreground/60 mt-1">Real-time revenue risk assessment</p>
            </div>

            {/* KPI + charts */}
            <ExecutiveDashboard />

            {/* Model accuracy sparkline — visible to both tracks */}
            <ModelTimeline />

            {/* Activity timeline + live events side by side */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <ActivityFeed />
                <SystemEventsPanel />
            </div>
        </div>
    )
}
