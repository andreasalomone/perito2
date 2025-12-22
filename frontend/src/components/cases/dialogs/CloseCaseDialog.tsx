import { useState, useRef } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { ReportVersion } from "@/types";
import { Upload, FileText, CheckCircle2, RefreshCw, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface CloseCaseDialogProps {
    isOpen: boolean;
    onClose: () => void;
    activeDraft?: ReportVersion;
    onFinalize: (file: File) => Promise<void>;
    onConfirmDocs: (versionId: string) => Promise<void>;
    isLoading: boolean;
}

export function CloseCaseDialog({
    isOpen,
    onClose,
    activeDraft,
    onFinalize,
    onConfirmDocs,
    isLoading
}: CloseCaseDialogProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedMode, setSelectedMode] = useState<'file' | 'docs' | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files?.length) {
            setSelectedFile(e.target.files[0]);
            setSelectedMode('file');
        }
    };

    const handleDocsSelect = () => {
        setSelectedMode('docs');
        setSelectedFile(null);
    };

    const handleConfirm = () => {
        if (selectedMode === 'file' && selectedFile) {
            onFinalize(selectedFile);
        } else if (selectedMode === 'docs' && activeDraft) {
            onConfirmDocs(activeDraft.id);
        }
        // Note: Dialog stays open during loading (controlled by page)
    };

    const handleClose = () => {
        setSelectedMode(null);
        setSelectedFile(null);
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                        Chiudi Sinistro
                    </DialogTitle>
                    <DialogDescription>
                        Per chiudere il caso, seleziona la versione finale del report.
                    </DialogDescription>
                </DialogHeader>

                <div className="grid gap-4 py-4">
                    {/* Option 1: Google Docs (if available) */}
                    {activeDraft && (
                        <div
                            className={cn(
                                "border rounded-lg p-4 cursor-pointer transition-all hover:bg-accent/50",
                                selectedMode === 'docs' ? "border-primary bg-primary/5 ring-1 ring-primary" : "border-border"
                            )}
                            onClick={handleDocsSelect}
                        >
                            <div className="flex items-start gap-3">
                                <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-full">
                                    <RefreshCw className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                                </div>
                                <div>
                                    <h4 className="font-semibold">Conferma Google Docs</h4>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        Utilizza la versione attualmente in bozza su Google Docs (v{activeDraft.version_number}).
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Option 2: Upload File */}
                    <div
                        className={cn(
                            "border rounded-lg p-4 cursor-pointer transition-all hover:bg-accent/50",
                            selectedMode === 'file' ? "border-primary bg-primary/5 ring-1 ring-primary" : "border-border"
                        )}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <div className="flex items-start gap-3">
                            <div className="p-2 bg-orange-100 dark:bg-orange-900 rounded-full">
                                <Upload className="h-5 w-5 text-orange-600 dark:text-orange-400" />
                            </div>
                            <div className="w-full">
                                <h4 className="font-semibold">Carica File Finale</h4>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Carica un file DOCX o PDF dal tuo computer.
                                </p>
                                {selectedFile && (
                                    <div className="mt-2 text-sm font-medium text-primary flex items-center bg-background/50 p-2 rounded">
                                        <FileText className="h-4 w-4 mr-2" />
                                        {selectedFile.name}
                                    </div>
                                )}
                            </div>
                        </div>
                        <Input
                            type="file"
                            ref={fileInputRef}
                            onChange={handleFileSelect}
                            accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            className="hidden"
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={handleClose} disabled={isLoading}>Annulla</Button>
                    <Button
                        onClick={handleConfirm}
                        disabled={!selectedMode || isLoading}
                        className="bg-green-600 hover:bg-green-700 text-white"
                    >
                        {isLoading ? "Elaborazione..." : "Chiudi Sinistro"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
