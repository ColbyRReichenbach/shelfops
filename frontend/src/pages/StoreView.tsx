import { Plus, Download, Loader2, AlertCircle } from 'lucide-react'
import StoreTable from '@/components/dashboard/StoreTable'
import { useStores } from '@/hooks/useShelfOps'

export default function StoreView() {
    const { data: stores = [], isLoading, isError } = useStores()

    return (
        <div className="p-6 lg:p-8 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Store Operations</h1>
                    <p className="text-sm text-shelf-foreground/60 mt-1">Manage store inventory and health status</p>
                </div>
                <div className="flex gap-3">
                    <button className="btn-secondary gap-2">
                        <Download className="h-4 w-4" />
                        Export
                    </button>
                    <button className="btn-primary gap-2 shadow-lg shadow-shelf-primary/20">
                        <Plus className="h-4 w-4" />
                        Add Store
                    </button>
                </div>
            </div>

            {isLoading && (
                <div className="card p-12 text-center border border-white/40 shadow-sm">
                    <Loader2 className="h-8 w-8 mx-auto mb-3 text-shelf-primary animate-spin" />
                    <p className="text-sm text-shelf-foreground/60">Loading stores...</p>
                </div>
            )}

            {isError && (
                <div className="card p-12 text-center border border-red-200 bg-red-50/50 shadow-sm">
                    <AlertCircle className="h-8 w-8 mx-auto mb-3 text-red-500" />
                    <p className="text-sm text-red-600">Failed to load stores</p>
                </div>
            )}

            {!isLoading && !isError && <StoreTable stores={stores} />}
        </div>
    )
}
