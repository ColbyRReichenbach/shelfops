import { useMemo, useState } from 'react'
import { DatabaseZap, FileSpreadsheet, ShieldCheck, TimerReset, UploadCloud } from 'lucide-react'

import DataQualityEvents from '@/components/data/DataQualityEvents'
import DataReadinessSummary from '@/components/data/DataReadinessSummary'
import MappingCoverageTable from '@/components/data/MappingCoverageTable'
import {
    useDataReadiness,
    useIngestCsvOnboarding,
    useSyncHealth,
    useValidateCsvOnboarding,
} from '@/hooks/useShelfOps'
import { getApiErrorDetail } from '@/lib/api'
import type { CsvOnboardingPayload, CsvValidationResponse } from '@/lib/types'

const CSV_SECTIONS: Array<{
    key: keyof CsvOnboardingPayload
    fileType: 'stores' | 'products' | 'transactions' | 'inventory'
    label: string
    description: string
    placeholder: string
}> = [
    {
        key: 'stores_csv',
        fileType: 'stores',
        label: 'Stores',
        description: 'Required first. Used to resolve store_name references in transaction and inventory rows.',
        placeholder: 'name,city,state,zip_code\nDowntown,Minneapolis,MN,55401',
    },
    {
        key: 'products_csv',
        fileType: 'products',
        label: 'Products',
        description: 'Required before transaction and inventory validation so SKU references can resolve.',
        placeholder: 'sku,name,category,unit_cost,unit_price\nSKU-001,Sparkling Water,Beverages,2.5,4.5',
    },
    {
        key: 'transactions_csv',
        fileType: 'transactions',
        label: 'Transactions',
        description: 'Historical sales are the main readiness driver. Include at least 90 days when possible.',
        placeholder: 'date,store_name,sku,quantity,unit_price\n2024-01-01,Downtown,SKU-001,4,4.5',
    },
    {
        key: 'inventory_csv',
        fileType: 'inventory',
        label: 'Inventory',
        description: 'Optional for onboarding, but needed for live replenishment and closeout accuracy.',
        placeholder: 'timestamp,store_name,sku,quantity_on_hand,quantity_on_order,quantity_reserved\n2024-04-05T09:00:00,Downtown,SKU-001,25,3,1',
    },
]

export default function DataReadinessPage() {
    const readinessQuery = useDataReadiness()
    const syncHealthQuery = useSyncHealth()
    const validateCsv = useValidateCsvOnboarding()
    const ingestCsv = useIngestCsvOnboarding()

    const [payloads, setPayloads] = useState<CsvOnboardingPayload>({
        stores_csv: '',
        products_csv: '',
        transactions_csv: '',
        inventory_csv: '',
    })
    const [validationResult, setValidationResult] = useState<CsvValidationResponse | null>(null)
    const [ingestSummary, setIngestSummary] = useState<string | null>(null)

    const readiness = readinessQuery.data
    const sources = syncHealthQuery.data ?? []
    const snapshot = readiness?.snapshot ?? {}
    const hasCsvPayload = useMemo(
        () => Object.values(payloads).some(value => Boolean(value && value.trim())),
        [payloads],
    )

    async function handleFileLoad(key: keyof CsvOnboardingPayload, file: File | null) {
        if (!file) {
            return
        }
        const text = await file.text()
        setPayloads(current => ({ ...current, [key]: text }))
        setValidationResult(null)
        setIngestSummary(null)
    }

    async function handleValidate() {
        setIngestSummary(null)
        const result = await validateCsv.mutateAsync(payloads)
        setValidationResult(result)
    }

    async function handleIngest() {
        const result = await ingestCsv.mutateAsync(payloads)
        setValidationResult(null)
        setIngestSummary(
            `Imported ${result.created.stores} stores, ${result.created.products} products, ${result.created.transactions} transactions, and ${result.created.inventory} inventory rows.`,
        )
    }

    return (
        <div className="page-shell">
            <div className="hero-panel hero-panel-green">
                <div className="max-w-3xl">
                    <div className="hero-chip text-[#1f8f45]">
                        <DatabaseZap className="h-3.5 w-3.5" />
                        Data Readiness
                    </div>
                    <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[#1d1d1f]">
                        Make sure your data is ready to support planning.
                    </h1>
                    <p className="mt-3 text-sm leading-6 text-[#4f4f53]">
                        Track history, catalog coverage, mappings, and freshness in one place so data issues are fixed before they affect forecasts or replenishment decisions.
                    </p>
                </div>

                <div className="mt-8 grid gap-4 md:grid-cols-3">
                    <HeroStat
                        icon={TimerReset}
                        label="History"
                        value={`${snapshot.history_days ?? 0}d`}
                        detail="Observed transaction span"
                    />
                    <HeroStat
                        icon={ShieldCheck}
                        label="State"
                        value={readiness?.state?.replace(/_/g, ' ') ?? 'not started'}
                        detail={readiness?.reason_code ?? 'no readiness state'}
                    />
                    <HeroStat
                        icon={DatabaseZap}
                        label="Sources"
                        value={String(sources.length)}
                        detail="Active sync sources monitored"
                    />
                </div>
            </div>

            {readinessQuery.isError ? (
                <div className="card border border-[#ff3b30]/20 bg-[#ff3b30]/5 p-12 text-center text-sm text-[#c9342a]">
                    {getApiErrorDetail(readinessQuery.error, 'Failed to load data readiness.')}
                </div>
            ) : readinessQuery.isLoading ? (
                <div className="card p-12 text-center text-sm text-[#86868b]">Loading data readiness…</div>
            ) : (
                <DataReadinessSummary readiness={readiness} />
            )}

            <section className="card space-y-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <FileSpreadsheet className="h-4 w-4 text-[#0071e3]" />
                            <h2 className="text-lg font-semibold text-[#1d1d1f]">CSV Onboarding</h2>
                        </div>
                        <p className="mt-2 text-sm text-[#6e6e73]">
                            Paste structured CSVs or load local files, validate them against the active schema, then ingest them into the pilot workspace.
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={() => void handleValidate()}
                            disabled={!hasCsvPayload || validateCsv.isPending}
                            className="btn-secondary px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {validateCsv.isPending ? 'Validating…' : 'Validate Batch'}
                        </button>
                        <button
                            type="button"
                            onClick={() => void handleIngest()}
                            disabled={!hasCsvPayload || ingestCsv.isPending}
                            className="btn-primary px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {ingestCsv.isPending ? 'Importing…' : 'Ingest Batch'}
                        </button>
                    </div>
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                    {CSV_SECTIONS.map(section => (
                        <div key={section.key} className="rounded-[20px] border border-black/[0.05] bg-[#fbfbfd] p-5">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <h3 className="text-sm font-semibold text-[#1d1d1f]">{section.label}</h3>
                                    <p className="mt-1 text-sm text-[#6e6e73]">{section.description}</p>
                                </div>
                                <label className="btn-secondary cursor-pointer px-3 py-2 text-xs">
                                    <UploadCloud className="h-3.5 w-3.5" />
                                    Load File
                                    <input
                                        type="file"
                                        accept=".csv,text/csv"
                                        className="hidden"
                                        onChange={event => void handleFileLoad(section.key, event.target.files?.[0] ?? null)}
                                    />
                                </label>
                            </div>
                            <textarea
                                value={payloads[section.key] ?? ''}
                                onChange={event => {
                                    setPayloads(current => ({ ...current, [section.key]: event.target.value }))
                                    setValidationResult(null)
                                    setIngestSummary(null)
                                }}
                                className="mt-4 min-h-44 w-full rounded-[18px] border border-black/[0.06] bg-white px-4 py-3 font-mono text-xs text-[#1d1d1f] outline-none transition focus:border-[#0071e3]/35"
                                placeholder={section.placeholder}
                            />
                            {validationResult?.summary?.[section.fileType] ? (
                                <p className="mt-3 text-xs text-[#86868b]">
                                    {validationResult.summary[section.fileType]?.rows ?? 0} rows · {validationResult.summary[section.fileType]?.columns.join(', ') ?? ''}
                                </p>
                            ) : null}
                        </div>
                    ))}
                </div>

                {validateCsv.isError ? (
                    <div className="rounded-[20px] border border-[#ff3b30]/20 bg-[#ff3b30]/5 px-4 py-4 text-sm text-[#c9342a]">
                        {getApiErrorDetail(validateCsv.error, 'Failed to validate CSV payloads.')}
                    </div>
                ) : null}

                {ingestCsv.isError ? (
                    <div className="rounded-[20px] border border-[#ff3b30]/20 bg-[#ff3b30]/5 px-4 py-4 text-sm text-[#c9342a]">
                        {getApiErrorDetail(ingestCsv.error, 'Failed to ingest CSV payloads.')}
                    </div>
                ) : null}

                {ingestSummary ? (
                    <div className="rounded-[20px] border border-[#34c759]/20 bg-[#34c759]/10 px-4 py-4 text-sm text-[#1f8f45]">
                        {ingestSummary}
                    </div>
                ) : null}

                {validationResult ? (
                    <CsvValidationPanel result={validationResult} />
                ) : null}
            </section>

            <MappingCoverageTable sources={sources} />
            <DataQualityEvents readiness={readiness} sources={sources} />
        </div>
    )
}

function CsvValidationPanel({ result }: { result: CsvValidationResponse }) {
    const errors = result.issues.filter(issue => issue.severity === 'error')
    const warnings = result.issues.filter(issue => issue.severity === 'warning')

    return (
        <section className="space-y-4 rounded-[20px] border border-black/[0.05] bg-[#f5f5f7] p-5">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <h3 className="text-sm font-semibold text-[#1d1d1f]">Validation Results</h3>
                    <p className="mt-1 text-sm text-[#6e6e73]">
                        {result.valid ? 'The batch can be ingested.' : 'Resolve blocking issues before ingesting this batch.'}
                    </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${result.valid ? 'bg-[#34c759]/10 text-[#1f8f45]' : 'bg-[#ff3b30]/10 text-[#c9342a]'}`}>
                    {result.valid ? 'valid' : 'blocked'}
                </span>
            </div>

            {errors.length > 0 ? (
                <IssueList title="Blocking Issues" issues={errors} />
            ) : null}
            {warnings.length > 0 ? (
                <IssueList title="Warnings" issues={warnings} />
            ) : null}
            {errors.length === 0 && warnings.length === 0 ? (
                <div className="rounded-[16px] bg-white px-4 py-4 text-sm text-[#1f8f45]">
                    No validation issues were returned for this batch.
                </div>
            ) : null}
        </section>
    )
}

function IssueList({
    title,
    issues,
}: {
    title: string
    issues: CsvValidationResponse['issues']
}) {
    return (
        <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#86868b]">{title}</p>
            <div className="space-y-2">
                {issues.map((issue, index) => (
                    <div key={`${issue.file_type}-${issue.message}-${index}`} className="rounded-[16px] bg-white px-4 py-3">
                        <p className="text-sm font-semibold text-[#1d1d1f]">
                            {issue.file_type} · {issue.message}
                        </p>
                        <p className="mt-1 text-xs text-[#6e6e73]">
                            {issue.row_number ? `Row ${issue.row_number}` : 'File-level issue'}
                            {issue.field ? ` · Field ${issue.field}` : ''}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    )
}

function HeroStat({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof TimerReset
    label: string
    value: string
    detail: string
}) {
    return (
        <div className="hero-stat-card">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f5f5f7]">
                <Icon className="h-5 w-5 text-[#1d1d1f]" />
            </div>
            <p className="mt-4 text-sm font-medium text-[#86868b]">{label}</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-[#1d1d1f] capitalize">{value}</p>
            <p className="mt-2 text-xs text-[#6e6e73]">{detail}</p>
        </div>
    )
}
