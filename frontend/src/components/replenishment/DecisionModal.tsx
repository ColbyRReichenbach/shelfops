import { useEffect, useState } from 'react'
import { AlertTriangle, X } from 'lucide-react'

import type { ReplenishmentRecommendation } from '@/lib/types'

interface DecisionModalProps {
    action: 'accept' | 'edit' | 'reject'
    isOpen: boolean
    isPending: boolean
    recommendation: ReplenishmentRecommendation | null
    errorMessage: string | null
    onClose: () => void
    onSubmit: (payload: { quantity?: number; reasonCode?: string; notes?: string }) => void
}

const actionCopy = {
    accept: {
        title: 'Accept Recommendation',
        body: 'Approve the suggested quantity and create the linked PO decision.',
        submitLabel: 'Accept and Create PO',
    },
    edit: {
        title: 'Edit Quantity',
        body: 'Adjust the quantity, capture a reason code, and store the buyer override.',
        submitLabel: 'Save Override',
    },
    reject: {
        title: 'Reject Recommendation',
        body: 'Close this recommendation without creating a PO and capture the buyer rationale.',
        submitLabel: 'Reject Recommendation',
    },
} as const

export default function DecisionModal({
    action,
    isOpen,
    isPending,
    recommendation,
    errorMessage,
    onClose,
    onSubmit,
}: DecisionModalProps) {
    const [quantity, setQuantity] = useState('')
    const [reasonCode, setReasonCode] = useState('')
    const [notes, setNotes] = useState('')

    useEffect(() => {
        if (!recommendation || !isOpen) {
            return
        }

        setQuantity(String(recommendation.recommended_quantity))
        setReasonCode('')
        setNotes('')
    }, [isOpen, recommendation])

    if (!isOpen || !recommendation) {
        return null
    }

    const copy = actionCopy[action]

    return (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-[#1d1d1f]/45 px-4 backdrop-blur-sm">
            <div className="w-full max-w-xl rounded-[28px] bg-[linear-gradient(180deg,#ffffff,#f8f9fb)] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#86868b]">Buyer Decision</p>
                        <h3 className="mt-2 text-2xl font-semibold tracking-tight text-[#1d1d1f]">{copy.title}</h3>
                        <p className="mt-2 text-sm text-[#6e6e73]">{copy.body}</p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-full bg-[#f5f5f7] p-2 text-[#86868b] transition hover:bg-[#ececf0] hover:text-[#1d1d1f]"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <div className="mt-6 grid gap-4 md:grid-cols-2">
                    <InfoTile label="Recommended quantity" value={`${recommendation.recommended_quantity.toLocaleString()} units`} />
                    <InfoTile label="Current inventory position" value={recommendation.inventory_position.toLocaleString()} />
                </div>

                <div className="mt-6 space-y-4">
                    {action === 'edit' && (
                        <label className="block">
                            <span className="mb-2 block text-sm font-medium text-[#1d1d1f]">Edited quantity</span>
                            <input
                                type="number"
                                min={1}
                                value={quantity}
                                onChange={event => setQuantity(event.target.value)}
                                className="input"
                            />
                        </label>
                    )}

                    <label className="block">
                        <span className="mb-2 block text-sm font-medium text-[#1d1d1f]">
                            Reason code {action !== 'accept' ? '(required)' : '(optional)'}
                        </span>
                        <input
                            value={reasonCode}
                            onChange={event => setReasonCode(event.target.value)}
                            placeholder={action === 'edit' ? 'min_order_qty_override' : 'buyer_confirmed'}
                            className="input"
                        />
                    </label>

                    <label className="block">
                        <span className="mb-2 block text-sm font-medium text-[#1d1d1f]">Notes</span>
                        <textarea
                            value={notes}
                            onChange={event => setNotes(event.target.value)}
                            rows={4}
                            placeholder="Optional buyer notes"
                            className="input min-h-[120px] resize-none"
                        />
                    </label>

                    {errorMessage ? (
                        <div className="rounded-[18px] border border-[#ff3b30]/15 bg-[#ff3b30]/5 px-4 py-3 text-sm text-[#c9342a] shadow-[0_4px_16px_rgba(255,59,48,0.06)]">
                            <div className="flex items-start gap-2">
                                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                                <span>{errorMessage}</span>
                            </div>
                        </div>
                    ) : null}
                </div>

                <div className="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                    <button type="button" onClick={onClose} className="btn-secondary">
                        Cancel
                    </button>
                    <button
                        type="button"
                        onClick={() => {
                            const trimmedReasonCode = reasonCode.trim()
                            const trimmedNotes = notes.trim()

                            if ((action === 'edit' || action === 'reject') && !trimmedReasonCode) {
                                return
                            }

                            onSubmit({
                                quantity: action === 'edit' ? Number(quantity) : undefined,
                                reasonCode: trimmedReasonCode || undefined,
                                notes: trimmedNotes || undefined,
                            })
                        }}
                        disabled={isPending}
                        className="btn-primary disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {isPending ? 'Saving…' : copy.submitLabel}
                    </button>
                </div>
            </div>
        </div>
    )
}

function InfoTile({ label, value }: { label: string; value: string }) {
    return (
        <div className="surface-muted px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-[#86868b]">{label}</p>
            <p className="mt-2 text-base font-semibold text-[#1d1d1f]">{value}</p>
        </div>
    )
}
