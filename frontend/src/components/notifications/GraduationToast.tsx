/**
 * GraduationToast — Banner notification for model graduation events.
 * WS-4 demo component. Uses Radix UI Toast.
 */

import * as Toast from '@radix-ui/react-toast'
import { X, TrendingUp } from 'lucide-react'

export interface GraduationToastProps {
    modelName: string
    prevMase: number
    newMase: number
    improvementPct: number
    onDismiss: () => void
}

export default function GraduationToast({
    modelName,
    prevMase,
    newMase,
    improvementPct,
    onDismiss,
}: GraduationToastProps) {
    return (
        <Toast.Provider swipeDirection="right" duration={8000}>
            <Toast.Root
                open={true}
                onOpenChange={open => {
                    if (!open) onDismiss()
                }}
                className="
                    group pointer-events-auto relative flex w-full max-w-md items-start gap-3
                    overflow-hidden rounded-xl border border-green-200 bg-white p-4 shadow-lg
                    data-[state=open]:animate-in data-[state=closed]:animate-out
                    data-[swipe=end]:animate-out data-[state=closed]:fade-out-80
                    data-[state=open]:slide-in-from-top-full data-[state=closed]:slide-out-to-right-full
                "
            >
                {/* Icon */}
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-green-100">
                    <TrendingUp className="h-5 w-5 text-green-600" />
                </div>

                <div className="flex-1 min-w-0">
                    <Toast.Title className="text-sm font-semibold text-shelf-foreground">
                        Model graduated!
                    </Toast.Title>
                    <Toast.Description className="mt-1 text-xs text-shelf-foreground/60 leading-relaxed">
                        <span className="font-medium text-shelf-foreground">{modelName}</span>
                        {' '}MASE improved from{' '}
                        <span className="font-mono">{prevMase.toFixed(2)}</span>
                        {' '}&rarr;{' '}
                        <span className="font-mono text-green-600">{newMase.toFixed(2)}</span>
                        {' '}(+{improvementPct.toFixed(0)}% accuracy)
                    </Toast.Description>
                </div>

                <Toast.Close
                    onClick={onDismiss}
                    className="flex-shrink-0 rounded-md p-1 text-shelf-foreground/40 hover:text-shelf-foreground/70 transition-colors"
                    aria-label="Dismiss graduation notification"
                >
                    <X className="h-4 w-4" />
                </Toast.Close>
            </Toast.Root>

            <Toast.Viewport className="fixed top-4 right-4 z-[100] flex max-h-screen w-full max-w-md flex-col gap-2 p-4" />
        </Toast.Provider>
    )
}
