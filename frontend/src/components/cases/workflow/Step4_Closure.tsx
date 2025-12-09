"use client";

import { useRef, useState } from "react";
import { CaseDetail } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle, Upload, Loader2, FileCheck, PartyPopper } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import confetti from 'canvas-confetti';

interface Step4ClosureProps {
    caseData: CaseDetail;
    onFinalize: (file: File) => Promise<void>;
    isLoading?: boolean;
}

/**
 * Step 4: Closure (Chiusura)
 * 
 * Upload the final signed document to close the case.
 * Shows confetti on success before redirecting to summary.
 */
export function Step4_Closure({
    caseData,
    onFinalize,
    isLoading = false,
}: Step4ClosureProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);

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

            // Trigger confetti
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { y: 0.6 }
            });

            setIsSuccess(true);

            // The redirect will happen in the parent component after status changes
        } catch (error) {
            console.error('Finalization failed:', error);
            setIsUploading(false);
        }
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
                    Chiusura Caso
                </h2>
                <p className="text-muted-foreground text-sm mt-1">
                    Carica la versione finale firmata per completare la pratica.
                </p>
            </div>

            {/* Instructions */}
            <Alert>
                <FileCheck className="h-4 w-4" />
                <AlertDescription>
                    Carica il documento finale dopo aver effettuato le revisioni e ottenuto le firme necessarie.
                </AlertDescription>
            </Alert>

            {/* Upload Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Documento Finale</CardTitle>
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
                        disabled={!selectedFile || isUploading || isLoading}
                        onClick={handleUpload}
                    >
                        {isUploading || isLoading ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Caricamento in corso...
                            </>
                        ) : (
                            <>
                                <Upload className="h-4 w-4 mr-2" />
                                Finalizza Caso
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
