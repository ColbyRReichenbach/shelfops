import { GaugeCircle, ShieldCheck } from 'lucide-react'

import { ACTIVE_CHAMPION_EVIDENCE } from '@/lib/modelEvidence'
import type { MLEffectiveness } from '@/lib/types'

interface CalibrationPanelProps {
    effectiveness: MLEffectiveness | undefined
}

export default function CalibrationPanel({ effectiveness }: CalibrationPanelProps) {
    const evidence = ACTIVE_CHAMPION_EVIDENCE
    const runtimeCoverage = effectiveness?.metrics?.coverage ?? null

    return (
        <section className="card space-y-5">
            <div className="flex items-center gap-2">
                <GaugeCircle className="h-4 w-4 text-[#0071e3]" />
                <h2 className="text-lg font-semibold text-[#1d1d1f]">Prediction Range Performance</h2>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <CalibrationTile label="Interval method" value={formatLabel(evidence.intervalMethod)} detail="Champion artifact metadata" />
                <CalibrationTile label="Champion coverage" value={`${(evidence.intervalCoverage * 100).toFixed(1)}%`} detail="Stored conformal coverage" />
                <CalibrationTile
                    label="Runtime window coverage"
                    value={runtimeCoverage !== null ? `${(runtimeCoverage * 100).toFixed(1)}%` : '—'}
                    detail="Rolling effectiveness endpoint"
                />
                <CalibrationTile label="Calibration status" value={formatLabel(evidence.calibrationStatus)} detail="Split-conformal intervals available" />
            </div>

            <div className="grid gap-4 xl:grid-cols-[0.95fr,1.05fr]">
                <div className="rounded-[20px] bg-[#f5f5f7] p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#86868b]">How To Read It</p>
                    <div className="mt-4 space-y-3 text-sm text-[#6e6e73]">
                        <p>This model stores calibrated demand ranges alongside its point forecasts.</p>
                        <p>If live coverage drifts away from the stored benchmark level, review the latest data mix and retraining cadence.</p>
                        <p>The forecast ranges shown in replenishment inherit these calibration settings.</p>
                    </div>
                </div>

                <div className="rounded-[20px] border border-[#34c759]/15 bg-[#34c759]/5 p-5">
                    <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4 text-[#1f8f45]" />
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#1f8f45]">Current Snapshot</p>
                    </div>
                    <div className="mt-4 space-y-3">
                        <StatusRow
                            label="Stored benchmark coverage"
                            value={`${(evidence.intervalCoverage * 100).toFixed(1)}%`}
                            tone="good"
                        />
                        <StatusRow
                            label="Runtime rolling coverage"
                            value={runtimeCoverage !== null ? `${(runtimeCoverage * 100).toFixed(1)}%` : 'Unavailable'}
                            tone={runtimeCoverage !== null && runtimeCoverage >= 0.85 ? 'good' : 'warn'}
                        />
                        <StatusRow
                            label="Recommendation queue usage"
                            value="Enabled"
                            tone="good"
                        />
                    </div>
                </div>
            </div>
        </section>
    )
}

function CalibrationTile({ label, value, detail }: { label: string; value: string; detail: string }) {
    return (
        <div className="rounded-[18px] bg-[#f5f5f7] px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-[#86868b]">{label}</p>
            <p className="mt-2 text-xl font-semibold tracking-tight text-[#1d1d1f]">{value}</p>
            <p className="mt-1 text-xs text-[#6e6e73]">{detail}</p>
        </div>
    )
}

function StatusRow({
    label,
    value,
    tone,
}: {
    label: string
    value: string
    tone: 'good' | 'warn'
}) {
    return (
        <div className="rounded-[16px] bg-white px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#86868b]">{label}</p>
            <p className={`mt-2 text-sm font-semibold ${tone === 'good' ? 'text-[#1f8f45]' : 'text-[#8a6a00]'}`}>
                {value}
            </p>
        </div>
    )
}

function formatLabel(value: string) {
    return value.replace(/_/g, ' ')
}
