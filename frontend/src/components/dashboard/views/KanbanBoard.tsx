"use client";

import { CaseSummary, CaseStatusType } from "@/types";
import { CaseCard } from "@/components/dashboard/CaseCard";

interface KanbanBoardProps {
    cases: CaseSummary[];
}

const COLUMNS: { id: CaseStatusType; label: string; headerBg: string; textColor: string; badgeBg: string }[] = [
    { id: "OPEN", label: "Aperti", headerBg: "bg-gradient-to-br from-blue-500/20 via-blue-500/10 to-blue-400/5", textColor: "text-blue-600 dark:text-blue-400", badgeBg: "bg-blue-500/20 text-blue-700 dark:text-blue-300" },
    { id: "GENERATING", label: "In Generazione", headerBg: "bg-gradient-to-br from-amber-500/20 via-amber-500/10 to-orange-400/5", textColor: "text-amber-600 dark:text-amber-400", badgeBg: "bg-amber-500/20 text-amber-700 dark:text-amber-300" },
    { id: "ERROR", label: "Errori / Attenzione", headerBg: "bg-gradient-to-br from-red-500/20 via-red-500/10 to-rose-400/5", textColor: "text-red-600 dark:text-red-400", badgeBg: "bg-red-500/20 text-red-700 dark:text-red-300" },
    { id: "CLOSED", label: "Chiusi", headerBg: "bg-gradient-to-br from-green-500/20 via-green-500/10 to-emerald-400/5", textColor: "text-green-600 dark:text-green-400", badgeBg: "bg-green-500/20 text-green-700 dark:text-green-300" },
];

export function KanbanBoard({ cases }: KanbanBoardProps) {
    return (
        <div className="grid grid-cols-4 gap-4 pb-4 h-[calc(100vh-250px)] min-h-[500px]">
            {COLUMNS.map((col) => {
                const colCases = cases.filter(c => c.status === col.id);

                return (
                    <div key={col.id} className="flex flex-col bg-muted/40 rounded-xl border min-w-0 overflow-hidden shadow-sm">
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
