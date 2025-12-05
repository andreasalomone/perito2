"use client";

import { CaseSummary, CaseStatusType } from "@/types";
import { CaseCard } from "@/components/dashboard/CaseCard";

interface KanbanBoardProps {
    cases: CaseSummary[];
}

const COLUMNS: { id: CaseStatusType; label: string; color: string }[] = [
    { id: "OPEN", label: "Aperti", color: "bg-blue-500/10 border-blue-500/20 text-blue-500" },
    { id: "GENERATING", label: "In Generazione", color: "bg-amber-500/10 border-amber-500/20 text-amber-500" },
    { id: "ERROR", label: "Errori / Attenzione", color: "bg-red-500/10 border-red-500/20 text-red-500" },
    { id: "CLOSED", label: "Chiusi", color: "bg-green-500/10 border-green-500/20 text-green-500" },
];

export function KanbanBoard({ cases }: KanbanBoardProps) {
    return (
        <div className="flex gap-4 overflow-x-auto pb-4 h-[calc(100vh-250px)] min-h-[500px]">
            {COLUMNS.map((col) => {
                const colCases = cases.filter(c => c.status === col.id);

                return (
                    <div key={col.id} className="min-w-[300px] w-[350px] flex flex-col bg-muted/40 rounded-xl border">
                        <div className={`p-4 border-b font-medium flex items-center justify-between ${col.color}`}>
                            <span>{col.label}</span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-background/50 border">
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
                                    Nessun fascicolo
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
