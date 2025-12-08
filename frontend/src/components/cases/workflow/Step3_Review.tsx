"use client";

import { CaseDetail, ReportVersion } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { VersionItem, TemplateType } from "@/components/cases/VersionItem";
import { Eye, Download, ArrowRight, Edit, Info } from "lucide-react";
import { motion } from "framer-motion";

interface Step3ReviewProps {
    caseData: CaseDetail;
    onDownload: (version: ReportVersion, template: TemplateType) => Promise<void>;
    onProceedToClosure: () => void;
    onGoBackToIngestion: () => void;
}

/**
 * Step 3: Review (Revisione)
 * 
 * Shows the latest non-final draft for download.
 * No regeneration button (per user decision).
 * Includes "Modifica Documenti" link to go back to Step 1.
 */
export function Step3_Review({
    caseData,
    onDownload,
    onProceedToClosure,
    onGoBackToIngestion,
}: Step3ReviewProps) {
    const versions = caseData?.report_versions || [];

    // Get the latest non-final version (the draft to review)
    const latestDraft = versions
        .filter(v => !v.is_final)
        .sort((a, b) => b.version_number - a.version_number)[0];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h2 className="text-xl font-semibold flex items-center gap-2">
                    <Eye className="h-5 w-5" />
                    Revisione Bozza
                </h2>
                <p className="text-muted-foreground text-sm mt-1">
                    Scarica e rivedi la bozza generata dall&apos;IA.
                </p>
            </div>

            {/* No Editor Notice */}
            <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                    La modifica avviene offline. Scarica la bozza, effettua le correzioni
                    nel tuo editor, poi carica la versione finale nello step successivo.
                </AlertDescription>
            </Alert>

            {/* Latest Draft Card */}
            {latestDraft ? (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">
                            Bozza v{latestDraft.version_number}
                        </CardTitle>
                        <CardDescription>
                            Generata il {new Date(latestDraft.created_at).toLocaleDateString('it-IT', {
                                day: '2-digit',
                                month: 'long',
                                year: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit'
                            })}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Download Buttons */}
                        <div className="flex flex-col sm:flex-row gap-3">
                            <Button
                                size="lg"
                                className="flex-1"
                                onClick={() => onDownload(latestDraft, 'bn')}
                            >
                                <Download className="h-4 w-4 mr-2" />
                                Scarica Bozza (BN)
                            </Button>
                            <Button
                                size="lg"
                                variant="outline"
                                className="flex-1"
                                onClick={() => onDownload(latestDraft, 'salomone')}
                            >
                                <Download className="h-4 w-4 mr-2" />
                                Scarica Bozza (Salomone)
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center text-muted-foreground">
                        <p>Nessuna bozza disponibile</p>
                    </CardContent>
                </Card>
            )}

            {/* Actions */}
            <div className="flex flex-col sm:flex-row justify-between gap-4 pt-4">
                {/* Go Back */}
                <Button
                    variant="ghost"
                    onClick={onGoBackToIngestion}
                    className="text-muted-foreground"
                >
                    <Edit className="h-4 w-4 mr-2" />
                    Modifica Documenti
                </Button>

                {/* Proceed to Closure */}
                <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                    <Button
                        size="lg"
                        onClick={onProceedToClosure}
                        disabled={!latestDraft}
                    >
                        Procedi alla Chiusura
                        <ArrowRight className="h-4 w-4 ml-2" />
                    </Button>
                </motion.div>
            </div>

            {/* Previous Versions (collapsed) */}
            {versions.filter(v => !v.is_final).length > 1 && (
                <details className="text-sm">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                        Mostra versioni precedenti ({versions.filter(v => !v.is_final).length - 1})
                    </summary>
                    <div className="mt-3 space-y-2 pl-4 border-l-2 border-muted">
                        {versions
                            .filter(v => !v.is_final && v.id !== latestDraft?.id)
                            .sort((a, b) => b.version_number - a.version_number)
                            .map(v => (
                                <VersionItem
                                    key={v.id}
                                    version={v}
                                    onDownload={onDownload}
                                />
                            ))}
                    </div>
                </details>
            )}
        </div>
    );
}
