"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { handleApiError } from "@/lib/error";
import { api } from "@/lib/api";
import { ClientCombobox } from "@/components/ui/combobox-client";

export default function CreateCasePage() {
    const { getToken } = useAuth();
    const router = useRouter();
    const [refCode, setRefCode] = useState("");
    const [clientName, setClientName] = useState("");
    const [loading, setLoading] = useState(false);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();

        const cleanRefCode = refCode.trim();
        const cleanClientName = clientName.trim();

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
                client_name: cleanClientName
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
                <CardHeader>
                    <CardTitle>Nuovo Sinistro</CardTitle>
                    <CardDescription>Apri un nuovo sinistro per iniziare a lavorare.</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleCreate} className="space-y-4">
                        <div className="space-y-2">
                            <label htmlFor="refCode" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                Riferimento <span className="text-red-500">*</span>
                            </label>
                            <Input
                                id="refCode"
                                value={refCode}
                                onChange={(e) => setRefCode(e.target.value)}
                                required
                                placeholder="Es. Sinistro 2024/001"
                                disabled={loading}
                            />
                            <p className="text-[0.8rem] text-muted-foreground">
                                Codice univoco per identificare la pratica.
                            </p>
                        </div>
                        <div className="space-y-2">
                            <label htmlFor="clientName" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                Cliente (Opzionale)
                            </label>
                            {/* Replaced simple Input with Smart Autocomplete */}
                            <ClientCombobox
                                value={clientName}
                                onChange={setClientName}
                                disabled={loading}
                            />
                            <p className="text-[0.8rem] text-muted-foreground">
                                Cerca un cliente esistente o digitane uno nuovo per crearlo.
                            </p>
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
