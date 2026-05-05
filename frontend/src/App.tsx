import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import ModernDashboardLayout from '@/layouts/ModernDashboardLayout'
import DataReadinessPage from '@/pages/DataReadinessPage'
import StoreView from '@/pages/StoreView'
import ProductDetailPage from '@/pages/ProductDetailPage'
import ForecastsPage from '@/pages/ForecastsPage'
import ProductsPage from '@/pages/ProductsPage'
import IntegrationsPage from '@/pages/IntegrationsPage'
import InventoryPage from '@/pages/InventoryPage'
import MLOpsPage from '@/pages/MLOpsPage'
import OperationsPage from '@/pages/OperationsPage'
import PilotImpactPage from '@/pages/PilotImpactPage'
import ReplenishmentPage from '@/pages/ReplenishmentPage'
import StoreDetailPage from '@/pages/StoreDetailPage'

function AuthGuard({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0()

    // Development bypass
    if (import.meta.env.DEV) {
        return <>{children}</>
    }

    if (isLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-[#f5f5f7]">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#0071e3] border-t-transparent" />
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
                    <Route index element={<Navigate to="/replenishment" replace />} />
                    <Route path="alerts" element={<Navigate to="/operations" replace />} />
                    <Route path="data-readiness" element={<DataReadinessPage />} />
                    <Route path="forecasts" element={<ForecastsPage />} />

                    {/* Product Routes */}
                    <Route path="products/:productId" element={<ProductDetailPage />} />
                    <Route path="products" element={<ProductsPage />} />

                    <Route path="inventory" element={<InventoryPage />} />
                    <Route path="pilot-impact" element={<PilotImpactPage />} />
                    <Route path="replenishment" element={<ReplenishmentPage />} />
                    <Route path="stores/:storeId" element={<StoreDetailPage />} />
                    <Route path="stores" element={<StoreView />} />
                    <Route path="integrations" element={<IntegrationsPage />} />
                    <Route path="operations" element={<OperationsPage />} />
                    <Route path="ml-ops" element={<MLOpsPage />} />
                </Route>

                {/* Catch-all redirect */}
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </AuthGuard>
    )
}
