"use client";
import { useState } from "react";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";
import { UploadCloud, FileText, CheckCircle, Loader2, AlertCircle } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function ReportGenerator() {
    const { getToken } = useAuth();
    const [files, setFiles] = useState<File[]>([]);
    const [status, setStatus] = useState<"idle" | "uploading" | "processing" | "completed" | "error">("idle");
    const [logs, setLogs] = useState<string[]>([]);
    const [reportId, setReportId] = useState<string | null>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) setFiles(Array.from(e.target.files));
    };

    const startProcess = async () => {
        if (files.length === 0) return;
        setStatus("uploading");
        setLogs(["Requesting upload permissions..."]);

        try {
            const token = await getToken();
            const headers = { Authorization: `Bearer ${token}` };
            const uploadedPaths: string[] = [];
            const originalNames: string[] = [];

            // 1. Direct Upload to Google Cloud Storage
            for (const file of files) {
                setLogs((prev) => [...prev, `Uploading ${file.name}...`]);

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

                uploadedPaths.push(signData.gcs_path); // Save the gs:// path
                originalNames.push(file.name);
            }

            // 2. Trigger Backend Generation
            setLogs((prev) => [...prev, "Files uploaded. Starting AI analysis..."]);
            setStatus("processing");

            const { data: genData } = await axios.post(
                `${API_URL}/api/reports/generate`,
                { file_paths: uploadedPaths, original_filenames: originalNames },
                { headers }
            );

            setReportId(genData.report_id);
            pollStatus(genData.report_id, token!);

        } catch (error) {
            console.error(error);
            setStatus("error");
            setLogs((prev) => [...prev, "Critical Error: " + (error as any).message]);
        }
    };

    const pollStatus = (id: string, token: string) => {
        const interval = setInterval(async () => {
            try {
                const { data } = await axios.get(`${API_URL}/api/reports/${id}/status`, {
                    headers: { Authorization: `Bearer ${token}` },
                });

                // Update logs from backend progress
                if (data.progress_logs?.length > 0) {
                    const messages = data.progress_logs.map((l: any) => l.message);
                    // Simple way to show latest logs
                    setLogs(messages);
                }

                if (data.status === "success") {
                    clearInterval(interval);
                    setStatus("completed");
                } else if (data.status === "error") {
                    clearInterval(interval);
                    setStatus("error");
                    setLogs((prev) => [...prev, "Error: " + data.error]);
                }
            } catch (e) {
                console.error("Polling failed", e);
            }
        }, 2000); // Poll every 2s
    };

    return (
        <div className="max-w-2xl mx-auto bg-white p-8 rounded-xl shadow-lg border border-gray-100">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">Generate New Report</h2>

            {/* Upload Area */}
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:bg-gray-50 transition-colors">
                <UploadCloud className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                <input type="file" multiple onChange={handleFileChange} className="hidden" id="fileInput" />
                <label htmlFor="fileInput" className="cursor-pointer text-blue-600 font-medium hover:underline">
                    Click to upload
                </label>
                <p className="text-sm text-gray-500 mt-2">PDFs, Images, or Excel files</p>
                {files.length > 0 && (
                    <div className="mt-4 text-sm font-semibold text-gray-700">
                        Selected: {files.length} files
                    </div>
                )}
            </div>

            {/* Action Button */}
            {status !== "completed" && (
                <button
                    onClick={startProcess}
                    disabled={files.length === 0 || status === "uploading" || status === "processing"}
                    className="w-full mt-6 bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-300 transition-all flex justify-center items-center gap-2"
                >
                    {status === "uploading" && <Loader2 className="animate-spin" />}
                    {status === "idle" ? "Start Analysis" : status.toUpperCase()}
                </button>
            )}

            {/* Logs / Status */}
            {(status !== "idle") && (
                <div className="mt-6 bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm h-48 overflow-y-auto">
                    {logs.map((log, i) => (
                        <div key={i} className="mb-1">{">"} {log}</div>
                    ))}
                    {status === "completed" && <div className="text-white font-bold mt-2">DONE. Report Ready.</div>}
                </div>
            )}

            {/* Download Link */}
            {status === "completed" && reportId && (
                <div className="mt-6 p-6 bg-green-50 border border-green-200 rounded-xl flex flex-col md:flex-row items-center justify-between gap-4 animate-in fade-in slide-in-from-bottom-4">
                    <div className="flex items-center gap-3">
                        <div className="bg-green-100 p-2 rounded-full">
                            <CheckCircle className="h-6 w-6 text-green-600" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-green-900">Analysis Complete</h3>
                            <p className="text-green-700 text-sm">Your professional report is ready.</p>
                        </div>
                    </div>

                    <button
                        onClick={async () => {
                            try {
                                const token = await getToken();
                                // 1. Get the secure link
                                const { data } = await axios.get(
                                    `${API_URL}/api/reports/${reportId}/download`,
                                    { headers: { Authorization: `Bearer ${token}` } }
                                );
                                // 2. Open it
                                window.open(data.download_url, "_blank");
                            } catch (e) {
                                alert("Error downloading file");
                            }
                        }}
                        className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-semibold shadow-sm transition-all"
                    >
                        <FileText className="h-5 w-5" />
                        Download DOCX
                    </button>
                </div>
            )}
        </div>
    );
}