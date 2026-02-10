/**
 * Dashboard Page — Wrapper for Executive Dashboard view.
 * Agent: full-stack-engineer | Skill: react-dashboard
 */

import ExecutiveDashboard from '@/components/dashboard/ExecutiveDashboard'

export default function DashboardPage() {
    return (
        <div className="p-6 lg:p-8 space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Executive Overview</h1>
                <p className="text-sm text-shelf-foreground/60 mt-1">Real-time revenue risk assessment</p>
            </div>

            {/* Dashboard Content */}
            <ExecutiveDashboard />
        </div>
    )
}
