/**
 * Dashboard Layout — Sidebar + header shell.
 * Agent: full-stack-engineer | Skill: react-dashboard (layout pattern)
 */

import { NavLink, Outlet } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import {
    LayoutDashboard,
    Package,
    Store,
    Bell,
    BarChart3,
    Link2,
    LogOut,
    Activity,
} from 'lucide-react'

const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/alerts', icon: Bell, label: 'Alerts' },
    { to: '/forecasts', icon: BarChart3, label: 'Forecasts' },
    { to: '/products', icon: Package, label: 'Products' },
    { to: '/stores', icon: Store, label: 'Stores' },
    { to: '/integrations', icon: Link2, label: 'Integrations' },
]

export default function DashboardLayout() {
    const { user, logout } = useAuth0()

    return (
        <div className="flex h-screen overflow-hidden">
            {/* Sidebar */}
            <aside className="w-64 flex-shrink-0 border-r border-surface-700 bg-surface-900/80 backdrop-blur-xl flex flex-col">
                {/* Logo */}
                <div className="flex items-center gap-3 px-6 py-5 border-b border-surface-700">
                    <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
                        <Activity className="h-4 w-4 text-white" />
                    </div>
                    <span className="text-lg font-bold tracking-tight">ShelfOps</span>
                </div>

                {/* Nav */}
                <nav className="flex-1 px-3 py-4 space-y-1">
                    {navItems.map(({ to, icon: Icon, label }) => (
                        <NavLink
                            key={to}
                            to={to}
                            end={to === '/'}
                            className={({ isActive }) =>
                                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 ${isActive
                                    ? 'bg-brand-600/15 text-brand-400 shadow-sm'
                                    : 'text-surface-200/70 hover:bg-surface-800 hover:text-white'
                                }`
                            }
                        >
                            <Icon className="h-4 w-4" />
                            {label}
                        </NavLink>
                    ))}
                </nav>

                {/* User */}
                <div className="border-t border-surface-700 px-4 py-4">
                    <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-full bg-brand-600/20 flex items-center justify-center text-xs font-bold text-brand-400">
                            {user?.name?.charAt(0) ?? 'U'}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{user?.name ?? 'User'}</p>
                            <p className="text-xs text-surface-200/50 truncate">{user?.email ?? ''}</p>
                        </div>
                        <button
                            onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
                            className="text-surface-200/50 hover:text-white transition-colors"
                            aria-label="Log out"
                        >
                            <LogOut className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </aside>

            {/* Main content */}
            <main className="flex-1 overflow-y-auto bg-surface-900">
                <Outlet />
            </main>
        </div>
    )
}
