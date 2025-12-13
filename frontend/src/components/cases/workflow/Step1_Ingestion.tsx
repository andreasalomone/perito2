"use client";

import { useState } from "react";
import { CaseDetail, DocumentAnalysis, PreliminaryReport } from "@/types";
import { CaseFileUploader } from "@/components/cases/CaseFileUploader";
import { DocumentItem } from "@/components/cases/DocumentItem";
import { DocumentAnalysisCard } from "@/components/cases/DocumentAnalysisCard";
import { PreliminaryReportCard } from "@/components/cases/PreliminaryReportCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Upload, UploadCloud, Play, FileText, AlertCircle, Loader2, Globe, MessageSquare } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// Language options for report generation
export type ReportLanguage = "italian" | "english" | "spanish";

const LANGUAGE_OPTIONS: { value: ReportLanguage; label: string }[] = [
    { value: "italian", label: "Italiano" },
    { value: "english", label: "English" },
    { value: "spanish", label: "Español" },
];

interface Step1IngestionProps {
    caseData: CaseDetail;
    caseId: string;
    onUploadComplete: () => void;
    onGenerate: (language: ReportLanguage, extraInstructions?: string) => Promise<void>;
    onDeleteDocument: (docId: string) => Promise<void>;
    isGenerating: boolean;
    isProcessingDocs: boolean;
    // Early Analysis props (optional for backward compatibility)
    documentAnalysis?: {
        analysis: DocumentAnalysis | null;
        isStale: boolean;
        canAnalyze: boolean;
        pendingDocs: number;
        isLoading: boolean;
        isGenerating: boolean;
        onGenerate: (force?: boolean) => void;
    };
    preliminaryReport?: {
        report: PreliminaryReport | null;
        canGenerate: boolean;
        pendingDocs: number;
        isLoading: boolean;
        isGenerating: boolean;
        onGenerate: (force?: boolean) => void;
    };
}

/**
 * Step 1: Ingestion (Acquisizione)
 *
 * Users upload documents for the case.
 * Shows existing documents with their processing status.
 * Enables generation when at least one document is ready.
 */
export function Step1_Ingestion({
    caseData,
    caseId,
    onUploadComplete,
    onGenerate,
    onDeleteDocument,
    isGenerating,
    isProcessingDocs,
    documentAnalysis,
    preliminaryReport,
}: Step1IngestionProps) {
    const documents = caseData?.documents || [];
    const [selectedLanguage, setSelectedLanguage] = useState<ReportLanguage>("italian");
    const [extraInstructions, setExtraInstructions] = useState<string>("");
    const MAX_INSTRUCTIONS_LENGTH = 2000;

    // Count documents by status
    const successDocs = documents.filter(d => d.ai_status === 'SUCCESS');
    const pendingDocs = documents.filter(d => ['PENDING', 'PROCESSING'].includes(d.ai_status));
    const errorDocs = documents.filter(d => d.ai_status === 'ERROR');

    // Can generate if we have at least one successfully processed document
    const canGenerate = successDocs.length > 0 && !isGenerating && !isProcessingDocs;

    // Show warning if some docs failed
    const hasErrors = errorDocs.length > 0;

    return (
        <div className="space-y-6">
            {/* Unified Ingestion Card */}
            <Card className="border-2 border-dashed bg-muted/5">
                <CardHeader className="pb-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-xl flex items-center gap-2">
                                <Upload className="h-5 w-5 text-primary" />
                                Gestione Documenti
                            </CardTitle>
                            <CardDescription className="mt-1">
                                {documents.length > 0
                                    ? `${documents.length} documenti caricati. Carica altri file se necessario.`
                                    : "Carica i documenti del caso per iniziare l'analisi."}
                            </CardDescription>
                        </div>
                        {documents.length > 0 && (
                            <CaseFileUploader
                                caseId={caseId}
                                onUploadComplete={onUploadComplete}
                            />
                        )}
                    </div>
                </CardHeader>
                <CardContent>
                    {documents.length === 0 ? (
                        <CaseFileUploader
                            caseId={caseId}
                            onUploadComplete={onUploadComplete}
                            trigger={
                                <div className="flex flex-col items-center justify-center py-12 px-4 rounded-lg border-2 border-dashed border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50 cursor-pointer transition-all">
                                    <div className="p-4 rounded-full bg-background shadow-sm mb-4">
                                        <UploadCloud className="h-8 w-8 text-primary" />
                                    </div>
                                    <h3 className="font-semibold text-lg mb-1">Carica file del caso</h3>
                                    <p className="text-sm text-muted-foreground text-center max-w-sm mb-4">
                                        Supporta PDF, DOCX, Immagini, EML.
                                    </p>
                                    <Button variant="default">Seleziona File</Button>
                                </div>
                            }
                        />
                    ) : (
                        <div className="space-y-4">
                            <AnimatePresence mode="popLayout">
                                <div className="grid gap-2">
                                    {documents.map((doc) => (
                                        <motion.div
                                            key={doc.id}
                                            layout
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            exit={{ opacity: 0, x: -10 }}
                                            transition={{ duration: 0.2 }}
                                        >
                                            <DocumentItem
                                                doc={doc}
                                                onDelete={() => onDeleteDocument(doc.id)}
                                            />
                                        </motion.div>
                                    ))}
                                </div>
                            </AnimatePresence>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Early Analysis Section */}
            {(documentAnalysis || preliminaryReport) && (
                <div className="grid md:grid-cols-2 gap-4">
                    {documentAnalysis && (
                        <DocumentAnalysisCard
                            analysis={documentAnalysis.analysis}
                            isStale={documentAnalysis.isStale}
                            canAnalyze={documentAnalysis.canAnalyze}
                            pendingDocs={documentAnalysis.pendingDocs}
                            isLoading={documentAnalysis.isLoading}
                            isGenerating={documentAnalysis.isGenerating}
                            onGenerate={documentAnalysis.onGenerate}
                        />
                    )}
                    {preliminaryReport && (
                        <PreliminaryReportCard
                            report={preliminaryReport.report}
                            canGenerate={preliminaryReport.canGenerate}
                            pendingDocs={preliminaryReport.pendingDocs}
                            isLoading={preliminaryReport.isLoading}
                            isGenerating={preliminaryReport.isGenerating}
                            onGenerate={preliminaryReport.onGenerate}
                        />
                    )}
                </div>
            )}

            {/* Error Warning */}
            {hasErrors && (
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                        {errorDocs.length} documento/i non elaborato/i correttamente.
                        Puoi eliminarli e ricaricarli, oppure procedere senza.
                    </AlertDescription>
                </Alert>
            )}

            {/* Processing Notice */}
            {isProcessingDocs && (
                <Alert>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <AlertDescription>
                        Elaborazione documenti in corso... ({pendingDocs.length} rimanenti)
                    </AlertDescription>
                </Alert>
            )}

            {/* Language Selection & Generate Button */}
            <div className="flex flex-col gap-4 pt-4">
                {/* Extra Instructions */}
                <div className="space-y-2">
                    <Label htmlFor="extra-instructions" className="flex items-center gap-2 text-sm font-medium">
                        <MessageSquare className="h-4 w-4" />
                        Istruzioni Aggiuntive (opzionale)
                    </Label>
                    <Textarea
                        id="extra-instructions"
                        placeholder="Es: Concentrati sui danni causati dall'acqua. Ignora i dettagli sulla responsabilità."
                        value={extraInstructions}
                        onChange={(e) => setExtraInstructions(e.target.value.slice(0, MAX_INSTRUCTIONS_LENGTH))}
                        disabled={isGenerating || isProcessingDocs}
                        className="min-h-[80px] resize-none"
                    />
                    <p className="text-xs text-muted-foreground text-right">
                        {extraInstructions.length}/{MAX_INSTRUCTIONS_LENGTH}
                    </p>
                </div>

                {/* Language and Generate */}
                <div className="flex flex-col sm:flex-row justify-end items-stretch sm:items-center gap-3">
                    {/* Language Dropdown */}
                    <div className="flex items-center gap-2">
                        <Globe className="h-4 w-4 text-muted-foreground" />
                        <Select
                            value={selectedLanguage}
                            onValueChange={(value) => setSelectedLanguage(value as ReportLanguage)}
                            disabled={isGenerating || isProcessingDocs}
                        >
                            <SelectTrigger className="w-[140px]">
                                <SelectValue placeholder="Lingua" />
                            </SelectTrigger>
                            <SelectContent>
                                {LANGUAGE_OPTIONS.map((lang) => (
                                    <SelectItem key={lang.value} value={lang.value}>
                                        {lang.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Generate Button */}
                    <Button
                        size="lg"
                        disabled={!canGenerate}
                        onClick={() => onGenerate(selectedLanguage, extraInstructions || undefined)}
                        className="min-w-[200px]"
                    >
                        {isGenerating ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Generazione in corso...
                            </>
                        ) : isProcessingDocs ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Elaborazione documenti...
                            </>
                        ) : (
                            <>
                                <Play className="h-4 w-4 mr-2" />
                                Genera Report
                            </>
                        )}
                    </Button>
                </div>
            </div>


        </div>
    );
}
