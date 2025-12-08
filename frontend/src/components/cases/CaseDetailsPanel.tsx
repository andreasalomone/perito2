import { useState, useEffect } from "react";
import { CaseDetail } from "@/types";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import ReactMarkdown from "react-markdown";

type Props = {
    caseDetail: CaseDetail;
    onUpdate: (updatedCase: CaseDetail) => void;
};

// Field definition for rendering
type FieldDef = {
    key: keyof CaseDetail;
    label: string;
    type?: "text" | "number" | "date" | "textarea" | "markdown";
    step?: string;
};

const FIELDS: Record<string, FieldDef[]> = {
    "Dati Generali": [
        { key: "ns_rif", label: "Ns. Rif", type: "number" },
        { key: "reference_code", label: "Reference Code", type: "text" },
        { key: "polizza", label: "Polizza", type: "text" },
        { key: "tipo_perizia", label: "Tipo Perizia", type: "text" },
        { key: "data_sinistro", label: "Data Sinistro", type: "date" },
        { key: "data_incarico", label: "Data Incarico", type: "date" },
    ],
    "Economici": [
        { key: "riserva", label: "Riserva (€)", type: "number", step: "0.01" },
        { key: "importo_liquidato", label: "Importo Liquidato (€)", type: "number", step: "0.01" },
    ],
    "Parti Coinvolte": [
        { key: "client_name", label: "Cliente", type: "text" }, // Edits helper field -> creates client
        { key: "rif_cliente", label: "Rif. Cliente", type: "text" },
        { key: "assicurato", label: "Assicurato", type: "text" },
        { key: "riferimento_assicurato", label: "Rif. Assicurato", type: "text" },
        { key: "broker", label: "Broker", type: "text" },
        { key: "riferimento_broker", label: "Rif. Broker", type: "text" },
        { key: "perito", label: "Perito", type: "text" },
        { key: "gestore", label: "Gestore", type: "text" },
        { key: "mittenti", label: "Mittenti", type: "text" },
        { key: "destinatari", label: "Destinatari", type: "text" },
    ],
    "Merci e Trasporti": [
        { key: "merce", label: "Merce (Short)", type: "text" },
        { key: "descrizione_merce", label: "Descrizione Merce", type: "textarea" },
        { key: "mezzo_di_trasporto", label: "Mezzo", type: "text" },
        { key: "descrizione_mezzo_di_trasporto", label: "Desc. Mezzo", type: "text" },
    ],
    "Luogo e Lavorazione": [
        { key: "luogo_intervento", label: "Luogo Intervento", type: "text" },
        { key: "genere_lavorazione", label: "Genere Lavorazione", type: "text" },
    ],
    "Notes & Summary": [
        { key: "note", label: "Note", type: "textarea" },
        { key: "ai_summary", label: "AI Summary", type: "markdown" },
    ],
};

export default function CaseDetailsPanel({ caseDetail, onUpdate }: Props) {
    const { getToken } = useAuth();
    const [editingField, setEditingField] = useState<keyof CaseDetail | "client_name" | null>(null);
    const [tempValue, setTempValue] = useState<string | number>("");
    const [isSaving, setIsSaving] = useState(false);

    // Helper to get display value (handle nulls)
    const getDisplayValue = (key: string, type: string) => {
        // Special case for client_name which comes from helper prop
        if (key === "client_name") return caseDetail.client_name || "";

        const val = (caseDetail as any)[key];
        if (val === null || val === undefined) return "";
        return val;
    };

    const startEditing = (key: keyof CaseDetail | "client_name", currentValue: any, type: string) => {
        setEditingField(key);
        setTempValue(currentValue === null ? "" : currentValue);
    };

    const handleSave = async () => {
        if (!editingField) return;

        // Don't save if value hasn't changed (loose comparison for "5" vs 5)
        const currentVal = (caseDetail as any)[editingField];
        if (tempValue == currentVal && tempValue !== "") { // Note: == for type coercion
            setEditingField(null);
            return;
        }

        setIsSaving(true);
        try {
            const payload: any = { [editingField]: tempValue === "" ? null : tempValue };

            // If saving number, parse it
            const fieldDef = Object.values(FIELDS).flat().find(f => f.key === editingField);
            if (fieldDef?.type === "number" && tempValue !== "") {
                payload[editingField] = Number(tempValue);
            }

            const token = await getToken();
            await api.cases.update(token, caseDetail.id, payload);

            // Update parent with success
            onUpdate({ ...caseDetail, ...payload });

        } catch (e) {
            console.error("Failed to save field:", e);
            alert("Failed to save change.");
        } finally {
            setIsSaving(false);
            setEditingField(null);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            // Prevent enter from saving in textarea
            const fieldDef = Object.values(FIELDS).flat().find(f => f.key === editingField);
            if (fieldDef?.type !== "textarea" && fieldDef?.type !== "markdown") {
                handleSave();
            }
        }
        if (e.key === "Escape") {
            setEditingField(null);
        }
    };

    return (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold text-gray-800">Dettagli Pratica</h2>
                {caseDetail.ai_summary && (
                    <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-0.5 rounded">
                        AI Extracted
                    </span>
                )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
                {Object.entries(FIELDS).map(([section, fields]) => (
                    <div key={section} className="col-span-1 md:col-span-2 lg:col-span-1 border-t pt-4 first:border-t-0 first:pt-0">
                        <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">
                            {section}
                        </h3>
                        <div className="space-y-3">
                            {fields.map((field) => (
                                <div key={field.key as string} className="group">
                                    <dt className="text-xs text-gray-400 font-medium ml-1 mb-0.5">
                                        {field.label}
                                    </dt>
                                    <dd className="relative">
                                        {editingField === field.key ? (
                                            <div className="flex items-center gap-2">
                                                {field.type === "textarea" || field.type === "markdown" ? (
                                                    <textarea
                                                        autoFocus
                                                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                                                        rows={4}
                                                        value={tempValue}
                                                        onChange={(e) => setTempValue(e.target.value)}
                                                        onBlur={handleSave}
                                                        onKeyDown={handleKeyDown}
                                                        disabled={isSaving}
                                                    />
                                                ) : (
                                                    <input
                                                        autoFocus
                                                        type={field.type || "text"}
                                                        step={field.step}
                                                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                                                        value={tempValue}
                                                        onChange={(e) => setTempValue(e.target.value)}
                                                        onBlur={handleSave}
                                                        onKeyDown={handleKeyDown}
                                                        disabled={isSaving}
                                                    />
                                                )}
                                                {/* Save indicator? Handled by blur usually, but could add specific save button if needed */}
                                            </div>
                                        ) : (
                                            <div
                                                onClick={() => startEditing(field.key, getDisplayValue(field.key as string, field.type || "text"), field.type || "text")}
                                                className="p-2 -ml-2 rounded hover:bg-gray-50 cursor-pointer min-h-[2.5rem] flex items-center"
                                                title="Click to edit"
                                            >
                                                {field.type === "markdown" && getDisplayValue(field.key as string, "") ? (
                                                    <div className="prose prose-sm dark:prose-invert max-w-none w-full">
                                                        <ReactMarkdown>{String(getDisplayValue(field.key as string, ""))}</ReactMarkdown>
                                                    </div>
                                                ) : (
                                                    <span className={`text-sm text-gray-900 ${!getDisplayValue(field.key as string, field.type || "text") ? "text-gray-400 italic" : ""}`}>
                                                        {getDisplayValue(field.key as string, field.type || "text") || "Empty"}
                                                    </span>
                                                )}
                                            </div>
                                        )}
                                    </dd>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
