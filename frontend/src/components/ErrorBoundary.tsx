/**
 * Error Boundary — Catches render errors and shows a fallback UI.
 * Agent: full-stack-engineer | Skill: react-dashboard
 */

import { Component } from 'react'
import type { ReactNode, ErrorInfo } from 'react'
import { AlertCircle, RefreshCcw } from 'lucide-react'

interface Props {
    children: ReactNode
    fallback?: ReactNode
}

interface State {
    hasError: boolean
    error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props)
        this.state = { hasError: false, error: null }
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error }
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error('ErrorBoundary caught:', error, info.componentStack)
    }

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) return this.props.fallback

            return (
                <div className="flex items-center justify-center min-h-[300px] p-8">
                    <div className="text-center max-w-md">
                        <AlertCircle className="h-10 w-10 mx-auto mb-4 text-red-400" />
                        <h2 className="text-lg font-semibold text-shelf-foreground mb-2">Something went wrong</h2>
                        <p className="text-sm text-shelf-foreground/60 mb-4">
                            {this.state.error?.message ?? 'An unexpected error occurred.'}
                        </p>
                        <button
                            onClick={() => this.setState({ hasError: false, error: null })}
                            className="btn-secondary text-sm h-9 px-4 gap-2 mx-auto"
                        >
                            <RefreshCcw className="h-4 w-4" />
                            Try Again
                        </button>
                    </div>
                </div>
            )
        }

        return this.props.children
    }
}
