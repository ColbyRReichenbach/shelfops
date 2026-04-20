import { useMemo, useState } from 'react'
import type React from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Filter, Plus, Pencil, Trash2, Package, AlertCircle, Loader2, X } from 'lucide-react'

import { getApiErrorDetail } from '@/lib/api'
import type { Product, ProductMutationPayload } from '@/lib/types'
import { useCreateProduct, useDeleteProduct, useProducts, useUpdateProduct } from '@/hooks/useShelfOps'

type ProductFormState = {
    sku: string
    name: string
    category: string
    subcategory: string
    brand: string
    unit_cost: string
    unit_price: string
    weight: string
    shelf_life_days: string
    is_seasonal: boolean
    is_perishable: boolean
    status: string
}

function emptyProductForm(): ProductFormState {
    return {
        sku: '',
        name: '',
        category: '',
        subcategory: '',
        brand: '',
        unit_cost: '',
        unit_price: '',
        weight: '',
        shelf_life_days: '',
        is_seasonal: false,
        is_perishable: false,
        status: 'active',
    }
}

function productToForm(product: Product): ProductFormState {
    return {
        sku: product.sku,
        name: product.name,
        category: product.category ?? '',
        subcategory: product.subcategory ?? '',
        brand: product.brand ?? '',
        unit_cost: product.unit_cost != null ? String(product.unit_cost) : '',
        unit_price: product.unit_price != null ? String(product.unit_price) : '',
        weight: product.weight != null ? String(product.weight) : '',
        shelf_life_days: product.shelf_life_days != null ? String(product.shelf_life_days) : '',
        is_seasonal: product.is_seasonal,
        is_perishable: product.is_perishable,
        status: product.status,
    }
}

function buildCreatePayload(form: ProductFormState): ProductMutationPayload {
    return {
        sku: form.sku.trim(),
        name: form.name.trim(),
        category: form.category.trim() || null,
        subcategory: form.subcategory.trim() || null,
        brand: form.brand.trim() || null,
        unit_cost: form.unit_cost ? Number(form.unit_cost) : null,
        unit_price: form.unit_price ? Number(form.unit_price) : null,
        weight: form.weight ? Number(form.weight) : null,
        shelf_life_days: form.shelf_life_days ? Number(form.shelf_life_days) : null,
        is_seasonal: form.is_seasonal,
        is_perishable: form.is_perishable,
    }
}

function buildUpdatePayload(form: ProductFormState): Partial<ProductMutationPayload> {
    return {
        ...buildCreatePayload(form),
        status: form.status,
    }
}

export default function ProductsPage() {
    const navigate = useNavigate()
    const [searchTerm, setSearchTerm] = useState('')
    const [showFilters, setShowFilters] = useState(false)
    const [categoryFilter, setCategoryFilter] = useState('')
    const [statusFilter, setStatusFilter] = useState('')
    const [isFormOpen, setIsFormOpen] = useState(false)
    const [editingProduct, setEditingProduct] = useState<Product | null>(null)
    const [form, setForm] = useState<ProductFormState>(emptyProductForm)
    const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)

    const { data: products = [], isLoading, isError, error } = useProducts(categoryFilter || undefined, statusFilter || undefined)
    const createProduct = useCreateProduct()
    const updateProduct = useUpdateProduct()
    const deleteProduct = useDeleteProduct()

    const categories = useMemo(
        () => [...new Set(products.map(product => product.category).filter(Boolean))] as string[],
        [products],
    )

    const filteredProducts = useMemo(
        () =>
            products.filter(product =>
                product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                product.sku.toLowerCase().includes(searchTerm.toLowerCase()),
            ),
        [products, searchTerm],
    )

    const openCreateForm = () => {
        setEditingProduct(null)
        setForm(emptyProductForm())
        setIsFormOpen(true)
        setFeedback(null)
    }

    const openEditForm = (product: Product) => {
        setEditingProduct(product)
        setForm(productToForm(product))
        setIsFormOpen(true)
        setFeedback(null)
    }

    const closeForm = () => {
        setIsFormOpen(false)
        setEditingProduct(null)
        setForm(emptyProductForm())
    }

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setFeedback(null)

        try {
            if (editingProduct) {
                await updateProduct.mutateAsync({
                    productId: editingProduct.product_id,
                    payload: buildUpdatePayload(form),
                })
                setFeedback({ tone: 'success', text: `Updated ${form.name}.` })
            } else {
                await createProduct.mutateAsync(buildCreatePayload(form))
                setFeedback({ tone: 'success', text: `Created ${form.name}.` })
            }
            closeForm()
        } catch (submitError) {
            setFeedback({
                tone: 'error',
                text: getApiErrorDetail(submitError, 'Unable to save product.'),
            })
        }
    }

    async function handleDelete(product: Product) {
        if (!window.confirm(`Delete ${product.name}? This cannot be undone.`)) {
            return
        }

        try {
            await deleteProduct.mutateAsync(product.product_id)
            setFeedback({ tone: 'success', text: `Deleted ${product.name}.` })
            if (editingProduct?.product_id === product.product_id) {
                closeForm()
            }
        } catch (deleteError) {
            setFeedback({
                tone: 'error',
                text: getApiErrorDetail(deleteError, 'Unable to delete product.'),
            })
        }
    }

    const isSubmitting = createProduct.isPending || updateProduct.isPending

    return (
        <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-[#0071e3]">Products Catalog</h1>
                    <p className="mt-1 text-sm text-[#86868b]">Manage SKU metadata and inventory status</p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowFilters(current => !current)}
                        className="btn-secondary text-xs px-3 h-8 gap-2"
                    >
                        <Filter className="h-3 w-3" />
                        {showFilters ? 'Hide Filters' : 'Filters'}
                    </button>
                    <button onClick={openCreateForm} className="btn-primary text-xs px-3 h-8 gap-2">
                        <Plus className="h-3 w-3" />
                        Add Product
                    </button>
                </div>
            </div>

            {feedback && (
                <div
                    className={`rounded-xl border px-4 py-3 text-sm ${
                        feedback.tone === 'success'
                            ? 'border-[#34c759]/20 bg-[#34c759]/5 text-[#34c759]'
                            : 'border-[#ff3b30]/20 bg-[#ff3b30]/5 text-[#ff3b30]'
                    }`}
                >
                    {feedback.text}
                </div>
            )}

            {isFormOpen && (
                <div className="card border border-black/[0.02] shadow-sm">
                    <div className="mb-4 flex items-start justify-between gap-4">
                        <div>
                            <h2 className="text-lg font-semibold text-[#0071e3]">
                                {editingProduct ? 'Edit Product' : 'Create Product'}
                            </h2>
                            <p className="mt-1 text-sm text-[#86868b]">
                                Save catalog changes directly to the production API.
                            </p>
                        </div>
                        <button
                            onClick={closeForm}
                            className="rounded-lg p-2 text-[#86868b] transition-colors hover:bg-[#0071e3]/5 hover:text-[#0071e3]"
                            aria-label="Close product form"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>

                    <form className="space-y-4" onSubmit={handleSubmit}>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            <Field label="SKU">
                                <input value={form.sku} onChange={event => setForm(current => ({ ...current, sku: event.target.value }))} className="input" required />
                            </Field>
                            <Field label="Name">
                                <input value={form.name} onChange={event => setForm(current => ({ ...current, name: event.target.value }))} className="input" required />
                            </Field>
                            <Field label="Category">
                                <input value={form.category} onChange={event => setForm(current => ({ ...current, category: event.target.value }))} className="input" />
                            </Field>
                            <Field label="Subcategory">
                                <input value={form.subcategory} onChange={event => setForm(current => ({ ...current, subcategory: event.target.value }))} className="input" />
                            </Field>
                            <Field label="Brand">
                                <input value={form.brand} onChange={event => setForm(current => ({ ...current, brand: event.target.value }))} className="input" />
                            </Field>
                            <Field label="Status">
                                <select value={form.status} onChange={event => setForm(current => ({ ...current, status: event.target.value }))} className="input">
                                    <option value="active">Active</option>
                                    <option value="inactive">Inactive</option>
                                </select>
                            </Field>
                            <Field label="Unit Cost">
                                <input value={form.unit_cost} onChange={event => setForm(current => ({ ...current, unit_cost: event.target.value }))} className="input" inputMode="decimal" />
                            </Field>
                            <Field label="Unit Price">
                                <input value={form.unit_price} onChange={event => setForm(current => ({ ...current, unit_price: event.target.value }))} className="input" inputMode="decimal" />
                            </Field>
                            <Field label="Weight">
                                <input value={form.weight} onChange={event => setForm(current => ({ ...current, weight: event.target.value }))} className="input" inputMode="decimal" />
                            </Field>
                            <Field label="Shelf Life Days">
                                <input value={form.shelf_life_days} onChange={event => setForm(current => ({ ...current, shelf_life_days: event.target.value }))} className="input" inputMode="numeric" />
                            </Field>
                        </div>

                        <div className="flex flex-wrap gap-4">
                            <label className="inline-flex items-center gap-2 text-sm text-[#86868b]">
                                <input type="checkbox" checked={form.is_seasonal} onChange={event => setForm(current => ({ ...current, is_seasonal: event.target.checked }))} />
                                Seasonal
                            </label>
                            <label className="inline-flex items-center gap-2 text-sm text-[#86868b]">
                                <input type="checkbox" checked={form.is_perishable} onChange={event => setForm(current => ({ ...current, is_perishable: event.target.checked }))} />
                                Perishable
                            </label>
                        </div>

                        <div className="flex items-center justify-end gap-3">
                            <button type="button" onClick={closeForm} className="btn-secondary text-sm">
                                Cancel
                            </button>
                            <button type="submit" disabled={isSubmitting} className="btn-primary text-sm disabled:opacity-60">
                                {isSubmitting ? 'Saving...' : editingProduct ? 'Save Changes' : 'Create Product'}
                            </button>
                        </div>
                    </form>
                </div>
            )}

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
                <div className="card-compact flex items-center gap-3 lg:col-span-3">
                    <Search className="h-4 w-4 text-[#86868b]" />
                    <input
                        type="text"
                        placeholder="Search products by name or SKU..."
                        className="w-full border-none bg-transparent text-sm text-[#1d1d1f] placeholder:text-[#86868b] focus:outline-none"
                        value={searchTerm}
                        onChange={(event) => setSearchTerm(event.target.value)}
                    />
                </div>
                <div className="card-compact flex items-center justify-between">
                    <span className="text-xs font-medium text-[#86868b]">Visible SKUs</span>
                    <span className="text-lg font-bold text-[#0071e3]">{filteredProducts.length}</span>
                </div>
            </div>

            {showFilters && (
                <div className="card border border-black/[0.02] shadow-sm">
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <Field label="Category">
                            <select value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)} className="input">
                                <option value="">All Categories</option>
                                {categories.map(category => (
                                    <option key={category} value={category}>{category}</option>
                                ))}
                            </select>
                        </Field>
                        <Field label="Status">
                            <select value={statusFilter} onChange={event => setStatusFilter(event.target.value)} className="input">
                                <option value="">All Statuses</option>
                                <option value="active">Active</option>
                                <option value="inactive">Inactive</option>
                            </select>
                        </Field>
                    </div>
                </div>
            )}

            {isLoading && (
                <div className="card border border-black/[0.02] p-12 text-center shadow-sm">
                    <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-[#0071e3]" />
                    <p className="text-sm text-[#86868b]">Loading products...</p>
                </div>
            )}

            {isError && (
                <div className="card p-12 text-center bg-[#ff3b30]/5">
                    <AlertCircle className="mx-auto mb-3 h-8 w-8 text-[#ff3b30]" />
                    <p className="text-sm text-[#ff3b30]">
                        Failed to load products: {(error as Error)?.message ?? 'Unknown error'}
                    </p>
                </div>
            )}

            {!isLoading && !isError && (
                <div className="card overflow-hidden border border-black/[0.02] p-0 shadow-sm">
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="text-xs font-semibold uppercase tracking-wider text-[#86868b]">
                                <tr>
                                    <th className="px-6 py-4">Product Name</th>
                                    <th className="px-6 py-4">Category</th>
                                    <th className="px-6 py-4">Price / Cost</th>
                                    <th className="px-6 py-4">Brand</th>
                                    <th className="px-6 py-4">Status</th>
                                    <th className="px-6 py-4 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-black/5">
                                {filteredProducts.map((product) => (
                                    <tr
                                        key={product.product_id}
                                        onClick={() => navigate(`/products/${product.product_id}`)}
                                        className="group cursor-pointer transition-colors hover:bg-[#0071e3]/5"
                                    >
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5f5f7] text-[#0071e3]">
                                                    <Package className="h-5 w-5" />
                                                </div>
                                                <div>
                                                    <div className="font-medium text-[#1d1d1f]">{product.name}</div>
                                                    <div className="font-mono text-xs text-[#86868b]">{product.sku}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="inline-flex items-center rounded-md bg-[#f5f5f7] px-2 py-1 text-xs font-medium text-[#86868b] ring-1 ring-inset ring-black/5">
                                                {product.category ?? '—'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex flex-col">
                                                <span className="font-medium text-[#1d1d1f]">
                                                    {product.unit_price != null ? `$${product.unit_price.toFixed(2)}` : '—'}
                                                </span>
                                                <span className="text-xs text-[#86868b]">
                                                    {product.unit_cost != null ? `Cost: $${product.unit_cost.toFixed(2)}` : ''}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-[#86868b]">{product.brand ?? '—'}</td>
                                        <td className="px-6 py-4">
                                            <span className={`badge ${product.status === 'active' ? 'badge-low' : 'badge-critical'}`}>
                                                {product.status}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                                                <button
                                                    onClick={(event) => {
                                                        event.stopPropagation()
                                                        openEditForm(product)
                                                    }}
                                                    className="inline-flex items-center gap-1 rounded-lg border border-black/5 px-2 py-1 text-xs text-[#86868b] transition-colors hover:text-[#0071e3]"
                                                >
                                                    <Pencil className="h-3.5 w-3.5" />
                                                    Edit
                                                </button>
                                                <button
                                                    onClick={(event) => {
                                                        event.stopPropagation()
                                                        void handleDelete(product)
                                                    }}
                                                    className="inline-flex items-center gap-1 rounded-[8px] border border-[#ff3b30]/20 px-2 py-1 text-xs text-[#ff3b30] transition-colors hover:bg-[#ff3b30]/5"
                                                >
                                                    <Trash2 className="h-3.5 w-3.5" />
                                                    Delete
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {filteredProducts.length === 0 && (
                        <div className="p-12 text-center text-[#86868b]">
                            <AlertCircle className="mx-auto mb-3 h-10 w-10 opacity-20" />
                            <p>No products found{searchTerm ? ` matching "${searchTerm}"` : ''}</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

function Field({
    label,
    children,
}: {
    label: string
    children: React.ReactNode
}) {
    return (
        <label className="block space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-[#86868b]">{label}</span>
            {children}
        </label>
    )
}
