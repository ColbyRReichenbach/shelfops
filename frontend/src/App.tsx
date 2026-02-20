import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import ModernDashboardLayout from '@/layouts/ModernDashboardLayout'
import DashboardPage from '@/pages/DashboardPage'
import AlertsPage from '@/pages/AlertsPage'
import StoreView from '@/pages/StoreView'
import ProductDetailPage from '@/pages/ProductDetailPage'
import ForecastsPage from '@/pages/ForecastsPage'
import MLOpsPage from '@/pages/MLOpsPage'
import BuyCenterPage from '@/pages/BuyCenterPage'
import ProductsPage from '@/pages/ProductsPage'
import IntegrationsPage from '@/pages/IntegrationsPage'
import InventoryPage from '@/pages/InventoryPage'
import StoreActionView from '@/pages/StoreActionView'

function AuthGuard({ children }: { children: React.ReactNode }) {
    // Development bypass
    if (import.meta.env.DEV) {
        return <>{children}</>
    }

    const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0()

    if (isLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-shelf-background">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-shelf-primary border-t-transparent" />
            </div>
        )
    }

    if (!isAuthenticated) {
        loginWithRedirect()
        return null
    }

    return <>{children}</>
}

export default function App() {
    return (
        <AuthGuard>
            <Routes>
                <Route element={<ModernDashboardLayout />}>
                    <Route index element={<DashboardPage />} />
                    <Route path="alerts" element={<AlertsPage />} />
                    <Route path="forecasts" element={<ForecastsPage />} />
                    <Route path="mlops" element={<MLOpsPage />} />
                    <Route path="buy" element={<BuyCenterPage />} />

                    {/* Product Routes */}
                    <Route path="products/:productId" element={<ProductDetailPage />} />
                    <Route path="products" element={<ProductsPage />} />

                    <Route path="inventory" element={<InventoryPage />} />
                    <Route path="action-items" element={<StoreActionView />} />
                    <Route path="stores" element={<StoreView />} />
                    <Route path="integrations" element={<IntegrationsPage />} />
                </Route>

                {/* Catch-all redirect */}
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </AuthGuard>
    )
}
