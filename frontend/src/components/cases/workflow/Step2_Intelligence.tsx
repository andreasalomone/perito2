"use client";

import { useState, useEffect } from "react";
import { CaseDetail, Document } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
    Sparkles,
    FileText,
    CheckCircle,
    Loader2,
    AlertCircle,
    FileSearch,
    Brain,
    FileOutput,
    Lightbulb,
    Clock,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface Step2IntelligenceProps {
    caseData: CaseDetail;
}

// AI Processing phases
const AI_PHASES = [
    {
        id: 1,
        title: "Lettura documenti",
        description: "Estrazione testo e immagini",
        icon: FileSearch,
    },
    {
        id: 2,
        title: "Analisi contenuti",
        description: "Identificazione danni e informazioni",
        icon: Brain,
    },
    {
        id: 3,
        title: "Generazione report",
        description: "Strutturazione della perizia",
        icon: FileOutput,
    },
];

// Rotating tips
const TIPS = [
    "L'IA analizza le foto per identificare automaticamente il tipo di danno",
    "La perizia includerà una descrizione dettagliata di ogni documento caricato",
    "Il report sarà formattato secondo lo standard professionale delle perizie",
    "Stima automatica basata sull'analisi dei danni visibili nelle immagini",
    "I documenti vengono elaborati in parallelo per velocizzare il processo",
];

/**
 * Step 2: Intelligence (Elaborazione)
 * 
 * Enhanced UI showing AI processing progress with:
 * - AI phases stepper
 * - Rotating helpful tips
 * - Animated visuals
 * - Document status list
 */
export function Step2_Intelligence({ caseData }: Step2IntelligenceProps) {
    const documents = caseData?.documents || [];
    const [currentTipIndex, setCurrentTipIndex] = useState(0);

    // Rotate tips every 5 seconds
    useEffect(() => {
        const interval = setInterval(() => {
            setCurrentTipIndex((prev) => (prev + 1) % TIPS.length);
        }, 5000);
        return () => clearInterval(interval);
    }, []);

    // Count by status
    const successCount = documents.filter(d => d.ai_status === 'SUCCESS').length;
    const processingCount = documents.filter(d => ['PENDING', 'PROCESSING'].includes(d.ai_status)).length;
    const errorCount = documents.filter(d => d.ai_status === 'ERROR').length;
    const totalCount = documents.length;

    // Calculate progress percentage
    const progressPercent = totalCount > 0 ? Math.round((successCount / totalCount) * 100) : 0;

    // Determine current AI phase based on progress
    const isGenerating = caseData.status === 'GENERATING';
    const currentPhase = isGenerating ? 3 : (progressPercent >= 100 ? 3 : progressPercent > 0 ? 2 : 1);

    // Estimate remaining time (rough approximation: ~30 seconds per document)
    const estimatedMinutes = Math.max(1, Math.ceil((totalCount - successCount) * 0.5));

    // Phase title for header
    const phaseTitle = isGenerating
        ? 'Generazione report in corso...'
        : processingCount > 0
            ? 'Elaborazione documenti...'
            : 'Preparazione...';

    return (
        <div className="space-y-6">
            {/* Header with animated icon */}
            <div className="flex items-center gap-4">
                <motion.div
                    animate={{
                        scale: [1, 1.05, 1],
                        rotate: [0, 5, -5, 0],
                    }}
                    transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                    className="p-3 bg-gradient-to-br from-primary/20 to-primary/5 rounded-2xl shadow-lg shadow-primary/10"
                >
                    <Sparkles className="h-7 w-7 text-primary" />
                </motion.div>
                <div>
                    <h2 className="text-xl font-semibold">{phaseTitle}</h2>
                    <p className="text-muted-foreground text-sm">
                        L&apos;IA sta analizzando i tuoi documenti
                    </p>
                </div>
            </div>

            {/* Progress Card */}
            <Card className="overflow-hidden">
                <CardContent className="pt-6">
                    <div className="space-y-3">
                        <div className="flex justify-between text-sm">
                            <span className="font-medium">Progresso elaborazione</span>
                            <span className="font-bold text-primary">{progressPercent}%</span>
                        </div>

                        {/* Gradient progress bar */}
                        <div className="h-3 bg-muted rounded-full overflow-hidden relative">
                            <motion.div
                                className="h-full bg-gradient-to-r from-green-500 via-emerald-500 to-primary rounded-full"
                                initial={{ width: 0 }}
                                animate={{ width: `${progressPercent}%` }}
                                transition={{ duration: 0.5, ease: "easeOut" }}
                            />
                            {/* Shimmer effect */}
                            {progressPercent < 100 && (
                                <motion.div
                                    className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
                                    animate={{ x: ["-100%", "200%"] }}
                                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                                />
                            )}
                        </div>

                        <div className="flex justify-between items-center text-xs text-muted-foreground">
                            <span>{successCount} di {totalCount} documenti elaborati</span>
                            {progressPercent < 100 && (
                                <span className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    ~{estimatedMinutes} min rimanenti
                                </span>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* AI Phases Stepper */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                        <Brain className="h-4 w-4" />
                        Fasi di Elaborazione
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-1">
                        {AI_PHASES.map((phase, index) => {
                            const isCompleted = phase.id < currentPhase;
                            const isActive = phase.id === currentPhase;
                            const isPending = phase.id > currentPhase;
                            const Icon = phase.icon;

                            return (
                                <div key={phase.id} className="flex items-start gap-3">
                                    {/* Vertical line connector */}
                                    <div className="flex flex-col items-center">
                                        <motion.div
                                            className={cn(
                                                "w-8 h-8 rounded-full flex items-center justify-center transition-colors",
                                                isCompleted && "bg-green-100 dark:bg-green-950/50",
                                                isActive && "bg-primary/20",
                                                isPending && "bg-muted"
                                            )}
                                            animate={isActive ? { scale: [1, 1.1, 1] } : {}}
                                            transition={{ duration: 1.5, repeat: Infinity }}
                                        >
                                            {isCompleted ? (
                                                <CheckCircle className="h-4 w-4 text-green-600" />
                                            ) : isActive ? (
                                                <motion.div
                                                    animate={{ rotate: 360 }}
                                                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                                                >
                                                    <Loader2 className="h-4 w-4 text-primary" />
                                                </motion.div>
                                            ) : (
                                                <Icon className="h-4 w-4 text-muted-foreground" />
                                            )}
                                        </motion.div>
                                        {index < AI_PHASES.length - 1 && (
                                            <div
                                                className={cn(
                                                    "w-0.5 h-6 transition-colors",
                                                    isCompleted ? "bg-green-400" : "bg-muted"
                                                )}
                                            />
                                        )}
                                    </div>

                                    {/* Phase content */}
                                    <div className="pt-1 pb-4">
                                        <p className={cn(
                                            "font-medium text-sm",
                                            isActive && "text-primary",
                                            isPending && "text-muted-foreground"
                                        )}>
                                            {phase.title}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {phase.description}
                                        </p>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </CardContent>
            </Card>

            {/* Document Status List */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                        <FileText className="h-4 w-4" />
                        Stato Documenti
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-2 max-h-[200px] overflow-y-auto">
                        {documents.map((doc) => (
                            <DocumentStatusRow key={doc.id} doc={doc} />
                        ))}
                    </div>
                </CardContent>
            </Card>

            {/* Error Alert */}
            {errorCount > 0 && (
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                        {errorCount} documento/i non elaborato/i.
                        La generazione continuerà con i documenti validi.
                    </AlertDescription>
                </Alert>
            )}

            {/* Rotating Tips */}
            <Card className="bg-gradient-to-br from-amber-50/50 to-yellow-50/30 dark:from-amber-950/20 dark:to-yellow-950/10 border-amber-200/50 dark:border-amber-800/30">
                <CardContent className="py-4">
                    <div className="flex gap-3">
                        <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-lg h-fit">
                            <Lightbulb className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                        </div>
                        <div className="flex-1 min-h-[40px]">
                            <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">
                                Lo sapevi?
                            </p>
                            <AnimatePresence mode="wait">
                                <motion.p
                                    key={currentTipIndex}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: -10 }}
                                    transition={{ duration: 0.3 }}
                                    className="text-sm text-amber-900/80 dark:text-amber-100/80"
                                >
                                    {TIPS[currentTipIndex]}
                                </motion.p>
                            </AnimatePresence>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Footer message */}
            <div className="text-center text-sm text-muted-foreground py-2">
                <p>Non chiudere questa pagina. Riceverai una notifica al termine.</p>
            </div>
        </div>
    );
}

function DocumentStatusRow({ doc }: { doc: Document }) {
    const statusConfig = {
        SUCCESS: {
            icon: CheckCircle,
            color: "text-green-600",
            bgColor: "bg-green-50 dark:bg-green-950/30",
            label: "Completato",
            animate: false,
        },
        PROCESSING: {
            icon: Loader2,
            color: "text-blue-600",
            bgColor: "bg-blue-50 dark:bg-blue-950/30",
            label: "In elaborazione...",
            animate: true,
        },
        PENDING: {
            icon: Loader2,
            color: "text-gray-500",
            bgColor: "bg-gray-50 dark:bg-gray-900/30",
            label: "In coda",
            animate: true,
        },
        ERROR: {
            icon: AlertCircle,
            color: "text-red-600",
            bgColor: "bg-red-50 dark:bg-red-950/30",
            label: "Errore",
            animate: false,
        },
    };

    const config = statusConfig[doc.ai_status as keyof typeof statusConfig] || statusConfig.PENDING;
    const Icon = config.icon;

    return (
        <div className={cn(
            "flex items-center gap-3 p-2 rounded-lg",
            config.bgColor
        )}>
            <Icon className={cn(
                "h-4 w-4 flex-shrink-0",
                config.color,
                config.animate && "animate-spin"
            )} />
            <span className="flex-1 text-sm truncate">{doc.filename}</span>
            <span className={cn("text-xs", config.color)}>{config.label}</span>
        </div>
    );
}
