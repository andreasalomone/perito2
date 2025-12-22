"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { handleApiError } from "@/lib/error";
import { api } from "@/lib/api";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { Client } from "@/types";

// Type for assicurato API response
interface Assicurato {
    id: string;
    name: string;
}

export default function CreateCasePage() {
    const { getToken } = useAuth();
    const router = useRouter();
    const [refCode, setRefCode] = useState("");
    const [clientName, setClientName] = useState("");
    const [assicuratoName, setAssicuratoName] = useState("");
    const [loading, setLoading] = useState(false);

    // Memoized fetch functions to prevent re-renders
    const fetchClients = useCallback(async (query: string, limit: number) => {
        const token = await getToken();
        if (!token) return [];
        return api.clients.list(token, { q: query, limit });
    }, [getToken]);

    const fetchAssicurati = useCallback(async (query: string, limit: number) => {
        const token = await getToken();
        if (!token) return [];
        return api.assicurati.list(token, { q: query, limit });
    }, [getToken]);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();

        const cleanRefCode = refCode.trim();
        const cleanClientName = clientName.trim();
        const cleanAssicuratoName = assicuratoName.trim();

        // Basic Validation
        if (!cleanRefCode) {
            toast.error("Il codice di riferimento è obbligatorio.");
            return;
        }

        setLoading(true);
        try {
            const token = await getToken();

            if (!token) {
                throw new Error("Utente non autenticato");
            }

            const newCase = await api.cases.create(token, {
                reference_code: cleanRefCode,
                client_name: cleanClientName,
                assicurato_name: cleanAssicuratoName
            });

            toast.success("Sinistro aperto con successo");
            router.push(`/dashboard/cases/${newCase.id}`);
        } catch (error) {
            handleApiError(error, "Errore durante l'apertura del sinistro");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-md mx-auto mt-10 p-4">
            <Card>
                <CardContent>
                    <form onSubmit={handleCreate} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="refCode">
                                Riferimento <span className="text-destructive">*</span>
                            </Label>
                            <Input
                                id="refCode"
                                value={refCode}
                                onChange={(e) => setRefCode(e.target.value)}
                                required
                                placeholder="Es. Sinistro 2024/001"
                                disabled={loading}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="clientName">Cliente</Label>
                            <SearchableCombobox<Client>
                                value={clientName}
                                onChange={setClientName}
                                disabled={loading}
                                fetchFn={fetchClients}
                                getItemId={(c) => c.id}
                                getItemLabel={(c) => c.name}
                                placeholder="Seleziona cliente..."
                                searchPlaceholder="Cerca cliente..."
                                emptyMessage="Nessun cliente trovato."
                                groupHeading="Clienti Esistenti"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="assicuratoName">Assicurato</Label>
                            <SearchableCombobox<Assicurato>
                                value={assicuratoName}
                                onChange={setAssicuratoName}
                                disabled={loading}
                                fetchFn={fetchAssicurati}
                                getItemId={(a) => a.id}
                                getItemLabel={(a) => a.name}
                                placeholder="Seleziona assicurato..."
                                searchPlaceholder="Cerca assicurato..."
                                emptyMessage="Nessun assicurato trovato."
                                groupHeading="Assicurati Esistenti"
                            />
                        </div>
                        <Button type="submit" className="w-full" disabled={loading}>
                            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                            {loading ? "Apertura in corso..." : "Apri Sinistro"}
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
