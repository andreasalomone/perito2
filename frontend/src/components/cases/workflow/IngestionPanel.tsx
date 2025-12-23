"use client";

import { useState, useEffect, useMemo } from "react";
import { CaseDetail, DocumentWithUrl, ReportVersion } from "@/types";
import type { StreamState } from "@/hooks/useEarlyAnalysis";
import { CaseFileUploader } from "@/components/cases/CaseFileUploader";
import { DocumentItem } from "@/components/cases/DocumentItem";
import { DocumentAnalysisCard } from "@/components/cases/DocumentAnalysisCard";
import { PreliminaryReportCard } from "@/components/cases/PreliminaryReportCard";
import { FinalReportCard } from "@/components/cases/FinalReportCard";

import { TemplateType } from "@/components/cases/VersionItem";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Upload, UploadCloud, AlertCircle, Loader2 } from "lucide-react";
import { AnimatePresence } from "motion/react";
import { StaggerList, StaggerItem } from "@/components/primitives/motion/StaggerList";
import { FadeIn } from "@/components/primitives/motion/FadeIn";
import { ReportGeneratingSkeleton } from "@/components/cases/ReportGeneratingSkeleton";
import { useDocumentAnalysis, usePreliminaryReport } from "@/hooks/useEarlyAnalysis";


interface IngestionPanelProps {
    caseData: CaseDetail;
    caseId: string;
    onUpload: () => Promise<void>;
    onRemoveDocument: (docId: string) => Promise<void>;

    // Analysis & Report Actions
    documentAnalysis: ReturnType<typeof useDocumentAnalysis>;
    preliminaryReport: ReturnType<typeof usePreliminaryReport>;
    isProcessingDocs: boolean;
    // Removed redundant handler props as they are inside the objects now
    // onAnalyzeDocuments: (force?: boolean) => void;
    // onGeneratePreliminary: (force?: boolean) => void;

    // Preliminary Streaming
    preliminaryStreamState?: StreamState;
    preliminaryStreamedThoughts?: string;
    preliminaryStreamedContent?: string;

    // Final Report Props
    finalReportStreamState?: StreamState;
    finalReportStreamedThoughts?: string;
    finalReportStreamedContent?: string;
    finalReportStreamError?: string | null;
    onGenerateFinalReport: (language: string, extraInstructions?: string) => void;
    onUpdateNotes: (notes: string) => void;
    onDownloadFinalReport: (version: ReportVersion, template: TemplateType) => Promise<void>;
    onFinalizeCase: (file: File) => Promise<void>;
    onConfirmDocs: (versionId: string) => Promise<void>;
    onOpenInDocs: (version: ReportVersion, template: TemplateType) => Promise<void>;
    onPreliminaryGenerateStream?: () => void;

    // Case Details Panel props
    onCaseUpdate: (updatedCase: CaseDetail) => void;
}

/**
 * IngestionPanel - Document upload and early analysis
 *
 * Users upload documents for the case.
 * Shows existing documents with their processing status.
 * Enables generation when at least one document is ready.
 */
export function IngestionPanel({
    caseData,
    caseId,
    onUpload,
    onRemoveDocument,
    documentAnalysis,
    preliminaryReport,
    isProcessingDocs,
    preliminaryStreamState,
    preliminaryStreamedThoughts,
    preliminaryStreamedContent,

    // Final Report Props
    finalReportStreamState,
    finalReportStreamedThoughts,
    finalReportStreamedContent,
    finalReportStreamError,
    onGenerateFinalReport,
    onUpdateNotes,
    onDownloadFinalReport,
    onFinalizeCase,
    onConfirmDocs,
    onOpenInDocs,
    onPreliminaryGenerateStream,
    onCaseUpdate,
}: Readonly<IngestionPanelProps>) {
    const { getToken } = useAuth();
    const documents = caseData?.documents || [];
    // Determine if generating final report
    const isGeneratingFinal = caseData.status === "GENERATING" || finalReportStreamState === "thinking" || finalReportStreamState === "streaming";

    // Document URLs for preview/download
    const [documentUrls, setDocumentUrls] = useState<DocumentWithUrl[]>([]);

    // Create stable dependency: only refetch when SUCCESS doc IDs change
    const successfulDocIds = useMemo(
        () => documents.filter(d => d.ai_status === 'SUCCESS').map(d => d.id).sort().join(','),
        [documents]
    );

    // Fetch document URLs when successful docs change
    useEffect(() => {
        if (!successfulDocIds) {
            setDocumentUrls([]);
            return;
        }

        let cancelled = false;
        const fetchUrls = async () => {
            try {
                const token = await getToken();
                if (!token || cancelled) return;
                const response = await api.cases.listDocuments(token, caseId);
                if (!cancelled) setDocumentUrls(response.documents);
            } catch (error) {
                if (!cancelled) console.error("Failed to fetch document URLs:", error);
            }
        };

        fetchUrls();
        return () => { cancelled = true; };
    }, [successfulDocIds, caseId, getToken]);

    // Create a lookup map for document URLs by ID
    const urlMap = useMemo(() => {
        const map = new Map<string, { url: string | null; canPreview: boolean }>();
        documentUrls.forEach(doc => {
            map.set(doc.id, { url: doc.url ?? null, canPreview: doc.can_preview });
        });
        return map;
    }, [documentUrls]);

    // Count documents by status
    const pendingDocs = documents.filter(d => ['PENDING', 'PROCESSING'].includes(d.ai_status));
    const errorDocs = documents.filter(d => d.ai_status === 'ERROR');

    // Show warning if some docs failed
    const hasErrors = errorDocs.length > 0;

    const isGenerating = documentAnalysis.isGenerating || preliminaryReport.isGenerating;

    return (
        <div className="space-y-6">
            {/* Unified Ingestion Card */}
            <Card className="border">
                <CardHeader className="pb-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-xl flex items-center gap-2">
                                <Upload className="h-5 w-5 text-primary" />
                                Gestione Documenti
                            </CardTitle>
                            <CardDescription className="mt-1">
                                {documents.length > 0
                                    ? `${documents.length} documenti caricati. Carica altri file se necessario.`
                                    : "Carica i documenti del sinistro per iniziare l'analisi."}
                            </CardDescription>
                        </div>
                        {documents.length > 0 && (
                            <CaseFileUploader
                                caseId={caseId}
                                onUploadComplete={() => onUpload()}
                            />
                        )}
                    </div>
                </CardHeader>
                <CardContent>
                    {documents.length === 0 ? (
                        <CaseFileUploader
                            caseId={caseId}
                            onUploadComplete={() => onUpload()}
                            trigger={
                                <div className="flex flex-col items-center justify-center py-12 px-4 rounded-lg border-2 border-dashed border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50 cursor-pointer transition-all">
                                    <div className="p-4 rounded-full bg-background shadow-sm mb-4">
                                        <UploadCloud className="h-8 w-8 text-primary" />
                                    </div>
                                    <h3 className="font-semibold text-lg mb-1">Carica file del sinistro</h3>
                                    <p className="text-sm text-muted-foreground text-center max-w-sm mb-4">
                                        Supporta PDF, DOCX, XLSX, Immagini, e EML.
                                    </p>
                                    <Button variant="default">Seleziona File</Button>
                                </div>
                            }
                        />
                    ) : (
                        <div className="space-y-4">
                            <StaggerList className="grid gap-2">
                                <AnimatePresence mode="popLayout">
                                    {documents.map((doc) => {
                                        const urlData = urlMap.get(doc.id);
                                        return (
                                            <StaggerItem key={doc.id}>
                                                <DocumentItem
                                                    doc={doc}
                                                    onDelete={() => onRemoveDocument(doc.id)}
                                                    url={urlData?.url}
                                                    canPreview={urlData?.canPreview}
                                                />
                                            </StaggerItem>
                                        );
                                    })}
                                </AnimatePresence>
                            </StaggerList>
                            {/* Guidance when all documents are in error state */}
                            {documents.length > 0 && documents.every(d => d.ai_status === 'ERROR') && (
                                <div className="p-3 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                                    <p>⚠️ Tutti i file hanno errori. Ricarica i file corretti o procedi con documenti validi.</p>
                                </div>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Case Details Panel moved to parent page layout */}

            {/* Early Analysis Section - Always render to prevent CLS */}
            <div className="grid md:grid-cols-2 gap-4 min-h-[200px]">
                {/* Document Analysis Card or Skeleton */}
                {documentAnalysis ? (
                    documentAnalysis.isLoading && !documentAnalysis.analysis ? (
                        <Card className="h-48 animate-pulse">
                            <CardHeader className="pb-3">
                                <div className="flex items-center justify-between">
                                    <div className="h-5 w-32 bg-muted rounded" />
                                    <div className="h-5 w-20 bg-muted rounded" />
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="h-4 w-full bg-muted rounded" />
                                <div className="h-4 w-3/4 bg-muted rounded" />
                                <div className="h-10 w-full bg-muted rounded" />
                            </CardContent>
                        </Card>
                    ) : (
                        <DocumentAnalysisCard
                            analysis={documentAnalysis.analysis}
                            isStale={documentAnalysis.isStale}
                            canAnalyze={documentAnalysis.canAnalyze}
                            pendingDocs={documentAnalysis.pendingDocs}
                            isLoading={documentAnalysis.isLoading}
                            isGenerating={documentAnalysis.isGenerating}
                            onGenerate={documentAnalysis.generate}
                        />
                    )
                ) : <Card className="h-48 animate-pulse bg-muted/30" />}

                {/* Preliminary Report Card or Skeleton */}
                {preliminaryReport ? (
                    preliminaryReport.isLoading && !preliminaryReport.report ? (
                        <Card className="h-48 animate-pulse">
                            <CardHeader className="pb-3">
                                <div className="flex items-center justify-between">
                                    <div className="h-5 w-36 bg-muted rounded" />
                                    <div className="h-5 w-24 bg-muted rounded" />
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="h-4 w-full bg-muted rounded" />
                                <div className="h-4 w-2/3 bg-muted rounded" />
                                <div className="h-10 w-full bg-muted rounded" />
                            </CardContent>
                        </Card>
                    ) : (
                        <PreliminaryReportCard
                            report={preliminaryReport.report}
                            canGenerate={preliminaryReport.canGenerate}
                            pendingDocs={preliminaryReport.pendingDocs}
                            isLoading={preliminaryReport.isLoading}
                            isGenerating={preliminaryReport.isGenerating}
                            onGenerate={preliminaryReport.generate}
                            streamingEnabled={true}
                            streamState={preliminaryStreamState ?? "idle"}
                            streamedThoughts={preliminaryStreamedThoughts ?? ""}
                            streamedContent={preliminaryStreamedContent ?? ""}
                            onGenerateStream={onPreliminaryGenerateStream}
                        />
                    )
                ) : <Card className="h-48 animate-pulse bg-muted/30" />}
            </div>

            {/* Error Warning */}
            {hasErrors && (
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                        {errorDocs.length} documento/i non elaborato/i correttamente.
                        Puoi eliminarli e ricaricarli, oppure procedere senza.
                    </AlertDescription>
                </Alert>
            )}

            {/* Processing Notice */}
            {isProcessingDocs && (
                <Alert>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <AlertDescription>
                        Elaborazione documenti in corso... ({pendingDocs.length} rimanenti)
                    </AlertDescription>
                </Alert>
            )}

            {/* Optimistic Report Skeleton - Shows immediately when generation starts */}
            {isGenerating && (
                <FadeIn>
                    <ReportGeneratingSkeleton
                        variant="report"
                        estimatedTime="~30 sec"
                        className="mt-4"
                    />
                </FadeIn>
            )}

            {/* 3. Final Report Card (Replaces old footer) */}
            <FinalReportCard
                caseData={caseData}
                isGenerating={isGeneratingFinal}
                onGenerate={onGenerateFinalReport}
                onUpdateNotes={onUpdateNotes}
                onDownload={onDownloadFinalReport}
                onFinalize={onFinalizeCase}
                onConfirmDocs={onConfirmDocs}
                onOpenInDocs={onOpenInDocs}
                streamingEnabled={true}
                streamState={finalReportStreamState}
                streamedThoughts={finalReportStreamedThoughts}
                streamedContent={finalReportStreamedContent}
                streamError={finalReportStreamError}
            />
        </div>
    );
}


