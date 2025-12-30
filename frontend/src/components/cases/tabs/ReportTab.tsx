"use client";

import { useState, useMemo } from "react";
import { CaseDetail, ReportVersion } from "@/types";
import type { StreamState } from "@/hooks/useEarlyAnalysis";
import { PreliminaryReportCard } from "@/components/cases/PreliminaryReportCard";
import { FinalReportCard } from "@/components/cases/FinalReportCard";
import { TemplateType } from "@/components/cases/VersionItem";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, Download, Loader2 } from "lucide-react";
import { usePreliminaryReport } from "@/hooks/useEarlyAnalysis";

interface ReportTabProps {
    caseData: CaseDetail;
    isClosed: boolean;
    // Preliminary Report
    preliminaryReport: ReturnType<typeof usePreliminaryReport>;
    preliminaryStreamState?: StreamState;
    preliminaryStreamedThoughts?: string;
    preliminaryStreamedContent?: string;
    onPreliminaryGenerateStream?: () => void;
    // Final Report
    onGenerateFinalReport: (language: string, extraInstructions?: string) => void;
    onUpdateNotes: (notes: string) => void;
    onDownloadFinalReport: (version: ReportVersion, template: TemplateType) => Promise<void>;
    onFinalizeCase: (file: File) => Promise<void>;
    onConfirmDocs: (versionId: string) => Promise<void>;
    onOpenInDocs: (version: ReportVersion, template: TemplateType) => Promise<void>;
    finalReportStreamState?: StreamState;
    finalReportStreamedThoughts?: string;
    finalReportStreamedContent?: string;
    finalReportStreamError?: string | null;
}

/**
 * ClosedCaseView - Simplified view for closed cases with download button
 */
function ClosedCaseView({
    finalVersion,
    onDownload
}: {
    finalVersion: ReportVersion | undefined;
    onDownload: (version: ReportVersion, template: TemplateType) => Promise<void>;
}) {
    const [isDownloading, setIsDownloading] = useState(false);

    const handleDownload = async () => {
        if (!finalVersion) return;
        setIsDownloading(true);
        try {
            await onDownload(finalVersion, 'default');
        } finally {
            setIsDownloading(false);
        }
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 bg-emerald-500/10 rounded-lg">
                            <FileText className="h-5 w-5 text-emerald-600" />
                        </div>
                        <div className="flex items-center gap-3">
                            <CardTitle className="text-xl">Report Finale</CardTitle>
                            <Badge variant="success">Finalizzato</Badge>
                        </div>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                <p className="text-muted-foreground">
                    Il caso è stato chiuso con la perizia finale.
                </p>
                {finalVersion ? (
                    <Button
                        onClick={handleDownload}
                        disabled={isDownloading}
                        className="w-full sm:w-auto"
                        variant="brand"
                    >
                        {isDownloading ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Download in corso...
                            </>
                        ) : (
                            <>
                                <Download className="h-4 w-4 mr-2" />
                                Scarica Report Finale
                            </>
                        )}
                    </Button>
                ) : (
                    <p className="text-sm text-muted-foreground italic">
                        Nessun report finale disponibile.
                    </p>
                )}
            </CardContent>
        </Card>
    );
}

/**
 * ReportTab - Preliminary and Final report generation
 *
 * Handles:
 * - Preliminary report with streaming visualization
 * - Final report generation with language selection
 * - Simplified download-only UI for closed cases
 */
export function ReportTab({
    caseData,
    isClosed,
    preliminaryReport,
    preliminaryStreamState,
    preliminaryStreamedThoughts,
    preliminaryStreamedContent,
    onPreliminaryGenerateStream,
    onGenerateFinalReport,
    onUpdateNotes,
    onDownloadFinalReport,
    onFinalizeCase,
    onConfirmDocs,
    onOpenInDocs,
    finalReportStreamState,
    finalReportStreamedThoughts,
    finalReportStreamedContent,
    finalReportStreamError,
}: Readonly<ReportTabProps>) {
    // Get the final version for closed cases
    const finalVersion = useMemo(() => {
        const versions = caseData.report_versions || [];
        // Find the version marked as final, or the latest human/final source version
        const finalV = versions.find(v => v.is_final);
        if (finalV) return finalV;
        // Fallback: latest version sorted by version_number
        const sorted = [...versions]
            .filter(v => v.source !== 'preliminary')
            .sort((a, b) => (b.version_number ?? 0) - (a.version_number ?? 0));
        return sorted[0];
    }, [caseData.report_versions]);

    // Streaming state derived
    const isGeneratingFinal = caseData.status === "GENERATING" ||
        finalReportStreamState === "thinking" ||
        finalReportStreamState === "streaming";

    if (isClosed) {
        // Simplified closed case UI: just download button
        return <ClosedCaseView finalVersion={finalVersion} onDownload={onDownloadFinalReport} />;
    }

    // Open case: full workflow with Preliminary + Final Report cards
    return (
        <div className="space-y-6">
            {/* Preliminary Report Card */}
            <PreliminaryReportCard
                report={preliminaryReport.report}
                canGenerate={preliminaryReport.canGenerate}
                pendingDocs={preliminaryReport.pendingDocs}
                isLoading={preliminaryReport.isLoading}
                isGenerating={preliminaryReport.isGenerating}
                onGenerate={preliminaryReport.generate}
                // Streaming props
                streamState={preliminaryStreamState}
                streamedThoughts={preliminaryStreamedThoughts}
                streamedContent={preliminaryStreamedContent}
                onGenerateStream={onPreliminaryGenerateStream}
            />

            {/* Final Report Card */}
            <FinalReportCard
                caseData={caseData}
                isGenerating={isGeneratingFinal}
                onGenerate={onGenerateFinalReport}
                onUpdateNotes={onUpdateNotes}
                onDownload={onDownloadFinalReport}
                onFinalize={onFinalizeCase}
                onConfirmDocs={onConfirmDocs}
                onOpenInDocs={onOpenInDocs}
                // Streaming props
                streamingEnabled={true}
                streamState={finalReportStreamState}
                streamedThoughts={finalReportStreamedThoughts}
                streamedContent={finalReportStreamedContent}
                streamError={finalReportStreamError}
            />
        </div>
    );
}
