# UX & Integration Audit: `CaseWorkspace`

## 1. Executive UX/Integration Summary

*   **UX Score:** **8/10** (Strong foundation, but lacks "defensive" polish)
*   **Integration Robustness:** **Fragile**
*   **Verdict:** **Visually good, but unsafe API handling.**
    *   The UI is clean and responsive, but it trusts the backend too much. It assumes `caseData` will always have `documents` and `report_versions` arrays. If the backend returns `null` for these fields (instead of empty arrays), the app will crash (White Screen of Death).
    *   Error handling is generic ("Errore nel caricamento"). It doesn't distinguish between "Not Found" (404), "Unauthorized" (401), or "Server Error" (500).

## 2. The "Unhappy Path" Review

*   **API Failure (500):** The user sees a generic toast "Errore nel caricamento". The UI stays in the loading state or shows the "Errore nel caricamento dei dati" text, which is a dead end. No "Retry" button is offered.
*   **Empty Data:** If `caseData.documents` is `undefined` (e.g., partial API response), `caseData.documents.map` throws `TypeError: Cannot read properties of undefined (reading 'map')`.
*   **Network Latency:** If the user clicks "Genera con IA" twice rapidly, the `generating` state handles it, but there is no *optimistic* feedback. The user waits until the request finishes to see any change.
*   **Auth Token Expiry:** If `getToken()` fails or returns undefined, the function silently returns, leaving the user confused why nothing is happening.

## 3. Recommended Improvements (UI & Logic)

*   **Guard Rails:** Use optional chaining (`?.`) and default values (`|| []`) for all array maps.
*   **Specific Error Handling:** Check `error.response.status` to give specific feedback (e.g., "Sessione scaduta" for 401).
*   **Retry Mechanism:** Add a "Riprova" button in the error state.
*   **Empty States:** Improve the empty state visuals (already present, but can be more descriptive).
*   **Skeleton Loading:** The current loader is a spinner. A skeleton UI (mimicking the card layout) is preferred for perceived performance.

## 4. Refactored Component

I have rewritten the component with:
1.  **Defensive Programming:** Added `documents?.map` and `report_versions?.map` with fallbacks.
2.  **Robust Error Handling:** Added a `handleError` helper to parse status codes.
3.  **Retry UI:** Added a specific Error UI with a "Retry" button.
4.  **Skeleton Loader:** Replaced the simple spinner with a skeleton structure.

```tsx
"use client";

import { useEffect, useState, useCallback, useRef, memo } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Case, Document, ReportVersion } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { UploadCloud, FileText, Play, CheckCircle, Download, Loader2, File as FileIcon, AlertCircle, RefreshCw } from "lucide-react";
import axios, { AxiosError } from "axios";
import { toast } from "sonner";

// --- Types ---
type TemplateType = "bn" | "salomone";

// --- Components ---

// 1. Document Item (Memoized)
const DocumentItem = memo(({ doc }: { doc: Document }) => (
    <div className="flex items-center justify-between p-3 border rounded-md bg-background hover:bg-muted/10 transition-colors">
        <div className="flex items-center gap-3 overflow-hidden">
            <FileIcon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <span className="truncate text-sm font-medium" title={doc.filename}>{doc.filename}</span>
        </div>
        <Badge variant={doc.ai_status === "completed" ? "outline" : "secondary"} className="text-xs">
            {doc.ai_status}
        </Badge>
    </div>
));
DocumentItem.displayName = "DocumentItem";

// 2. Version Item (Encapsulates Local State)
const VersionItem = memo(({
    version,
    caseId,
    onDownload
}: {
    version: ReportVersion;
    caseId: string;
    onDownload: (v: ReportVersion, template: TemplateType) => void
}) => {
    const [template, setTemplate] = useState<TemplateType>("bn");

    return (
        <div className="flex items-center justify-between p-3 bg-muted/20 rounded border">
            <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-blue-500" />
                <div>
                    <p className="font-medium text-sm">Versione {version.version_number}</p>
                    <p className="text-xs text-muted-foreground">
                        {version.is_final ? "Finale Approvata" : "Bozza IA"}
                    </p>
                </div>
            </div>
            <div className="flex items-center gap-4">
                {/* Template Selection - Local State */}
                {!version.is_final && (
                    <div className="flex items-center gap-1 text-xs border rounded p-1 bg-background" role="group" aria-label="Seleziona modello report">
                        <button
                            onClick={() => setTemplate("bn")}
                            className={`px-2 py-1 rounded transition-colors ${template === "bn" ? "bg-primary text-primary-foreground" : "hover:bg-muted text-muted-foreground"}`}
                            aria-pressed={template === "bn"}
                        >
                            BN
                        </button>
                        <button
                            onClick={() => setTemplate("salomone")}
                            className={`px-2 py-1 rounded transition-colors ${template === "salomone" ? "bg-primary text-primary-foreground" : "hover:bg-muted text-muted-foreground"}`}
                            aria-pressed={template === "salomone"}
                        >
                            Salomone
                        </button>
                    </div>
                )}

                <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => onDownload(version, template)}
                    aria-label={`Scarica versione ${version.version_number}`}
                >
                    <Download className="h-4 w-4" />
                </Button>
            </div>
        </div>
    );
});
VersionItem.displayName = "VersionItem";

// --- Main Page Component ---

export default function CaseWorkspace() {
    const { id } = useParams();
    const { getToken } = useAuth();
    const [caseData, setCaseData] = useState<Case | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null); // Specific error state
    const [uploading, setUploading] = useState(false);
    const [generating, setGenerating] = useState(false);

    // Refs for hidden inputs
    const docInputRef = useRef<HTMLInputElement>(null);
    const finalInputRef = useRef<HTMLInputElement>(null);

    const API = process.env.NEXT_PUBLIC_API_URL;

    // Helper: Robust Error Handling
    const handleError = (e: unknown, defaultMsg: string) => {
        console.error(e);
        if (axios.isAxiosError(e)) {
            const status = e.response?.status;
            if (status === 401) return toast.error("Sessione scaduta. Effettua nuovamente il login.");
            if (status === 403) return toast.error("Non hai i permessi per questa azione.");
            if (status === 404) return toast.error("Risorsa non trovata.");
            if (status && status >= 500) return toast.error("Errore del server. Riprova più tardi.");
        }
        toast.error(defaultMsg);
    };

    // Data Fetching
    const fetchCase = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const token = await getToken();
            if (!token) {
                setError("Autenticazione richiesta");
                return;
            }
            const res = await axios.get(`${API}/api/cases/${id}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setCaseData(res.data);
        } catch (e) {
            handleError(e, "Errore nel caricamento del fascicolo");
            setError("Impossibile caricare i dati del fascicolo.");
        } finally {
            setLoading(false);
        }
    }, [getToken, id, API]);

    useEffect(() => { fetchCase(); }, [fetchCase]);

    // Handlers
    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        setUploading(true);
        const file = e.target.files[0];

        try {
            const token = await getToken();
            // 1. Get Signed URL
            const signRes = await axios.post(`${API}/api/cases/${id}/documents/upload-url`,
                { filename: file.name, content_type: file.type },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            // 2. Upload to GCS
            await axios.put(signRes.data.upload_url, file, {
                headers: { "Content-Type": file.type }
            });

            // 3. Register
            await axios.post(`${API}/api/cases/${id}/documents/register`,
                { filename: file.name, gcs_path: signRes.data.gcs_path },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            // Optimistic Update (Partial) - Ideally we'd append to local state, but refetch is safer for now
            await fetchCase();
            toast.success("Documento caricato con successo");
        } catch (error) {
            handleError(error, "Errore durante il caricamento");
        } finally {
            setUploading(false);
            if (docInputRef.current) docInputRef.current.value = ""; // Reset input
        }
    };

    const handleGenerate = async () => {
        setGenerating(true);
        try {
            const token = await getToken();
            await axios.post(`${API}/api/cases/${id}/generate`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            toast.success("Generazione avviata! Riceverai una notifica al termine.");
        } catch (error) {
            handleError(error, "Errore durante l'avvio della generazione");
        } finally {
            setGenerating(false);
        }
    };

    const handleDownload = useCallback(async (v: ReportVersion, template: TemplateType) => {
        if (v.is_final) {
            window.open(v.docx_storage_path || "#", "_blank", "noopener,noreferrer");
            return;
        }

        try {
            const token = await getToken();
            const res = await axios.post(
                `${API}/api/cases/${id}/versions/${v.id}/download-generated`,
                { template_type: template },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            window.open(res.data.download_url, "_blank", "noopener,noreferrer");
        } catch (e) {
            handleError(e, "Errore durante il download");
        }
    }, [API, id, getToken]);

    const handleFinalize = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        const file = e.target.files[0];
        const toastId = toast.loading("Caricamento versione finale...");

        try {
            const token = await getToken();
            const signRes = await axios.post(`${API}/api/cases/${id}/documents/upload-url`,
                { filename: `FINAL_${file.name}`, content_type: file.type },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            await axios.put(signRes.data.upload_url, file, { headers: { "Content-Type": file.type } });

            await axios.post(`${API}/api/cases/${id}/finalize`,
                { final_docx_path: signRes.data.gcs_path },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            await fetchCase();
            toast.success("Versione finale caricata", { id: toastId });
        } catch (error) {
            handleError(error, "Errore caricamento finale");
            toast.dismiss(toastId); // Dismiss loading toast on error
        } finally {
            if (finalInputRef.current) finalInputRef.current.value = "";
        }
    };

    // --- Render States ---

    if (loading) {
        return (
            <div className="space-y-6 max-w-6xl mx-auto p-4 animate-pulse">
                <div className="h-8 w-1/3 bg-muted rounded"></div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div className="h-96 bg-muted rounded-lg"></div>
                    <div className="h-96 bg-muted rounded-lg"></div>
                </div>
            </div>
        );
    }

    if (error || !caseData) {
        return (
            <div className="flex flex-col items-center justify-center h-96 text-center space-y-4">
                <AlertCircle className="h-12 w-12 text-destructive" />
                <h3 className="text-lg font-semibold">Qualcosa è andato storto</h3>
                <p className="text-muted-foreground max-w-sm">{error || "Impossibile caricare i dati."}</p>
                <Button onClick={fetchCase} variant="outline">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Riprova
                </Button>
            </div>
        );
    }

    // Guard Rails: Ensure arrays exist
    const documents = caseData.documents || [];
    const versions = caseData.report_versions || [];

    return (
        <div className="space-y-6 max-w-6xl mx-auto p-4">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">{caseData.reference_code}</h1>
                    <p className="text-muted-foreground">Cliente: <span className="font-medium text-foreground">{caseData.client_name || "N/A"}</span></p>
                </div>
                <Badge variant={caseData.status === "open" ? "default" : "secondary"} className="text-sm px-3 py-1">
                    {caseData.status.toUpperCase()}
                </Badge>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* LEFT: Documents */}
                <Card className="h-full flex flex-col">
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                        <CardTitle className="text-lg">Documenti ({documents.length})</CardTitle>
                        <div>
                            <input
                                type="file"
                                ref={docInputRef}
                                onChange={handleFileUpload}
                                className="hidden"
                                accept=".pdf,.doc,.docx,.txt"
                            />
                            <Button
                                size="sm"
                                variant="outline"
                                disabled={uploading}
                                onClick={() => docInputRef.current?.click()}
                            >
                                {uploading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <UploadCloud className="h-4 w-4 mr-2" />}
                                Carica
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="flex-1 overflow-y-auto max-h-[500px] space-y-2">
                        {documents.length === 0 ? (
                            <div className="text-center py-10 text-muted-foreground border-2 border-dashed rounded-lg">
                                <UploadCloud className="h-10 w-10 mx-auto mb-2 opacity-20" />
                                <p>Nessun documento caricato</p>
                            </div>
                        ) : (
                            documents.map(doc => <DocumentItem key={doc.id} doc={doc} />)
                        )}
                    </CardContent>
                </Card>

                {/* RIGHT: Versions */}
                <Card className="h-full flex flex-col">
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                        <CardTitle className="text-lg">Report Generati</CardTitle>
                        <Button
                            size="sm"
                            onClick={handleGenerate}
                            disabled={generating || documents.length === 0}
                            className="bg-blue-600 hover:bg-blue-700 text-white"
                        >
                            {generating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Play className="h-4 w-4 mr-2" />}
                            Genera con IA
                        </Button>
                    </CardHeader>
                    <CardContent className="flex-1 overflow-y-auto max-h-[500px] space-y-4">
                        {versions.length === 0 && (
                            <div className="text-center py-10 text-muted-foreground border-2 border-dashed rounded-lg">
                                <FileText className="h-10 w-10 mx-auto mb-2 opacity-20" />
                                <p>Nessun report generato.</p>
                            </div>
                        )}

                        {versions.map(v => (
                            <VersionItem
                                key={v.id}
                                version={v}
                                caseId={id as string}
                                onDownload={handleDownload}
                            />
                        ))}

                        {/* Finalize Action */}
                        {versions.length > 0 && (
                            <div className="mt-6 pt-6 border-t">
                                <p className="text-sm font-medium text-muted-foreground mb-3">Hai completato il report?</p>
                                <div>
                                    <input
                                        type="file"
                                        ref={finalInputRef}
                                        onChange={handleFinalize}
                                        className="hidden"
                                        accept=".docx,.pdf"
                                    />
                                    <Button
                                        variant="secondary"
                                        className="w-full border-green-200 bg-green-50 text-green-700 hover:bg-green-100 transition-colors"
                                        onClick={() => finalInputRef.current?.click()}
                                    >
                                        <CheckCircle className="h-4 w-4 mr-2" />
                                        Carica Versione Firmata
                                    </Button>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
```
