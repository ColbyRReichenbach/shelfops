import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import {
    Package,
    Warehouse,
    ClipboardList,
    DatabaseZap,
    LineChart,
    Store,
    BarChart3,
    Link2,
    LogOut,
    Brain,
    Activity,
} from 'lucide-react'
import ErrorBoundary from '@/components/ErrorBoundary'
import { useAlertSummary } from '@/hooks/useShelfOps'

const primaryNavItems = [
    { to: '/replenishment', icon: ClipboardList, label: 'Replenishment' },
    { to: '/data-readiness', icon: DatabaseZap, label: 'Data Readiness' },
    { to: '/pilot-impact', icon: LineChart, label: 'Impact' },
    { to: '/ml-ops', icon: Brain, label: 'Model Performance' },
]

const secondaryNavItems = [
    { to: '/inventory', icon: Warehouse, label: 'Inventory' },
    { to: '/forecasts', icon: BarChart3, label: 'Forecasts' },
    { to: '/operations', icon: Activity, label: 'Operations', badgeCount: 'alerts' as const },
    { to: '/integrations', icon: Link2, label: 'Integrations' },
    { to: '/products', icon: Package, label: 'Products' },
    { to: '/stores', icon: Store, label: 'Stores' },
]

export default function ModernDashboardLayout() {
    const { user, logout } = useAuth0()
    const [isCollapsed] = useState(false)
    const { data: alertSummary } = useAlertSummary()
    const openAlertCount = alertSummary?.open ?? 0

    return (
        <div className="flex min-h-screen w-full bg-[#f5f5f7]">
            {/* Sidebar */}
            <aside className="sidebar-glass w-64 h-screen fixed left-0 top-0 flex flex-col z-40">
                {/* Logo Area */}
                <div className="p-6 flex items-center gap-3">
                    <Link to="/replenishment" className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-[10px] bg-gradient-to-br from-[#0071e3] to-[#34c759] flex items-center justify-center shadow-sm">
                            <Package className="w-5 h-5 text-white" />
                        </div>
                        <span className="font-semibold text-lg tracking-tight text-[#1d1d1f]">ShelfOps</span>
                    </Link>
                </div>

                {/* Navigation */}
                <nav className="flex-1 px-3 py-2 space-y-5 overflow-y-auto">
                    <NavSection
                        title="Operate"
                        items={primaryNavItems}
                        isCollapsed={isCollapsed}
                        openAlertCount={openAlertCount}
                    />
                    <NavSection
                        title="Insights"
                        items={secondaryNavItems}
                        isCollapsed={isCollapsed}
                        openAlertCount={openAlertCount}
                    />
                </nav>

                {/* User Profile */}
                <div className="p-4">
                    <div className="bg-white rounded-[16px] p-4 shadow-[0_2px_10px_rgba(0,0,0,0.04)] flex items-center gap-3 hover-lift">
                        <div className="h-10 w-10 rounded-full bg-[#f5f5f7] flex items-center justify-center text-sm font-semibold text-[#1d1d1f] overflow-hidden">
                            {user?.picture ? (
                                <img src={user.picture} alt={user.name} className="h-full w-full rounded-full object-cover" />
                            ) : (
                                user?.name?.charAt(0) ?? 'U'
                            )}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-[#1d1d1f] truncate">{user?.name ?? 'User'}</p>
                            <p className="text-xs text-[#86868b] truncate">{user?.email ?? ''}</p>
                        </div>
                        <button
                            onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
                            className="p-2 rounded-lg text-[#86868b] hover:bg-[#ff3b30]/10 hover:text-[#ff3b30] transition-colors"
                            title="Log out"
                        >
                            <LogOut className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 ml-64 min-h-screen">
                <div className="animate-fade-in">
                    <ErrorBoundary>
                        <Outlet />
                    </ErrorBoundary>
                </div>
            </main>
        </div>
    )
}

function NavSection({
    title,
    items,
    isCollapsed,
    openAlertCount,
}: {
    title: string
    items: Array<{ to: string; icon: typeof Package; label: string; badgeCount?: 'alerts' }>
    isCollapsed: boolean
    openAlertCount: number
}) {
    return (
        <div className="space-y-2">
            <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#86868b]">
                {title}
            </p>
            <div className="space-y-1">
                {items.map(({ to, icon: Icon, label, badgeCount }) => (
                    <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) =>
                            `w-full flex items-center gap-3 px-3 py-2.5 rounded-[12px] text-sm font-medium transition-colors ${
                                isActive
                                    ? 'bg-white text-[#0071e3] shadow-[0_2px_10px_rgba(0,0,0,0.04)]'
                                    : 'text-[#86868b] hover:bg-black/5 hover:text-[#1d1d1f]'
                            }`
                        }
                    >
                        <div className="relative shrink-0">
                            <Icon className="h-5 w-5 transition-colors" />
                            {badgeCount === 'alerts' && openAlertCount > 0 && isCollapsed && (
                                <span className="absolute -top-1.5 -right-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#ff3b30] text-[10px] font-bold text-white px-1">
                                    {openAlertCount > 9 ? '9+' : openAlertCount}
                                </span>
                            )}
                        </div>

                        <span className="flex-1 truncate">{label}</span>

                        {badgeCount === 'alerts' && openAlertCount > 0 && (
                            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-[#ff3b30] text-[10px] font-bold text-white px-1.5">
                                {openAlertCount > 99 ? '99+' : openAlertCount}
                            </span>
                        )}
                    </NavLink>
                ))}
            </div>
        </div>
    )
}
