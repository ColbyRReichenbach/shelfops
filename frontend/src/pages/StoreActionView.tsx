import { useState } from 'react'
import { CheckCircle2, XCircle, AlertTriangle, Package, AlertCircle } from 'lucide-react'
import { useAlerts, useRecordAlertOutcome, useRecordAnomalyOutcome } from '@/hooks/useShelfOps'

export default function StoreActionView() {
    const { data: alerts = [], isLoading } = useAlerts()
    const { mutate: recordAlertOutcome } = useRecordAlertOutcome()
    const { mutate: recordAnomalyOutcome } = useRecordAnomalyOutcome()

    // Filter to only show unresolved alerts
    const activeActions = alerts.filter(a => a.status !== 'resolved' && a.status !== 'dismissed')

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-12">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-shelf-primary border-t-transparent" />
            </div>
        )
    }

    if (activeActions.length === 0) {
        return (
            <div className="p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto space-y-6">
                <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Daily Action Items</h1>
                <div className="card p-12 text-center border-white/40 shadow-sm">
                    <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-500 opacity-80" />
                    <h2 className="text-lg font-semibold text-shelf-foreground">All Caught Up!</h2>
                    <p className="text-shelf-foreground/60 mt-2">No pending action items for your store today.</p>
                </div>
            </div>
        )
    }

    return (
        <div className="p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight text-shelf-primary">Daily Action Items</h1>
                <p className="text-sm text-shelf-foreground/60 mt-1">Review and process your store's assigned actions</p>
            </div>

            <div className="grid gap-4">
                {activeActions.map((action) => (
                    <ActionCard
                        key={action.alert_id}
                        action={action}
                        onAlertOutcome={recordAlertOutcome}
                        onAnomalyOutcome={recordAnomalyOutcome}
                    />
                ))}
            </div>
        </div>
    )
}

function ActionCard({ action, onAlertOutcome, onAnomalyOutcome }: { action: any, onAlertOutcome: any, onAnomalyOutcome: any }) {
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleOutcome = (outcomeType: string, actionCategory: string) => {
        setIsSubmitting(true)
        if (actionCategory === 'anomaly') {
            onAnomalyOutcome({
                anomalyId: action.alert_id,
                outcome: outcomeType,
                action_taken: 'Review completed by store manager'
            }, {
                onSettled: () => setIsSubmitting(false)
            })
        } else {
            onAlertOutcome({
                alertId: action.alert_id,
                outcome: outcomeType,
                outcome_notes: 'Approve outcome recorded via Store UI'
            }, {
                onSettled: () => setIsSubmitting(false)
            })
        }
    }

    const isAnomaly = action.alert_type === 'anomaly_detected'

    return (
        <div className="card p-4 sm:p-6 flex flex-col sm:flex-row gap-4 sm:items-center justify-between border-l-4 border-l-shelf-primary shadow-sm hover:shadow-md transition-shadow">
            <div className="flex gap-4 items-start sm:items-center">
                <div className={`p-3 rounded-full shrink-0 ${action.alert_type === 'reorder_recommended' ? 'bg-blue-50 text-blue-600' :
                    action.alert_type === 'markdown_recommended' ? 'bg-orange-50 text-orange-600' :
                        'bg-red-50 text-red-600'
                    }`}>
                    {action.alert_type === 'reorder_recommended' && <Package className="h-6 w-6" />}
                    {action.alert_type === 'markdown_recommended' && <AlertTriangle className="h-6 w-6" />}
                    {isAnomaly && <AlertCircle className="h-6 w-6" />}
                </div>

                <div>
                    <h3 className="font-semibold text-shelf-foreground capitalize">
                        {action.alert_type.replace('_', ' ')}
                    </h3>
                    <p className="text-sm text-shelf-foreground/70 mt-1 line-clamp-2">
                        {action.message}
                    </p>
                    {action.metadata?.suggested_qty && (
                        <div className="mt-2">
                            <p className="text-sm font-medium text-shelf-primary">
                                Suggested Quantity: <span className="font-bold text-lg">{action.metadata.suggested_qty}</span>
                            </p>
                            {(action.metadata?.case_pack_size > 1 || action.metadata?.moq > 1) && (
                                <p className="text-xs text-shelf-foreground/50 mt-0.5">
                                    (Rounded to meet supplier case pack of {action.metadata.case_pack_size} and MOQ of {action.metadata.moq})
                                </p>
                            )}
                        </div>
                    )}
                </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-2 shrink-0 mt-4 sm:mt-0 w-full sm:w-auto">
                <button
                    disabled={isSubmitting}
                    onClick={() => handleOutcome(isAnomaly ? 'false_positive' : 'false_positive', isAnomaly ? 'anomaly' : 'alert')}
                    className="btn px-4 py-2 bg-slate-100 text-slate-700 hover:bg-slate-200 border-none justify-center"
                >
                    <XCircle className="h-4 w-4 mr-2" />
                    Dismiss
                </button>
                <button
                    disabled={isSubmitting}
                    onClick={() => handleOutcome(isAnomaly ? 'true_positive' : 'true_positive', isAnomaly ? 'anomaly' : 'alert')}
                    className="btn-primary px-6 py-2 shadow-md justify-center"
                >
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    Approve
                </button>
            </div>
        </div>
    )
}
