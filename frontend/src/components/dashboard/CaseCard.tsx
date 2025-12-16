"use client";

import { memo, useRef, useCallback, useState, useEffect } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BadgeWithDot } from "@/components/ui/base/badges/badges";
import { Calendar, Building2 } from "lucide-react";
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
                className="overflow-hidden transition-all hover:shadow-md hover:border-primary/20 group relative h-full cursor-pointer"
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
                {/* Status badge - top right */}
                <Badge
                    variant={c.status === "OPEN" ? "default" : "outline"}
                    className={cn(
                        "absolute top-4 right-4 z-20",
                        c.status === "CLOSED" && "border-green-500 text-green-600 bg-green-50 dark:bg-green-950 dark:text-green-400"
                    )}
                >
                    {c.status.toUpperCase()}
                </Badge>

                <div className="p-6 flex flex-col h-full gap-3 relative z-10">
                    <h3 className="font-semibold text-lg group-hover:text-primary transition-colors pr-20">
                        {c.reference_code}
                    </h3>

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
                        <div className="flex items-center gap-2">
                            <Calendar className="h-3.5 w-3.5" />
                            <span>{new Date(c.created_at).toLocaleDateString("it-IT", {
                                day: 'numeric', month: 'short', year: 'numeric'
                            })}</span>
                        </div>

                        {/* Creator Badge */}
                        {(c.creator_name || c.creator_email) && (
                            <div className="flex justify-start pt-1">
                                <BadgeWithDot type="modern" color="purple" size="sm">
                                    {c.creator_name || c.creator_email}
                                </BadgeWithDot>
                            </div>
                        )}
                    </div>
                </div>
            </Card>
        </Link>
    );
});
