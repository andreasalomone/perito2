"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

export default function CreateCasePage() {
    const { getToken } = useAuth();
    const router = useRouter();
    const [refCode, setRefCode] = useState("");
    const [clientName, setClientName] = useState("");
    const [loading, setLoading] = useState(false);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const token = await getToken();
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/cases`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    reference_code: refCode,
                    client_name: clientName
                }),
            });

            if (res.ok) {
                const newCase = await res.json();
                // Redirect to the Case Workspace
                router.push(`/dashboard/cases/${newCase.id}`);
            }
        } catch (error) {
            console.error("Failed to create case", error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-md mx-auto mt-10">
            <Card>
                <CardHeader>
                    <CardTitle>Nuovo Sinistro</CardTitle>
                    <CardDescription>Crea un fascicolo per iniziare a lavorare.</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleCreate} className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Riferimento (Es. Sinistro 2024/001)</label>
                            <Input
                                value={refCode}
                                onChange={(e) => setRefCode(e.target.value)}
                                required
                                placeholder="Inserisci codice riferimento"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Cliente (Opzionale)</label>
                            <Input
                                value={clientName}
                                onChange={(e) => setClientName(e.target.value)}
                                placeholder="Es. Generali Italia"
                            />
                        </div>
                        <Button type="submit" className="w-full" disabled={loading}>
                            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                            Crea Fascicolo
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
