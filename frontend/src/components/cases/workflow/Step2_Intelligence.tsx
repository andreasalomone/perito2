"use client";

import { CaseDetail, Document } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Sparkles, FileText, CheckCircle, Loader2, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface Step2IntelligenceProps {
    caseData: CaseDetail;
}

/**
 * Step 2: Intelligence (Elaborazione)
 * 
 * Shows real document-level progress during AI processing.
 * Uses actual document.ai_status data, NOT simulated progress.
 */
export function Step2_Intelligence({ caseData }: Step2IntelligenceProps) {
    const documents = caseData?.documents || [];

    // Count by status
    const successCount = documents.filter(d => d.ai_status === 'SUCCESS').length;
    const processingCount = documents.filter(d => ['PENDING', 'PROCESSING'].includes(d.ai_status)).length;
    const errorCount = documents.filter(d => d.ai_status === 'ERROR').length;
    const totalCount = documents.length;

    // Calculate progress percentage
    const progressPercent = totalCount > 0 ? Math.round((successCount / totalCount) * 100) : 0;

    // Determine overall phase
    const isGenerating = caseData.status === 'GENERATING';
    const phase = isGenerating
        ? 'Generazione report in corso...'
        : processingCount > 0
            ? 'Elaborazione documenti...'
            : 'Preparazione...';

    return (
        <div className="space-y-6">
            {/* Header with pulsing icon */}
            <div className="flex items-center gap-3">
                <motion.div
                    animate={{ scale: [1, 1.1, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="p-2 bg-primary/10 rounded-full"
                >
                    <Sparkles className="h-6 w-6 text-primary" />
                </motion.div>
                <div>
                    <h2 className="text-xl font-semibold">{phase}</h2>
                    <p className="text-muted-foreground text-sm">
                        L&apos;IA sta analizzando i tuoi documenti
                    </p>
                </div>
            </div>

            {/* Progress Bar */}
            <Card>
                <CardContent className="pt-6">
                    <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                            <span>Progresso elaborazione</span>
                            <span className="font-medium">{progressPercent}%</span>
                        </div>
                        <div className="h-3 bg-muted rounded-full overflow-hidden">
                            <motion.div
                                className="h-full bg-primary"
                                initial={{ width: 0 }}
                                animate={{ width: `${progressPercent}%` }}
                                transition={{ duration: 0.5 }}
                            />
                        </div>
                        <p className="text-xs text-muted-foreground">
                            {successCount} di {totalCount} documenti elaborati
                        </p>
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
                    <div className="space-y-2">
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

            {/* Info message */}
            <div className="text-center text-sm text-muted-foreground py-4">
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
