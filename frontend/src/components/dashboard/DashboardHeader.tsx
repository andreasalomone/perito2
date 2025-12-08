"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SmartSearch } from "@/components/dashboard/SmartSearch";
import { ViewSwitcher, ViewMode } from "@/components/dashboard/ViewSwitcher";

interface DashboardHeaderProps {
    searchQuery: string;
    onSearchChange: (q: string) => void;
    viewMode: ViewMode;
    onViewModeChange: (m: ViewMode) => void;
}

export function DashboardHeader({
    searchQuery,
    onSearchChange,
    viewMode,
    onViewModeChange
}: DashboardHeaderProps) {
    return (
        <div className="flex flex-col gap-6 pb-6 border-b">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                        I Miei Fascicoli
                    </h1>
                    <p className="text-muted-foreground">
                        Gestisci i tuoi sinistri, cerca per cliente o monitora lo stato.
                    </p>
                </div>
                <Link href="/dashboard/create">
                    <Button className="gap-2 w-full sm:w-auto">
                        <Plus className="h-4 w-4" />
                        Nuovo Fascicolo
                    </Button>
                </Link>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                <SmartSearch
                    value={searchQuery}
                    onSearch={onSearchChange}
                    className="w-full sm:max-w-md"
                />
                <ViewSwitcher mode={viewMode} onModeChange={onViewModeChange} />
            </div>
        </div>
    );
}
