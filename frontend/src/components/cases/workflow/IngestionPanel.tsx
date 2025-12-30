/**
 * @deprecated This component is deprecated as of the tab refactor (Dec 2024).
 *
 * Responsibilities have been split into:
 * - `DocumentsTab` - Document upload, list, and analysis
 * - `ReportTab` - Preliminary and final report generation
 * - `CaseDetailsPanel` - Case field editing (used directly)
 *
 * This file is kept for reference. Remove after confirming all functionality
 * works correctly in the new tab components.
 */
"use client";

import { useState, useEffect, useMemo, useRef } from "react";
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
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Loader2 } from "lucide-react";
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
    // Determine if case is closed (finalized)
    const isClosed = caseData.status === "CLOSED" || caseData.report_versions?.some(v => v.is_final);
    // Determine if generating final report
    const isGeneratingFinal = caseData.status === "GENERATING" || finalReportStreamState === "thinking" || finalReportStreamState === "streaming";

    // Document URLs for preview/download
    const [documentUrls, setDocumentUrls] = useState<DocumentWithUrl[]>([]);
    // Track if we've ever fetched to avoid resetting on empty successfulDocIds
    const hasFetchedRef = useRef(false);

    // Create stable dependency: only refetch when SUCCESS doc IDs change
    const successfulDocIds = useMemo(
        () => documents.filter(d => d.ai_status === 'SUCCESS').map(d => d.id).sort().join(','),
        [documents]
    );

    // Fetch document URLs when successful docs change
    useEffect(() => {
        // Skip if no successful docs and we've never fetched
        if (!successfulDocIds && !hasFetchedRef.current) return;

        // Mark that we've initiated a fetch cycle (ref mutation doesn't trigger re-render)
        hasFetchedRef.current = true;

        let cancelled = false;
        const fetchUrls = async () => {
            try {
                const token = await getToken();
                if (!token || cancelled) return;
                const response = await api.cases.listDocuments(token, caseId);
                if (!cancelled) setDocumentUrls(response.documents);
            } catch (error) {
                if (!cancelled) {
                    console.error("Failed to fetch document URLs:", error);
                }
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
            {/* FinalReportCard at TOP when case is closed */}
            {isClosed && (
                <FinalReportCard
                    caseData={caseData}
                    isGenerating={false}
                    onGenerate={onGenerateFinalReport}
                    onUpdateNotes={onUpdateNotes}
                    onDownload={onDownloadFinalReport}
                    onFinalize={onFinalizeCase}
                    onConfirmDocs={onConfirmDocs}
                    onOpenInDocs={onOpenInDocs}
                    streamingEnabled={false}
                />
            )}

            {/* Document List Card */}
            <Card className="border">
                {isClosed ? (
                    /* Closed state: read-only, scrollable, alphabetical document list */
                    <>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base">Documenti del Sinistro</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="max-h-64 overflow-y-auto space-y-2 pr-2">
                                {[...documents]
                                    .sort((a, b) => a.filename.localeCompare(b.filename))
                                    .map((doc) => {
                                        const urlData = urlMap.get(doc.id);
                                        return (
                                            <DocumentItem
                                                key={doc.id}
                                                doc={doc}
                                                url={urlData?.url}
                                                canPreview={urlData?.canPreview}
                                            /* No onDelete - read-only */
                                            />
                                        );
                                    })}
                            </div>
                        </CardContent>
                    </>
                ) : (
                    /* Open state: ALWAYS show uploader + document list below */
                    <CardContent className="space-y-4">
                        {/* CaseFileUploader ALWAYS visible for OPEN cases */}
                        <CaseFileUploader
                            caseId={caseId}
                            onUploadComplete={() => onUpload()}
                        />

                        {/* Document list (when documents exist) */}
                        {documents.length > 0 && (
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
                        )}

                        {/* Guidance when all documents are in error state */}
                        {documents.length > 0 && documents.every(d => d.ai_status === 'ERROR') && (
                            <div className="p-3 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                                <p>⚠️ Tutti i file hanno errori. Ricarica i file corretti o procedi con documenti validi.</p>
                            </div>
                        )}
                    </CardContent>
                )}
            </Card>

            {/* Case Details Panel moved to parent page layout */}

            {/* Early Analysis Section - Always render to prevent CLS */}
            <div className={cn("grid md:grid-cols-2 gap-4 min-h-[200px]", isClosed && "opacity-50 pointer-events-none")}>
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
            {
                hasErrors && (
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                            {errorDocs.length} documento/i non elaborato/i correttamente.
                            Puoi eliminarli e ricaricarli, oppure procedere senza.
                        </AlertDescription>
                    </Alert>
                )
            }

            {/* Processing Notice */}
            {
                isProcessingDocs && (
                    <Alert>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <AlertDescription>
                            Elaborazione documenti in corso... ({pendingDocs.length} rimanenti)
                        </AlertDescription>
                    </Alert>
                )
            }

            {/* Optimistic Report Skeleton - Shows immediately when generation starts */}
            {
                isGenerating && (
                    <FadeIn>
                        <ReportGeneratingSkeleton
                            variant="report"
                            estimatedTime="~30 sec"
                            className="mt-4"
                        />
                    </FadeIn>
                )
            }

            {/* 3. Final Report Card - only show at bottom when NOT closed (shown at top when closed) */}
            {!isClosed && (
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
            )}
        </div>
    );
}


