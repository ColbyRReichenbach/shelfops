import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Filter, Plus, MoreHorizontal, Package, AlertCircle, Loader2 } from 'lucide-react'
import { useProducts } from '@/hooks/useShelfOps'

export default function ProductsPage() {
    const navigate = useNavigate()
    const [searchTerm, setSearchTerm] = useState('')

    const { data: products = [], isLoading, isError, error } = useProducts()

    const filteredProducts = products.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.sku.toLowerCase().includes(searchTerm.toLowerCase())
    )

    const getStatusBadge = (status: string) => {
        switch (status) {
            case 'active':
                return <span className="badge badge-low">Active</span>
            case 'inactive':
                return <span className="badge badge-critical">Inactive</span>
            default:
                return <span className="badge bg-gray-100 text-gray-600">{status}</span>
        }
    }

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Products Catalog</h1>
                    <p className="text-sm text-shelf-foreground/60 mt-1">Manage SKU metadata and inventory status</p>
                </div>
                <div className="flex items-center gap-2">
                    <button className="btn-secondary text-xs px-3 h-8 gap-2">
                        <Filter className="h-3 w-3" />
                        Filter
                    </button>
                    <button className="btn-primary text-xs px-3 h-8 gap-2">
                        <Plus className="h-3 w-3" />
                        Add Product
                    </button>
                </div>
            </div>

            {/* Search and Stats Bar */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="lg:col-span-3 card-compact flex items-center gap-3">
                    <Search className="h-4 w-4 text-shelf-foreground/40" />
                    <input
                        type="text"
                        placeholder="Search products by name or SKU..."
                        className="bg-transparent border-none focus:outline-none text-sm w-full text-shelf-foreground placeholder:text-shelf-foreground/40"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <div className="card-compact flex items-center justify-between">
                    <span className="text-xs font-medium text-shelf-foreground/60">Total SKUs</span>
                    <span className="text-lg font-bold text-shelf-primary">{products.length}</span>
                </div>
            </div>

            {/* Loading state */}
            {isLoading && (
                <div className="card p-12 text-center border border-white/40 shadow-sm">
                    <Loader2 className="h-8 w-8 mx-auto mb-3 text-shelf-primary animate-spin" />
                    <p className="text-sm text-shelf-foreground/60">Loading products...</p>
                </div>
            )}

            {/* Error state */}
            {isError && (
                <div className="card p-12 text-center border border-red-200 bg-red-50/50 shadow-sm">
                    <AlertCircle className="h-8 w-8 mx-auto mb-3 text-red-500" />
                    <p className="text-sm text-red-600">Failed to load products: {(error as Error)?.message ?? 'Unknown error'}</p>
                </div>
            )}

            {/* Product Table */}
            {!isLoading && !isError && (
                <div className="card p-0 overflow-hidden border border-white/40 shadow-sm">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-shelf-secondary/5 text-shelf-foreground/70 uppercase text-xs font-semibold tracking-wider">
                                <tr>
                                    <th className="px-6 py-4">Product Name</th>
                                    <th className="px-6 py-4">Category</th>
                                    <th className="px-6 py-4">Price / Cost</th>
                                    <th className="px-6 py-4">Brand</th>
                                    <th className="px-6 py-4">Status</th>
                                    <th className="px-6 py-4 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-shelf-foreground/5">
                                {filteredProducts.map((product) => (
                                    <tr
                                        key={product.product_id}
                                        onClick={() => navigate(`/products/${product.product_id}`)}
                                        className="hover:bg-shelf-primary/5 transition-colors cursor-pointer group"
                                    >
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="h-10 w-10 rounded-lg bg-shelf-secondary/10 flex items-center justify-center text-shelf-primary">
                                                    <Package className="h-5 w-5" />
                                                </div>
                                                <div>
                                                    <div className="font-medium text-shelf-foreground">{product.name}</div>
                                                    <div className="text-xs text-shelf-foreground/50 font-mono">{product.sku}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="inline-flex items-center rounded-md bg-shelf-foreground/5 px-2 py-1 text-xs font-medium text-shelf-foreground/70 ring-1 ring-inset ring-shelf-foreground/10">
                                                {product.category ?? '—'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex flex-col">
                                                <span className="font-medium text-shelf-foreground">
                                                    {product.unit_price != null ? `$${product.unit_price.toFixed(2)}` : '—'}
                                                </span>
                                                <span className="text-xs text-shelf-foreground/50">
                                                    {product.unit_cost != null ? `Cost: $${product.unit_cost.toFixed(2)}` : ''}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-shelf-foreground/70">
                                            {product.brand ?? '—'}
                                        </td>
                                        <td className="px-6 py-4">
                                            {getStatusBadge(product.status)}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <button className="p-2 rounded-lg hover:bg-shelf-secondary/10 text-shelf-foreground/40 hover:text-shelf-foreground transition-colors">
                                                <MoreHorizontal className="h-4 w-4" />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {filteredProducts.length === 0 && !isLoading && (
                        <div className="p-12 text-center text-shelf-foreground/40">
                            <AlertCircle className="h-10 w-10 mx-auto mb-3 opacity-20" />
                            <p>No products found{searchTerm ? ` matching "${searchTerm}"` : ''}</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
