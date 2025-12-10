"use client";

import { memo, useRef, useCallback, useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Folder, Calendar, ArrowRight } from "lucide-react";
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
        <Card
            ref={cardRef}
            onMouseMove={handleMouseMove}
            className={cn(
                "overflow-hidden transition-all hover:shadow-md hover:border-primary/20 group relative",
                index === 0 ? "@lg:col-span-2 @lg:row-span-2" : "col-span-1"
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
            <div className="p-6 flex flex-col justify-between h-full gap-4 relative z-10">
                <div className="space-y-1">
                    <div className="flex items-center gap-3">
                        <h3 className="font-semibold text-lg flex items-center gap-2 group-hover:text-primary transition-colors">
                            <Folder className="h-4 w-4 text-primary" />
                            {c.reference_code}
                        </h3>
                        <Badge variant={c.status === "OPEN" ? "default" : "secondary"}>
                            {c.status.toUpperCase()}
                        </Badge>
                    </div>

                    {/* Creator Badge (Neon Style) */}
                    {c.creator_email && (
                        <div className="flex justify-start pt-1">
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium 
                                bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 
                                shadow-[0_0_8px_rgba(6,182,212,0.2)] tracking-wide uppercase">
                                {c.creator_email}
                            </span>
                        </div>
                    )}

                    <div className="flex items-center gap-2 text-sm text-muted-foreground pt-1">
                        <span className="font-medium text-foreground">{c.client_name || "Cliente non specificato"}</span>
                        <span>•</span>
                        <Calendar className="h-3.5 w-3.5" />
                        <span>{new Date(c.created_at).toLocaleDateString("it-IT", {
                            day: 'numeric', month: 'short', year: 'numeric'
                        })}</span>
                    </div>
                </div>

                <div className="flex items-center gap-2 mt-auto">
                    <Link href={`/dashboard/cases/${c.id}`} className="w-full" tabIndex={-1}>
                        <Button
                            variant="ghost"
                            className="w-full justify-end group-hover:bg-primary/5"
                            aria-label={`Apri sinistro ${c.reference_code}`}
                        >
                            <ArrowRight className="h-4 w-4" />
                        </Button>
                    </Link>
                </div>
            </div>
        </Card>
    );
});
