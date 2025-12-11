"use client";

import { useClient } from "@/hooks/useClients";
import { useCases } from "@/hooks/useCases";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Globe, MapPin, Building2, Phone, Mail, User, RefreshCw, ChevronRight } from "lucide-react";
import Link from "next/link";
import { CaseCard } from "@/components/dashboard/CaseCard";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useState } from "react";
import { toast } from "sonner";
import { ClientDialog } from "@/components/dashboard/ClientDialog";
import { ClientDetail } from "@/types";

export default function ClientDetailPage({ params }: { params: { id: string } }) {
    const { client, isLoading: isClientLoading, mutate: mutateClient } = useClient(params.id);
    const { cases, isLoading: isCasesLoading } = useCases({ client_id: params.id });
    const { getToken } = useAuth();
    const [isEnriching, setIsEnriching] = useState(false);

    const handleEnrichment = async () => {
        setIsEnriching(true);
        try {
            const token = await getToken();
            if (!token) return;
            await api.clients.triggerEnrichment(token, params.id);
            toast.success("Arricchimento avviato", {
                description: "I dati verranno aggiornati a breve.",
            });
        } catch (e) {
            toast.error("Errore", {
                description: "Impossibile avviare l'arricchimento.",
            });
        } finally {
            setIsEnriching(false);
        }
    };

    const handleEditSuccess = (updatedClient: ClientDetail) => {
        toast.success("Cliente aggiornato", {
            description: "I dati sono stati salvati con successo.",
        });
        mutateClient();
    };

    if (isClientLoading) {
        return <div className="p-8 space-y-8 animate-pulse">
            <div className="h-8 w-48 bg-muted rounded" />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="h-64 bg-muted rounded col-span-2" />
                <div className="h-64 bg-muted rounded" />
            </div>
        </div>;
    }

    if (!client) {
        return <div className="p-8 text-center">Cliente non trovato</div>;
    }

    return (
        <div className="space-y-6 max-w-[1600px] mx-auto animate-in fade-in duration-500 pb-12">
            {/* Header */}
            <div className="flex flex-col gap-4 border-b pb-6">
                <Link href="/dashboard/clienti" className="text-muted-foreground hover:text-foreground flex items-center gap-2 mb-2 w-fit">
                    <ArrowLeft className="h-4 w-4" />
                    Torna ai Clienti
                </Link>
                <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-4">
                        {client.logo_url ? (
                            <img src={client.logo_url} className="h-16 w-16 rounded-full bg-white object-contain p-2 border shadow-sm" />
                        ) : (
                            <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center border shadow-sm">
                                <Building2 className="h-8 w-8 text-muted-foreground" />
                            </div>
                        )}
                        <div>
                            <h1 className="text-3xl font-bold tracking-tight">{client.name}</h1>
                            {client.vat_number && (
                                <p className="text-muted-foreground">P.IVA: {client.vat_number}</p>
                            )}
                        </div>
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={handleEnrichment} disabled={isEnriching}>
                            <RefreshCw className={`mr-2 h-4 w-4 ${isEnriching ? 'animate-spin' : ''}`} />
                            Aggiorna Dati
                        </Button>
                        <ClientDialog
                            client={client}
                            onSuccess={handleEditSuccess}
                            trigger={
                                <Button size="sm" variant="outline">Modifica</Button>
                            }
                        />
                    </div>
                </div>
            </div>

            {/* Bento Grid layout */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

                {/* Block 1: Company Info */}
                <Card className="md:col-span-2">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-lg">
                            <Building2 className="h-5 w-5 text-primary" />
                            Dati Aziendali
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        <div className="space-y-4">
                            <div>
                                <h4 className="text-sm font-medium text-muted-foreground mb-1">Indirizzo Sede Legale</h4>
                                <div className="flex items-start gap-2">
                                    <MapPin className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                                    <span>
                                        {client.address_street || "-"}<br />
                                        {client.zip_code} {client.city} {client.province && `(${client.province})`}<br />
                                        {client.country}
                                    </span>
                                </div>
                            </div>
                        </div>
                        <div className="space-y-4">
                            <div>
                                <h4 className="text-sm font-medium text-muted-foreground mb-1">Sito Web</h4>
                                {client.website ? (
                                    <a href={client.website.startsWith('http') ? client.website : `https://${client.website}`}
                                        target="_blank" rel="noopener noreferrer"
                                        className="flex items-center gap-2 text-primary hover:underline group">
                                        <Globe className="h-4 w-4" />
                                        {client.website}
                                    </a>
                                ) : (
                                    <span className="text-muted-foreground">-</span>
                                )}
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Block 2: Contacts */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-lg">
                            <User className="h-5 w-5 text-primary" />
                            Contatti
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-1">Referente</h4>
                            <div className="flex items-center gap-2">
                                <User className="h-4 w-4 text-muted-foreground" />
                                <span>{client.referente || "-"}</span>
                            </div>
                        </div>
                        <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-1">Email</h4>
                            <div className="flex items-center gap-2">
                                <Mail className="h-4 w-4 text-muted-foreground" />
                                <span>{client.email || "-"}</span>
                            </div>
                        </div>
                        <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-1">Telefono</h4>
                            <div className="flex items-center gap-2">
                                <Phone className="h-4 w-4 text-muted-foreground" />
                                <span>{client.telefono || "-"}</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Block 3: Stats (Optional row or sidebar) */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Statistiche</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex justify-between items-center pb-2 border-b border-border/50">
                            <span className="text-muted-foreground">Totale Sinistri</span>
                            <Badge variant="secondary" className="text-base">{cases?.length || 0}</Badge>
                        </div>
                        <div className="flex justify-between items-center pb-2 border-b border-border/50">
                            <span className="text-muted-foreground">Aperti</span>
                            <Badge variant="outline" className="text-base border-green-500/50 text-green-600">
                                {cases?.filter(c => c.status === "OPEN").length || 0}
                            </Badge>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Chiusi</span>
                            <Badge variant="outline" className="text-base">
                                {cases?.filter(c => c.status === "CLOSED").length || 0}
                            </Badge>
                        </div>
                    </CardContent>
                </Card>

                {/* Block 4: Recent Cases */}
                <div className="md:col-span-2 space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold">Sinistri Recenti</h2>
                        {cases && cases.length > 0 && (
                            <Link href={`/dashboard?client_id=${params.id}`}>
                                <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-primary">
                                    Vedi tutti <ChevronRight className="ml-1 h-4 w-4" />
                                </Button>
                            </Link>
                        )}
                    </div>
                    {isCasesLoading ? (
                        <div className="h-32 bg-muted rounded animate-pulse" />
                    ) : cases?.length === 0 ? (
                        <div className="text-muted-foreground border-2 border-dashed rounded-lg p-8 text-center bg-muted/10">
                            Nessun sinistro associato a questo cliente.
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            {cases?.map((c, i) => (
                                <CaseCard key={c.id} caseItem={c} index={i} />
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
