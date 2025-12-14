"use client";

import { useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, FileText, CheckCircle2, XCircle, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { useConfig } from "@/context/ConfigContext";
import { batchUploadFiles } from "@/utils/batchUpload";
import axios from "axios";

interface FileStatus {
    id: string;
    file: File;
    progress: number;
    status: "queued" | "uploading" | "complete" | "error";
    error?: string;
}

interface CaseFileUploaderProps {
    caseId: string;
    onUploadComplete: () => void;
    /** Optional custom trigger element. If provided, dropzone is replaced by this element. */
    trigger?: React.ReactNode;
}

/**
 * Magnetic Dropzone File Uploader
 *
 * Features:
 * - Drag physics with scale/color feedback
 * - Optimistic file list (shows immediately on drop)
 * - Inline progress visualization
 * - Error state with retry
 */
export function CaseFileUploader({ caseId, onUploadComplete, trigger }: CaseFileUploaderProps) {
    const { getToken } = useAuth();
    const { apiUrl } = useConfig();
    const [dragActive, setDragActive] = useState(false);
    const [files, setFiles] = useState<FileStatus[]>([]);
    const inputRef = useRef<HTMLInputElement>(null);

    // Upload a single file with progress tracking
    const uploadSingleFile = useCallback(async (fileItem: FileStatus) => {
        // Mark as uploading
        setFiles(prev => prev.map(f =>
            f.id === fileItem.id ? { ...f, status: "uploading" as const, progress: 0 } : f
        ));

        try {
            const token = await getToken();

            // 1. Get signed URL
            const signRes = await axios.post(
                `${apiUrl}/api/v1/cases/${caseId}/documents/upload-url`,
                null,
                {
                    headers: { Authorization: `Bearer ${token}` },
                    params: { filename: fileItem.file.name, content_type: fileItem.file.type }
                }
            );

            // Update progress: signed URL obtained
            setFiles(prev => prev.map(f =>
                f.id === fileItem.id ? { ...f, progress: 20 } : f
            ));

            // 2. Upload to GCS with progress
            const maxFileSize = 50 * 1024 * 1024; // 50MB
            await axios.put(signRes.data.upload_url, fileItem.file, {
                headers: {
                    "Content-Type": fileItem.file.type,
                    "x-goog-content-length-range": `0,${maxFileSize}`
                },
                onUploadProgress: (progressEvent) => {
                    if (progressEvent.total) {
                        // Map 20-80% of progress to the actual upload
                        const uploadProgress = Math.round((progressEvent.loaded / progressEvent.total) * 60);
                        setFiles(prev => prev.map(f =>
                            f.id === fileItem.id ? { ...f, progress: 20 + uploadProgress } : f
                        ));
                    }
                }
            });

            // Update progress: uploaded, now registering
            setFiles(prev => prev.map(f =>
                f.id === fileItem.id ? { ...f, progress: 85 } : f
            ));

            // 3. Register document
            await axios.post(
                `${apiUrl}/api/v1/cases/${caseId}/documents/register`,
                {
                    filename: fileItem.file.name,
                    gcs_path: signRes.data.gcs_path,
                    mime_type: fileItem.file.type
                },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            // Complete
            setFiles(prev => prev.map(f =>
                f.id === fileItem.id ? { ...f, status: "complete" as const, progress: 100 } : f
            ));

        } catch (error) {
            console.error(`Failed to upload ${fileItem.file.name}:`, error);
            const errorMessage = axios.isAxiosError(error)
                ? error.response?.data?.detail || error.message
                : "Upload failed";
            setFiles(prev => prev.map(f =>
                f.id === fileItem.id ? { ...f, status: "error" as const, error: errorMessage } : f
            ));
        }
    }, [getToken, apiUrl, caseId]);

    // Handle new files (from drop or file picker)
    const handleFiles = useCallback((newFiles: File[]) => {
        if (!newFiles.length) return;

        const fileItems: FileStatus[] = newFiles.map(f => ({
            id: crypto.randomUUID(),
            file: f,
            progress: 0,
            status: "queued" as const
        }));

        // Show files immediately (optimistic)
        setFiles(prev => [...prev, ...fileItems]);

        // Start uploads concurrently
        fileItems.forEach(item => uploadSingleFile(item));

        // Notify parent to refetch after a delay (let uploads complete)
        // We use a completion check instead of fixed timeout
        const checkCompletion = setInterval(() => {
            setFiles(current => {
                const allDone = fileItems.every(item =>
                    current.find(f => f.id === item.id)?.status === "complete" ||
                    current.find(f => f.id === item.id)?.status === "error"
                );
                if (allDone) {
                    clearInterval(checkCompletion);
                    onUploadComplete();
                    // Clear completed files after refetch
                    setTimeout(() => {
                        setFiles(prev => prev.filter(f => f.status !== "complete"));
                    }, 1500);
                }
                return current;
            });
        }, 500);
    }, [uploadSingleFile, onUploadComplete]);

    // Retry a failed upload
    const handleRetry = useCallback((fileItem: FileStatus) => {
        setFiles(prev => prev.map(f =>
            f.id === fileItem.id ? { ...f, status: "queued" as const, progress: 0, error: undefined } : f
        ));
        uploadSingleFile(fileItem);
    }, [uploadSingleFile]);

    // Drag and drop handlers
    const handleDrag = useCallback((e: React.DragEvent, active: boolean) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(active);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files?.length) {
            handleFiles(Array.from(e.dataTransfer.files));
        }
    }, [handleFiles]);

    const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files?.length) {
            handleFiles(Array.from(e.target.files));
            e.target.value = ""; // Reset input
        }
    }, [handleFiles]);

    // If trigger is provided, render simplified version
    if (trigger) {
        return (
            <div onClick={() => inputRef.current?.click()} className="cursor-pointer">
                <input
                    ref={inputRef}
                    type="file"
                    multiple
                    className="hidden"
                    accept=".pdf,.docx,.xlsx,.txt,.eml,.png,.jpg,.jpeg,.webp,.gif"
                    onChange={handleInputChange}
                    data-testid="file-upload-input"
                />
                {trigger}
            </div>
        );
    }

    return (
        <div className="w-full space-y-4">
            {/* Magnetic Dropzone */}
            <motion.div
                layout
                className={cn(
                    "relative group cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed p-8 transition-colors duration-300 ease-out",
                    dragActive
                        ? "border-primary bg-primary/5 scale-[1.02]"
                        : "border-muted-foreground/20 hover:border-primary/50 hover:bg-muted/30"
                )}
                onDragEnter={(e) => handleDrag(e, true)}
                onDragLeave={(e) => handleDrag(e, false)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
                whileTap={{ scale: 0.98 }}
            >
                <input
                    ref={inputRef}
                    type="file"
                    multiple
                    className="hidden"
                    accept=".pdf,.docx,.xlsx,.txt,.eml,.png,.jpg,.jpeg,.webp,.gif"
                    onChange={handleInputChange}
                    data-testid="file-upload-input"
                />

                <div className="flex flex-col items-center justify-center space-y-4 text-center">
                    {/* Animated Icon */}
                    <motion.div
                        animate={dragActive ? { y: -8, scale: 1.1 } : { y: 0, scale: 1 }}
                        className="rounded-full bg-background p-4 shadow-lg ring-1 ring-border/50"
                    >
                        <UploadCloud
                            className={cn(
                                "h-8 w-8 transition-colors",
                                dragActive ? "text-primary" : "text-muted-foreground"
                            )}
                        />
                    </motion.div>

                    <div className="space-y-1">
                        <p className="text-lg font-medium tracking-tight text-foreground">
                            Trascina i documenti qui
                        </p>
                        <p className="text-sm text-muted-foreground">
                            PDF, DOCX, immagini, email
                        </p>
                    </div>
                </div>
            </motion.div>

            {/* Optimistic File List */}
            <div className="space-y-2">
                <AnimatePresence mode="popLayout">
                    {files.map((item) => (
                        <motion.div
                            key={item.id}
                            initial={{ opacity: 0, y: 20, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
                            layout
                            className={cn(
                                "relative overflow-hidden rounded-xl border bg-card p-3 shadow-sm",
                                item.status === "error" ? "border-destructive/50" : "border-border/50"
                            )}
                        >
                            {/* Progress Bar Background */}
                            {item.status !== "error" && (
                                <motion.div
                                    className="absolute bottom-0 left-0 top-0 bg-primary/5"
                                    initial={{ width: "0%" }}
                                    animate={{ width: `${item.progress}%` }}
                                    transition={{ duration: 0.3, ease: "easeOut" }}
                                />
                            )}

                            <div className="relative z-10 flex items-center justify-between gap-3">
                                <div className="flex items-center gap-3 overflow-hidden">
                                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-background/50 ring-1 ring-border/20">
                                        <FileText className="h-4 w-4 text-primary" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <p className="truncate text-sm font-medium leading-none">
                                            {item.file.name}
                                        </p>
                                        <p className="mt-1 text-xs text-muted-foreground">
                                            {(item.file.size / 1024).toFixed(0)} KB •{" "}
                                            {item.status === "complete"
                                                ? "Caricato"
                                                : item.status === "error"
                                                    ? "Errore"
                                                    : `${item.progress}%`}
                                        </p>
                                    </div>
                                </div>

                                <div className="flex shrink-0 items-center gap-2">
                                    {item.status === "complete" && (
                                        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
                                            <CheckCircle2 className="h-5 w-5 text-green-500" />
                                        </motion.div>
                                    )}
                                    {item.status === "uploading" && (
                                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                                    )}
                                    {item.status === "error" && (
                                        <>
                                            <XCircle className="h-5 w-5 text-destructive" />
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleRetry(item);
                                                }}
                                                className="p-1 rounded-full hover:bg-muted transition-colors"
                                                title="Riprova"
                                            >
                                                <RotateCcw className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                                            </button>
                                        </>
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>
            </div>
        </div>
    );
}
