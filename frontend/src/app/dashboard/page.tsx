"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Folder, Plus, Calendar, ArrowRight, AlertCircle, RefreshCw } from "lucide-react";
import { CaseSummary } from "@/types";
import { toast } from "sonner";
import axios from "axios";
import { api, ApiError } from "@/lib/api";

// --- Hooks ---
import { useInterval } from "@/hooks/useInterval";

export default function DashboardPage() {
    const { getToken } = useAuth();
    const [cases, setCases] = useState<CaseSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // ...

    const fetchCases = useCallback(async (isPolling = false) => {
        if (!isPolling) {
            setLoading(true);
            setError(null);
        }
        try {
            const token = await getToken();
            if (!token) return;

            const data = await api.cases.list(token);
            setCases(data);

        } catch (error: unknown) {
            if (!isPolling) {
                console.error("Failed to fetch cases", error);
                if (error instanceof ApiError) {
                    setError(error.message);
                    if (error.status === 401) toast.error("Sessione scaduta.");
                } else {
                    setError("Impossibile caricare i fascicoli.");
                    toast.error("Errore nel caricamento dei dati.");
                }
            }
        } finally {
            if (!isPolling) setLoading(false);
        }
    }, [getToken]);

    // Initial Fetch
    useEffect(() => {
        fetchCases();
    }, [fetchCases]);

    // Polling every 5 seconds to keep status updated
    useInterval(() => {
        fetchCases(true);
    }, 5000);

    if (loading) {
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

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-center space-y-4">
                <AlertCircle className="h-12 w-12 text-destructive" />
                <h3 className="text-lg font-semibold">Qualcosa è andato storto</h3>
                <p className="text-muted-foreground">{error}</p>
                <Button onClick={() => fetchCases()} variant="outline">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Riprova
                </Button>
            </div>
        );
    }

    // Guard Rails
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
                            <Card
                                key={c.id}
                                className={cn(
                                    "overflow-hidden transition-all hover:shadow-md hover:border-primary/20 group",
                                    i === 0 ? "md:col-span-2 md:row-span-2" : "col-span-1"
                                )}
                            >
                                <div className="p-6 flex flex-col justify-between h-full gap-4">
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
                                        <Link href={`/dashboard/cases/${c.id}`} className="w-full">
                                            <Button variant="ghost" className="w-full justify-between group-hover:bg-primary/5">
                                                Apri Fascicolo
                                                <ArrowRight className="h-4 w-4" />
                                            </Button>
                                        </Link>
                                    </div>
                                </div>
                            </Card>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
