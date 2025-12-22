"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { FileText, Loader2, Edit, Download, CheckCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
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
    // Type-safe language configuration
    type Language = "italian" | "english" | "spanish" | "german" | "french";

    const LANGUAGE_OPTIONS: { value: Language; label: string }[] = [
        { value: "italian", label: "Italiano" },
        { value: "english", label: "Inglese" },
        { value: "spanish", label: "Spagnolo" },
        { value: "german", label: "Tedesco" },
        { value: "french", label: "Francese" },
    ];

    // State
    const [language, setLanguage] = useState<Language>("italian");

    // Dialog States
    const [showNotesDialog, setShowNotesDialog] = useState(false);
    const [showDownloadDialog, setShowDownloadDialog] = useState(false);
    const [showEditDialog, setShowEditDialog] = useState(false);
    const [showCloseDialog, setShowCloseDialog] = useState(false);
    const [isClosing, setIsClosing] = useState(false);

    // Helper: Map StreamState to ThinkingProcess state
    const getThinkingState = (): "idle" | "thinking" | "done" => {
        if (streamState === "thinking" || streamState === "streaming") return "thinking";
        if (streamState === "idle") return "idle";
        return "done";
    };

    // Derived Data - ONLY consider non-preliminary reports for FinalReportCard
    // source values: 'preliminary' (Early Analysis), 'final' (AI report), 'human' (finalized), or null (legacy)
    const versions = (caseData?.report_versions || []).filter(
        v => v.source !== "preliminary"
    );
    const latestVersion = useMemo(() => {
        if (!versions.length) return undefined;
        return [...versions].sort((a, b) => (b.version_number ?? 0) - (a.version_number ?? 0))[0];
    }, [versions]);
    const hasReport = !!latestVersion;
    const isFinal = caseData.status === "CLOSED" || latestVersion?.is_final;
    const activeDraft = versions.find(v => v.is_draft_active && !v.is_final);

    // Determines if we are in "Generating" visual state
    // Either backend status says generating OR frontend streaming is active
    // Error state should cancel "generating" UI so user can retry
    const showGeneratingState = !streamError && (
        isGenerating || (streamingEnabled && (streamState === "thinking" || streamState === "streaming"))
    );

    // Content to show: Streamed content (if available/generating) OR Latest Version content
    const displayContent = (showGeneratingState && streamedContent) ? streamedContent : (latestVersion?.ai_raw_output || "");

    const handleGenerateClick = () => {
        onGenerate(language, caseData.note || undefined);
    };

    return (
        <>
            <ExpandableScreen>
                <Card className="overflow-hidden">
                    {/* LEADER: Title + Controls (Top), Description (Bottom) */}
                    <CardHeader className="pb-4">
                        <div className="flex items-center justify-between">
                            {/* Left: Icon + Title */}
                            <div className="flex items-center gap-3">
                                <div className="p-2.5 bg-emerald-500/10 rounded-lg">
                                    <FileText className="h-5 w-5 text-emerald-600" />
                                </div>
                                <div className="flex items-center gap-3">
                                    <CardTitle className="text-xl">Report Finale</CardTitle>
                                    {isFinal && <Badge variant="success">Finalizzato</Badge>}
                                    {activeDraft && !isFinal && <Badge variant="secondary">In Modifica su Docs</Badge>}
                                </div>
                            </div>

                            {/* Right: Actions */}
                            <div className="flex items-center gap-2">
                                {(!hasReport || showGeneratingState) && (
                                    <>
                                        <div className="w-[100px]">
                                            <Select value={language} onValueChange={(v) => setLanguage(v as Language)} disabled={showGeneratingState}>
                                                <SelectTrigger className="h-9">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {LANGUAGE_OPTIONS.map((opt) => (
                                                        <SelectItem key={opt.value} value={opt.value}>
                                                            {opt.label}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        <Button
                                            onClick={handleGenerateClick}
                                            disabled={showGeneratingState}
                                            variant="brand"
                                            size="default"
                                            className="shadow-sm"
                                        >
                                            {showGeneratingState ? (
                                                <>
                                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                    Generazione...
                                                </>
                                            ) : (
                                                <>
                                                    <FileText className="h-4 w-4 mr-2" />
                                                    Genera Report
                                                </>
                                            )}
                                        </Button>
                                    </>
                                )}

                                {hasReport && !showGeneratingState && (
                                    <ExpandableScreenTrigger>
                                        <Button variant="brand" size="default" className="shadow-sm">
                                            <FileText className="h-4 w-4 mr-2" />
                                            Vedi Report
                                        </Button>
                                    </ExpandableScreenTrigger>
                                )}
                            </div>
                        </div>

                        {/* Description: Full Width below Header Row */}
                        <CardDescription className="text-base mt-2 max-w-none">
                            Genera, revisiona e finalizza la perizia completa.
                        </CardDescription>
                    </CardHeader>

                    {/* CONTENT: Status + Notes Button */}
                    <CardContent className="pt-0 pb-6">
                        <div className="flex items-center gap-6 p-4 bg-muted/30 rounded-lg border border-border/50 w-full">
                            {/* Status Label Block */}
                            <div className="flex items-center gap-3">
                                <Label className="text-sm text-muted-foreground font-normal cursor-default">
                                    Versione Attuale:
                                </Label>
                                <Label className={cn(
                                    "text-sm font-medium cursor-default",
                                    hasReport ? "text-primary" : "text-muted-foreground/70 italic"
                                )}>
                                    {hasReport && latestVersion ? `v${latestVersion.version_number}` : "Nessun report generato"}
                                </Label>
                            </div>

                            {/* Separator */}
                            <div className="h-4 w-px bg-border/60" />

                            {/* Notes Button */}
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowNotesDialog(true)}
                                className="text-muted-foreground hover:text-foreground h-8 -ml-2"
                            >
                                <Edit className="h-3.5 w-3.5 mr-2" />
                                {caseData.note ? "Modifica Note" : "Aggiungi Note"}
                            </Button>
                        </div>

                        {/* ERROR STATE */}
                        {streamError && (
                            <div className="mt-4 p-3 bg-destructive/10 border border-destructive/20 rounded-md flex items-center gap-2 text-destructive text-sm animate-in fade-in slide-in-from-top-2">
                                <AlertCircle className="h-4 w-4" />
                                <span>{streamError}</span>
                            </div>
                        )}

                        {/* GENERATING STATE VISUALIZATION */}
                        {showGeneratingState && (
                            <div className="mt-6 pt-6 border-t animate-in fade-in zoom-in-95 duration-300">
                                <ThinkingProcess
                                    thoughts={streamedThoughts}
                                    state={getThinkingState()}
                                />
                            </div>
                        )}
                    </CardContent>


                    {/* EXPANDED CONTENT */}
                    <ExpandableScreenContent>
                        {/* OUTER WRAPPER: Needs h-full to fill screen, overflow-hidden to prevent double scrollbars */}
                        <div className="flex flex-col h-full bg-muted/10 overflow-hidden">

                            {/* HEADER: flex-none ensures it never shrinks. z-10 ensures it stays above content. */}
                            <div className="flex-none bg-background border-b px-6 py-4 flex items-center justify-between shadow-sm z-10">
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

                            {/* CONTENT AREA: flex-1 takes all remaining height. overflow-y-auto makes ONLY this part scroll. */}
                            <div className="flex-1 overflow-y-auto w-full">
                                <div className="p-8 max-w-5xl mx-auto">
                                    {displayContent ? (
                                        <div className="prose prose-sm md:prose-base dark:prose-invert max-w-none bg-card p-8 md:p-12 rounded-2xl shadow-sm border border-border/40">
                                            <MarkdownContent content={displayContent} />
                                        </div>
                                    ) : (
                                        /* Empty State */
                                        <div className="flex flex-col items-center justify-center h-full text-muted-foreground min-h-[300px]">
                                            <FileText className="h-16 w-16 mb-4 opacity-20" />
                                            <p>Nessun contenuto disponibile</p>
                                        </div>
                                    )}
                                </div>
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
                onFinalize={async (file) => {
                    setIsClosing(true);
                    try {
                        await onFinalize(file);
                    } finally {
                        setIsClosing(false);
                    }
                }}
                onConfirmDocs={async (versionId) => {
                    setIsClosing(true);
                    try {
                        await onConfirmDocs(versionId);
                    } finally {
                        setIsClosing(false);
                    }
                }}
                isLoading={isClosing}
            />
        </>
    );
}
