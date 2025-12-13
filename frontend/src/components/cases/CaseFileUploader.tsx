"use client";

import { useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { useConfig } from "@/context/ConfigContext";
import { batchUploadFiles } from "@/utils/batchUpload";

interface CaseFileUploaderProps {
    caseId: string;
    onUploadComplete: () => void;
    trigger?: React.ReactNode;
}

export function CaseFileUploader({ caseId, onUploadComplete, trigger }: CaseFileUploaderProps) {
    const { getToken } = useAuth();
    const { apiUrl } = useConfig();
    const docInputRef = useRef<HTMLInputElement>(null);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        const files = Array.from(e.target.files);
        const toastId = toast.loading(`Caricamento di ${files.length} file...`);

        try {


            const { successCount, failCount } = await batchUploadFiles(files, {
                getToken,
                getSignedUrl: async (filename, contentType) => {
                    const token = await getToken();
                    const res = await axios.post(`${apiUrl}/api/v1/cases/${caseId}/documents/upload-url`,
                        null,
                        {
                            headers: { Authorization: `Bearer ${token}` },
                            params: { filename, content_type: contentType }
                        }
                    );
                    return res.data;
                },
                uploadToGcs: async (url, file, contentType) => {
                    const maxFileSize = 50 * 1024 * 1024; // 50MB
                    await axios.put(url, file, {
                        headers: {
                            "Content-Type": contentType,
                            "x-goog-content-length-range": `0,${maxFileSize}`
                        }
                    });
                },
                registerDocument: async (filename, gcsPath, mimeType) => {
                    const token = await getToken();
                    await axios.post(`${apiUrl}/api/v1/cases/${caseId}/documents/register`,
                        {
                            filename,
                            gcs_path: gcsPath,
                            mime_type: mimeType
                        },
                        { headers: { Authorization: `Bearer ${token}` } }
                    );
                },
                onProgress: (current, total) => {
                    const BATCH_SIZE = 4;
                    const end = Math.min(current + BATCH_SIZE - 1, total);
                    toast.loading(`Caricamento ${current}-${end}/${total}...`, { id: toastId });
                }
            });

            if (failCount === 0) {
                toast.success(`${successCount} documenti caricati`, { id: toastId });
            } else {
                toast.warning(`${successCount} ok, ${failCount} falliti`, { id: toastId });
            }
        } catch (error) {
            console.error('Unexpected upload error:', error);
            toast.error('Errore imprevisto durante il caricamento', { id: toastId });
        } finally {
            onUploadComplete();
            if (docInputRef.current) docInputRef.current.value = "";
        }
    };

    return (
        <div onClick={() => trigger && docInputRef.current?.click()} className={trigger ? "cursor-pointer" : ""}>
            <input
                type="file"
                ref={docInputRef}
                onChange={handleFileUpload}
                className="hidden"
                accept=".pdf,.docx,.xlsx,.txt,.eml,.png,.jpg,.jpeg,.webp,.gif"
                multiple
                data-testid="file-upload-input"
            />
            {trigger || (
                <Button
                    size="sm"
                    variant="outline"
                    onClick={(e) => {
                        e.stopPropagation();
                        docInputRef.current?.click();
                    }}
                >
                    <UploadCloud className="h-4 w-4 mr-2" />
                    Carica
                </Button>
            )}
        </div>
    );
}
