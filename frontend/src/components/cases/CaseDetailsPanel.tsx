import { useState } from "react";
import { CaseDetail } from "@/types";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { MarkdownContent } from "@/components/ui/markdown-content";
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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
    Table,
    TableBody,
    TableCell,
    TableRow,
} from "@/components/ui/table";

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
    readOnly?: boolean; // Computed fields that cannot be edited directly
};

// Section Config with Icons - using design system color classes
const SECTIONS = [
    {
        id: "Dati Generali",
        icon: FileSpreadsheet,
        colorClass: "text-primary",
        bgClass: "bg-primary/10",
        fields: [
            { key: "reference_code", label: "Ns. Rif", type: "text" },
            { key: "polizza", label: "Polizza", type: "text" },
            { key: "tipo_perizia", label: "Tipo Perizia", type: "text" },
            { key: "data_sinistro", label: "Data Sinistro", type: "date" },
            { key: "data_incarico", label: "Data Incarico", type: "date" },
        ] as FieldDef[]
    },
    {
        id: "Economici",
        icon: Euro,
        colorClass: "text-chart-2",
        bgClass: "bg-chart-2/10",
        fields: [
            { key: "riserva", label: "Riserva", type: "number", step: "0.01" },
            { key: "importo_liquidato", label: "Importo Liquidato", type: "number", step: "0.01" },
        ] as FieldDef[]
    },
    {
        id: "Parti Coinvolte",
        icon: Users,
        colorClass: "text-chart-1",
        bgClass: "bg-chart-1/10",
        fields: [
            { key: "client_name", label: "Cliente", type: "text" },
            { key: "rif_cliente", label: "Rif. Cliente", type: "text" },
            { key: "assicurato_display", label: "Assicurato", type: "text" },
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
        colorClass: "text-chart-4",
        bgClass: "bg-chart-4/10",
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
        colorClass: "text-destructive",
        bgClass: "bg-destructive/10",
        fields: [
            { key: "luogo_intervento", label: "Luogo Intervento", type: "text" },
            { key: "genere_lavorazione", label: "Genere Lavorazione", type: "text" },
        ] as FieldDef[]
    },
    {
        id: "Note",
        icon: ClipboardList,
        colorClass: "text-muted-foreground",
        bgClass: "bg-muted",
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
        if (val === null || val === undefined || val === "") {
            return <span className="text-muted-foreground/50 font-normal italic">Non definito</span>;
        }

        // Currency Formatting
        if (field.type === "number" && (field.key === "riserva" || field.key === "importo_liquidato")) {
            return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(Number(val));
        }

        // Date Formatting
        if (field.type === "date") {
            try {
                return new Intl.DateTimeFormat('it-IT').format(new Date(val));
            } catch {
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
        return (
            <div className="p-1 px-4">
                {field.type === "textarea" ? (
                    <Textarea
                        autoFocus
                        className="min-h-[100px] ring-1 ring-primary text-sm shadow-sm"
                        value={tempValue}
                        onChange={(e) => setTempValue(e.target.value)}
                        onBlur={() => onSave(tempValue === "" ? null : tempValue)}
                        onKeyDown={handleKeyDown}
                    />
                ) : (
                    <Input
                        autoFocus
                        className="h-8 ring-1 ring-primary text-sm px-2 shadow-sm"
                        type={field.type || "text"}
                        step={field.step}
                        value={tempValue}
                        onChange={(e) => setTempValue(e.target.value)}
                        onBlur={() => onSave(tempValue === "" ? null : tempValue)}
                        onKeyDown={handleKeyDown}
                    />
                )}
            </div>
        );
    }

    if (field.readOnly) {
        return (
            <div className="px-4 py-2.5 text-sm font-medium text-foreground min-h-[40px] flex items-center">
                {formatValue(value)}
            </div>
        );
    }

    return (
        <div
            onClick={onStartEdit}
            className={cn(
                "px-4 py-2.5 cursor-pointer transition-colors duration-200 min-h-[40px] flex items-center group/cell",
                "text-sm font-medium text-foreground hover:bg-primary/5"
            )}
        >
            <div className={cn(
                "flex-1",
                field.type === "textarea" ? "whitespace-pre-wrap line-clamp-6" : "truncate"
            )}>
                {field.type === "markdown" ? (
                    <MarkdownContent content={String(value || "")} variant="compact" />
                ) : (
                    formatValue(value)
                )}
            </div>
            <div className="opacity-0 group-hover/cell:opacity-100 transition-opacity ml-2">
                <span className="text-2xs text-primary/50 uppercase font-bold">Modifica</span>
            </div>
        </div>
    );
};


export default function CaseDetailsPanel({ caseDetail, onUpdate }: Props) {
    const { getToken } = useAuth();
    const [editingKey, setEditingKey] = useState<string | null>(null);
    const [isOpen, setIsOpen] = useState(false); // Default: collapsed

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
        <Card className="border shadow-md overflow-hidden bg-background">
            <CardHeader
                className="flex flex-row items-center justify-between py-5 px-6 cursor-pointer hover:bg-muted/50 transition-all group"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div className="flex items-center gap-4">
                    <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                        <FileSpreadsheet className="h-5 w-5" />
                    </div>
                    <div>
                        <CardTitle className="text-xl font-bold tracking-tight text-foreground">
                            Dettagli Pratica
                        </CardTitle>
                        <p className="text-sm text-muted-foreground mt-0.5">
                            Gestisci tutte le informazioni strutturate del caso.
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mr-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        {isOpen ? "Chiudi" : "Espandi"}
                    </span>
                    <Button variant="outline" size="icon" className="h-8 w-8 rounded-full border-muted-foreground/20">
                        {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </Button>
                </div>
            </CardHeader>

            {isOpen && (
                <CardContent className="p-0">
                    <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x">
                        {SECTIONS.map((section, idx) => (
                            <div key={section.id} className={cn(
                                "p-0 flex flex-col",
                                // Add borders to simulate a unified grid if needed, or just let them stay separate
                                "last:border-b-0"
                            )}>
                                <div className="flex items-center gap-2 px-6 py-4 bg-muted/10">
                                    <div className={cn("p-1 rounded-md", section.bgClass)}>
                                        <section.icon className={cn("h-4 w-4", section.colorClass)} />
                                    </div>
                                    <h3 className="text-xs font-bold text-foreground uppercase tracking-widest">
                                        {section.id}
                                    </h3>
                                </div>

                                <Table className="border-0">
                                    <TableBody>
                                        {section.fields.map((field) => (
                                            <TableRow key={field.key as string} className="group/row hover:bg-transparent last:border-0 border-muted/30">
                                                <TableCell className="bg-muted/5 font-semibold text-muted-foreground w-1/3 min-w-[140px] py-2 px-6 border-r border-muted/30 text-2xs uppercase tracking-wider select-none">
                                                    {field.label}
                                                </TableCell>
                                                <TableCell className="p-0">
                                                    <FieldCell
                                                        field={field}
                                                        value={(caseDetail as any)[field.key] ?? (field.key === "client_name" ? caseDetail.client_name : null)}
                                                        isEditing={editingKey === field.key}
                                                        onStartEdit={() => setEditingKey(field.key as string)}
                                                        onSave={(val) => handleSave(field.key as string, val)}
                                                        onCancel={() => setEditingKey(null)}
                                                    />
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        ))}
                    </div>
                </CardContent>
            )}
        </Card>
    );
}
