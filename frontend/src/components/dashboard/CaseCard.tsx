"use client";

import { memo, useRef, useCallback } from "react";
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

    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        const card = cardRef.current;
        if (!card) return;

        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        card.style.setProperty("--x", `${x}px`);
        card.style.setProperty("--y", `${y}px`);
    }, []);

    return (
        <Card
            ref={cardRef}
            onMouseMove={handleMouseMove}
            className={cn(
                "overflow-hidden transition-all hover:shadow-md hover:border-primary/20 group relative",
                index === 0 ? "@lg:col-span-2 @lg:row-span-2" : "col-span-1"
            )}
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
                        <Badge variant={c.status === "open" ? "default" : "secondary"}>
                            {c.status.toUpperCase()}
                        </Badge>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
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
                            className="w-full justify-between group-hover:bg-primary/5"
                            aria-label={`Apri fascicolo ${c.reference_code}`}
                        >
                            Apri Fascicolo
                            <ArrowRight className="h-4 w-4" />
                        </Button>
                    </Link>
                </div>
            </div>
        </Card>
    );
});
