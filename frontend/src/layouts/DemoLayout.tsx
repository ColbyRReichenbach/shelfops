import { Link, Outlet, useLocation } from 'react-router-dom'
import { Cpu, ShoppingCart } from 'lucide-react'

import ShelfOpsLogo from '@/components/ShelfOpsLogo'
import WelcomeModal from '@/components/demo/WelcomeModal'

const TRACKS = [
    { to: '/demo?track=buyer', search: '?track=buyer', label: 'Buyer Track', icon: ShoppingCart },
    { to: '/demo?track=technical', search: '?track=technical', label: 'Technical Track', icon: Cpu },
]

export default function DemoLayout() {
    const location = useLocation()

    return (
        <div className="min-h-screen bg-shelf-background text-shelf-foreground">
            <header className="border-b border-white/20 bg-white/70 backdrop-blur-xl">
                <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4 lg:px-8">
                    <div className="flex items-center gap-4">
                        <ShelfOpsLogo collapsed={false} />
                        <div className="hidden text-sm text-shelf-foreground/55 md:block">
                            Dedicated demo environment
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {TRACKS.map(({ to, search, label, icon: Icon }) => (
                            <Link
                                key={to}
                                to={to}
                                className={
                                    `inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                                        location.search === search
                                            ? 'bg-shelf-primary text-white'
                                            : 'bg-white text-shelf-foreground/65 hover:text-shelf-primary'
                                    }`
                                }
                            >
                                <Icon className="h-3.5 w-3.5" />
                                {label}
                            </Link>
                        ))}
                        <Link
                            to="/"
                            className="ml-2 inline-flex items-center rounded-full border border-shelf-foreground/10 px-3 py-1.5 text-xs font-medium text-shelf-foreground/65 transition-colors hover:text-shelf-primary"
                        >
                            Open Production App
                        </Link>
                    </div>
                </div>
            </header>

            <WelcomeModal />
            <main>
                <Outlet />
            </main>
        </div>
    )
}
