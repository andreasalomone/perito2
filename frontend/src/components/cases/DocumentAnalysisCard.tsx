"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { FileSearch, Loader2, RefreshCw, AlertCircle, Clock, CheckCircle2 } from "lucide-react";
import { DocumentAnalysis } from "@/types";
import { cn } from "@/lib/utils";
import { MarkdownContent } from "@/components/ui/markdown-content";
import { Steps, StepsContent, StepsItem, StepsTrigger } from "@/components/ui/steps";

import { useRef, useState, useEffect } from "react";
import { ScrollProgress } from "@/components/motion-primitives/scroll-progress";

import { ExpandableScreen, ExpandableScreenTrigger, ExpandableScreenContent } from "@/components/ui/expandable-screen";

interface DocumentAnalysisCardProps {
    analysis: DocumentAnalysis | null;
    isStale: boolean;
    canAnalyze: boolean;
    pendingDocs: number;
    isLoading: boolean;
    isGenerating: boolean;
    onGenerate: (force?: boolean) => void;
}

/** LLM thinking steps shown during analysis */
const ANALYSIS_STEPS = [
    { text: "Caricamento documenti...", delay: 0 },
    { text: "Analisi delle immagini...", delay: 2000 },
    { text: "Estrazione informazioni chiave...", delay: 4000 },
    { text: "Identificazione documenti mancanti...", delay: 6000 },
    { text: "Generazione summary...", delay: 8000 },
];

/** Progressive steps shown while LLM processes documents */
function AnalysisSteps() {
    const [visibleSteps, setVisibleSteps] = useState(1);

    useEffect(() => {
        const timers: NodeJS.Timeout[] = [];
        ANALYSIS_STEPS.forEach((step, index) => {
            if (index > 0) {
                const timer = setTimeout(() => {
                    setVisibleSteps(prev => Math.max(prev, index + 1));
                }, step.delay);
                timers.push(timer);
            }
        });
        return () => timers.forEach(clearTimeout);
    }, []);

    return (
        <div className="space-y-4">
            <Steps defaultOpen>
                <StepsTrigger leftIcon={<Loader2 className="h-4 w-4 animate-spin" />}>
                    Analisi in corso...
                </StepsTrigger>
                <StepsContent>
                    <div className="space-y-1">
                        {ANALYSIS_STEPS.slice(0, visibleSteps).map((step, idx) => (
                            <StepsItem
                                key={step.text}
                                className={cn(
                                    "transition-opacity duration-300",
                                    idx === visibleSteps - 1 ? "text-foreground" : "text-muted-foreground"
                                )}
                            >
                                {step.text}
                            </StepsItem>
                        ))}
                    </div>
                </StepsContent>
            </Steps>
        </div>
    );
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
}: Readonly<DocumentAnalysisCardProps>) {
    const hasAnalysis = analysis !== null;
    const isBlocked = pendingDocs > 0;
    const scrollRef = useRef<HTMLDivElement>(null);

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

                {/* Stale Warning - Only show if analysis won't be immediately visible */}
                {isStale && hasAnalysis && !isBlocked && (
                    <Alert variant="destructive" className="bg-amber-500/10 border-amber-500/50 text-amber-700 dark:text-amber-400">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                            I documenti sono stati modificati.
                        </AlertDescription>
                    </Alert>
                )}

                {/* Analysis Content & Actions */}
                {hasAnalysis ? (
                    <ExpandableScreen
                        layoutId="document-analysis-expand"
                        triggerRadius="8px"
                        contentRadius="12px"
                    >
                        <div className="space-y-4">
                            <div className="bg-muted/30 rounded-lg p-4 border border-dashed flex flex-col items-center justify-center text-center space-y-3">
                                <CheckCircle2 className="h-8 w-8 text-green-500" />
                                <div className="space-y-1">
                                    <h4 className="font-medium">Analisi Completata</h4>
                                    <p className="text-sm text-muted-foreground px-4">
                                        {analysis.received_docs.length} documenti rilevati, {analysis.missing_docs.length} mancanti.
                                    </p>
                                </div>
                                <ExpandableScreenTrigger className="w-full">
                                    <Button variant="outline" className="w-full border-blue-200 hover:bg-blue-50 hover:text-blue-700 dark:border-blue-900 dark:hover:bg-blue-950/50 dark:hover:text-blue-400 transition-colors group">
                                        <FileSearch className="h-4 w-4 mr-2 group-hover:scale-110 transition-transform" />
                                        Vedi Analisi
                                    </Button>
                                </ExpandableScreenTrigger>
                            </div>
                        </div>

                        <ExpandableScreenContent className="p-0">
                            <div className="flex flex-col h-full max-w-4xl mx-auto w-full">
                                {/* Header */}
                                <div className="flex items-center justify-between p-6 border-b shrink-0 bg-background/95 backdrop-blur z-10 relative">
                                    <div className="space-y-1">
                                        <h2 className="text-2xl font-bold flex items-center gap-2">
                                            <FileSearch className="h-6 w-6 text-blue-600" />
                                            Analisi Documenti
                                        </h2>
                                        <p className="text-muted-foreground">
                                            Dettaglio dell'estrazione informazioni e verifica completezza.
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2 mr-12"> {/* mr-12 to avoid close button */}
                                        <Button
                                            variant={isStale ? "default" : "outline"}
                                            size="sm"
                                            disabled={!canAnalyze || isGenerating || isLoading}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onGenerate(true); // Always force refresh here
                                            }}
                                        >
                                            {isGenerating ? (
                                                <>
                                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                    Analisi in corso...
                                                </>
                                            ) : (
                                                <>
                                                    <RefreshCw className="h-4 w-4 mr-2" />
                                                    {isStale ? "Aggiorna Ora" : "Rigenera Analisi"}
                                                </>
                                            )}
                                        </Button>
                                    </div>
                                    <ScrollProgress containerRef={scrollRef} className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-cyan-500 z-50" />
                                </div>

                                {/* Scrollable Content */}
                                <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8 relative">
                                    {/* Summary with Markdown */}
                                    <div className="prose prose-blue dark:prose-invert max-w-none">
                                        <MarkdownContent content={analysis.summary} variant="default" />
                                    </div>

                                    {/* Analysis Breakdown Grid */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        {/* Received Docs */}
                                        <div className="bg-green-50/50 dark:bg-green-900/10 p-5 rounded-xl border border-green-200/50 dark:border-green-800/20">
                                            <h4 className="text-sm uppercase tracking-wide font-bold text-green-700 dark:text-green-400 mb-4 flex items-center gap-2">
                                                <CheckCircle2 className="h-4 w-4" />
                                                Documenti Rilevati ({analysis.received_docs.length})
                                            </h4>
                                            <ul className="space-y-2">
                                                {analysis.received_docs.map((doc, idx) => (
                                                    <li key={idx} className="text-sm text-foreground/80 flex items-start gap-3 bg-background/50 p-2 rounded-md border border-green-100 dark:border-green-900/30">
                                                        <span className="text-green-500 mt-1 h-2 w-2 rounded-full bg-green-500 shrink-0" />
                                                        {doc}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>

                                        {/* Missing Docs */}
                                        <div className="bg-red-50/50 dark:bg-red-900/10 p-5 rounded-xl border border-red-200/50 dark:border-red-800/20">
                                            <h4 className="text-sm uppercase tracking-wide font-bold text-red-700 dark:text-red-400 mb-4 flex items-center gap-2">
                                                <AlertCircle className="h-4 w-4" />
                                                Documenti Mancanti
                                            </h4>
                                            {analysis.missing_docs.length > 0 ? (
                                                <ul className="space-y-2">
                                                    {analysis.missing_docs.map((doc, idx) => (
                                                        <li key={idx} className="text-sm text-foreground/80 flex items-start gap-3 bg-background/50 p-2 rounded-md border border-red-100 dark:border-red-900/30">
                                                            <span className="text-red-500 mt-1 h-2 w-2 rounded-full bg-red-500 shrink-0" />
                                                            {doc}
                                                        </li>
                                                    ))}
                                                </ul>
                                            ) : (
                                                <div className="h-full flex flex-col items-center justify-center p-4 text-center text-green-600 dark:text-green-400">
                                                    <CheckCircle2 className="h-8 w-8 mb-2 opacity-50" />
                                                    <p className="font-medium">Tutto completo</p>
                                                    <p className="text-xs opacity-75">Nessun documento critico mancante.</p>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </ExpandableScreenContent>
                    </ExpandableScreen>
                ) : (
                    /* Empty State or Generating State */
                    !isLoading && !isBlocked && (
                        <div className="space-y-4">
                            {isGenerating ? (
                                <AnalysisSteps />
                            ) : (
                                <>
                                    <div className="text-center py-6 text-muted-foreground">
                                        <FileSearch className="h-10 w-10 mx-auto mb-3 opacity-50" />
                                        <p>Nessuna analisi disponibile</p>
                                        <p className="text-sm">Clicca per analizzare i documenti caricati.</p>
                                    </div>
                                    <Button
                                        variant="default"
                                        className="w-full"
                                        disabled={!canAnalyze || isGenerating || isLoading}
                                        onClick={() => onGenerate(false)}
                                    >
                                        <FileSearch className="h-4 w-4 mr-2" />
                                        Avvia Analisi
                                    </Button>
                                </>
                            )}
                        </div>
                    )
                )}
            </CardContent>
        </Card>
    );
}
