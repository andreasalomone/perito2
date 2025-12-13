"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { FileSearch, Loader2, RefreshCw, AlertCircle, Clock, CheckCircle2 } from "lucide-react";
import { DocumentAnalysis } from "@/types";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";

interface DocumentAnalysisCardProps {
    analysis: DocumentAnalysis | null;
    isStale: boolean;
    canAnalyze: boolean;
    pendingDocs: number;
    isLoading: boolean;
    isGenerating: boolean;
    onGenerate: (force?: boolean) => void;
}

/**
 * DocumentAnalysisCard - Displays AI document analysis results.
 * Part of the Early Analysis feature for the Case Hub.
 *
 * Shows:
 * - Summary of extracted documents
 * - Key facts as a bullet list
 * - Staleness indicator (if documents changed since analysis)
 * - Generate/refresh button
 */
export function DocumentAnalysisCard({
    analysis,
    isStale,
    canAnalyze,
    pendingDocs,
    isLoading,
    isGenerating,
    onGenerate,
}: DocumentAnalysisCardProps) {
    const hasAnalysis = analysis !== null;
    const isBlocked = pendingDocs > 0;

    // Determine status for badge
    const getStatus = () => {
        if (isBlocked) return { label: "In attesa", variant: "secondary" as const, icon: Clock };
        if (isStale) return { label: "Da aggiornare", variant: "outline" as const, icon: RefreshCw };
        if (hasAnalysis) return { label: "Completata", variant: "default" as const, icon: CheckCircle2 };
        return { label: "Non effettuata", variant: "secondary" as const, icon: FileSearch };
    };

    const status = getStatus();
    const StatusIcon = status.icon;

    return (
        <Card className={cn(isStale && "border-amber-500/50")}>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <FileSearch className="h-5 w-5 text-blue-600" />
                        Analisi Documenti
                    </CardTitle>
                    <Badge variant={status.variant} className="flex items-center gap-1">
                        <StatusIcon className="h-3 w-3" />
                        {status.label}
                    </Badge>
                </div>
                <CardDescription>
                    Estrazione automatica di informazioni chiave dai documenti caricati.
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

                {/* Stale Warning */}
                {isStale && hasAnalysis && (
                    <Alert variant="destructive" className="bg-amber-500/10 border-amber-500/50 text-amber-700 dark:text-amber-400">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                            I documenti sono stati modificati. Rigenera l&apos;analisi per risultati aggiornati.
                        </AlertDescription>
                    </Alert>
                )}
                {/* Analysis Content */}
                {hasAnalysis && (
                    <div className="space-y-4">
                        {/* Summary with Markdown */}
                        <div>
                            <h4 className="text-sm font-medium mb-2">Sintesi</h4>
                            <div className="prose prose-sm dark:prose-invert max-w-none text-muted-foreground">
                                <ReactMarkdown
                                    components={{
                                        p: ({ children }) => <p className="my-1.5 text-sm text-muted-foreground leading-relaxed">{children}</p>,
                                        strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                                        ul: ({ children }) => <ul className="list-disc list-inside my-1.5 space-y-0.5">{children}</ul>,
                                        li: ({ children }) => <li className="text-sm">{children}</li>,
                                    }}
                                >
                                    {analysis.summary}
                                </ReactMarkdown>
                            </div>
                        </div>

                        {/* Analysis Breakdown */}
                        <div className="grid grid-cols-1 gap-4 pt-2">
                            {/* Received Docs */}
                            <div className="bg-green-50/50 dark:bg-green-900/10 p-3 rounded-md border border-green-200/50 dark:border-green-800/20">
                                <h4 className="text-xs uppercase font-semibold text-green-700 dark:text-green-400 mb-2 flex items-center gap-2">
                                    <CheckCircle2 className="h-3 w-3" />
                                    Documenti Rilevati ({analysis.received_docs.length})
                                </h4>
                                <ul className="space-y-1.5">
                                    {analysis.received_docs.map((doc, idx) => (
                                        <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                                            <span className="text-green-500 mt-1.5 h-1.5 w-1.5 rounded-full bg-green-500 shrink-0" />
                                            {doc}
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            {/* Missing Docs */}
                            <div className="bg-red-50/50 dark:bg-red-900/10 p-3 rounded-md border border-red-200/50 dark:border-red-800/20">
                                <h4 className="text-xs uppercase font-semibold text-red-700 dark:text-red-400 mb-2 flex items-center gap-2">
                                    <AlertCircle className="h-3 w-3" />
                                    Documenti Mancanti
                                </h4>
                                {analysis.missing_docs.length > 0 ? (
                                    <ul className="space-y-1.5">
                                        {analysis.missing_docs.map((doc, idx) => (
                                            <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                                                <span className="text-red-500 mt-1.5 h-1.5 w-1.5 rounded-full bg-red-500 shrink-0" />
                                                {doc}
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <p className="text-sm text-green-600 dark:text-green-400 italic flex items-center gap-2">
                                        <CheckCircle2 className="h-4 w-4" />
                                        Nessun documento critico mancante.
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* Empty State */}
                {!hasAnalysis && !isLoading && !isBlocked && (
                    <div className="text-center py-6 text-muted-foreground">
                        <FileSearch className="h-10 w-10 mx-auto mb-3 opacity-50" />
                        <p>Nessuna analisi disponibile</p>
                        <p className="text-sm">Clicca per analizzare i documenti caricati.</p>
                    </div>
                )}

                {/* Generate/Refresh Button */}
                <div className="pt-2">
                    <Button
                        variant={isStale ? "default" : hasAnalysis ? "outline" : "default"}
                        className="w-full"
                        disabled={!canAnalyze || isGenerating || isLoading || isBlocked}
                        onClick={() => onGenerate(isStale)}
                    >
                        {isGenerating ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Analisi in corso...
                            </>
                        ) : isStale ? (
                            <>
                                <RefreshCw className="h-4 w-4 mr-2" />
                                Aggiorna Analisi
                            </>
                        ) : hasAnalysis ? (
                            <>
                                <RefreshCw className="h-4 w-4 mr-2" />
                                Rigenera
                            </>
                        ) : (
                            <>
                                <FileSearch className="h-4 w-4 mr-2" />
                                Avvia Analisi
                            </>
                        )}
                    </Button>
                </div>
            </CardContent>
        </Card >
    );
}
