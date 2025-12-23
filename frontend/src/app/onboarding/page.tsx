"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { useConfig } from "@/context/ConfigContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Loader2, UserCircle, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import axios from "axios";

export default function OnboardingPage() {
    const { dbUser, syncError, getToken, logout } = useAuth();
    const { apiUrl } = useConfig();
    const router = useRouter();

    const [firstName, setFirstName] = useState(dbUser?.first_name || "");
    const [lastName, setLastName] = useState(dbUser?.last_name || "");
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Handle 403 forbidden - show error, not form
    if (syncError === 'forbidden') {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4 text-center space-y-4">
                <div className="bg-destructive/10 p-3 rounded-full">
                    <ShieldAlert className="h-12 w-12 text-destructive" />
                </div>
                <h1 className="text-2xl font-bold">Accesso Negato</h1>
                <p className="text-muted-foreground max-w-md">
                    Il tuo account non è autorizzato ad accedere a questa applicazione.
                    Contatta l&apos;amministratore per richiedere l&apos;accesso.
                </p>
                <Button variant="outline" onClick={() => logout()}>
                    Torna alla Login
                </Button>
            </div>
        );
    }

    // Handle other sync errors
    if (syncError === 'error') {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4 text-center space-y-4">
                <h1 className="text-2xl font-bold text-destructive">Errore di Sincronizzazione</h1>
                <p className="text-muted-foreground">Si è verificato un errore. Riprova più tardi.</p>
                <Button variant="outline" onClick={() => logout()}>
                    Torna alla Login
                </Button>
            </div>
        );
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        const trimmedFirst = firstName.trim();
        const trimmedLast = lastName.trim();

        if (!trimmedFirst || !trimmedLast) {
            toast.error("Compila tutti i campi");
            return;
        }

        setIsSubmitting(true);

        try {
            const token = await getToken();
            if (!token) {
                toast.error("Sessione scaduta. Effettua nuovamente il login.");
                router.push("/");
                return;
            }

            await axios.patch(
                `${apiUrl}/api/v1/users/me`,
                { first_name: trimmedFirst, last_name: trimmedLast },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            // Update cookie BEFORE redirect
            document.cookie = "profile_complete=1; path=/; max-age=86400; SameSite=Lax";

            toast.success("Profilo completato!");
            router.push("/dashboard");
        } catch (error) {
            console.error("Profile update failed:", error);

            if (axios.isAxiosError(error)) {
                if (error.response?.status === 401) {
                    toast.error("Sessione scaduta. Effettua nuovamente il login.");
                    router.push("/");
                } else if (error.response?.status === 404) {
                    toast.error("Utente non trovato. Contatta l'assistenza.");
                } else {
                    toast.error("Errore durante il salvataggio. Riprova.");
                }
            } else {
                toast.error("Errore di rete. Verifica la connessione.");
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-background px-4">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/5 rounded-full blur-3xl -z-10" />

            <Card className="w-full max-w-md border-border/50 shadow-xl bg-card/50 backdrop-blur-sm">
                <CardHeader className="text-center">
                    <div className="flex justify-center mb-4">
                        <div className="bg-primary/10 p-3 rounded-full">
                            <UserCircle className="h-8 w-8 text-primary" />
                        </div>
                    </div>
                    <CardTitle className="text-2xl">Completa il tuo Profilo</CardTitle>
                    <CardDescription>
                        Inserisci il tuo nome e cognome per continuare
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="firstName">Nome</Label>
                            <Input
                                id="firstName"
                                type="text"
                                placeholder="Mario"
                                value={firstName}
                                onChange={(e) => setFirstName(e.target.value)}
                                disabled={isSubmitting}
                                required
                                maxLength={100}
                                className="bg-background/50"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="lastName">Cognome</Label>
                            <Input
                                id="lastName"
                                type="text"
                                placeholder="Rossi"
                                value={lastName}
                                onChange={(e) => setLastName(e.target.value)}
                                disabled={isSubmitting}
                                required
                                maxLength={100}
                                className="bg-background/50"
                            />
                        </div>
                        <Button type="submit" className="w-full" disabled={isSubmitting}>
                            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Continua
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
