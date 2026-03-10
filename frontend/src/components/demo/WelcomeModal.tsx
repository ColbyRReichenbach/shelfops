/**
 * WelcomeModal — First-load demo tour selector.
 * WS-4 demo component. Uses sessionStorage to prevent repeat displays.
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, ShoppingCart, Cpu } from 'lucide-react'

const SESSION_KEY = 'demo_tour_seen'

export default function WelcomeModal() {
    const [isVisible, setIsVisible] = useState(false)
    const navigate = useNavigate()

    useEffect(() => {
        const seen = sessionStorage.getItem(SESSION_KEY)
        if (!seen) {
            setIsVisible(true)
        }
    }, [])

    const dismiss = () => {
        sessionStorage.setItem(SESSION_KEY, 'true')
        setIsVisible(false)
    }

    const handleBuyerTour = () => {
        dismiss()
        navigate('/demo?track=buyer')
    }

    const handleTechnicalTour = () => {
        dismiss()
        navigate('/demo?track=technical')
    }

    if (!isVisible) return null

    return (
        /* Overlay */
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ backgroundColor: 'rgba(0,0,0,0.55)' }}
            onClick={e => {
                // Dismiss when clicking the backdrop
                if (e.target === e.currentTarget) dismiss()
            }}
        >
            {/* Card */}
            <div
                className="relative w-full max-w-lg rounded-2xl bg-white shadow-2xl p-8 animate-in fade-in zoom-in-95 duration-200"
                role="dialog"
                aria-modal="true"
                aria-labelledby="welcome-modal-title"
            >
                {/* Close button */}
                <button
                    onClick={dismiss}
                    className="absolute top-4 right-4 p-1.5 rounded-lg text-shelf-foreground/30 hover:text-shelf-foreground/60 hover:bg-shelf-secondary/10 transition-colors"
                    aria-label="Close welcome modal"
                >
                    <X className="h-4 w-4" />
                </button>

                {/* Header */}
                <div className="mb-6 text-center">
                    <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-shelf-primary/10 mb-4">
                        <span className="text-2xl" role="img" aria-label="chart">
                            &#x1F4CA;
                        </span>
                    </div>
                    <h2
                        id="welcome-modal-title"
                        className="text-xl font-bold text-shelf-primary"
                    >
                        Summit Outdoor Supply
                    </h2>
                    <p className="text-sm font-semibold text-shelf-foreground mt-1">
                        AI-Powered Inventory Intelligence
                    </p>
                    <p className="text-sm text-shelf-foreground/60 mt-2 leading-relaxed">
                        95 days of continuous learning. See what happened automatically.
                    </p>
                </div>

                {/* Divider */}
                <div className="border-t border-shelf-foreground/5 mb-6" />

                {/* CTA section */}
                <p className="text-xs font-semibold text-shelf-foreground/40 uppercase tracking-wider text-center mb-4">
                    Choose your experience
                </p>

                <div className="grid grid-cols-2 gap-3">
                    {/* Buyer tour */}
                    <button
                        onClick={handleBuyerTour}
                        className="
                            flex flex-col items-center gap-2 rounded-xl border-2 border-shelf-primary/20
                            p-4 text-center hover:border-shelf-primary hover:bg-shelf-primary/5
                            transition-all duration-150 group
                        "
                    >
                        <div className="h-9 w-9 rounded-full bg-shelf-primary/10 flex items-center justify-center group-hover:bg-shelf-primary/20 transition-colors">
                            <ShoppingCart className="h-4 w-4 text-shelf-primary" />
                        </div>
                        <div>
                            <p className="text-sm font-semibold text-shelf-foreground">
                                Walk me through as a buyer
                            </p>
                            <p className="text-[10px] text-shelf-foreground/50 mt-0.5 leading-relaxed">
                                Business outcomes, plain-language insights
                            </p>
                        </div>
                    </button>

                    {/* Technical tour */}
                    <button
                        onClick={handleTechnicalTour}
                        className="
                            flex flex-col items-center gap-2 rounded-xl border-2 border-shelf-secondary/20
                            p-4 text-center hover:border-shelf-secondary hover:bg-shelf-secondary/5
                            transition-all duration-150 group
                        "
                    >
                        <div className="h-9 w-9 rounded-full bg-shelf-secondary/10 flex items-center justify-center group-hover:bg-shelf-secondary/20 transition-colors">
                            <Cpu className="h-4 w-4 text-shelf-secondary" />
                        </div>
                        <div>
                            <p className="text-sm font-semibold text-shelf-foreground">
                                Show me the technical depth
                            </p>
                            <p className="text-[10px] text-shelf-foreground/50 mt-0.5 leading-relaxed">
                                ML pipeline, SHAP, arena logs
                            </p>
                        </div>
                    </button>
                </div>

                {/* Skip link */}
                <div className="mt-5 text-center">
                    <button
                        onClick={dismiss}
                        className="text-xs text-shelf-foreground/30 hover:text-shelf-foreground/60 transition-colors underline underline-offset-2"
                    >
                        Skip — explore on my own
                    </button>
                </div>
            </div>
        </div>
    )
}
