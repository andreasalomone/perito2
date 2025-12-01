"use client";

import { useState, useRef } from "react";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";
import {
    UploadCloud,
    FileText,
    CheckCircle2,
    Loader2,
    AlertCircle,
    X,
    File as FileIcon,
    ArrowRight
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

interface LogMessage {
    message: string;
    timestamp?: string;
}

export default function ReportGenerator() {
    const { getToken } = useAuth();
    const [files, setFiles] = useState<File[]>([]);
    const [status, setStatus] = useState<"idle" | "uploading" | "processing" | "completed" | "error">("idle");
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState<string[]>([]);
    const [reportId, setReportId] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            setFiles(Array.from(e.target.files));
            setStatus("idle");
            setLogs([]);
            setProgress(0);
        }
    };

    const removeFile = (index: number) => {
        setFiles(files.filter((_, i) => i !== index));
    };

    const startProcess = async () => {
        if (files.length === 0) return;
        setStatus("uploading");
        setProgress(10);
        setLogs(["Avvio sessione di caricamento sicuro..."]);

        try {
            const token = await getToken();
            const headers = { Authorization: `Bearer ${token}` };
            const uploadedPaths: string[] = [];
            const originalNames: string[] = [];

            // 1. Direct Upload to Google Cloud Storage
            let uploadedCount = 0;
            for (const file of files) {
                setLogs((prev) => [...prev, `Caricamento ${file.name}...`]);

                // Get Signed URL from Backend
                const { data: signData } = await axios.post(
                    `${API_URL}/api/reports/upload-url`,
                    { filename: file.name, content_type: file.type },
                    { headers }
                );

                // Upload directly to Google (PUT)
                await axios.put(signData.upload_url, file, {
                    headers: { "Content-Type": file.type },
                });

                uploadedPaths.push(signData.gcs_path);
                originalNames.push(file.name);
                uploadedCount++;
                setProgress(10 + (uploadedCount / files.length) * 30); // Upload is 10-40%
            }

            // 2. Trigger Backend Generation
            setLogs((prev) => [...prev, "Tutti i file caricati in modo sicuro.", "Avvio motore di analisi IA..."]);
            setStatus("processing");
            setProgress(50);

            const { data: genData } = await axios.post(
                `${API_URL}/api/reports/generate`,
                { file_paths: uploadedPaths, original_filenames: originalNames },
                { headers }
            );

            setReportId(genData.report_id);
            pollStatus(genData.report_id, token!);

        } catch (error: unknown) {
            console.error(error);
            setStatus("error");
            const errorMessage = error instanceof Error ? error.message : "Errore sconosciuto";
            setLogs((prev) => [...prev, "Errore Critico: " + errorMessage]);
        }
    };

    const resetState = () => {
        setFiles([]);
        setStatus("idle");
        setProgress(0);
        setLogs([]);
        setReportId(null);
    };

    const pollStatus = (id: string, token: string) => {
        const interval = setInterval(async () => {
            try {
                const { data } = await axios.get(`${API_URL}/api/reports/${id}/status`, {
                    headers: { Authorization: `Bearer ${token}` },
                });

                // Update logs from backend progress
                if (data.progress_logs?.length > 0) {
                    const messages = data.progress_logs.map((l: LogMessage) => l.message);
                    setLogs(messages);
                }

                if (data.status === "success") {
                    clearInterval(interval);
                    setStatus("completed");
                    setProgress(100);
                } else if (data.status === "error") {
                    clearInterval(interval);
                    setStatus("error");
                    setLogs((prev) => [...prev, "Errore: " + data.error]);
                } else {
                    // Simulate progress during processing (50-90%)
                    setProgress((prev) => Math.min(prev + 5, 90));
                }
            } catch (error: unknown) {
                console.error("Polling failed", error);
            }
        }, 2000);
    };

    return (
        <Card className="w-full border-border/60 shadow-lg">
            <CardHeader>
                <CardTitle>Nuova Analisi</CardTitle>
                <CardDescription>Carica i tuoi file (PDF, Immagini, Excel) per generare un report.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">

                {/* Upload Area */}
                {status === "idle" || status === "uploading" ? (
                    <div
                        onClick={() => status === "idle" && fileInputRef.current?.click()}
                        className={cn(
                            "border-2 border-dashed rounded-xl p-10 text-center transition-all duration-200 ease-in-out",
                            status === "idle"
                                ? "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50 cursor-pointer"
                                : "border-muted-foreground/10 bg-muted/10 cursor-default"
                        )}
                    >
                        <input
                            type="file"
                            multiple
                            onChange={handleFileChange}
                            className="hidden"
                            ref={fileInputRef}
                            disabled={status !== "idle"}
                        />
                        <div className="flex flex-col items-center gap-4">
                            <div className="p-4 bg-primary/5 rounded-full">
                                <UploadCloud className="h-10 w-10 text-primary" />
                            </div>
                            <div className="space-y-1">
                                <h3 className="font-semibold text-lg">
                                    {files.length > 0 ? `${files.length} file selezionati` : "Clicca per caricare i file"}
                                </h3>
                                <p className="text-sm text-muted-foreground">
                                    Supporto per PDF, JPG, PNG, XLSX
                                </p>
                            </div>
                        </div>
                    </div>
                ) : null}

                {/* File List */}
                {files.length > 0 && status === "idle" && (
                    <div className="space-y-2">
                        {files.map((file, i) => (
                            <div key={i} className="flex items-center justify-between p-3 bg-muted/30 rounded-lg border border-border/50">
                                <div className="flex items-center gap-3 overflow-hidden">
                                    <FileIcon className="h-5 w-5 text-blue-500 flex-shrink-0" />
                                    <span className="text-sm font-medium truncate">{file.name}</span>
                                    <span className="text-xs text-muted-foreground flex-shrink-0">
                                        ({(file.size / 1024 / 1024).toFixed(2)} MB)
                                    </span>
                                </div>
                                <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); removeFile(i); }} className="h-8 w-8 text-muted-foreground hover:text-destructive">
                                    <X className="h-4 w-4" />
                                </Button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Progress State */}
                {status !== "idle" && status !== "completed" && (
                    <div className="space-y-4 py-4">
                        <div className="flex items-center justify-between text-sm">
                            <span className="font-medium flex items-center gap-2">
                                {status === "uploading" ? "Caricamento file..." : "Analisi contenuto..."}
                                <Loader2 className="h-3 w-3 animate-spin" />
                            </span>
                            <span className="text-muted-foreground">{Math.round(progress)}%</span>
                        </div>
                        <Progress value={progress} className="h-2" />

                        {/* Terminal-like Logs */}
                        <div className="bg-zinc-950 rounded-lg p-4 font-mono text-xs text-zinc-400 h-32 overflow-y-auto border border-zinc-800 shadow-inner">
                            {logs.map((log, i) => (
                                <div key={i} className="mb-1.5 flex gap-2">
                                    <span className="text-zinc-600">{">"}</span>
                                    <span className={i === logs.length - 1 ? "text-zinc-100" : ""}>{log}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Success State */}
                {status === "completed" && reportId && (
                    <div className="rounded-xl border border-accent/20 bg-accent/5 p-6 flex flex-col items-center text-center gap-4 animate-in fade-in zoom-in-95 duration-300">
                        <div className="h-12 w-12 bg-accent/10 rounded-full flex items-center justify-center">
                            <CheckCircle2 className="h-6 w-6 text-accent" />
                        </div>
                        <div className="space-y-1">
                            <h3 className="font-semibold text-xl text-foreground">Perizia completata.</h3>
                            <p className="text-muted-foreground">Il tuo report è stato generato con successo.</p>
                        </div>
                        <div className="flex flex-col sm:flex-row gap-3 mt-2 w-full sm:w-auto">
                            <Button
                                onClick={resetState}
                                variant="outline"
                                size="lg"
                                className="w-full sm:w-auto border-accent/20 text-accent hover:bg-accent/10 hover:text-accent"
                            >
                                Nuova Perizia
                            </Button>
                            <Button
                                onClick={async () => {
                                    try {
                                        const token = await getToken();
                                        const { data } = await axios.get(
                                            `${API_URL}/api/reports/${reportId}/download`,
                                            { headers: { Authorization: `Bearer ${token}` } }
                                        );
                                        window.open(data.download_url, "_blank");
                                    } catch {
                                        alert("Error downloading file");
                                    }
                                }}

                                className="bg-accent hover:bg-accent/90 text-accent-foreground gap-2 w-full sm:w-auto"
                                size="lg"
                            >
                                <FileText className="h-4 w-4" />
                                Download Report
                            </Button>
                            <Button
                                onClick={() => window.location.href = "/dashboard"}
                                variant="ghost"
                                className="w-full sm:w-auto"
                            >
                                Vai alla Dashboard
                            </Button>
                        </div>
                    </div>
                )}

                {/* Error State */}
                {status === "error" && (
                    <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 flex items-start gap-3 text-destructive">
                        <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
                        <div className="text-sm">
                            <p className="font-semibold">Generazione fallita</p>
                            <p className="opacity-90 mt-1">
                                {logs[logs.length - 1] || "Si è verificato un errore imprevisto."}
                            </p>
                            <Button
                                variant="outline"
                                size="sm"
                                className="mt-3 border-destructive/30 hover:bg-destructive/10 text-destructive"
                                onClick={() => setStatus("idle")}
                            >
                                Riprova
                            </Button>
                        </div>
                    </div>
                )}

            </CardContent>

            {/* Footer Actions */}
            {
                status === "idle" && (
                    <CardFooter className="flex justify-end pt-2">
                        <Button
                            onClick={startProcess}
                            disabled={files.length === 0}
                            size="lg"
                            className="w-full sm:w-auto gap-2"
                        >
                            Avvia Analisi
                            <ArrowRight className="h-4 w-4" />
                        </Button>
                    </CardFooter>
                )
            }
        </Card >
    );
}