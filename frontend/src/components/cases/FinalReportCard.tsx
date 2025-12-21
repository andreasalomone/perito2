"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { FileText, Loader2, Edit, Download, CheckCircle, AlertCircle } from "lucide-react";
import { ExpandableScreen, ExpandableScreenTrigger, ExpandableScreenContent } from "@/components/ui/expandable-screen";
import { CaseDetail, ReportVersion } from "@/types";
import { MarkdownContent } from "@/components/ui/markdown-content";
import { ThinkingProcess } from "@/components/cases/ThinkingProcess";
import { useState, useMemo } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { NotesDialog } from "@/components/cases/dialogs/NotesDialog";
import { TemplateSelectionDialog } from "@/components/cases/dialogs/DownloadDialog";
import { CloseCaseDialog } from "@/components/cases/dialogs/CloseCaseDialog";
import { TemplateType } from "@/components/cases/VersionItem";
import type { StreamState } from "@/hooks/useEarlyAnalysis";

interface FinalReportCardProps {
    caseData: CaseDetail;
    isGenerating: boolean;
    // Handlers
    onGenerate: (language: string, extraInstructions?: string) => void;
    onUpdateNotes: (notes: string) => void;
    onDownload: (version: ReportVersion, template: TemplateType) => Promise<void>;
    onFinalize: (file: File) => Promise<void>;
    onConfirmDocs: (versionId: string) => Promise<void>;
    onOpenInDocs: (version: ReportVersion, template: TemplateType) => Promise<void>;
    // Streaming props
    streamingEnabled?: boolean;
    streamState?: StreamState;
    streamedThoughts?: string;
    streamedContent?: string;
    streamError?: string | null;
}

export function FinalReportCard({
    caseData,
    isGenerating,
    onGenerate,
    onUpdateNotes,
    onDownload,
    onFinalize,
    onConfirmDocs,
    onOpenInDocs,
    streamingEnabled = false,
    streamState = "idle",
    streamedThoughts = "",
    streamedContent = "",
    streamError = null,
}: Readonly<FinalReportCardProps>) {
    // State
    const [language, setLanguage] = useState("italian");

    // Dialog States
    const [showNotesDialog, setShowNotesDialog] = useState(false);
    const [showDownloadDialog, setShowDownloadDialog] = useState(false);
    const [showEditDialog, setShowEditDialog] = useState(false);
    const [showCloseDialog, setShowCloseDialog] = useState(false);

    // Derived Data - ONLY consider non-preliminary reports for FinalReportCard
    // source values: 'preliminary' (Early Analysis), 'final' (AI report), 'human' (finalized), or null (legacy)
    const versions = (caseData?.report_versions || []).filter(
        v => v.source !== "preliminary"
    );
    const latestVersion = useMemo(() => {
        if (!versions.length) return undefined;
        return [...versions].sort((a, b) => b.version_number - a.version_number)[0];
    }, [versions]);
    const hasReport = !!latestVersion;
    const isFinal = caseData.status === "CLOSED" || latestVersion?.is_final;
    const activeDraft = versions.find(v => v.is_draft_active && !v.is_final);

    // Determines if we are in "Generating" visual state
    // Either backend status says generating OR frontend streaming is active
    const showGeneratingState = isGenerating || (streamingEnabled && (streamState === "thinking" || streamState === "streaming"));

    // Content to show: Streamed content (if available/generating) OR Latest Version content
    const displayContent = (showGeneratingState && streamedContent) ? streamedContent : (latestVersion?.ai_raw_output || "");

    const handleGenerateClick = () => {
        onGenerate(language, caseData.note || undefined);
    };

    return (
        <>
            <ExpandableScreen>
                <Card className="overflow-hidden">
                    {/* TRIGGER / COLLAPSED STATE */}
                    <div className="p-8">
                        <div className="flex items-start justify-between">
                            {/* Left: Title & Status */}
                            <div className="space-y-1.5">
                                <div className="flex items-center gap-3">
                                    <div className="p-2.5 bg-emerald-500/10 rounded-lg">
                                        <FileText className="h-5 w-5 text-emerald-600" />
                                    </div>
                                    <h3 className="text-xl font-semibold">Report Finale</h3>
                                    {isFinal && <Badge variant="success">Finalizzato</Badge>}
                                    {activeDraft && !isFinal && <Badge variant="secondary">In Modifica su Docs</Badge>}
                                </div>
                                <p className="text-sm text-muted-foreground max-w-xl">
                                    Genera, revisiona e finalizza la perizia completa.
                                    {hasReport ? ` Ultima versione: v${latestVersion.version_number}` : " Nessun report generato."}
                                </p>
                            </div>

                            {/* Right: Actions (Collapsed) */}
                            <div className="flex items-center gap-4">
                                {/* Show generation controls only when no report exists or while generating */}
                                {(!hasReport || showGeneratingState) && (
                                    <>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setShowNotesDialog(true)}
                                        >
                                            <Edit className="h-4 w-4 mr-2" />
                                            {caseData.note ? "Modifica Info" : "Aggiungi Info"}
                                        </Button>

                                        <div className="min-w-[150px]">
                                            <Select value={language} onValueChange={setLanguage} disabled={showGeneratingState}>
                                                <SelectTrigger className="h-10">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="italian">Italiano</SelectItem>
                                                    <SelectItem value="english">Inglese</SelectItem>
                                                    <SelectItem value="spanish">Spagnolo</SelectItem>
                                                    <SelectItem value="german">Tedesco</SelectItem>
                                                    <SelectItem value="french">Francese</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        <Button
                                            onClick={handleGenerateClick}
                                            disabled={showGeneratingState}
                                            variant="brand"
                                            size="default"
                                        >
                                            {showGeneratingState ? (
                                                <>
                                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                    Generazione...
                                                </>
                                            ) : (
                                                "Genera Report"
                                            )}
                                        </Button>
                                    </>
                                )}

                                {/* Show "Vedi Report" as main CTA when report exists and not generating */}
                                {hasReport && !showGeneratingState && (
                                    <ExpandableScreenTrigger>
                                        <Button variant="brand" size="default">
                                            <FileText className="h-4 w-4 mr-2" />
                                            Vedi Report
                                        </Button>
                                    </ExpandableScreenTrigger>
                                )}
                            </div>
                        </div>


                        {/* ERROR STATE */}
                        {streamError && (
                            <div className="mt-4 p-3 bg-destructive/10 border border-destructive/20 rounded-md flex items-center gap-2 text-destructive text-sm animate-in fade-in slide-in-from-top-2">
                                <AlertCircle className="h-4 w-4" />
                                <span>{streamError}</span>
                            </div>
                        )}


                        {/* GENERATING STATE (Visible in collapsed view too if generating) */}
                        {showGeneratingState && (
                            <div className="mt-8 border-t pt-8 animate-in fade-in zoom-in-95 duration-300">
                                <ThinkingProcess
                                    thoughts={streamedThoughts}
                                    state={streamState === "thinking" ? "thinking" : "done"}
                                />
                            </div>
                        )}
                    </div>

                    {/* EXPANDED CONTENT */}
                    <ExpandableScreenContent>
                        <div className="flex flex-col h-full bg-slate-50 dark:bg-zinc-950/50">
                            {/* Toolbar */}
                            <div className="bg-white dark:bg-zinc-900 border-b px-6 py-4 flex items-center justify-between sticky top-0 z-10">
                                <div className="flex items-center gap-2 ml-12">
                                    <h4 className="font-semibold text-sm uppercase tracking-wider text-muted-foreground">
                                        Anteprima Report {latestVersion ? `(v${latestVersion.version_number})` : ""}
                                    </h4>
                                </div>

                                <div className="flex items-center gap-2">
                                    {/* Edit Online */}
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setShowEditDialog(true)}
                                        disabled={!latestVersion}
                                    >
                                        <Edit className="h-4 w-4 mr-2" />
                                        Modifica Online
                                    </Button>

                                    {/* Download */}
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setShowDownloadDialog(true)}
                                        disabled={!latestVersion}
                                    >
                                        <Download className="h-4 w-4 mr-2" />
                                        Scarica
                                    </Button>

                                    {/* Close Case */}
                                    <Button
                                        variant="success"
                                        size="sm"
                                        onClick={() => setShowCloseDialog(true)}
                                    >
                                        <CheckCircle className="h-4 w-4 mr-2" />
                                        Chiudi Sinistro
                                    </Button>
                                </div>
                            </div>

                            {/* Main Content Area */}
                            <div className="flex-1 overflow-auto p-8 max-w-4xl mx-auto w-full">
                                {displayContent ? (
                                    <div className="prose prose-slate dark:prose-invert max-w-none bg-white dark:bg-zinc-900 p-8 rounded-2xl shadow-sm min-h-[500px]">
                                        <MarkdownContent content={displayContent} />
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground min-h-[300px]">
                                        <FileText className="h-12 w-12 mb-4 opacity-20" />
                                        <p>Nessun contenuto disponibile.</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </ExpandableScreenContent>
                </Card>
            </ExpandableScreen>

            {/* DIALOGS */}
            <NotesDialog
                isOpen={showNotesDialog}
                onClose={() => setShowNotesDialog(false)}
                initialNotes={caseData.note || ""}
                onSave={onUpdateNotes}
            />

            {/* DOWNLOAD DIALOG */}
            <TemplateSelectionDialog
                isOpen={showDownloadDialog}
                onClose={() => setShowDownloadDialog(false)}
                onSelect={(template) => latestVersion && onDownload(latestVersion, template)}
                title="Scarica Report"
                description="Seleziona il modello di documento da scaricare."
            />

            {/* EDIT DIALOG */}
            <TemplateSelectionDialog
                isOpen={showEditDialog}
                onClose={() => setShowEditDialog(false)}
                onSelect={(template) => latestVersion && onOpenInDocs(latestVersion, template)}
                title="Modifica con Google Docs"
                description="Seleziona il modello da utilizzare per la modifica online."
            />

            <CloseCaseDialog
                isOpen={showCloseDialog}
                onClose={() => setShowCloseDialog(false)}
                activeDraft={activeDraft}
                onFinalize={onFinalize}
                onConfirmDocs={onConfirmDocs}
                isLoading={false} // Loading handled by parent via isGenerating usually, but close logic is separate
            />
        </>
    );
}
