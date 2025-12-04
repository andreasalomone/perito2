"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Folder, Plus, AlertCircle, RefreshCw } from "lucide-react";
import { useCases } from "@/hooks/useCases";
import { CaseCard } from "@/components/dashboard/CaseCard";

export default function DashboardPage() {
    const { cases, isLoading, isError, mutate } = useCases();

    if (isLoading) {
        return (
            <div className="space-y-4 max-w-5xl mx-auto">
                <div className="flex justify-between items-center">
                    <div className="h-8 w-48 bg-muted rounded animate-pulse" />
                    <div className="h-10 w-32 bg-muted rounded animate-pulse" />
                </div>
                <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="h-24 bg-muted rounded-lg animate-pulse" />
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

    return (
        <div className="space-y-8 max-w-5xl mx-auto">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">I Miei Fascicoli</h1>
                    <p className="text-muted-foreground">Gestisci i tuoi sinistri e genera le perizie.</p>
                </div>
                <Link href="/dashboard/create">
                    <Button className="gap-2 shadow-lg shadow-primary/20">
                        <Plus className="h-4 w-4" />
                        Nuovo Fascicolo
                    </Button>
                </Link>
            </div>

            {safeCases.length === 0 ? (
                <Card className="border-dashed border-2 bg-muted/10">
                    <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="p-4 bg-muted rounded-full mb-4">
                            <Folder className="h-8 w-8 text-muted-foreground" />
                        </div>
                        <h3 className="text-lg font-semibold">Nessun fascicolo trovato</h3>
                        <p className="text-muted-foreground mb-6 max-w-sm">
                            Non hai ancora creato nessun fascicolo. Inizia ora per gestire le tue perizie.
                        </p>
                        <Link href="/dashboard/create">
                            <Button variant="outline">Crea il tuo primo fascicolo</Button>
                        </Link>
                    </CardContent>
                </Card>
            ) : (
                <div className="@container">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 auto-rows-[minmax(180px,auto)] grid-flow-dense">
                        {safeCases.map((c, i) => (
                            <CaseCard key={c.id} caseItem={c} index={i} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
