"use client";

import { useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useConfig } from "@/context/ConfigContext";
import { ReportVersion } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { UploadCloud, FileText, Play, CheckCircle, Loader2, AlertCircle, RefreshCw, Trash2 } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { handleApiError } from "@/lib/error";
import { DocumentItem } from "@/components/cases/DocumentItem";
import { VersionItem, TemplateType } from "@/components/cases/VersionItem";
import { useCaseDetail } from "@/hooks/useCaseDetail";
import { api } from "@/lib/api";

export default function CaseWorkspace() {
    const { id } = useParams();
    const router = useRouter();
    const { getToken } = useAuth();
    const { apiUrl } = useConfig();
    const caseId = Array.isArray(id) ? id[0] : id;

    const {
        caseData,
        isLoading,
        isError,
        mutate,
        isGeneratingReport,
        isProcessingDocs,
        setIsGenerating
    } = useCaseDetail(caseId);

    // Refs for hidden inputs
    const docInputRef = useRef<HTMLInputElement>(null);
    const finalInputRef = useRef<HTMLInputElement>(null);

    // Handlers
    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        const file = e.target.files[0];
        const toastId = toast.loading("Caricamento in corso...");

        try {
            const token = await getToken();
            // 1. Get Signed URL
            const signRes = await axios.post(`${apiUrl}/api/v1/cases/${caseId}/documents/upload-url`,
                null,
                {
                    headers: { Authorization: `Bearer ${token}` },
                    params: { filename: file.name, content_type: file.type }
                }
            );

            // 2. Upload to GCS
            // The x-goog-content-length-range header must match what was signed in the URL
            const maxFileSize = 50 * 1024 * 1024; // 50MB - must match backend settings.MAX_FILE_SIZE_MB
            await axios.put(signRes.data.upload_url, file, {
                headers: {
                    "Content-Type": file.type,
                    "x-goog-content-length-range": `0,${maxFileSize}`
                }
            });

            // 3. Register & Update State Locally
            await axios.post<Document>(`${apiUrl}/api/v1/cases/${caseId}/documents/register`,
                {
                    filename: file.name,
                    gcs_path: signRes.data.gcs_path,
                    mime_type: file.type
                },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            toast.success("Documento caricato con successo", { id: toastId });
            mutate(); // Refresh data
        } catch (error) {
            handleApiError(error, "Errore durante il caricamento");
            toast.dismiss(toastId);
        } finally {
            if (docInputRef.current) docInputRef.current.value = ""; // Reset input
        }
    };

    const handleGenerate = async () => {
        setIsGenerating(true);
        try {
            const token = await getToken();
            await axios.post(`${apiUrl}/api/v1/cases/${caseId}/generate`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            toast.success("Generazione avviata! Il sistema ti avviserà al termine.");
            mutate(); // Trigger immediate refresh to potentially see status change
        } catch (error) {
            handleApiError(error, "Errore durante l'avvio della generazione");
            setIsGenerating(false);
        }
    };

    const handleDownload = useCallback(async (v: ReportVersion, template: TemplateType) => {
        try {
            const token = await getToken();
            const res = await axios.post(
                `${apiUrl}/api/v1/cases/${caseId}/versions/${v.id}/download`,
                { template_type: template },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            window.open(res.data.download_url, "_blank", "noopener,noreferrer");
        } catch (e) {
            handleApiError(e, "Errore durante il download");
        }
    }, [caseId, getToken, apiUrl]);

    const handleDeleteDocument = useCallback(async (docId: string) => {
        if (!caseId) return;
        const id = caseId as string; // Type narrowing for TypeScript
        if (!confirm("Sei sicuro di voler eliminare questo documento?")) return;

        try {
            const token = await getToken();
            await api.cases.deleteDocument(token, id, docId);
            toast.success("Documento eliminato");
            mutate();
        } catch (error) {
            handleApiError(error, "Errore durante l'eliminazione");
        }
    }, [caseId, getToken, mutate]);

    const handleDeleteCase = useCallback(async () => {
        if (!caseId) return;
        const id = caseId as string; // Type narrowing for TypeScript
        if (!confirm("Sei sicuro di voler eliminare questo caso e tutti i documenti associati?")) return;

        try {
            const token = await getToken();
            await api.cases.deleteCase(token, id);
            toast.success("Caso eliminato");
            router.push("/dashboard");
        } catch (error) {
            handleApiError(error, "Errore durante l'eliminazione");
        }
    }, [caseId, getToken, router]);

    const handleFinalize = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        const file = e.target.files[0];
        const toastId = toast.loading("Caricamento versione finale...");

        try {
            const token = await getToken();
            const signRes = await axios.post(`${apiUrl}/api/v1/cases/${caseId}/documents/upload-url`,
                null,
                {
                    headers: { Authorization: `Bearer ${token}` },
                    params: { filename: `FINAL_${file.name}`, content_type: file.type }
                }
            );

            const maxFileSize = 50 * 1024 * 1024; // 50MB - must match backend
            await axios.put(signRes.data.upload_url, file, {
                headers: {
                    "Content-Type": file.type,
                    "x-goog-content-length-range": `0,${maxFileSize}`
                }
            });

            await axios.post<ReportVersion>(`${apiUrl}/api/v1/cases/${caseId}/finalize`,
                { final_docx_path: signRes.data.gcs_path },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            toast.success("Versione finale caricata", { id: toastId });
            mutate();
        } catch (error) {
            handleApiError(error, "Errore caricamento finale");
            toast.dismiss(toastId);
        } finally {
            if (finalInputRef.current) finalInputRef.current.value = "";
        }
    };

    // --- Render States ---

    if (isLoading) {
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

    if (isError || !caseData) {
        return (
            <div className="flex flex-col items-center justify-center h-96 text-center space-y-4">
                <AlertCircle className="h-12 w-12 text-destructive" />
                <h3 className="text-lg font-semibold">Qualcosa è andato storto</h3>
                <p className="text-muted-foreground max-w-sm">Impossibile caricare i dati.</p>
                <Button onClick={() => mutate()} variant="outline">
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
                <div className="flex items-center gap-3">
                    <Badge variant={caseData.status === "OPEN" ? "default" : "secondary"} className="text-sm px-3 py-1">
                        {caseData.status.toUpperCase()}
                    </Badge>
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={handleDeleteCase}
                        className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        title="Elimina caso"
                    >
                        <Trash2 className="h-4 w-4" />
                    </Button>
                </div>
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
                                accept=".pdf,.docx,.xlsx,.txt,.eml,.png,.jpg,.jpeg,.webp,.gif"
                            />
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => docInputRef.current?.click()}
                            >
                                <UploadCloud className="h-4 w-4 mr-2" />
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
                            documents.map(doc => <DocumentItem key={doc.id} doc={doc} onDelete={handleDeleteDocument} />)
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
                            disabled={isGeneratingReport || isProcessingDocs || documents.length === 0}
                            className="bg-blue-600 hover:bg-blue-700 text-white"
                        >
                            {(isGeneratingReport || isProcessingDocs) ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Play className="h-4 w-4 mr-2" />}
                            {isGeneratingReport ? "Generazione in corso..." : isProcessingDocs ? "Elaborazione documenti..." : "Genera con IA"}
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

