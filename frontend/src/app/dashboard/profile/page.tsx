"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import { Loader2, User, Building2, Copy, Check } from "lucide-react";
import { api } from "@/lib/api";

export default function ProfilePage() {
    const { user, dbUser, getToken } = useAuth();
    const [firstName, setFirstName] = useState("");
    const [lastName, setLastName] = useState("");
    const [saving, setSaving] = useState(false);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        if (dbUser) {
            setFirstName(dbUser.first_name || "");
            setLastName(dbUser.last_name || "");
        }
    }, [dbUser]);

    const handleSave = async () => {
        setSaving(true);
        try {
            const token = await getToken();
            const updatedUser = await api.users.updateProfile(token, {
                first_name: firstName,
                last_name: lastName,
            });
            toast.success("Profilo aggiornato con successo");
        } catch (error: any) {
            console.error("Error updating profile:", error);
            toast.error(error.message || "Errore durante l'aggiornamento del profilo");
        } finally {
            setSaving(false);
        }
    };

    const copyOrgId = async () => {
        if (dbUser?.organization_id) {
            await navigator.clipboard.writeText(dbUser.organization_id);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
            toast.success("ID Organizzazione copiato");
        }
    };

    if (!user || !dbUser) {
        return (
            <div className="flex h-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Il Mio Profilo</h1>
                <p className="text-muted-foreground">
                    Gestisci le tue informazioni personali e visualizza i dettagli dell'organizzazione.
                </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                {/* Personal Info Card */}
                <Card>
                    <CardHeader>
                        <div className="flex items-center space-x-2">
                            <User className="h-5 w-5 text-primary" />
                            <CardTitle>Informazioni Personali</CardTitle>
                        </div>
                        <CardDescription>
                            Aggiorna il tuo nome e cognome per i report
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="firstName">Nome</Label>
                                <Input
                                    id="firstName"
                                    value={firstName}
                                    onChange={(e) => setFirstName(e.target.value)}
                                    placeholder="Nome"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="lastName">Cognome</Label>
                                <Input
                                    id="lastName"
                                    value={lastName}
                                    onChange={(e) => setLastName(e.target.value)}
                                    placeholder="Cognome"
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <Input
                                id="email"
                                value={user.email || ""}
                                disabled
                                className="bg-muted text-muted-foreground"
                            />
                            <p className="text-xs text-muted-foreground">
                                L'email non può essere modificata.
                            </p>
                        </div>

                        <div className="pt-4">
                            <Button onClick={handleSave} disabled={saving}>
                                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                Salva Modifiche
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Organization Info Card */}
                <Card>
                    <CardHeader>
                        <div className="flex items-center space-x-2">
                            <Building2 className="h-5 w-5 text-primary" />
                            <CardTitle>Organizzazione</CardTitle>
                        </div>
                        <CardDescription>
                            Dettagli della tua organizzazione di appartenenza
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="space-y-2">
                            <Label>Nome Organizzazione</Label>
                            <div className="p-3 bg-muted/50 rounded-md border text-sm font-medium">
                                {dbUser.organization_name || "N/A"}
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label>ID Organizzazione</Label>
                            <div className="flex items-center space-x-2">
                                <div className="flex-1 p-3 bg-muted/50 rounded-md border text-xs font-mono truncate">
                                    {dbUser.organization_id}
                                </div>
                                <Button
                                    variant="outline"
                                    size="icon"
                                    onClick={copyOrgId}
                                    title="Copia ID"
                                >
                                    {copied ? (
                                        <Check className="h-4 w-4 text-green-500" />
                                    ) : (
                                        <Copy className="h-4 w-4" />
                                    )}
                                </Button>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Usa questo ID per invitare colleghi (richiede permessi admin).
                            </p>
                        </div>

                        <div className="rounded-md bg-blue-50 p-4 border border-blue-100">
                            <div className="flex">
                                <div className="flex-shrink-0">
                                    <User className="h-5 w-5 text-blue-400" aria-hidden="true" />
                                </div>
                                <div className="ml-3">
                                    <h3 className="text-sm font-medium text-blue-800">Ruolo: {dbUser.role}</h3>
                                    <div className="mt-2 text-sm text-blue-700">
                                        <p>
                                            Hai accesso come {dbUser.role === "ADMIN" ? "Amministratore" : "Membro"} a questa organizzazione.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
