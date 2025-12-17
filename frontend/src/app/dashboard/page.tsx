"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Folder, AlertCircle, RefreshCw, EyeOff } from "lucide-react";
import { useCases } from "@/hooks/useCases";
import { CaseCard } from "@/components/dashboard/CaseCard";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { ViewMode } from "@/components/dashboard/ViewSwitcher";
import { KanbanBoard } from "@/components/dashboard/views/KanbanBoard";
import { ClientGroupedList } from "@/components/dashboard/views/ClientGroupedList";
import { AssicuratoGroupedList } from "@/components/dashboard/views/AssicuratoGroupedList";
import { Toggle } from "@/components/ui/toggle";
import { CaseTableView } from "@/components/dashboard/views/CaseTableView";

export default function DashboardPage() {
    const [viewMode, setViewMode] = useState<ViewMode>("grid");
    const [searchQuery, setSearchQuery] = useState("");
    const [scope, setScope] = useState<"all" | "mine">("mine"); // Default to 'mine' for focus
    const [hideClosed, setHideClosed] = useState(false);

    // URL Params
    const searchParams = useSearchParams();
    const clientIdParam = searchParams.get("client_id");

    // Pass search params to hook
    const { cases, isLoading, isError, mutate } = useCases({
        search: searchQuery,
        scope: scope,
        client_id: clientIdParam || undefined
    });



    // Apply client-side filters
    const allCases = cases || [];
    const safeCases = hideClosed
        ? allCases.filter(c => c.status !== "CLOSED")
        : allCases;

    // View Rendering Logic
    // View Rendering Logic
    const renderContent = () => {
        if (isLoading) {
            return (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                        <div key={i} className="h-[280px] bg-muted/40 rounded-xl animate-pulse border border-border/50" />
                    ))}
                </div>
            );
        }

        if (isError) {
            return (
                <div className="flex flex-col items-center justify-center h-64 text-center space-y-4 py-12">
                    <div className="p-4 bg-destructive/10 rounded-full">
                        <AlertCircle className="h-8 w-8 text-destructive" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold">Qualcosa è andato storto</h3>
                        <p className="text-muted-foreground max-w-sm mx-auto mt-1">Impossibile caricare i sinistri. Verifica la connessione e riprova.</p>
                    </div>
                    <Button onClick={() => mutate()} variant="outline" className="mt-4">
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Riprova
                    </Button>
                </div>
            );
        }
        if (allCases.length === 0) {
            return (
                <Card className="border-dashed border-2 bg-muted/10 mt-8">
                    <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="p-4 bg-muted rounded-full mb-4">
                            <Folder className="h-8 w-8 text-muted-foreground" />
                        </div>
                        <h3 className="text-lg font-semibold">
                            {searchQuery ? "Nessun risultato" : "Nessun sinistro trovato"}
                        </h3>
                        <p className="text-muted-foreground mb-6 max-w-sm">
                            {searchQuery
                                ? `Nessun sinistro corrisponde alla ricerca "${searchQuery}".`
                                : "Non hai ancora creato nessun sinistro. Inizia ora a gestire le tue perizie."}
                        </p>
                        <Link href="/dashboard/create">
                            <Button variant={searchQuery ? "secondary" : "default"}>
                                {searchQuery ? "Nuovo Sinistro" : "Apri il tuo primo sinistro"}
                            </Button>
                        </Link>
                    </CardContent>
                </Card>
            );
        }

        if (safeCases.length === 0 && hideClosed) {
            return (
                <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                    <Folder className="h-12 w-12 mb-4 opacity-50" />
                    <p>Tutti i casi trovati sono chiusi e al momento nascosti.</p>
                    <Button
                        variant="link"
                        onClick={() => setHideClosed(false)}
                        className="mt-2"
                    >
                        Mostra casi chiusi
                    </Button>
                </div>
            );
        }



        switch (viewMode) {
            case "kanban":
                return <KanbanBoard cases={safeCases} />;
            case "client":
                return <ClientGroupedList cases={safeCases} />;
            case "assicurato":
                return <AssicuratoGroupedList cases={safeCases} />;
            case "table":
                return <CaseTableView cases={safeCases} />;
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

            <div className="flex flex-wrap items-center gap-4">
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

                <div className="h-6 w-px bg-border hidden sm:block" />

                <Toggle
                    pressed={hideClosed}
                    onPressedChange={setHideClosed}
                    variant="outline"
                    aria-label="Nascondi casi chiusi"
                    className="gap-2 data-[state=on]:bg-muted data-[state=on]:text-foreground"
                >
                    <EyeOff className="h-4 w-4" />
                    <span className="hidden sm:inline">Nascondi Casi Chiusi</span>
                </Toggle>
            </div>

            <div className="min-h-[500px] animate-in fade-in slide-in-from-bottom-2 duration-500">
                {renderContent()}
            </div>
        </div>
    );
}
