"use client";

import { AlertCircle, RefreshCw, Trash2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CaseDetail, Document } from "@/types";

interface ErrorStateOverlayProps {
    caseData: CaseDetail;
    onDeleteDocument: (docId: string) => Promise<void>;
    onRetryGeneration: () => Promise<void>;
    isDeleting?: boolean;
    isRetrying?: boolean;
}

/**
 * Error state overlay shown when case.status === 'ERROR'
 * Provides recovery options: delete failed docs and retry generation
 */
export function ErrorStateOverlay({
    caseData,
    onDeleteDocument,
    onRetryGeneration,
    isDeleting = false,
    isRetrying = false,
}: ErrorStateOverlayProps) {
    // Find documents that failed processing
    const failedDocs = caseData.documents.filter(d => d.ai_status === 'ERROR');
    const hasFailedDocs = failedDocs.length > 0;

    // Find documents that succeeded
    const successDocs = caseData.documents.filter(d => d.ai_status === 'SUCCESS');
    const hasSuccessDocs = successDocs.length > 0;

    return (
        <div className="space-y-6">
            {/* Error Banner */}
            <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Errore durante la generazione</AlertTitle>
                <AlertDescription>
                    Si è verificato un errore durante l&apos;elaborazione.
                    {hasFailedDocs && ` ${failedDocs.length} documento/i non sono stati elaborati correttamente.`}
                </AlertDescription>
            </Alert>

            {/* Recovery Options */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Opzioni di Recupero</CardTitle>
                    <CardDescription>
                        Seleziona un&apos;azione per risolvere l&apos;errore
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Option 1: Delete failed docs and retry */}
                    {hasFailedDocs && (
                        <div className="flex flex-col gap-3 p-4 border rounded-lg bg-muted/50">
                            <div className="flex items-start gap-3">
                                <Trash2 className="h-5 w-5 text-destructive mt-0.5" />
                                <div className="flex-1">
                                    <h4 className="font-medium">Rimuovi documenti falliti</h4>
                                    <p className="text-sm text-muted-foreground">
                                        Elimina i documenti che non sono stati elaborati e riprova con i restanti.
                                    </p>
                                    <ul className="mt-2 text-sm text-muted-foreground list-disc list-inside">
                                        {failedDocs.map(doc => (
                                            <li key={doc.id} className="flex flex-col"><span>{doc.filename}</span>{doc.error_message && (<span className="text-xs text-destructive ml-4">→ {doc.error_message}</span>)}</li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                            <div className="flex gap-2 ml-8">
                                {failedDocs.map(doc => (
                                    <Button
                                        key={doc.id}
                                        variant="destructive"
                                        size="sm"
                                        disabled={isDeleting}
                                        onClick={() => onDeleteDocument(doc.id)}
                                    >
                                        <Trash2 className="h-4 w-4 mr-1" />
                                        Elimina {doc.filename.length > 15 ? doc.filename.slice(0, 12) + '...' : doc.filename}
                                    </Button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Option 2: Retry generation (if we have successful docs) */}
                    {hasSuccessDocs && (
                        <div className="flex flex-col gap-3 p-4 border rounded-lg bg-muted/50">
                            <div className="flex items-start gap-3">
                                <RefreshCw className="h-5 w-5 text-primary mt-0.5" />
                                <div className="flex-1">
                                    <h4 className="font-medium">Riprova la generazione</h4>
                                    <p className="text-sm text-muted-foreground">
                                        Genera nuovamente il report usando i {successDocs.length} documenti elaborati con successo.
                                    </p>
                                </div>
                            </div>
                            <Button
                                className="ml-8 w-fit"
                                disabled={isRetrying || !hasSuccessDocs}
                                onClick={onRetryGeneration}
                            >
                                <RefreshCw className={`h-4 w-4 mr-2 ${isRetrying ? 'animate-spin' : ''}`} />
                                {isRetrying ? 'Generazione in corso...' : 'Genera Report'}
                            </Button>
                        </div>
                    )}

                    {/* No successful docs - need to upload new ones */}
                    {!hasSuccessDocs && (
                        <div className="p-4 border rounded-lg bg-muted/50">
                            <p className="text-sm text-muted-foreground">
                                Nessun documento è stato elaborato con successo.
                                Elimina i documenti falliti e carica nuovi documenti per continuare.
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
