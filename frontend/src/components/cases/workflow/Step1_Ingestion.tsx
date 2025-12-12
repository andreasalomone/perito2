"use client";

import { useState } from "react";
import { CaseDetail } from "@/types";
import { CaseFileUploader } from "@/components/cases/CaseFileUploader";
import { DocumentItem } from "@/components/cases/DocumentItem";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Upload, Play, FileText, AlertCircle, Loader2, Globe } from "lucide-react";
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
    onGenerate: (language: ReportLanguage) => Promise<void>;
    onDeleteDocument: (docId: string) => Promise<void>;
    isGenerating: boolean;
    isProcessingDocs: boolean;
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
}: Step1IngestionProps) {
    const documents = caseData?.documents || [];
    const [selectedLanguage, setSelectedLanguage] = useState<ReportLanguage>("italian");

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
            {/* Header */}
            <div>
                <h2 className="text-xl font-semibold flex items-center gap-2">
                    <Upload className="h-5 w-5" />
                    Carica Documenti
                </h2>
                <p className="text-muted-foreground text-sm mt-1">
                    Carica i documenti del caso per generare la perizia.
                </p>
            </div>

            {/* Upload Zone */}
            <Card>
                <CardContent className="pt-6">
                    <CaseFileUploader
                        caseId={caseId}
                        onUploadComplete={onUploadComplete}
                    />
                </CardContent>
            </Card>

            {/* Documents List */}
            {documents.length > 0 && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center justify-between">
                            <span className="flex items-center gap-2">
                                <FileText className="h-4 w-4" />
                                Documenti Caricati
                            </span>
                            <span className="text-sm font-normal text-muted-foreground">
                                {successDocs.length}/{documents.length} elaborati
                            </span>
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
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
                    </CardContent>
                </Card>
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
            <div className="flex flex-col sm:flex-row justify-end items-stretch sm:items-center gap-3 pt-4">
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
                    onClick={() => onGenerate(selectedLanguage)}
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

            {/* Empty State */}
            {documents.length === 0 && !isProcessingDocs && (
                <div className="text-center py-8 text-muted-foreground">
                    <Upload className="h-12 w-12 mx-auto mb-3 opacity-50" />
                    <p>Nessun documento caricato</p>
                    <p className="text-sm">Trascina file o clicca per caricare</p>
                </div>
            )}
        </div>
    );
}
