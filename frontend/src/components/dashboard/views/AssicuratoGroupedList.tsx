"use client";

import { CaseSummary } from "@/types";
import { CaseCard } from "@/components/dashboard/CaseCard";
import { User, Users } from "lucide-react";

interface AssicuratoGroupedListProps {
    cases: CaseSummary[];
}

export function AssicuratoGroupedList({ cases }: AssicuratoGroupedListProps) {
    // Group by assicurato_display (smart) -> assicurato (raw) -> "Nessun Assicurato"
    const groups = cases.reduce((acc, c) => {
        const key = c.assicurato_display || c.assicurato || "Nessun Assicurato";
        if (!acc[key]) acc[key] = [];
        acc[key].push(c);
        return acc;
    }, {} as Record<string, CaseSummary[]>);

    const sortedGroups = Object.keys(groups).sort();

    return (
        <div className="space-y-8">
            {sortedGroups.map((groupName) => (
                <div key={groupName} className="space-y-4">
                    <div className="flex items-center gap-2 border-b pb-2">
                        <User className="h-5 w-5 text-muted-foreground" />
                        <h3 className="text-lg font-semibold">{groupName}</h3>
                        <span className="text-xs text-muted-foreground ml-auto">
                            {groups[groupName].length} sinistri
                        </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                        {groups[groupName].map((c, i) => (
                            <CaseCard key={c.id} caseItem={c} index={i} />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}
