interface LogoProps {
    className?: string
    collapsed?: boolean
}

export default function ShelfOpsLogo({ className = "", collapsed = false }: LogoProps) {
    return (
        <div className={`flex items-center gap-3 ${className}`}>
            {/* Icon: Abstract Shelf */}
            <svg
                viewBox="0 0 40 40"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="h-8 w-8 shrink-0"
            >
                {/* Shelves */}
                <path d="M4 12H36" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="text-[#1d1d1f]/20" />
                <path d="M4 24H36" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="text-[#1d1d1f]/20" />
                <path d="M4 36H36" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="text-[#1d1d1f]/20" />

                {/* Products on Shelves (Geometric Shapes) */}
                {/* Row 1: Circle */}
                <circle cx="10" cy="9" r="3" className="fill-[#0071e3]" />

                {/* Row 2: Square & Triangle */}
                <rect x="24" y="19" width="6" height="6" rx="1" className="fill-[#0071e3]" />
                <path d="M12 24L15 18L18 24H12Z" className="fill-[#5856d6]" />

                {/* Row 3: Stack */}
                <rect x="28" y="30" width="4" height="6" rx="1" className="fill-[#0071e3]/80" />
                <rect x="33" y="28" width="4" height="8" rx="1" className="fill-[#0071e3]" />
            </svg>

            {/* Text Label (Hidden if collapsed) */}
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
