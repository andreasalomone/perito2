"use client";

import { useCallback, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useConfig } from "@/context/ConfigContext";
import { ReportVersion } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, RefreshCw, Trash2 } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { handleApiError } from "@/lib/error";
import { TemplateType } from "@/components/cases/VersionItem";

import { useCaseDetail } from "@/hooks/useCaseDetail";
import { useDocumentAnalysis, usePreliminaryReport, usePreliminaryReportStream, useFinalReportStream } from "@/hooks/useEarlyAnalysis";
import { api } from "@/lib/api";
import { mutate as globalMutate } from 'swr';

import {
    ErrorStateOverlay,
    IngestionPanel,
} from "@/components/cases/workflow";
import CaseDetailsPanel from "@/components/cases/CaseDetailsPanel";

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
        isProcessingDocs,
        currentStep,
    } = useCaseDetail(caseId);

    // Early Analysis hooks - poll only when documents are processing
    const documentAnalysisHook = useDocumentAnalysis(caseId, isProcessingDocs ?? false);
    const preliminaryReportHook = usePreliminaryReport(caseId, isProcessingDocs ?? false);

    // Streaming hook for preliminary report (chain of thought visibility)
    const preliminaryStreamHook = usePreliminaryReportStream(caseId);
    // Streaming hook for final report
    const finalReportStreamHook = useFinalReportStream(caseId);

    // Redirect CLOSED/finalized cases to summary page
    useEffect(() => {
        if (!caseData || isLoading) return;

        const isClosed = caseData.status === 'CLOSED';
        const hasFinalVersion = caseData.report_versions?.some(v => v.is_final);

        if (isClosed || hasFinalVersion) {
            router.replace(`/dashboard/cases/${caseId}/summary`);
        }
    }, [caseData, isLoading, caseId, router]);



    // --- Handlers ---

    // Note: handleGenerate (blocking) is kept for fallback but UI uses streaming hook now.
    // We implement handleUpdateNotes for the new functionality
    const handleUpdateNotes = useCallback(async (notes: string) => {
        if (!caseId) return;
        try {
            const token = await getToken();
            await api.cases.update(token, caseId, { note: notes });
            toast.success("Note salvate");
            mutate();
        } catch (error) {
            handleApiError(error, "Errore salvataggio note");
        }
    }, [caseId, getToken, mutate]);

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
        const id = caseId as string;

        const optimisticData = caseData ? {
            ...caseData,
            documents: caseData.documents.filter(d => d.id !== docId)
        } : undefined;

        try {
            const token = await getToken();
            mutate(optimisticData, false);
            await api.cases.deleteDocument(token, id, docId);
            toast.success("Documento eliminato");
            mutate();
        } catch (error) {
            handleApiError(error, "Errore durante l'eliminazione");
            mutate();
        }
    }, [caseId, getToken, mutate, caseData]);

    const handleDeleteCase = useCallback(async () => {
        if (!caseId) return;
        const id = caseId as string;
        if (!confirm("Sei sicuro di voler eliminare questo caso e tutti i documenti associati?")) return;

        try {
            const token = await getToken();
            await api.cases.deleteCase(token, id);
            toast.success("Caso eliminato");
            globalMutate(
                (key) => Array.isArray(key) && key[0] === 'cases',
                undefined,
                { revalidate: true }
            );
            router.push("/dashboard");
        } catch (error) {
            handleApiError(error, "Errore durante l'eliminazione");
        }
    }, [caseId, getToken, router]);

    const handleFinalize = async (file: File) => {
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

            const maxFileSize = 50 * 1024 * 1024;
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

            toast.success("Caso finalizzato con successo!", { id: toastId });

            // Explicit redirect to summary page (don't rely on useEffect)
            // Small delay to let confetti animation play
            setTimeout(() => {
                router.push(`/dashboard/cases/${caseId}/summary`);
            }, 2000);
        } catch (error) {
            handleApiError(error, "Errore caricamento finale");
            toast.dismiss(toastId);
            throw error;
        }
    };

    const handleOpenInDocs = useCallback(async (v: ReportVersion, template: TemplateType) => {
        const toastId = toast.loading("Apertura in Google Docs...");
        try {
            const token = await getToken();
            const res = await axios.post(
                `${apiUrl}/api/v1/cases/${caseId}/versions/${v.id}/open-in-docs`,
                { template },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            window.open(res.data.url, "_blank", "noopener,noreferrer");
            toast.success("Documento aperto in Google Docs", { id: toastId });
            mutate();
        } catch (e) {
            handleApiError(e, "Errore apertura Google Docs");
            toast.dismiss(toastId);
        }
    }, [caseId, getToken, apiUrl, mutate]);

    const handleConfirmDocs = useCallback(async (versionId: string) => {
        const toastId = toast.loading("Sincronizzazione da Google Docs...");
        try {
            const token = await getToken();
            await axios.post(
                `${apiUrl}/api/v1/cases/${caseId}/versions/${versionId}/confirm-docs`,
                {},
                { headers: { Authorization: `Bearer ${token}` } }
            );
            toast.success("Caso finalizzato con successo!", { id: toastId });
            setTimeout(() => {
                router.push(`/dashboard/cases/${caseId}/summary`);
            }, 2000);
        } catch (e) {
            handleApiError(e, "Errore sincronizzazione");
            toast.dismiss(toastId);
            throw e;
        }
    }, [caseId, getToken, apiUrl, router]);



    // --- Render States ---

    if (isLoading) {
        return (
            <div className="space-y-6 max-w-6xl mx-auto p-4 animate-pulse">
                <div className="h-8 w-1/3 bg-muted rounded"></div>
                <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-8">
                    <div className="h-64 bg-muted rounded-lg"></div>
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

    // --- Main Render ---

    return (
        <div className="max-w-6xl mx-auto p-4 space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">{caseData.reference_code}</h1>
                    {caseData.client_name && (
                        <p className="text-muted-foreground">
                            Cliente: <span className="font-medium text-foreground">{caseData.client_name}</span>
                        </p>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    <Badge
                        variant={caseData.status === "OPEN" ? "default" : caseData.status === "ERROR" ? "destructive" : "secondary"}
                        className="text-sm px-3 py-1"
                    >
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

            {/* Main: Consolidated Workflow (Ingestion -> Analysis -> Final Report) */}
            <main className="min-h-[500px]">
                {currentStep === 'ERROR' ? (
                    <ErrorStateOverlay
                        caseData={caseData}
                        onDeleteDocument={handleDeleteDocument}
                        onRetryGeneration={() => finalReportStreamHook.generateStream("italian")} // Simple retry
                    />
                ) : (
                    <>
                        <IngestionPanel
                            caseData={caseData}
                            caseId={caseId as string}
                            onUpload={async () => {
                                await mutate();
                            }}
                            onRemoveDocument={handleDeleteDocument}
                            documentAnalysis={documentAnalysisHook}
                            preliminaryReport={preliminaryReportHook}
                            isProcessingDocs={isProcessingDocs ?? false}

                            // Streaming Props (Preliminary)
                            preliminaryStreamState={preliminaryStreamHook.state}
                            preliminaryStreamedThoughts={preliminaryStreamHook.thoughts}
                            preliminaryStreamedContent={preliminaryStreamHook.content}
                            onPreliminaryGenerateStream={preliminaryStreamHook.generateStream}

                            // Streaming Props (Final Report)
                            onGenerateFinalReport={finalReportStreamHook.generateStream}
                            finalReportStreamState={finalReportStreamHook.state}
                            finalReportStreamedThoughts={finalReportStreamHook.thoughts}
                            finalReportStreamedContent={finalReportStreamHook.content}

                            // Actions
                            onUpdateNotes={handleUpdateNotes}
                            onDownloadFinalReport={handleDownload}
                            onFinalizeCase={handleFinalize}
                            onConfirmDocs={handleConfirmDocs}
                            onOpenInDocs={handleOpenInDocs}
                        />
                        <CaseDetailsPanel
                            caseDetail={caseData}
                            onUpdate={(updated) => mutate(updated, false)}
                        />
                    </>
                )}
            </main>

        </div >
    );
}
