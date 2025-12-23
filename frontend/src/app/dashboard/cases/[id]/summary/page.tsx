"use client";

import { useCallback, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useConfig } from "@/context/ConfigContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, Download, AlertCircle, RefreshCw, ArrowLeft } from "lucide-react";
import axios from "axios";
import { handleApiError } from "@/lib/error";
import { TemplateType } from "@/components/cases/VersionItem";
import CaseDetailsPanel from "@/components/cases/CaseDetailsPanel";
import { SummaryCard } from "@/components/cases/SummaryCard";
import { useCaseDetail } from "@/hooks/useCaseDetail";

/**
 * Summary page for closed cases.
 * Shows:
 * - Success banner
 * - Final report download
 * - AI Summary
 * - CaseDetailsPanel (still editable)
 */
export default function CaseSummaryPage() {
    const { id } = useParams();
    const router = useRouter();
    const { getToken } = useAuth();
    const { apiUrl } = useConfig();
    const caseId = Array.isArray(id) ? id[0] : id;

    const {
        caseData,
        isLoading,
        isError,
        mutate,
    } = useCaseDetail(caseId);

    // If case is not closed/finalized, redirect back to workflow
    useEffect(() => {
        if (!caseData || isLoading) return;

        const isClosed = caseData.status === 'CLOSED';
        const hasFinalVersion = caseData.report_versions?.some(v => v.is_final);

        // If not closed and no final version, this case shouldn't be on summary page
        if (!isClosed && !hasFinalVersion) {
            router.replace(`/dashboard/cases/${caseId}`);
        }
    }, [caseData, isLoading, caseId, router]);

    // Find the final version
    const finalVersion = caseData?.report_versions?.find(v => v.is_final);

    const handleDownloadFinal = useCallback(async (template: TemplateType) => {
        if (!finalVersion) return;

        try {
            const token = await getToken();
            const res = await axios.post(
                `${apiUrl}/api/v1/cases/${caseId}/versions/${finalVersion.id}/download`,
                { template_type: template },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            window.open(res.data.download_url, "_blank", "noopener,noreferrer");
        } catch (e) {
            handleApiError(e, "Errore durante il download");
        }
    }, [caseId, finalVersion, getToken, apiUrl]);

    // --- Render States ---

    if (isLoading) {
        return (
            <div className="space-y-6 max-w-4xl mx-auto p-4 animate-pulse">
                <div className="h-8 w-1/3 bg-muted rounded"></div>
                <div className="h-24 bg-muted rounded-lg"></div>
                <div className="h-48 bg-muted rounded-lg"></div>
            </div>
        );
    }

    if (isError || !caseData) {
        return (
            <div className="flex flex-col items-center justify-center h-96 text-center space-y-4">
                <AlertCircle className="h-12 w-12 text-destructive" />
                <h3 className="text-lg font-semibold">Qualcosa è andato storto</h3>
                <p className="text-muted-foreground max-w-sm">Impossibile caricare i dati.</p>
                <Button onClick={() => mutate()} variant="outline">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Riprova
                </Button>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-4xl mx-auto p-4">
            {/* Back button */}
            <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push('/dashboard')}
                className="mb-2"
            >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Torna alla Dashboard
            </Button>

            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">{caseData.reference_code}</h1>
                    {caseData.client_name && (
                        <p className="text-muted-foreground">{caseData.client_name}</p>
                    )}
                </div>
                <Badge variant="default" className="bg-green-600 hover:bg-green-700">
                    <CheckCircle className="h-4 w-4 mr-1" />
                    Caso Chiuso
                </Badge>
            </div>

            {/* Success Banner */}
            <Card className="border-green-500 bg-green-50 dark:bg-green-950/20">
                <CardContent className="py-6 flex items-center gap-4">
                    <div className="p-3 bg-green-100 dark:bg-green-900 rounded-full">
                        <CheckCircle className="h-8 w-8 text-green-600" />
                    </div>
                    <div>
                        <h2 className="text-xl font-semibold text-green-700 dark:text-green-400">
                            Caso Completato con Successo
                        </h2>
                        <p className="text-muted-foreground">
                            La perizia è stata finalizzata e archiviata.
                        </p>
                    </div>
                </CardContent>
            </Card>

            {/* Final Report Download */}
            {finalVersion && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Download className="h-5 w-5" />
                            Report Finale
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm text-muted-foreground mb-4">
                            Versione {finalVersion.version_number} •
                            Finalizzata il {new Date(finalVersion.created_at).toLocaleDateString('it-IT')}
                        </p>
                        <div className="flex gap-2">
                            <Button onClick={() => handleDownloadFinal('bn')}>
                                <Download className="h-4 w-4 mr-2" />
                                Scarica (BN)
                            </Button>
                            <Button variant="outline" onClick={() => handleDownloadFinal('salomone')}>
                                <Download className="h-4 w-4 mr-2" />
                                Scarica (Salomone)
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* AI Summary */}
            {caseData.ai_summary && (
                <SummaryCard summary={caseData.ai_summary} />
            )}

            {/* Case Details Panel - Still Editable */}
            <CaseDetailsPanel
                caseDetail={caseData}
                onUpdate={(updatedCase) => {
                    mutate(updatedCase, false);
                }}
            />
        </div>
    );
}
