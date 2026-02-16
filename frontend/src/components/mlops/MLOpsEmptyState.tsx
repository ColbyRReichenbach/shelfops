interface MLOpsEmptyStateProps {
    showBootstrap: boolean
}

const bootstrapCommands = [
    'docker compose exec -T ml-worker celery -A workers.celery_app call workers.sync.run_alert_check --kwargs \'{"customer_id":"00000000-0000-0000-0000-000000000001"}\'',
    'docker compose exec -T ml-worker celery -A workers.celery_app call workers.monitoring.detect_model_drift --kwargs \'{"customer_id":"00000000-0000-0000-0000-000000000001"}\'',
    'curl -s -X POST http://localhost:8000/experiments -H "Content-Type: application/json" -d \'{"experiment_name":"Category segmentation trial","hypothesis":"Category segmentation improves volatile demand fit","experiment_type":"segmentation","model_name":"demand_forecast","proposed_by":"ml-team@shelfops.com"}\'',
]

const apiLinks = [
    '/models/health',
    '/models/history?limit=20',
    '/ml-alerts?limit=50',
    '/ml-alerts/stats',
    '/experiments?limit=50',
    '/outcomes/alerts/effectiveness',
    '/outcomes/anomalies/effectiveness',
    '/outcomes/roi',
]

export default function MLOpsEmptyState({ showBootstrap }: MLOpsEmptyStateProps) {
    return (
        <div className="card border border-white/40 shadow-sm">
            <h3 className="text-sm font-semibold text-shelf-primary uppercase tracking-wider mb-3">
                How to Populate This Page
            </h3>
            {showBootstrap ? (
                <>
                    <p className="text-sm text-shelf-foreground/70 mb-3">
                        No model versions, ML alerts, or experiments are currently registered. Run these commands to generate real pipeline activity.
                    </p>
                    <div className="space-y-2">
                        {bootstrapCommands.map((cmd) => (
                            <pre
                                key={cmd}
                                className="bg-shelf-foreground/[0.03] border border-shelf-foreground/10 rounded-lg p-2 text-[11px] overflow-x-auto text-shelf-foreground/80"
                            >
                                {cmd}
                            </pre>
                        ))}
                    </div>
                </>
            ) : (
                <p className="text-sm text-shelf-foreground/70 mb-3">
                    Use this panel as a quick reference for the APIs backing the MLOps command center.
                </p>
            )}
            <div className="mt-4">
                <p className="text-xs text-shelf-foreground/50 uppercase tracking-wider mb-2">API Paths Used</p>
                <div className="flex flex-wrap gap-2">
                    {apiLinks.map((path) => (
                        <code
                            key={path}
                            className="rounded-full border border-shelf-foreground/10 bg-white px-2 py-1 text-[11px] text-shelf-foreground/70"
                        >
                            {path}
                        </code>
                    ))}
                </div>
            </div>
        </div>
    )
}
