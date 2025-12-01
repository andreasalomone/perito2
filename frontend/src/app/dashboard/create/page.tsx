"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";

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
            const res = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/api/cases`,
                {
                    reference_code: cleanRefCode,
                    client_name: cleanClientName
                },
                {
                    headers: { Authorization: `Bearer ${token}` }
                }
            );

            toast.success("Fascicolo creato con successo");
            router.push(`/dashboard/cases/${res.data.id}`);
        } catch (error) {
            console.error("Failed to create case", error);
            if (axios.isAxiosError(error)) {
                const status = error.response?.status;
                if (status === 401) toast.error("Sessione scaduta. Effettua il login.");
                else if (status === 403) toast.error("Non hai i permessi necessari.");
                else toast.error("Errore del server. Riprova più tardi.");
            } else {
                toast.error("Errore imprevisto durante la creazione.");
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-md mx-auto mt-10 p-4">
            <Card>
                <CardHeader>
                    <CardTitle>Nuovo Sinistro</CardTitle>
                    <CardDescription>Crea un nuovo fascicolo per iniziare a lavorare.</CardDescription>
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
                            <Input
                                id="clientName"
                                value={clientName}
                                onChange={(e) => setClientName(e.target.value)}
                                placeholder="Es. Generali Italia"
                                disabled={loading}
                            />
                        </div>
                        <Button type="submit" className="w-full" disabled={loading}>
                            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                            {loading ? "Creazione in corso..." : "Crea Fascicolo"}
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
