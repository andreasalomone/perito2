"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Folder, Plus, Calendar, Loader2, ArrowRight } from "lucide-react";
import { Case } from "@/types";

export default function DashboardPage() {
    const { getToken } = useAuth();
    const [cases, setCases] = useState<Case[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchCases = async () => {
            const token = await getToken();
            if (!token) return;

            try {
                const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/cases/`, {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                });
                if (res.ok) {
                    const data = await res.json();
                    // Sort by created_at desc
                    const sorted = data.sort((a: Case, b: Case) =>
                        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
                    );
                    setCases(sorted);
                }
            } catch (error) {
                console.error("Failed to fetch cases", error);
            } finally {
                setLoading(false);
            }
        };

        fetchCases();
    }, [getToken]);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="space-y-8">
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

            {cases.length === 0 ? (
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
                <div className="grid gap-4">
                    {cases.map((c) => (
                        <Card key={c.id} className="overflow-hidden transition-all hover:shadow-md hover:border-primary/20 group">
                            <div className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
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
                                        <span>Creato il {new Date(c.created_at).toLocaleDateString("it-IT", {
                                            day: 'numeric', month: 'long', year: 'numeric'
                                        })}</span>
                                    </div>
                                </div>

                                <div className="flex items-center gap-2">
                                    <Link href={`/dashboard/cases/${c.id}`}>
                                        <Button variant="ghost" className="gap-2 group-hover:bg-primary/5">
                                            Apri Fascicolo
                                            <ArrowRight className="h-4 w-4" />
                                        </Button>
                                    </Link>
                                </div>
                            </div>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
