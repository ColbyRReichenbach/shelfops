import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import {
    LayoutDashboard,
    Package,
    ShoppingCart,
    Warehouse,
    Store,
    Bell,
    BarChart3,
    Cpu,
    Link2,
    LogOut,
    ChevronLeft,
    ChevronRight,
    Settings,
} from 'lucide-react'
import ShelfOpsLogo from '@/components/ShelfOpsLogo'
import ErrorBoundary from '@/components/ErrorBoundary'
import { useAlertSummary } from '@/hooks/useShelfOps'

const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/alerts', icon: Bell, label: 'Alerts' },
    { to: '/forecasts', icon: BarChart3, label: 'Forecasts' },
    { to: '/buy', icon: ShoppingCart, label: 'Buy Center' },
    { to: '/mlops', icon: Cpu, label: 'MLOps' },
    { to: '/products', icon: Package, label: 'Products' },
    { to: '/inventory', icon: Warehouse, label: 'Inventory' },
    { to: '/stores', icon: Store, label: 'Stores' },
    { to: '/integrations', icon: Link2, label: 'Integrations' },
]

export default function ModernDashboardLayout() {
    const { user, logout } = useAuth0()
    const [isCollapsed, setIsCollapsed] = useState(false)
    const location = useLocation()
    const { data: alertSummary } = useAlertSummary()
    const openAlertCount = alertSummary?.open ?? 0

    // Derive current page name from the route path
    const currentPage = navItems.find(item => {
        if (item.to === '/') return location.pathname === '/'
        return location.pathname.startsWith(item.to)
    })?.label ?? 'Dashboard'

    return (
        <div className="flex h-screen overflow-hidden bg-shelf-background text-shelf-foreground font-sans">
            {/* Sidebar */}
            <aside
                className={`
                    relative z-20 flex flex-col border-r border-white/20 bg-white/60 backdrop-blur-2xl transition-all duration-300 ease-in-out
                    ${isCollapsed ? 'w-20' : 'w-64'}
                `}
            >
                {/* Toggle Button */}
                <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className="absolute -right-3 top-8 flex h-6 w-6 items-center justify-center rounded-full bg-white shadow-md border border-shelf-foreground/10 text-shelf-foreground/60 hover:text-shelf-primary transition-colors hover:scale-110 active:scale-95 z-30"
                >
                    {isCollapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
                </button>

                {/* Logo Area */}
                <div className={`flex items-center gap-3 px-6 py-6 border-b border-shelf-foreground/5 transition-all duration-300 ${isCollapsed ? 'justify-center px-2' : ''}`}>
                    <ShelfOpsLogo collapsed={isCollapsed} />
                </div>

                {/* Navigation */}
                <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
                    {navItems.map(({ to, icon: Icon, label }) => (
                        <NavLink
                            key={to}
                            to={to}
                            end={to === '/'}
                            className={({ isActive }) =>
                                `flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-all duration-200 group
                                ${isActive
                                    ? 'bg-shelf-primary/10 text-shelf-primary shadow-sm'
                                    : 'text-shelf-foreground/70 hover:bg-white/50 hover:text-shelf-foreground'
                                }
                                ${isCollapsed ? 'justify-center' : ''}`
                            }
                            title={isCollapsed ? label : undefined}
                        >
                            <div className="relative shrink-0">
                                <Icon className="h-5 w-5 transition-colors" />
                                {label === 'Alerts' && openAlertCount > 0 && isCollapsed && (
                                    <span className="absolute -top-1.5 -right-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white px-1">
                                        {openAlertCount > 9 ? '9+' : openAlertCount}
                                    </span>
                                )}
                            </div>

                            {!isCollapsed && (
                                <span className="flex-1 truncate transition-opacity duration-300">
                                    {label}
                                </span>
                            )}

                            {!isCollapsed && label === 'Alerts' && openAlertCount > 0 && (
                                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white px-1.5">
                                    {openAlertCount > 99 ? '99+' : openAlertCount}
                                </span>
                            )}
                        </NavLink>
                    ))}
                </nav>

                {/* User Profile */}
                <div className="border-t border-shelf-foreground/5 p-4">
                    <div className={`flex items-center gap-3 transition-all duration-300 ${isCollapsed ? 'justify-center flex-col' : ''}`}>
                        <div className="h-9 w-9 rounded-full bg-shelf-primary/10 flex items-center justify-center text-xs font-bold text-shelf-primary border border-white/50 shadow-sm">
                            {user?.picture ? (
                                <img src={user.picture} alt={user.name} className="h-full w-full rounded-full object-cover" />
                            ) : (
                                user?.name?.charAt(0) ?? 'U'
                            )}
                        </div>

                        {!isCollapsed && (
                            <div className="flex-1 min-w-0 transition-opacity duration-300">
                                <p className="text-sm font-semibold text-shelf-foreground truncate">{user?.name ?? 'User'}</p>
                                <p className="text-xs text-shelf-foreground/50 truncate">{user?.email ?? ''}</p>
                            </div>
                        )}

                        <button
                            onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
                            className={`p-2 rounded-lg text-shelf-foreground/40 hover:bg-red-50 hover:text-red-500 transition-colors ${isCollapsed ? 'mt-2' : ''}`}
                            title="Log out"
                        >
                            <LogOut className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto relative z-10">
                {/* Header/Breadcrumbs mockup */}
                <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-white/20 bg-shelf-background/80 px-8 backdrop-blur-md">
                    <div className="flex items-center gap-2 text-sm text-shelf-foreground/50">
                        <span>ShelfOps</span>
                        <span>/</span>
                        <span className="font-medium text-shelf-foreground">{currentPage}</span>
                    </div>
                    <div className="flex items-center gap-4">
                        <button className="p-2 text-shelf-foreground/40 hover:text-shelf-primary transition-colors">
                            <Settings className="h-5 w-5" />
                        </button>
                    </div>
                </header>

                <div className="animate-fade-in p-0">
                    <ErrorBoundary>
                        <Outlet />
                    </ErrorBoundary>
                </div>
            </main>
        </div>
    )
}
