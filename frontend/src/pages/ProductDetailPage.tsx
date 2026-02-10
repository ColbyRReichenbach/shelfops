import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Package, Truck, AlertTriangle, Loader2, AlertCircle } from 'lucide-react'
import ForecastChart from '@/components/dashboard/ForecastChart'
import { useProduct, useForecasts, useAlerts } from '@/hooks/useShelfOps'

export default function ProductDetailPage() {
    const { productId } = useParams()
    const navigate = useNavigate()

    const { data: product, isLoading: productLoading, isError: productError } = useProduct(productId)

    const { data: forecasts = [] } = useForecasts(
        productId ? { product_id: productId } : undefined
    )

    const { data: alerts = [] } = useAlerts(
        productId ? { status: 'open' } : undefined
    )
    const productAlerts = alerts.filter(a => a.product_id === productId)

    // Transform forecast data for the chart
    const chartData = forecasts.map(f => ({
        date: f.forecast_date,
        forecast: Math.round(f.forecasted_demand),
        lower: f.lower_bound != null ? Math.round(f.lower_bound) : undefined,
        upper: f.upper_bound != null ? Math.round(f.upper_bound) : undefined,
    }))

    if (productLoading) {
        return (
            <div className="p-6 lg:p-8 flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                    <Loader2 className="h-8 w-8 mx-auto mb-3 text-shelf-primary animate-spin" />
                    <p className="text-sm text-shelf-foreground/60">Loading product details...</p>
                </div>
            </div>
        )
    }

    if (productError || !product) {
        return (
            <div className="p-6 lg:p-8">
                <div className="card p-12 text-center border border-red-200 bg-red-50/50 shadow-sm">
                    <AlertCircle className="h-8 w-8 mx-auto mb-3 text-red-500" />
                    <p className="text-sm text-red-600">Product not found</p>
                    <button onClick={() => navigate(-1)} className="btn-secondary mt-4 text-sm">Go Back</button>
                </div>
            </div>
        )
    }

    const margin = product.unit_price && product.unit_cost
        ? (((product.unit_price - product.unit_cost) / product.unit_price) * 100).toFixed(1)
        : null

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            {/* Header / Nav */}
            <div className="flex items-center gap-4">
                <button
                    onClick={() => navigate(-1)}
                    className="p-2 rounded-lg hover:bg-shelf-secondary/10 text-shelf-foreground/60 hover:text-shelf-foreground transition-colors"
                >
                    <ArrowLeft className="h-5 w-5" />
                </button>
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">
                        {product.name}
                    </h1>
                    <div className="flex items-center gap-2 text-sm text-shelf-foreground/60 mt-1">
                        <span className="font-mono bg-shelf-secondary/10 px-1.5 py-0.5 rounded text-shelf-secondary text-xs">SKU: {product.sku}</span>
                        {product.category && (
                            <>
                                <span>•</span>
                                <span>{product.category}{product.subcategory ? ` / ${product.subcategory}` : ''}</span>
                            </>
                        )}
                        {product.brand && (
                            <>
                                <span>•</span>
                                <span>{product.brand}</span>
                            </>
                        )}
                    </div>
                </div>
            </div>

            {/* Top Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Product Info Card */}
                <div className="card border border-white/40 shadow-sm relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <Package className="h-16 w-16 text-shelf-primary" />
                    </div>
                    <h3 className="text-sm font-semibold text-shelf-foreground/70 uppercase tracking-wider">Pricing</h3>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-3xl font-bold text-shelf-primary">
                            {product.unit_price != null ? `$${product.unit_price.toFixed(2)}` : '—'}
                        </span>
                        <span className="text-sm text-shelf-foreground/60">retail</span>
                    </div>
                    <div className="mt-4 space-y-1 text-sm">
                        <div className="flex justify-between">
                            <span className="text-shelf-foreground/60">Cost</span>
                            <span className="font-medium">{product.unit_cost != null ? `$${product.unit_cost.toFixed(2)}` : '—'}</span>
                        </div>
                        {margin && (
                            <div className="flex justify-between">
                                <span className="text-shelf-foreground/60">Margin</span>
                                <span className="font-medium text-green-600">{margin}%</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Supply Info */}
                <div className="card border border-white/40 shadow-sm relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <Truck className="h-16 w-16 text-shelf-secondary" />
                    </div>
                    <h3 className="text-sm font-semibold text-shelf-foreground/70 uppercase tracking-wider">Product Info</h3>
                    <div className="mt-4 space-y-2 text-sm">
                        <div className="flex justify-between">
                            <span className="text-shelf-foreground/60">Perishable</span>
                            <span className="font-medium">{product.is_perishable ? 'Yes' : 'No'}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-shelf-foreground/60">Seasonal</span>
                            <span className="font-medium">{product.is_seasonal ? 'Yes' : 'No'}</span>
                        </div>
                        {product.shelf_life_days && (
                            <div className="flex justify-between">
                                <span className="text-shelf-foreground/60">Shelf Life</span>
                                <span className="font-medium">{product.shelf_life_days} days</span>
                            </div>
                        )}
                        {product.weight && (
                            <div className="flex justify-between">
                                <span className="text-shelf-foreground/60">Weight</span>
                                <span className="font-medium">{product.weight} lbs</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Active Alerts */}
                <div className={`card border shadow-sm relative overflow-hidden group ${productAlerts.length > 0 ? 'bg-red-50/50 border-red-200/50' : 'border-white/40'
                    }`}>
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <AlertTriangle className="h-16 w-16 text-shelf-accent" />
                    </div>
                    <h3 className="text-sm font-semibold text-shelf-accent uppercase tracking-wider">Active Alerts</h3>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-3xl font-bold text-shelf-accent">{productAlerts.length}</span>
                        <span className="text-sm text-shelf-foreground/60">open</span>
                    </div>
                    {productAlerts.length > 0 && (
                        <div className="mt-4 space-y-1">
                            {productAlerts.slice(0, 2).map(a => (
                                <p key={a.alert_id} className="text-xs text-shelf-foreground/70 truncate">
                                    • {a.message}
                                </p>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Forecast Chart */}
            {chartData.length > 0 && <ForecastChart data={chartData} />}

            {/* Product Details Grid */}
            <div className="card border border-white/40 shadow-sm">
                <h3 className="text-lg font-semibold text-shelf-primary mb-4">Product Details</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-sm">
                    <div>
                        <p className="text-shelf-foreground/60 mb-1">SKU</p>
                        <p className="font-medium text-shelf-foreground font-mono">{product.sku}</p>
                    </div>
                    <div>
                        <p className="text-shelf-foreground/60 mb-1">Status</p>
                        <p className="font-medium text-shelf-foreground capitalize">{product.status}</p>
                    </div>
                    <div>
                        <p className="text-shelf-foreground/60 mb-1">Category</p>
                        <p className="font-medium text-shelf-foreground">{product.category ?? '—'}</p>
                    </div>
                    <div>
                        <p className="text-shelf-foreground/60 mb-1">Brand</p>
                        <p className="font-medium text-shelf-foreground">{product.brand ?? '—'}</p>
                    </div>
                    <div>
                        <p className="text-shelf-foreground/60 mb-1">Created</p>
                        <p className="font-medium text-shelf-foreground">{new Date(product.created_at).toLocaleDateString()}</p>
                    </div>
                    <div>
                        <p className="text-shelf-foreground/60 mb-1">Last Updated</p>
                        <p className="font-medium text-shelf-foreground">{new Date(product.updated_at).toLocaleDateString()}</p>
                    </div>
                    {product.unit_cost && (
                        <div>
                            <p className="text-shelf-foreground/60 mb-1">Unit Cost</p>
                            <p className="font-medium text-shelf-foreground">${product.unit_cost.toFixed(2)}</p>
                        </div>
                    )}
                    {product.unit_price && (
                        <div>
                            <p className="text-shelf-foreground/60 mb-1">Retail Price</p>
                            <p className="font-medium text-shelf-foreground">${product.unit_price.toFixed(2)}</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
