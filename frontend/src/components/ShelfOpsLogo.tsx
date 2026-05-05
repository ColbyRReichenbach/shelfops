import shelfOpsLogoMarkup from '@/assets/shelfops-logo.svg?raw'

interface LogoProps {
    className?: string
    collapsed?: boolean
}

export default function ShelfOpsLogo({ className = '', collapsed = false }: LogoProps) {
    return (
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-3'} ${className}`}>
            <span
                className="h-10 w-12 shrink-0 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-black/[0.04] [&_svg]:h-full [&_svg]:w-full"
                role="img"
                aria-label="ShelfOps"
                dangerouslySetInnerHTML={{ __html: shelfOpsLogoMarkup }}
            />

            {!collapsed && (
                <div className="flex flex-col">
                    <span className="text-lg font-bold tracking-tight text-[#1d1d1f] leading-none">
                        Shelf<span className="text-[#0071e3]">Ops</span>
                    </span>
                    <span className="text-[0.65rem] font-semibold tracking-widest text-[#86868b] uppercase leading-none mt-0.5">
                        Retail Intelligence
                    </span>
                </div>
            )}
        </div>
    )
}
