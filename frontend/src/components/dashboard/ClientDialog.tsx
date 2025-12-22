"use client";

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ClientDetail, ClientCreate, ClientUpdate } from "@/types";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

interface ClientDialogProps {
    client?: ClientDetail; // If present, edit mode
    trigger?: React.ReactNode;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    onSuccess?: (client: ClientDetail) => void;
}

export function ClientDialog({ client, trigger, open, onOpenChange, onSuccess }: ClientDialogProps) {
    const isEdit = !!client;
    const { getToken } = useAuth();
    // sonner uses 'toast' function

    const [isLoading, setIsLoading] = useState(false);
    const [isOpen, setIsOpen] = useState(false);

    // Form State
    const [name, setName] = useState(client?.name || "");
    const [vatNumber, setVatNumber] = useState(client?.vat_number || "");
    const [website, setWebsite] = useState(client?.website || "");
    const [address, setAddress] = useState(client?.address_street || "");
    const [city, setCity] = useState(client?.city || "");

    // Sync when client prop changes
    useEffect(() => {
        if (client) {
            setName(client.name);
            setVatNumber(client.vat_number || "");
            setWebsite(client.website || "");
            setAddress(client.address_street || "");
            setCity(client.city || "");
        } else {
            // Reset for create mode
            if (!isOpen) {
                setName("");
                setVatNumber("");
                setWebsite("");
                setAddress("");
                setCity("");
            }
        }
    }, [client, isOpen]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        // 1. TRIM INPUTS
        const cleanName = name.trim();
        const cleanVat = vatNumber.trim();
        const cleanWebsite = website.trim();
        const cleanAddress = address.trim();
        const cleanCity = city.trim();

        // 2. VALIDATION
        if (!cleanName) {
            toast.error("Errore", { description: "Il nome del cliente è obbligatorio." });
            return;
        }

        setIsLoading(true);
        try {
            const token = await getToken();
            if (!token) throw new Error("No token");

            let result: ClientDetail;
            if (isEdit && client) {
                const updateData: ClientUpdate = {
                    name: cleanName,
                    vat_number: cleanVat || null,
                    website: cleanWebsite || null,
                    address_street: cleanAddress || null,
                    city: cleanCity || null,
                    // Additional fields from schema
                    zip_code: null,
                    province: null,
                    country: null,
                    referente: null,
                    email: null,
                    telefono: null,
                };
                result = await api.clients.update(token, client.id, updateData);
            } else {
                const createData: ClientCreate = {
                    name: cleanName,
                    vat_number: cleanVat || null,
                    website: cleanWebsite || null,
                    address_street: cleanAddress || null,
                    city: cleanCity || null,
                    // Additional fields from schema
                    zip_code: null,
                    province: null,
                    country: "Italia", // Default
                    referente: null,
                    email: null,
                    telefono: null,
                    logo_url: null,
                };
                result = await api.clients.create(token, createData);
            }

            if (onSuccess) onSuccess(result);
            setIsOpen(false);
            if (onOpenChange) onOpenChange(false);

        } catch (error) {
            console.error(error);
            if (error instanceof Error) {
                toast.error("Errore", { description: error.message });
            } else {
                toast.error("Errore imprevisto", { description: "Si è verificato un errore durante l'operazione." });
            }
        } finally {
            setIsLoading(false);
        }
    };

    // Handle controlled open state
    const show = open !== undefined ? open : isOpen;
    const setShow = onOpenChange || setIsOpen;

    return (
        <Dialog open={show} onOpenChange={setShow}>
            {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{isEdit ? "Modifica Cliente" : "Nuovo Cliente"}</DialogTitle>
                    <DialogDescription>
                        {isEdit
                            ? "Modifica i dettagli del cliente qui. Clicca salva quando hai fatto."
                            : "Inserisci i dati principali. L'IA proverà ad arricchire il resto."}
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="grid gap-4 py-4">
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="name" className="text-right">
                            Nome <span className="text-red-500">*</span>
                        </Label>
                        <Input
                            id="name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="col-span-3"
                            required
                        />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="vat" className="text-right">
                            P.IVA
                        </Label>
                        <Input
                            id="vat"
                            value={vatNumber}
                            onChange={(e) => setVatNumber(e.target.value)}
                            className="col-span-3"
                        />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="city" className="text-right">
                            Città
                        </Label>
                        <Input
                            id="city"
                            value={city}
                            onChange={(e) => setCity(e.target.value)}
                            className="col-span-3"
                        />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="website" className="text-right">
                            Sito Web
                        </Label>
                        <Input
                            id="website"
                            value={website}
                            onChange={(e) => setWebsite(e.target.value)}
                            className="col-span-3"
                            placeholder="example.com"
                        />
                    </div>
                    <DialogFooter>
                        <Button type="submit" disabled={isLoading}>
                            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            {isEdit ? "Salva Modifiche" : "Crea Cliente"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
