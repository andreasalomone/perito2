import { useState } from "react";
import { CaseDetail } from "@/types";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import ReactMarkdown from "react-markdown";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    ChevronDown,
    ChevronUp,
    Users,
    Truck,
    Euro,
    MapPin,
    ClipboardList,
    FileSpreadsheet
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
    caseDetail: CaseDetail;
    onUpdate: (updatedCase: CaseDetail) => void;
};

// --- Field Configuration ---

type FieldDef = {
    key: keyof CaseDetail;
    label: string;
    type?: "text" | "number" | "date" | "textarea" | "markdown";
    step?: string;
    fullWidth?: boolean;
};

// Section Config with Icons
const SECTIONS = [
    {
        id: "Dati Generali",
        icon: FileSpreadsheet,
        color: "text-blue-500",
        fields: [
            { key: "ns_rif", label: "Ns. Rif", type: "number" },
            { key: "reference_code", label: "Reference Code", type: "text" },
            { key: "polizza", label: "Polizza", type: "text" },
            { key: "tipo_perizia", label: "Tipo Perizia", type: "text" },
            { key: "data_sinistro", label: "Data Sinistro", type: "date" },
            { key: "data_incarico", label: "Data Incarico", type: "date" },
        ] as FieldDef[]
    },
    {
        id: "Economici",
        icon: Euro,
        color: "text-green-600",
        fields: [
            { key: "riserva", label: "Riserva", type: "number", step: "0.01" },
            { key: "importo_liquidato", label: "Importo Liquidato", type: "number", step: "0.01" },
        ] as FieldDef[]
    },
    {
        id: "Parti Coinvolte",
        icon: Users,
        color: "text-indigo-500",
        fields: [
            { key: "client_name", label: "Cliente", type: "text" },
            { key: "rif_cliente", label: "Rif. Cliente", type: "text" },
            { key: "assicurato", label: "Assicurato", type: "text" },
            { key: "riferimento_assicurato", label: "Rif. Assicurato", type: "text" },
            { key: "broker", label: "Broker", type: "text" },
            { key: "riferimento_broker", label: "Rif. Broker", type: "text" },
            { key: "perito", label: "Perito", type: "text" },
            { key: "gestore", label: "Gestore", type: "text" },
            { key: "mittenti", label: "Mittenti", type: "text" },
            { key: "destinatari", label: "Destinatari", type: "text" },
        ] as FieldDef[]
    },
    {
        id: "Merci e Trasporti",
        icon: Truck,
        color: "text-orange-500",
        fields: [
            { key: "merce", label: "Merce (Short)", type: "text" },
            { key: "mezzo_di_trasporto", label: "Mezzo", type: "text" },
            { key: "descrizione_mezzo_di_trasporto", label: "Desc. Mezzo", type: "text" },
            { key: "descrizione_merce", label: "Descrizione Merce", type: "textarea", fullWidth: true },
        ] as FieldDef[]
    },
    {
        id: "Luogo e Lavorazione",
        icon: MapPin,
        color: "text-red-500",
        fields: [
            { key: "luogo_intervento", label: "Luogo Intervento", type: "text" },
            { key: "genere_lavorazione", label: "Genere Lavorazione", type: "text" },
        ] as FieldDef[]
    },
    {
        id: "Note",
        icon: ClipboardList,
        color: "text-gray-500",
        fields: [
            { key: "note", label: "Note Interne", type: "textarea", fullWidth: true },
        ] as FieldDef[]
    }
];

// --- Subcomponent: FieldCell ---

interface FieldCellProps {
    field: FieldDef;
    value: any;
    isEditing: boolean;
    onStartEdit: () => void;
    onSave: (val: string | number | null) => void;
    onCancel: () => void;
}

const FieldCell = ({ field, value, isEditing, onStartEdit, onSave, onCancel }: FieldCellProps) => {
    const [tempValue, setTempValue] = useState(value === null ? "" : value);

    const formatValue = (val: any) => {
        if (val === null || val === undefined || val === "") return <span className="text-gray-300 font-normal">—</span>;

        // Currency Formatting
        if (field.type === "number" && (field.key === "riserva" || field.key === "importo_liquidato")) {
            return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(Number(val));
        }

        // Date Formatting
        if (field.type === "date") {
            try {
                return new Intl.DateTimeFormat('it-IT').format(new Date(val));
            } catch (e) {
                return val;
            }
        }

        return val;
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey && field.type !== "textarea") {
            onSave(tempValue === "" ? null : tempValue);
        }
        if (e.key === "Escape") {
            onCancel();
        }
    };

    if (isEditing) {
        const InputComponent = field.type === "textarea" ? "textarea" : "input";
        return (
            <div className="relative">
                <label className="block text-xs font-semibold text-blue-600 mb-1 uppercase tracking-wide">
                    {field.label}
                </label>
                <InputComponent
                    autoFocus
                    className={cn(
                        "block w-full rounded-md border-2 border-blue-500 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 bg-white",
                        field.type === "textarea" ? "min-h-[100px]" : "h-10"
                    )}
                    type={field.type === "textarea" ? undefined : field.type || "text"}
                    step={field.step}
                    rows={field.type === "textarea" ? 4 : undefined}
                    value={tempValue}
                    onChange={(e: any) => setTempValue(e.target.value)}
                    onBlur={() => onSave(tempValue === "" ? null : tempValue)}
                    onKeyDown={handleKeyDown}
                />
            </div>
        );
    }

    return (
        <div
            onClick={onStartEdit}
            className={cn(
                "group p-3 rounded-lg border border-transparent hover:border-gray-200 hover:bg-gray-50 cursor-pointer transition-all duration-200",
                "flex flex-col justify-center min-h-[64px]"
            )}
        >
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1 group-hover:text-blue-600 transition-colors">
                {field.label}
            </span>
            <div className={cn(
                "text-sm font-medium text-gray-900 truncate",
                field.type === "textarea" ? "whitespace-pre-wrap truncate-none line-clamp-4" : ""
            )}>
                {field.type === "markdown" ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown>{String(value || "")}</ReactMarkdown>
                    </div>
                ) : (
                    formatValue(value)
                )}
            </div>
        </div>
    );
};


export default function CaseDetailsPanel({ caseDetail, onUpdate }: Props) {
    const { getToken } = useAuth();
    const [editingKey, setEditingKey] = useState<string | null>(null);
    const [isOpen, setIsOpen] = useState(true);

    const handleSave = async (key: string, newVal: string | number | null) => {
        // Optimistic check
        const currentVal = (caseDetail as any)[key];
        // Weak comparison for numbers/strings equality
        if (newVal == currentVal && newVal !== "") {
            setEditingKey(null);
            return;
        }

        try {
            const payload: any = { [key]: newVal };

            // Number parsing
            const allFields = SECTIONS.flatMap(s => s.fields);
            const fieldDef = allFields.find(f => f.key === key);
            if (fieldDef?.type === "number" && newVal !== "" && newVal !== null) {
                payload[key] = Number(newVal);
            }

            const token = await getToken();
            await api.cases.update(token, caseDetail.id, payload);

            // Notify parent
            onUpdate({ ...caseDetail, ...payload });
        } catch (e) {
            console.error("Save failed", e);
            alert("Failed to save. Please try again.");
        } finally {
            setEditingKey(null);
        }
    };

    return (
        <Card className="mb-8 border-none shadow-md overflow-hidden ring-1 ring-gray-200">
            <CardHeader
                className="bg-gray-50/50 border-b flex flex-row items-center justify-between py-4 px-6 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div>
                    <CardTitle className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                        Dettagli Pratica
                    </CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                        Gestisci tutte le informazioni strutturate del caso.
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

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                                    {section.fields.map((field) => (
                                        <div
                                            key={field.key as string}
                                            className={cn(
                                                field.fullWidth ? "col-span-full" : "col-span-1"
                                            )}
                                        >
                                            <FieldCell
                                                field={field}
                                                value={(caseDetail as any)[field.key] ?? (field.key === "client_name" ? caseDetail.client_name : null)}
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
