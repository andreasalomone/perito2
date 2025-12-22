"use client";

import { CaseSummary, CaseStatusType } from "@/types";
import { CaseCard } from "@/components/dashboard/CaseCard";

interface KanbanBoardProps {
    cases: CaseSummary[];
}

const COLUMNS: { id: CaseStatusType; label: string; headerBg: string; textColor: string; badgeBg: string }[] = [
    { id: "OPEN", label: "Aperti", headerBg: "bg-primary/10", textColor: "text-primary", badgeBg: "bg-primary/20 text-primary" },
    { id: "CLOSED", label: "Chiusi", headerBg: "bg-system-green/10", textColor: "text-system-green", badgeBg: "bg-system-green/20 text-system-green" },
    { id: "ERROR", label: "Errori / Attenzione", headerBg: "bg-destructive/10", textColor: "text-destructive", badgeBg: "bg-destructive/20 text-destructive" },
];

export function KanbanBoard({ cases }: KanbanBoardProps) {
    return (
        <div className="grid grid-cols-3 gap-4 pb-4 h-[calc(100vh-250px)] min-h-content">
            {COLUMNS.map((col) => {
                const colCases = cases.filter(c => c.status === col.id);

                return (
                    <div key={col.id} className="flex flex-col bg-muted/40 rounded-2xl border min-w-0 overflow-hidden shadow-sm">
                        <div className={`p-4 flex items-center justify-between ${col.headerBg} border-b border-black/5 dark:border-white/5`}>
                            <span className={`font-semibold tracking-tight ${col.textColor}`}>{col.label}</span>
                            <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${col.badgeBg}`}>
                                {colCases.length}
                            </span>
                        </div>
                        <div className="p-3 flex flex-col gap-3 overflow-y-auto flex-1 scrollbar-hide">
                            {colCases.map((c) => (
                                <div key={c.id} className="scale-95 origin-top">
                                    <CaseCard caseItem={c} index={1} />
                                </div>
                            ))}
                            {colCases.length === 0 && (
                                <div className="text-center py-10 text-muted-foreground text-sm opacity-50 border-2 border-dashed rounded-lg">
                                    Nessun sinistro
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
