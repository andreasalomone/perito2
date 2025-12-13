"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { FileText, Loader2, RefreshCw, Clock, CheckCircle2 } from "lucide-react";
import { PreliminaryReport } from "@/types";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface PreliminaryReportCardProps {
    report: PreliminaryReport | null;
    canGenerate: boolean;
    pendingDocs: number;
    isLoading: boolean;
    isGenerating: boolean;
    onGenerate: (force?: boolean) => void;
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
}: PreliminaryReportCardProps) {
    const hasReport = report !== null;
    const isBlocked = pendingDocs > 0;
    const [isExpanded, setIsExpanded] = useState(false);

    // Determine status for badge
    const getStatus = () => {
        if (isBlocked) return { label: "In attesa", variant: "secondary" as const, icon: Clock };
        if (hasReport) return { label: "Disponibile", variant: "default" as const, icon: CheckCircle2 };
        return { label: "Non generato", variant: "secondary" as const, icon: FileText };
    };

    const status = getStatus();
    const StatusIcon = status.icon;

    // Truncate content for preview (first 500 chars)
    const PREVIEW_LENGTH = 500;
    const shouldTruncate = hasReport && report.content.length > PREVIEW_LENGTH;
    const displayContent = isExpanded
        ? report?.content
        : report?.content?.slice(0, PREVIEW_LENGTH) + (shouldTruncate ? "..." : "");

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
                <CardDescription>
                    Documento di lavoro interno generato dall&apos;AI per la revisione del caso.
                </CardDescription>
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

                {/* Report Content */}
                {hasReport && (
                    <div className="space-y-3">
                        <div className={cn(
                            "prose prose-sm dark:prose-invert max-w-none",
                            "bg-muted/30 rounded-lg p-4",
                            !isExpanded && "max-h-[300px] overflow-hidden relative"
                        )}>
                            <ReactMarkdown
                                components={{
                                    h1: ({ children }) => <h1 className="text-xl font-bold mt-4 mb-2">{children}</h1>,
                                    h2: ({ children }) => <h2 className="text-lg font-semibold mt-3 mb-2">{children}</h2>,
                                    h3: ({ children }) => <h3 className="text-base font-medium mt-2 mb-1">{children}</h3>,
                                    ul: ({ children }) => <ul className="list-disc list-inside my-2 space-y-1">{children}</ul>,
                                    ol: ({ children }) => <ol className="list-decimal list-inside my-2 space-y-1">{children}</ol>,
                                    p: ({ children }) => <p className="my-2 text-muted-foreground leading-relaxed">{children}</p>,
                                    strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                                }}
                            >
                                {displayContent || ""}
                            </ReactMarkdown>

                            {/* Fade overlay when truncated */}
                            {!isExpanded && shouldTruncate && (
                                <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-muted/80 to-transparent" />
                            )}
                        </div>

                        {/* Expand/Collapse Toggle */}
                        {shouldTruncate && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="w-full text-muted-foreground"
                                onClick={() => setIsExpanded(!isExpanded)}
                            >
                                {isExpanded ? "Mostra meno" : "Mostra tutto"}
                            </Button>
                        )}

                        {/* Generation timestamp */}
                        <p className="text-xs text-muted-foreground text-right">
                            Generato: {new Date(report.created_at).toLocaleString("it-IT")}
                        </p>
                    </div>
                )}

                {/* Empty State */}
                {!hasReport && !isLoading && !isBlocked && (
                    <div className="text-center py-6 text-muted-foreground">
                        <FileText className="h-10 w-10 mx-auto mb-3 opacity-50" />
                        <p>Nessun report preliminare</p>
                        <p className="text-sm">Genera un documento di lavoro per il caso.</p>
                    </div>
                )}

                {/* Generate/Refresh Button */}
                <div className="pt-2">
                    <Button
                        variant={hasReport ? "outline" : "default"}
                        className="w-full"
                        disabled={!canGenerate || isGenerating || isLoading || isBlocked}
                        onClick={() => onGenerate(hasReport)}
                    >
                        {isGenerating ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Generazione in corso...
                            </>
                        ) : hasReport ? (
                            <>
                                <RefreshCw className="h-4 w-4 mr-2" />
                                Rigenera Report
                            </>
                        ) : (
                            <>
                                <FileText className="h-4 w-4 mr-2" />
                                Genera Report Preliminare
                            </>
                        )}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
