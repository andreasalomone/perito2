"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { Loader2, User, Building2, Copy, Check, ShieldCheck } from "lucide-react";
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
            await api.users.updateProfile(token, {
                first_name: firstName,
                last_name: lastName,
            });
            toast.success("Profilo aggiornato con successo");
        } catch (error: unknown) {
            console.error("Error updating profile:", error);
            const message = error instanceof Error ? error.message : "Errore durante l'aggiornamento del profilo";
            toast.error(message);
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
            <div className="space-y-6">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Il Mio Profilo</h1>
                    <Skeleton className="h-5 w-80 mt-1" />
                </div>
                <div className="grid gap-6 md:grid-cols-2">
                    <Card>
                        <CardHeader>
                            <div className="flex items-center space-x-2">
                                <Skeleton className="h-5 w-5 rounded-full" />
                                <Skeleton className="h-6 w-40" />
                            </div>
                            <Skeleton className="h-4 w-60 mt-2" />
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Skeleton className="h-4 w-20" />
                                    <Skeleton className="h-10 w-full" />
                                </div>
                                <div className="space-y-2">
                                    <Skeleton className="h-4 w-20" />
                                    <Skeleton className="h-10 w-full" />
                                </div>
                            </div>
                            <div className="space-y-2">
                                <Skeleton className="h-4 w-20" />
                                <Skeleton className="h-10 w-full" />
                            </div>
                            <Skeleton className="h-10 w-32 pt-4" />
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader>
                            <div className="flex items-center space-x-2">
                                <Skeleton className="h-5 w-5 rounded-full" />
                                <Skeleton className="h-6 w-40" />
                            </div>
                            <Skeleton className="h-4 w-60 mt-2" />
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="space-y-2">
                                <Skeleton className="h-4 w-32" />
                                <Skeleton className="h-10 w-full" />
                            </div>
                            <div className="space-y-2">
                                <Skeleton className="h-4 w-32" />
                                <div className="flex space-x-2">
                                    <Skeleton className="h-10 flex-1" />
                                    <Skeleton className="h-10 w-10" />
                                </div>
                            </div>
                            <Skeleton className="h-24 w-full rounded-lg" />
                        </CardContent>
                    </Card>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Il Mio Profilo</h1>
                <p className="text-muted-foreground">
                    Gestisci le tue informazioni personali e visualizza i dettagli dell&apos;organizzazione.
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
                                readOnly
                                disabled
                                className="bg-muted text-muted-foreground select-all"
                            />
                            <p className="text-xs text-muted-foreground">
                                L&apos;email non può essere modificata.
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
                            <Input
                                value={dbUser.organization_name || "N/A"}
                                readOnly
                                disabled
                                className="bg-muted/50"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>ID Organizzazione</Label>
                            <div className="flex items-center space-x-2">
                                <Input
                                    value={dbUser.organization_id}
                                    readOnly
                                    disabled
                                    className="flex-1 font-mono text-xs bg-muted/50"
                                />
                                <Button
                                    variant="outline"
                                    size="icon"
                                    onClick={copyOrgId}
                                    className="shrink-0"
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

                        <Alert className="bg-primary/5 border-primary/10">
                            <ShieldCheck className="h-4 w-4 text-primary" />
                            <AlertTitle className="flex items-center gap-2">
                                Ruolo: <Badge variant="secondary" className="capitalize">{dbUser.role.toLowerCase()}</Badge>
                            </AlertTitle>
                            <AlertDescription>
                                Hai accesso come {dbUser.role === "ADMIN" ? "Amministratore" : "Membro"} a questa organizzazione.
                            </AlertDescription>
                        </Alert>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
