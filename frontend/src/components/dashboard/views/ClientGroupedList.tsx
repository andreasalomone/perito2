"use client";

import { CaseSummary } from "@/types";
import { CaseCard } from "@/components/dashboard/CaseCard";
import { Folder } from "lucide-react";

interface ClientGroupedListProps {
    cases: CaseSummary[];
}

export function ClientGroupedList({ cases }: ClientGroupedListProps) {
    // Group by client_name
    const groups = cases.reduce((acc, c) => {
        const key = c.client_name || "Nessun Cliente";
        if (!acc[key]) acc[key] = [];
        acc[key].push(c);
        return acc;
    }, {} as Record<string, CaseSummary[]>);

    const sortedClients = Object.keys(groups).sort();

    return (
        <div className="space-y-8">
            {sortedClients.map((clientName) => (
                <div key={clientName} className="space-y-4">
                    <div className="flex items-center gap-2 border-b pb-2">
                        <Folder className="h-5 w-5 text-muted-foreground" />
                        <h3 className="text-lg font-semibold">{clientName}</h3>
                        <span className="text-xs text-muted-foreground ml-auto">
                            {groups[clientName].length} sinistri
                        </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                        {groups[clientName].map((c) => (
                            <CaseCard key={c.id} caseItem={c} index={1} />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}
