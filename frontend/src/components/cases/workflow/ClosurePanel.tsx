"use client";

import { useRef, useState } from "react";
import { CaseDetail } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle, Upload, Loader2, FileCheck, PartyPopper, RefreshCw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import confetti from 'canvas-confetti';

interface ClosurePanelProps {
    caseData: CaseDetail;
    onFinalize: (file: File) => Promise<void>;
    onConfirmDocs: (versionId: string) => Promise<void>;
    isLoading?: boolean;
}

/**
 * ClosurePanel - Case finalization
 *
 * Two paths to finalize:
 * 1. Upload local DOCX file
 * 2. Confirm Google Docs edits (if active draft exists)
 *
 * Shows confetti on success before redirecting to summary.
 */
export function ClosurePanel({
    caseData,
    onFinalize,
    onConfirmDocs,
    isLoading = false,
}: ClosurePanelProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [isConfirming, setIsConfirming] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);

    // Find active draft
    const activeDraft = caseData?.report_versions?.find(v => v.is_draft_active && !v.is_final);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files?.length) {
            setSelectedFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) return;

        setIsUploading(true);
        try {
            await onFinalize(selectedFile);
            triggerSuccess();
        } catch (error) {
            console.error('Finalization failed:', error);
            setIsUploading(false);
        }
    };

    const handleConfirmDocs = async () => {
        if (!activeDraft) return;

        setIsConfirming(true);
        try {
            await onConfirmDocs(activeDraft.id);
            triggerSuccess();
        } catch (error) {
            console.error('Confirm docs failed:', error);
            setIsConfirming(false);
        }
    };

    const triggerSuccess = () => {
        confetti({
            particleCount: 100,
            spread: 70,
            origin: { y: 0.6 }
        });
        setIsSuccess(true);
    };

    // Success state
    if (isSuccess) {
        return (
            <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex flex-col items-center justify-center py-12 space-y-6"
            >
                <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 0.5 }}
                    className="p-4 bg-green-100 dark:bg-green-900 rounded-full"
                >
                    <PartyPopper className="h-12 w-12 text-green-600" />
                </motion.div>
                <div className="text-center">
                    <h2 className="text-2xl font-bold text-green-700 dark:text-green-400">
                        Caso Completato!
                    </h2>
                    <p className="text-muted-foreground mt-2">
                        Reindirizzamento al riepilogo...
                    </p>
                </div>
            </motion.div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h2 className="text-xl font-semibold flex items-center gap-2">
                    <CheckCircle className="h-5 w-5" />
                    Chiusura Sinistro
                </h2>
                <p className="text-muted-foreground text-sm mt-1">
                    Carica la versione finale o conferma le modifiche da Google Docs.
                </p>
            </div>

            {/* Active Docs Draft - Confirm Button */}
            {activeDraft && (
                <Card className="border-primary bg-primary/5">
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">
                            <RefreshCw className="h-4 w-4" />
                            Sessione Google Docs Attiva
                        </CardTitle>
                        <CardDescription>
                            Hai modificato la bozza v{activeDraft.version_number} in Google Docs.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button
                            size="lg"
                            className="w-full"
                            onClick={handleConfirmDocs}
                            disabled={isConfirming || isLoading}
                        >
                            {isConfirming ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Sincronizzazione...
                                </>
                            ) : (
                                <>
                                    <RefreshCw className="h-4 w-4 mr-2" />
                                    Conferma Versione Finale
                                </>
                            )}
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* Divider if both options available */}
            {activeDraft && (
                <div className="flex items-center gap-4">
                    <div className="flex-1 h-px bg-border" />
                    <span className="text-sm text-muted-foreground">oppure</span>
                    <div className="flex-1 h-px bg-border" />
                </div>
            )}

            {/* Upload Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Carica Report</CardTitle>
                    <CardDescription>
                        Formati accettati: DOCX, PDF
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Hidden file input */}
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        className="hidden"
                    />

                    {/* Upload zone */}
                    <div
                        onClick={() => fileInputRef.current?.click()}
                        className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
                       hover:border-primary hover:bg-primary/5 transition-colors"
                    >
                        <AnimatePresence mode="wait">
                            {selectedFile ? (
                                <motion.div
                                    key="file"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="flex items-center justify-center gap-3"
                                >
                                    <FileCheck className="h-8 w-8 text-green-600" />
                                    <div className="text-left">
                                        <p className="font-medium">{selectedFile.name}</p>
                                        <p className="text-sm text-muted-foreground">
                                            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                                        </p>
                                    </div>
                                </motion.div>
                            ) : (
                                <motion.div
                                    key="empty"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                >
                                    <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-2" />
                                    <p className="text-muted-foreground">
                                        Clicca per selezionare o trascina qui il file
                                    </p>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Upload Button */}
                    <Button
                        size="lg"
                        className="w-full"
                        variant={activeDraft ? "outline" : "default"}
                        disabled={!selectedFile || isUploading || isLoading || isConfirming}
                        onClick={handleUpload}
                    >
                        {isUploading ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Caricamento...
                            </>
                        ) : (
                            <>
                                <Upload className="h-4 w-4 mr-2" />
                                Carica e Finalizza
                            </>
                        )}
                    </Button>
                </CardContent>
            </Card>

            {/* Case Summary Preview */}
            <Card className="bg-muted/30">
                <CardHeader className="pb-3">
                    <CardTitle className="text-sm text-muted-foreground">
                        Riepilogo
                    </CardTitle>
                </CardHeader>
                <CardContent className="text-sm space-y-1">
                    <p><strong>Caso:</strong> {caseData.reference_code}</p>
                    {caseData.client_name && (
                        <p><strong>Cliente:</strong> {caseData.client_name}</p>
                    )}
                    <p><strong>Documenti:</strong> {caseData.documents?.length || 0}</p>
                    <p><strong>Versioni bozza:</strong> {caseData.report_versions?.filter(v => !v.is_final).length || 0}</p>
                </CardContent>
            </Card>
        </div>
    );
}
