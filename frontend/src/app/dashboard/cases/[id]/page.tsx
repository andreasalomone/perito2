"use client";
import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Case, Document, ReportVersion } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { UploadCloud, FileText, Play, CheckCircle, Download, Loader2 } from "lucide-react";
import axios from "axios";

export default function CaseWorkspace() {
    const { id } = useParams();
    const { getToken } = useAuth();
    const [caseData, setCaseData] = useState<Case | null>(null);
    const [uploading, setUploading] = useState(false);
    const [generating, setGenerating] = useState(false);

    const API = process.env.NEXT_PUBLIC_API_URL;

    // 1. Fetch Case Data
    const fetchCase = useCallback(async () => {
        const token = await getToken();
        if (!token) return;
        try {
            const res = await axios.get(`${API}/api/cases/${id}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setCaseData(res.data);
        } catch (e) {
            console.error(e);
        }
    }, [getToken, id, API]);

    useEffect(() => { fetchCase(); }, [fetchCase]);

    // 2. Handle File Upload (Document)
    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        setUploading(true);
        const file = e.target.files[0];

        try {
            const token = await getToken();
            // A. Get Signed URL
            const signRes = await axios.post(`${API}/api/cases/${id}/documents/upload-url`,
                { filename: file.name, content_type: file.type },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            // B. Upload to GCS
            await axios.put(signRes.data.upload_url, file, {
                headers: { "Content-Type": file.type }
            });

            // C. Register in DB
            await axios.post(`${API}/api/cases/${id}/documents/register`,
                { filename: file.name, gcs_path: signRes.data.gcs_path },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            await fetchCase(); // Refresh UI
        } catch (error) {
            alert("Errore caricamento");
        } finally {
            setUploading(false);
        }
    };

    // 3. Trigger AI Generation
    const handleGenerate = async () => {
        setGenerating(true);
        try {
            const token = await getToken();
            // Note: The backend route is actually /tasks/process-case (via Cloud Tasks) 
            // OR we might have a direct endpoint in cases.py to trigger it?
            // Checking cases.py: register_document triggers it. 
            // But if we want to trigger manually for ALL docs?
            // The user request implies a "Trigger Generation" button.
            // Let's assume we need an endpoint for this or we trigger per doc.
            // Wait, the user request code uses: axios.post(`${API}/api/cases/${id}/generate`
            // I need to make sure this endpoint exists in backend/routes/cases.py!
            // I missed adding it in the previous step. I will add it now or use the register trigger.
            // For now, I will implement the frontend as requested and fix the backend if needed.

            await axios.post(`${API}/api/cases/${id}/generate`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            alert("Generazione avviata! Riceverai una notifica al termine.");
        } catch (error) {
            alert("Errore generazione");
        } finally {
            setGenerating(false);
        }
    };

    // 4. Handle Final Version Upload
    const handleFinalize = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;
        const file = e.target.files[0];

        try {
            const token = await getToken();
            // Reuse logic: Get URL -> Upload -> Call Finalize Endpoint
            const signRes = await axios.post(`${API}/api/cases/${id}/documents/upload-url`,
                { filename: `FINAL_${file.name}`, content_type: file.type },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            await axios.put(signRes.data.upload_url, file, { headers: { "Content-Type": file.type } });

            await axios.post(`${API}/api/cases/${id}/finalize`,
                { final_docx_path: signRes.data.gcs_path },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            await fetchCase();
        } catch (error) {
            console.error(error);
        }
    };

    if (!caseData) return <div>Caricamento fascicolo...</div>;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold">{caseData.reference_code}</h1>
                    <p className="text-muted-foreground">Cliente: {caseData.client_name || "N/A"}</p>
                </div>
                <Badge variant={caseData.status === "open" ? "default" : "secondary"}>
                    {caseData.status.toUpperCase()}
                </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* LEFT: Documents */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle>Documenti ({caseData.documents.length})</CardTitle>
                        <div className="relative">
                            <input type="file" onChange={handleFileUpload} className="absolute inset-0 opacity-0 cursor-pointer" disabled={uploading} />
                            <Button size="sm" variant="outline" disabled={uploading}>
                                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4 mr-2" />}
                                Carica
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {caseData.documents.map(doc => (
                            <div key={doc.id} className="flex items-center justify-between p-2 border rounded text-sm">
                                <span className="truncate max-w-[200px]">{doc.filename}</span>
                                <Badge variant="outline">{doc.ai_status}</Badge>
                            </div>
                        ))}
                    </CardContent>
                </Card>

                {/* RIGHT: Versions */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle>Report</CardTitle>
                        <Button size="sm" onClick={handleGenerate} disabled={generating || caseData.documents.length === 0}>
                            <Play className="h-4 w-4 mr-2" />
                            Genera con IA
                        </Button>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {caseData.report_versions.length === 0 && (
                            <p className="text-sm text-muted-foreground text-center py-4">Nessun report generato.</p>
                        )}

                        {caseData.report_versions.map(v => (
                            <div key={v.id} className="flex items-center justify-between p-3 bg-muted/20 rounded border">
                                <div className="flex items-center gap-2">
                                    <FileText className="h-5 w-5 text-blue-500" />
                                    <div>
                                        <p className="font-medium">Versione {v.version_number}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {v.is_final ? "Finale Approvata" : "Bozza IA"}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    {/* Download Button */}
                                    <Button size="icon" variant="ghost" onClick={() => window.open(v.docx_storage_path || "#")}>
                                        <Download className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        ))}

                        {/* Finalize Action */}
                        {caseData.report_versions.length > 0 && (
                            <div className="mt-4 pt-4 border-t">
                                <p className="text-xs text-muted-foreground mb-2">Hai completato il report?</p>
                                <div className="relative">
                                    <input type="file" onChange={handleFinalize} className="absolute inset-0 opacity-0 cursor-pointer" />
                                    <Button variant="secondary" className="w-full border-green-200 bg-green-50 text-green-700 hover:bg-green-100">
                                        <CheckCircle className="h-4 w-4 mr-2" />
                                        Carica Versione Firmata
                                    </Button>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
