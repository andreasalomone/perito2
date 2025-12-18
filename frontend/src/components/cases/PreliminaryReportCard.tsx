"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText, Loader2, RefreshCw, Clock, CheckCircle2, Edit, Download, BrainCircuit } from "lucide-react";
import { ExpandableScreen, ExpandableScreenTrigger, ExpandableScreenContent } from "@/components/ui/expandable-screen";
import { PreliminaryReport } from "@/types";
import { MarkdownContent } from "@/components/ui/markdown-content";
import { ReportGeneratingSkeleton } from "@/components/cases/ReportGeneratingSkeleton";
import { ThinkingProcess } from "@/components/cases/ThinkingProcess";
import { useRef, useMemo } from "react";
import { ScrollProgress } from "@/components/motion-primitives/scroll-progress";
import type { StreamState } from "@/hooks/useEarlyAnalysis";

interface PreliminaryReportCardProps {
    report: PreliminaryReport | null;
    canGenerate: boolean;
    pendingDocs: number;
    isLoading: boolean;
    isGenerating: boolean;
    onGenerate: (force?: boolean) => void;
    // Streaming mode props (optional)
    streamingEnabled?: boolean;
    streamState?: StreamState;
    streamedThoughts?: string;
    streamedContent?: string;
    onGenerateStream?: () => void;
}

/**
 * PreliminaryReportCard - Displays AI-generated preliminary working report.
 * Part of the Early Analysis feature for the Case Hub.
 *
 * Shows:
 * - Markdown-rendered report content (collapsible)
 * - Generation status
 * - Generate/refresh button
 */
export function PreliminaryReportCard({
    report,
    canGenerate,
    pendingDocs,
    isLoading,
    isGenerating,
    onGenerate,
    // Streaming props
    streamingEnabled = false,
    streamState = "idle",
    streamedThoughts = "",
    streamedContent = "",
    onGenerateStream,
}: Readonly<PreliminaryReportCardProps>) {
    const hasReport = report !== null;
    const isBlocked = pendingDocs > 0;
    const scrollRef = useRef<HTMLDivElement>(null);

    // Determine if we're actively streaming
    const isStreaming = streamState === "thinking" || streamState === "streaming";
    const hasStreamedContent = streamedContent.length > 0;

    // Determine status for badge
    const getStatus = () => {
        if (isStreaming) return { label: "In generazione", variant: "secondary" as const, icon: BrainCircuit };
        if (isBlocked) return { label: "In attesa", variant: "secondary" as const, icon: Clock };
        if (hasReport || hasStreamedContent) return { label: "Disponibile", variant: "default" as const, icon: CheckCircle2 };
        return { label: "Non generato", variant: "secondary" as const, icon: FileText };
    };

    const status = getStatus();
    const StatusIcon = status.icon;

    // Stable date formatting to avoid hydration mismatch
    const formattedDate = useMemo(() => {
        if (!report) return "";
        try {
            return new Intl.DateTimeFormat('it-IT', {
                dateStyle: 'long',
                timeStyle: 'short'
            }).format(new Date(report.created_at));
        } catch {
            return "Data sconosciuta";
        }
    }, [report]);

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <FileText className="h-5 w-5 text-purple-600" />
                        Report Preliminare
                    </CardTitle>
                    <Badge variant={status.variant} className="flex items-center gap-1">
                        <StatusIcon className="h-3 w-3" />
                        {status.label}
                    </Badge>
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                {/* Pending Documents Warning */}
                {isBlocked && (
                    <Alert>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <AlertDescription>
                            {pendingDocs} documento/i in elaborazione. Attendi il completamento.
                        </AlertDescription>
                    </Alert>
                )}

                {/* Loading State */}
                {isLoading && !hasReport && !isBlocked && (
                    <div className="space-y-3">
                        <Skeleton className="h-4 w-3/4" />
                        <Skeleton className="h-4 w-1/2" />
                        <Skeleton className="h-10 w-full" />
                    </div>
                )}

                {/* Report Content & Actions */}
                {hasReport ? (
                    <ExpandableScreen
                        layoutId="preliminary-report-expand"
                    >
                        <div className="space-y-4">
                            <div className="bg-muted/30 rounded-lg p-6 border border-dashed flex flex-col items-center justify-center text-center space-y-4">
                                <FileText className="h-10 w-10 text-purple-600 dark:text-purple-400" />
                                <div className="space-y-1">
                                    <h4 className="text-lg font-semibold">Report Disponibile</h4>
                                    <p className="text-sm text-muted-foreground px-4">
                                        Generato il {formattedDate}
                                    </p>
                                </div>
                                <ExpandableScreenTrigger className="w-full max-w-xs">
                                    <Button className="w-full bg-purple-600 hover:bg-purple-700 text-white shadow-lg shadow-purple-900/20 group">
                                        <FileText className="h-4 w-4 mr-2 group-hover:scale-110 transition-transform" />
                                        Vedi Report
                                    </Button>
                                </ExpandableScreenTrigger>
                            </div>
                        </div>

                        <ExpandableScreenContent className="p-0">
                            <div className="flex flex-col h-full max-w-5xl mx-auto w-full bg-background">
                                {/* Header */}
                                <div className="flex items-center justify-between p-6 border-b shrink-0 bg-background/95 backdrop-blur z-10 relative">
                                    <div className="space-y-1 ml-12">
                                        <h2 className="text-2xl font-bold flex items-center gap-2 text-purple-700 dark:text-purple-400">
                                            <FileText className="h-6 w-6" />
                                            Report Preliminare
                                        </h2>
                                        <p className="text-muted-foreground">
                                            Bozza di lavoro generata dall'AI.
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <Button variant="outline" size="sm" disabled title="Funzionalità in arrivo">
                                            <Edit className="h-4 w-4 mr-2" />
                                            Modifica
                                        </Button>
                                        <Button variant="outline" size="sm" disabled title="Funzionalità in arrivo">
                                            <Download className="h-4 w-4 mr-2" />
                                            Download
                                        </Button>
                                        <div className="h-6 w-px bg-border mx-1" />
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-muted-foreground hover:text-destructive"
                                            disabled={!canGenerate || isGenerating || isLoading}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onGenerate(true); // Force regenerate
                                            }}
                                        >
                                            {isGenerating ? (
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                            ) : (
                                                <RefreshCw className="h-4 w-4" />
                                            )}
                                        </Button>
                                    </div>
                                    <ScrollProgress containerRef={scrollRef} className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-500 to-pink-500 z-50" />
                                </div>

                                {/* Content */}
                                <div ref={scrollRef} className="flex-1 overflow-y-auto p-8 md:p-12 bg-muted/10 relative">
                                    <div className="bg-background shadow-sm border rounded-xl p-8 md:p-12 min-h-full max-w-4xl mx-auto">
                                        <MarkdownContent
                                            content={report.content}
                                            variant="report"
                                            className="prose-lg"
                                        />
                                    </div>
                                </div>
                            </div>
                        </ExpandableScreenContent>
                    </ExpandableScreen>
                ) : (
                    /* Empty State, Generating State, or Streaming State */
                    !isLoading && !isBlocked && (
                        <div className="space-y-4">
                            {/* Streaming Mode: Show ThinkingProcess + Live Content */}
                            {isStreaming && (
                                <>
                                    <ThinkingProcess
                                        thoughts={streamedThoughts}
                                        state="thinking"
                                        className="mb-4"
                                    />
                                    {hasStreamedContent && (
                                        <div className="bg-background border rounded-lg p-6 animate-in fade-in duration-300">
                                            <MarkdownContent
                                                content={streamedContent}
                                                variant="report"
                                            />
                                        </div>
                                    )}
                                </>
                            )}

                            {/* Non-streaming generating: Show skeleton */}
                            {isGenerating && !isStreaming && (
                                <ReportGeneratingSkeleton variant="report" estimatedTime="~15 sec" />
                            )}

                            {/* Idle state: Show generate button */}
                            {!isGenerating && !isStreaming && (
                                <>
                                    <div className="text-center py-6 text-muted-foreground">
                                        <FileText className="h-10 w-10 mx-auto mb-3 opacity-50" />
                                        <p>Nessun report preliminare</p>
                                        <p className="text-sm">Genera un documento di lavoro per il caso.</p>
                                    </div>
                                    <Button
                                        variant="default"
                                        className="w-full"
                                        disabled={!canGenerate || isGenerating || isLoading || isBlocked}
                                        onClick={() => {
                                            // Prefer streaming if available
                                            if (streamingEnabled && onGenerateStream) {
                                                onGenerateStream();
                                            } else {
                                                onGenerate(hasReport);
                                            }
                                        }}
                                    >
                                        <FileText className="h-4 w-4 mr-2" />
                                        Genera Report Preliminare
                                    </Button>
                                </>
                            )}
                        </div>
                    )
                )}
            </CardContent>
        </Card >
    );
}
