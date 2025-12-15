"use client";

import { useState } from "react";
import { ClientDetail } from "@/types";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    ChevronDown,
    ChevronUp,
    Building2,
    MapPin,
    User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type Props = {
    client: ClientDetail;
    onUpdate: (updatedClient: ClientDetail) => void;
};

// --- Field Configuration ---

type FieldDef = {
    key: keyof ClientDetail;
    label: string;
    type?: "text" | "email" | "tel" | "url";
};

// Section Config with Icons
const SECTIONS = [
    {
        id: "Dati Aziendali",
        icon: Building2,
        color: "text-blue-500",
        fields: [
            { key: "name", label: "Nome Azienda", type: "text" },
            { key: "vat_number", label: "P.IVA", type: "text" },
            { key: "website", label: "Sito Web", type: "url" },
        ] as FieldDef[]
    },
    {
        id: "Indirizzo",
        icon: MapPin,
        color: "text-red-500",
        fields: [
            { key: "address_street", label: "Indirizzo", type: "text" },
            { key: "city", label: "Città", type: "text" },
            { key: "zip_code", label: "CAP", type: "text" },
            { key: "province", label: "Provincia", type: "text" },
            { key: "country", label: "Paese", type: "text" },
        ] as FieldDef[]
    },
    {
        id: "Contatti",
        icon: User,
        color: "text-indigo-500",
        fields: [
            { key: "referente", label: "Referente", type: "text" },
            { key: "email", label: "Email", type: "email" },
            { key: "telefono", label: "Telefono", type: "tel" },
        ] as FieldDef[]
    },
];

// --- Subcomponent: FieldCell ---

interface FieldCellProps {
    field: FieldDef;
    value: any;
    isEditing: boolean;
    onStartEdit: () => void;
    onSave: (val: string | null) => void;
    onCancel: () => void;
}

const FieldCell = ({ field, value, isEditing, onStartEdit, onSave, onCancel }: FieldCellProps) => {
    const [tempValue, setTempValue] = useState(value === null ? "" : value);

    const formatValue = (val: any) => {
        if (val === null || val === undefined || val === "") {
            return <span className="text-gray-300 font-normal">—</span>;
        }
        return val;
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter") {
            onSave(tempValue === "" ? null : tempValue);
        }
        if (e.key === "Escape") {
            onCancel();
        }
    };

    if (isEditing) {
        return (
            <div className="relative">
                <label className="block text-xs font-semibold text-blue-600 mb-1 uppercase tracking-wide">
                    {field.label}
                </label>
                <input
                    autoFocus
                    className={cn(
                        "block w-full rounded-md border-2 border-blue-500 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 bg-white h-10"
                    )}
                    type={field.type || "text"}
                    value={tempValue}
                    onChange={(e) => setTempValue(e.target.value)}
                    onBlur={() => onSave(tempValue === "" ? null : tempValue)}
                    onKeyDown={handleKeyDown}
                />
            </div>
        );
    }

    return (
        <div
            role="button"
            tabIndex={0}
            onClick={onStartEdit}
            onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onStartEdit();
                }
            }}
            className={cn(
                "group p-3 rounded-lg border border-transparent hover:border-gray-200 hover:bg-gray-50 cursor-pointer transition-all duration-200",
                "flex flex-col justify-center min-h-[64px] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
            )}
        >
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1 group-hover:text-blue-600 transition-colors">
                {field.label}
            </span>
            <div className="text-sm font-medium text-gray-900 truncate">
                {formatValue(value)}
            </div>
        </div>
    );
};


export default function ClientDetailsPanel({ client, onUpdate }: Props) {
    const { getToken } = useAuth();
    const [editingKey, setEditingKey] = useState<string | null>(null);
    const [isOpen, setIsOpen] = useState(true);

    const handleSave = async (key: string, newVal: string | null) => {
        // Optimistic check
        const currentVal = (client as any)[key];
        // Weak comparison for strings equality
        if (newVal == currentVal && newVal !== "") {
            setEditingKey(null);
            return;
        }

        try {
            const payload: any = { [key]: newVal };

            const token = await getToken();
            const updated = await api.clients.update(token!, client.id, payload);

            // Notify parent
            onUpdate(updated);
            toast.success("Salvato", { description: `${key} aggiornato con successo.` });
        } catch (e) {
            console.error("Save failed", e);
            toast.error("Errore", { description: "Salvataggio fallito. Riprova." });
        } finally {
            setEditingKey(null);
        }
    };

    return (
        <Card className="border-none shadow-md overflow-hidden ring-1 ring-gray-200">
            <CardHeader
                className="bg-gray-50/50 border-b flex flex-row items-center justify-between py-4 px-6 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div>
                    <CardTitle className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                        Dettagli Cliente
                    </CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                        Clicca su un campo per modificarlo.
                    </p>
                </div>

                <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-muted-foreground">
                    {isOpen ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                </Button>
            </CardHeader>

            {isOpen && (
                <CardContent className="p-0">
                    <div className="divide-y divide-gray-100">
                        {SECTIONS.map((section) => (
                            <div key={section.id} className="p-6">
                                <div className="flex items-center gap-2 mb-4">
                                    <div className={cn("p-1.5 rounded-md bg-opacity-10", section.color.replace("text-", "bg-"))}>
                                        <section.icon className={cn("h-4 w-4", section.color)} />
                                    </div>
                                    <h3 className="text-sm font-bold text-gray-700 uppercase tracking-wider">
                                        {section.id}
                                    </h3>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {section.fields.map((field) => (
                                        <div key={field.key as string} className="col-span-1">
                                            <FieldCell
                                                field={field}
                                                value={(client as any)[field.key] ?? null}
                                                isEditing={editingKey === field.key}
                                                onStartEdit={() => setEditingKey(field.key as string)}
                                                onSave={(val) => handleSave(field.key as string, val)}
                                                onCancel={() => setEditingKey(null)}
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            )}
        </Card>
    );
}
