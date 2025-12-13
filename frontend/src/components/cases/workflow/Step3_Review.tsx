"use client";

import { useState } from "react";
import { CaseDetail, ReportVersion } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { VersionItem, TemplateType } from "@/components/cases/VersionItem";
import { Eye, Download, ArrowRight, Edit, ExternalLink, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface Step3ReviewProps {
    caseData: CaseDetail;
    onDownload: (version: ReportVersion, template: TemplateType) => Promise<void>;
    onOpenInDocs: (version: ReportVersion, template: TemplateType) => Promise<void>;
    onProceedToClosure: () => void;
    onGoBackToIngestion: () => void;
}

/**
 * Step 3: Review (Revisione)
 *
 * Shows the latest non-final draft with options to:
 * - Select template (BN/Salomone)
 * - Edit in Google Docs (main CTA)
 * - Download directly (secondary)
 * - Proceed to Step 4
 */
export function Step3_Review({
    caseData,
    onDownload,
    onOpenInDocs,
    onProceedToClosure,
    onGoBackToIngestion,
}: Step3ReviewProps) {
    const versions = caseData?.report_versions || [];
    const [selectedTemplate, setSelectedTemplate] = useState<TemplateType>("bn");
    const [isOpening, setIsOpening] = useState(false);

    // Get the latest non-final, non-preliminary version (the draft to review)
    const latestDraft = versions
        .filter(v => !v.is_final && v.source !== 'preliminary')
        .sort((a, b) => b.version_number - a.version_number)[0];

    const handleOpenInDocs = async () => {
        if (!latestDraft) return;
        setIsOpening(true);
        try {
            await onOpenInDocs(latestDraft, selectedTemplate);
        } finally {
            setIsOpening(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h2 className="text-xl font-semibold flex items-center gap-2">
                    <Eye className="h-5 w-5" />
                    Revisione Bozza
                </h2>
                <p className="text-muted-foreground text-sm mt-1">
                    Modifica la bozza in Google Docs o scaricala per modificarla localmente.
                </p>
            </div>

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
                        {/* Template Selector */}
                        <div className="space-y-3">
                            <label className="text-sm font-medium">Scegli Template</label>
                            <div className="flex gap-2">
                                <Button
                                    variant={selectedTemplate === "bn" ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => setSelectedTemplate("bn")}
                                    className={cn(
                                        "flex-1",
                                        selectedTemplate === "bn" && "ring-2 ring-primary ring-offset-2"
                                    )}
                                >
                                    BN
                                </Button>
                                <Button
                                    variant={selectedTemplate === "salomone" ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => setSelectedTemplate("salomone")}
                                    className={cn(
                                        "flex-1",
                                        selectedTemplate === "salomone" && "ring-2 ring-primary ring-offset-2"
                                    )}
                                >
                                    Salomone
                                </Button>
                            </div>
                        </div>

                        {/* Active Draft Notice */}
                        {latestDraft.is_draft_active && latestDraft.edit_link && (
                            <Alert className="bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800">
                                <ExternalLink className="h-4 w-4 text-blue-600" />
                                <AlertDescription className="text-blue-800 dark:text-blue-200">
                                    Hai una sessione di modifica attiva.{" "}
                                    <a
                                        href={latestDraft.edit_link}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="underline font-medium"
                                    >
                                        Riprendi la modifica →
                                    </a>
                                </AlertDescription>
                            </Alert>
                        )}

                        {/* Action Buttons */}
                        <div className="flex flex-col gap-3">
                            {/* Main CTA: Edit in Docs */}
                            <Button
                                size="lg"
                                className="w-full"
                                onClick={handleOpenInDocs}
                                disabled={isOpening}
                            >
                                {isOpening ? (
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                ) : (
                                    <ExternalLink className="h-4 w-4 mr-2" />
                                )}
                                {latestDraft.is_draft_active ? "Riprendi Modifica" : "Modifica"}
                            </Button>

                            {/* Secondary: Download */}
                            <Button
                                size="lg"
                                variant="outline"
                                className="w-full"
                                onClick={() => onDownload(latestDraft, selectedTemplate)}
                            >
                                <Download className="h-4 w-4 mr-2" />
                                Scarica
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

            {/* Proceed Link */}
            <div className="text-center pt-2">
                <button
                    onClick={onProceedToClosure}
                    className="text-sm text-muted-foreground hover:text-primary underline underline-offset-4"
                    disabled={!latestDraft}
                >
                    Quando sei pronto a chiudere il sinistro, clicca qui →
                </button>
            </div>

            {/* Actions Row */}
            <div className="flex justify-start pt-2">
                <Button
                    variant="ghost"
                    onClick={onGoBackToIngestion}
                    className="text-muted-foreground"
                >
                    <Edit className="h-4 w-4 mr-2" />
                    Modifica Documenti
                </Button>
            </div>

            {/* Previous Versions (collapsed) */}
            {versions.filter(v => !v.is_final && v.source !== 'preliminary').length > 1 && (
                <details className="text-sm">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                        Mostra versioni precedenti ({versions.filter(v => !v.is_final && v.source !== 'preliminary').length - 1})
                    </summary>
                    <div className="mt-3 space-y-2 pl-4 border-l-2 border-muted">
                        {versions
                            .filter(v => !v.is_final && v.source !== 'preliminary' && v.id !== latestDraft?.id)
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
