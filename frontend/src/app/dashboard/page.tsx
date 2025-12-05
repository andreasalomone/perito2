"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Folder, AlertCircle, RefreshCw, Plus } from "lucide-react";
import { useCases } from "@/hooks/useCases";
import { CaseCard } from "@/components/dashboard/CaseCard";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { ViewMode } from "@/components/dashboard/ViewSwitcher";
import { KanbanBoard } from "@/components/dashboard/views/KanbanBoard";
import { ClientGroupedList } from "@/components/dashboard/views/ClientGroupedList";

export default function DashboardPage() {
    const [viewMode, setViewMode] = useState<ViewMode>("grid");
    const [searchQuery, setSearchQuery] = useState("");
    const [scope, setScope] = useState<"all" | "mine">("mine"); // Default to 'mine' for focus

    // Pass search params to hook
    const { cases, isLoading, isError, mutate } = useCases({
        search: searchQuery,
        scope: scope
    });

    if (isLoading) {
        return (
            <div className="space-y-4 max-w-7xl mx-auto px-4 md:px-0">
                <div className="h-32 bg-muted rounded-lg animate-pulse mb-8" />
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                        <div key={i} className="h-48 bg-muted rounded-lg animate-pulse" />
                    ))}
                </div>
            </div>
        );
    }

    if (isError) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-center space-y-4">
                <AlertCircle className="h-12 w-12 text-destructive" />
                <h3 className="text-lg font-semibold">Qualcosa è andato storto</h3>
                <p className="text-muted-foreground">Impossibile caricare i fascicoli.</p>
                <Button onClick={() => mutate()} variant="outline">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Riprova
                </Button>
            </div>
        );
    }

    const safeCases = cases || [];

    // View Rendering Logic
    const renderContent = () => {
        if (safeCases.length === 0) {
            return (
                <Card className="border-dashed border-2 bg-muted/10 mt-8">
                    <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="p-4 bg-muted rounded-full mb-4">
                            <Folder className="h-8 w-8 text-muted-foreground" />
                        </div>
                        <h3 className="text-lg font-semibold">
                            {searchQuery ? "Nessun risultato" : "Nessun fascicolo trovato"}
                        </h3>
                        <p className="text-muted-foreground mb-6 max-w-sm">
                            {searchQuery
                                ? `Nessun fascicolo corrisponde alla ricerca "${searchQuery}".`
                                : "Non hai ancora creato nessun fascicolo. Inizia ora per gestire le tue perizie."}
                        </p>
                        <Link href="/dashboard/create">
                            <Button variant={searchQuery ? "secondary" : "default"}>
                                {searchQuery ? "Nuovo Fascicolo" : "Crea il tuo primo fascicolo"}
                            </Button>
                        </Link>
                    </CardContent>
                </Card>
            );
        }

        switch (viewMode) {
            case "kanban":
                return <KanbanBoard cases={safeCases} />;
            case "client":
                return <ClientGroupedList cases={safeCases} />;
            case "grid":
            default:
                return (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 auto-rows-[minmax(180px,auto)]">
                        {safeCases.map((c, i) => (
                            <CaseCard key={c.id} caseItem={c} index={i} />
                        ))}
                    </div>
                );
        }
    };

    return (
        <div className="space-y-6 max-w-[1600px] mx-auto transition-all duration-300">
            <DashboardHeader
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                viewMode={viewMode}
                onViewModeChange={setViewMode}
            />

            <div className="flex justify-start">
                <div className="inline-flex items-center p-1 rounded-lg bg-muted/50 border border-border">
                    <button
                        onClick={() => setScope("mine")}
                        className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${scope === "mine"
                                ? "bg-background text-foreground shadow-sm ring-1 ring-border"
                                : "text-muted-foreground hover:text-foreground hover:bg-muted"
                            }`}
                    >
                        I miei casi
                    </button>
                    <button
                        onClick={() => setScope("all")}
                        className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${scope === "all"
                                ? "bg-background text-foreground shadow-sm ring-1 ring-border"
                                : "text-muted-foreground hover:text-foreground hover:bg-muted"
                            }`}
                    >
                        Tutti
                    </button>
                </div>
            </div>

            <div className="min-h-[500px] animate-in fade-in slide-in-from-bottom-2 duration-500">
                {renderContent()}
            </div>
        </div>
    );
}
