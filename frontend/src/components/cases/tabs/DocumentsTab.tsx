"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { CaseDetail, DocumentWithUrl } from "@/types";
import { CaseFileUploader } from "@/components/cases/CaseFileUploader";
import { DocumentItem } from "@/components/cases/DocumentItem";
import { DocumentAnalysisCard } from "@/components/cases/DocumentAnalysisCard";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Loader2, FileText } from "lucide-react";
import { AnimatePresence } from "motion/react";
import { StaggerList, StaggerItem } from "@/components/primitives/motion/StaggerList";
import { FadeIn } from "@/components/primitives/motion/FadeIn";
import { useDocumentAnalysis } from "@/hooks/useEarlyAnalysis";
import { Badge } from "@/components/ui/badge";

interface DocumentsTabProps {
    caseData: CaseDetail;
    caseId: string;
    isClosed: boolean;
    onUpload: () => Promise<void>;
    onRemoveDocument: (docId: string) => Promise<void>;
    documentAnalysis: ReturnType<typeof useDocumentAnalysis>;
    isProcessingDocs: boolean;
}

/**
 * DocumentsTab - Document upload, list, and analysis
 *
 * Handles:
 * - File upload (CaseFileUploader) for open cases
 * - Document list with status badges
 * - Read-only alphabetical list for closed cases
 * - Document analysis card (always viewable, regeneration disabled when closed)
 */
export function DocumentsTab({
    caseData,
    caseId,
    isClosed,
    onUpload,
    onRemoveDocument,
    documentAnalysis,
    isProcessingDocs,
}: Readonly<DocumentsTabProps>) {
    const { getToken } = useAuth();
    const documents = caseData?.documents || [];

    // Document URLs for preview/download
    const [documentUrls, setDocumentUrls] = useState<DocumentWithUrl[]>([]);
    const hasFetchedRef = useRef(false);

    const successfulDocIds = useMemo(
        () => documents.filter(d => d.ai_status === 'SUCCESS').map(d => d.id).sort().join(','),
        [documents]
    );

    useEffect(() => {
        if (!successfulDocIds && !hasFetchedRef.current) return;
        hasFetchedRef.current = true;

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

    const urlMap = useMemo(() => {
        const map = new Map<string, { url: string | null; canPreview: boolean }>();
        documentUrls.forEach(doc => {
            map.set(doc.id, { url: doc.url ?? null, canPreview: doc.can_preview });
        });
        return map;
    }, [documentUrls]);

    const hasErrors = documents.some(d => d.ai_status === "ERROR");
    const sortedDocs = useMemo(() => {
        if (!isClosed) return documents;
        // Closed case: alphabetical by filename
        return [...documents].sort((a, b) => a.filename.localeCompare(b.filename));
    }, [documents, isClosed]);

    return (
        <div className="space-y-6">
            {/* Document List Card */}
            <Card className="border">
                {isClosed ? (
                    // Closed case: read-only document list
                    <>
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <FileText className="h-5 w-5 text-muted-foreground" />
                                    <CardTitle className="text-lg">Documenti del Sinistro</CardTitle>
                                </div>
                                <Badge variant="secondary">{documents.length}</Badge>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {sortedDocs.length > 0 ? (
                                <div className="max-h-64 overflow-y-auto space-y-2 pr-2">
                                    {sortedDocs.map(doc => {
                                        const urlInfo = urlMap.get(doc.id);
                                        return (
                                            <DocumentItem
                                                key={doc.id}
                                                doc={doc}
                                                url={urlInfo?.url}
                                                canPreview={urlInfo?.canPreview}
                                            // No onDelete - read-only for closed cases
                                            />
                                        );
                                    })}
                                </div>
                            ) : (
                                <p className="text-sm text-muted-foreground italic text-center py-4">
                                    Nessun documento caricato.
                                </p>
                            )}
                        </CardContent>
                    </>
                ) : (
                    // Open case: full upload + management UI
                    <>
                        <CaseFileUploader
                            caseId={caseId}
                            onUploadComplete={onUpload}
                        />
                        <CardContent className="space-y-4">
                            {/* Section Header */}
                            {documents.length > 0 && (
                                <div className="flex items-center justify-between pt-2">
                                    <h3 className="text-sm font-medium text-muted-foreground">
                                        Documenti Caricati
                                    </h3>
                                    <Badge variant="secondary">{documents.length}</Badge>
                                </div>
                            )}

                            {/* Document List */}
                            {documents.length > 0 ? (
                                <AnimatePresence mode="popLayout">
                                    <StaggerList className="space-y-2">
                                        {documents.map(doc => {
                                            const urlInfo = urlMap.get(doc.id);
                                            return (
                                                <StaggerItem key={doc.id}>
                                                    <DocumentItem
                                                        doc={doc}
                                                        onDelete={onRemoveDocument}
                                                        url={urlInfo?.url}
                                                        canPreview={urlInfo?.canPreview}
                                                    />
                                                </StaggerItem>
                                            );
                                        })}
                                    </StaggerList>
                                </AnimatePresence>
                            ) : (
                                <div className="text-center py-8 text-muted-foreground">
                                    <FileText className="h-10 w-10 mx-auto mb-3 opacity-40" />
                                    <p className="text-sm">Nessun documento caricato.</p>
                                    <p className="text-xs mt-1 opacity-70">Trascina i file qui sopra per iniziare.</p>
                                </div>
                            )}
                        </CardContent>
                    </>
                )}
            </Card>

            {/* Alerts for processing/errors */}
            {!isClosed && isProcessingDocs && (
                <FadeIn>
                    <Alert>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <AlertDescription>
                            {documents.filter(d => ['PENDING', 'PROCESSING'].includes(d.ai_status)).length} documento/i in elaborazione...
                        </AlertDescription>
                    </Alert>
                </FadeIn>
            )}

            {!isClosed && hasErrors && (
                <FadeIn>
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                            Alcuni documenti hanno riscontrato errori. Puoi eliminarli e riprovare.
                        </AlertDescription>
                    </Alert>
                </FadeIn>
            )}

            {/* Document Analysis Card - ALWAYS CLICKABLE/VIEWABLE */}
            {/* Only disable regeneration when closed, not viewing */}
            <DocumentAnalysisCard
                analysis={documentAnalysis.analysis}
                isStale={documentAnalysis.isStale}
                canAnalyze={documentAnalysis.canAnalyze && !isClosed}
                pendingDocs={documentAnalysis.pendingDocs}
                isLoading={documentAnalysis.isLoading}
                isGenerating={documentAnalysis.isGenerating}
                onGenerate={documentAnalysis.generate}
            />
        </div>
    );
}
