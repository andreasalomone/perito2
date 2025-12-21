"use client";

import { memo, useRef, useCallback, useState, useEffect } from "react";
import Link from "next/link";
import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/card";
import { BadgeWithDot } from "@/components/ui/base/badges/badges";
import { Calendar, Building2, Umbrella } from "lucide-react";
import { CaseSummary } from "@/types";
import { cn } from "@/lib/utils";

interface CaseCardProps {
    caseItem: CaseSummary;
    index: number;
}

export const CaseCard = memo(function CaseCard({ caseItem: c, index }: CaseCardProps) {
    const cardRef = useRef<HTMLDivElement>(null);
    const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
    const rafRef = useRef<number | null>(null);

    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        // Cancel previous RAF if still pending
        if (rafRef.current !== null) {
            cancelAnimationFrame(rafRef.current);
        }

        rafRef.current = requestAnimationFrame(() => {
            const card = cardRef.current;
            if (!card) return;

            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            setMousePos({ x, y });
        });
    }, []);

    // Cleanup RAF on unmount
    useEffect(() => {
        return () => {
            if (rafRef.current !== null) {
                cancelAnimationFrame(rafRef.current);
            }
        };
    }, []);

    return (
        <Link href={`/dashboard/cases/${c.id}`} className={cn(
            "block",
            index === 0 ? "@lg:col-span-2 @lg:row-span-2" : "col-span-1"
        )}>
            <Card
                ref={cardRef}
                onMouseMove={handleMouseMove}
                className={cn(
                    "transition-all hover:shadow-md hover:border-primary/20 group h-full cursor-pointer",
                    c.status === "CLOSED" && "opacity-70 grayscale-[20%]"
                )}
                style={{
                    // Use CSS custom properties for GPU-accelerated animations
                    "--x": `${mousePos.x}px`,
                    "--y": `${mousePos.y}px`,
                } as React.CSSProperties}
            >
                <div
                    className="pointer-events-none absolute -inset-px opacity-0 transition duration-300 group-hover:opacity-100"
                    style={{
                        background: `radial-gradient(600px circle at var(--x) var(--y), var(--glass-highlight), transparent 40%)`
                    }}
                    aria-hidden="true"
                />
                {/* Header with status dot + ref code + date */}
                <CardHeader className="flex-row items-center justify-between space-y-0 px-5 py-3 border-b border-border bg-card-header">
                    <div className="flex items-center gap-2.5 min-w-0">
                        {/* Status Dot */}
                        <span
                            className={cn(
                                "h-2.5 w-2.5 rounded-full shrink-0",
                                c.status === "OPEN" && "bg-green-500",
                                c.status === "CLOSED" && "bg-foreground",
                                c.status === "GENERATING" && "bg-orange-500 animate-pulse",
                                c.status === "ERROR" && "bg-red-500"
                            )}
                            aria-label={`Status: ${c.status}`}
                        />
                        <h3 className="font-bold text-lg text-primary group-hover:text-primary/80 transition-colors truncate">
                            {c.reference_code}
                        </h3>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground shrink-0 ml-3">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>{new Date(c.created_at).toLocaleDateString("it-IT", {
                            day: 'numeric', month: 'short', year: 'numeric'
                        })}</span>
                    </div>
                </CardHeader>

                {/* Card content */}
                <CardContent className="p-5 flex flex-col flex-1 gap-3">
                    <div className="space-y-2 text-sm text-muted-foreground mt-auto">
                        <div className="flex items-center gap-2">
                            {c.client_logo_url ? (
                                <img
                                    src={c.client_logo_url}
                                    alt={c.client_name || "Client"}
                                    className="h-4 w-4 rounded-full object-contain"
                                />
                            ) : (
                                <Building2 className="h-3.5 w-3.5" />
                            )}
                            <span className="font-medium text-foreground">{c.client_name || "Cliente non specificato"}</span>
                        </div>
                        {/* Assicurato Badge */}
                        <div className="flex items-center gap-2">
                            <Umbrella className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="font-medium text-muted-foreground">
                                {c.assicurato_display || c.assicurato || "Assicurato non specificato"}
                            </span>
                        </div>
                    </div>
                </CardContent>

                {/* Footer with creator */}
                {(c.creator_name || c.creator_email) && (
                    <CardFooter className="px-5 py-3 border-t border-transparent">
                        <BadgeWithDot type="modern" color="purple" size="sm">
                            {c.creator_name || c.creator_email}
                        </BadgeWithDot>
                    </CardFooter>
                )}
            </Card>
        </Link>
    );
});
