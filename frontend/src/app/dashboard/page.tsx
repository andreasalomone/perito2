"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText, Download, Plus, Calendar, Loader2 } from "lucide-react";

interface Report {
    id: string;
    status: string;
    created_at: string;
    final_docx_path: string | null;
}

export default function DashboardPage() {
    const { getToken } = useAuth();
    const [reports, setReports] = useState<Report[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchReports = async () => {
            const token = await getToken();
            if (!token) return;

            try {
                const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/reports/`, {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                });
                if (res.ok) {
                    const data = await res.json();
                    // Sort by created_at desc
                    const sorted = data.sort((a: Report, b: Report) =>
                        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
                    );
                    setReports(sorted);
                }
            } catch (error) {
                console.error("Failed to fetch reports", error);
            } finally {
                setLoading(false);
            }
        };

        fetchReports();
    }, [getToken]);

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "success":
                return <Badge variant="success">Completato</Badge>;
            case "error":
                return <Badge variant="destructive">Errore</Badge>;
            case "processing":
                return <Badge variant="secondary" className="animate-pulse">In Corso</Badge>;
            default:
                return <Badge variant="outline">{status}</Badge>;
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">I Miei Report</h1>
                    <p className="text-muted-foreground">Gestisci e scarica le tue perizie generate.</p>
                </div>
                <Link href="/dashboard/create">
                    <Button className="gap-2 shadow-lg shadow-primary/20">
                        <Plus className="h-4 w-4" />
                        Nuova Perizia
                    </Button>
                </Link>
            </div>

            {reports.length === 0 ? (
                <Card className="border-dashed border-2 bg-muted/10">
                    <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="p-4 bg-muted rounded-full mb-4">
                            <FileText className="h-8 w-8 text-muted-foreground" />
                        </div>
                        <h3 className="text-lg font-semibold">Nessun report trovato</h3>
                        <p className="text-muted-foreground mb-6 max-w-sm">
                            Non hai ancora generato nessuna perizia. Inizia caricando i documenti per il tuo primo caso.
                        </p>
                        <Link href="/dashboard/create">
                            <Button variant="outline">Crea la tua prima perizia</Button>
                        </Link>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid gap-4">
                    {reports.map((report) => (
                        <Card key={report.id} className="overflow-hidden transition-all hover:shadow-md hover:border-primary/20">
                            <div className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                <div className="space-y-1">
                                    <div className="flex items-center gap-3">
                                        <h3 className="font-semibold text-lg flex items-center gap-2">
                                            <FileText className="h-4 w-4 text-primary" />
                                            Report #{report.id.slice(0, 8)}
                                        </h3>
                                        {getStatusBadge(report.status)}
                                    </div>
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <Calendar className="h-3.5 w-3.5" />
                                        <span>Creato il {new Date(report.created_at).toLocaleDateString("it-IT", {
                                            day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
                                        })}</span>
                                    </div>
                                </div>

                                <div className="flex items-center gap-2">
                                    {report.status === 'success' && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="gap-2 border-primary/20 text-primary hover:bg-primary/5 hover:text-primary"
                                            onClick={async () => {
                                                const token = await getToken();
                                                const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/reports/${report.id}/download`, {
                                                    headers: { Authorization: `Bearer ${token}` }
                                                });
                                                const data = await res.json();
                                                if (data.download_url) {
                                                    const link = document.createElement('a');
                                                    link.href = data.download_url;
                                                    link.target = '_blank';
                                                    link.rel = 'noopener noreferrer';
                                                    document.body.appendChild(link);
                                                    link.click();
                                                    document.body.removeChild(link);
                                                }
                                            }}
                                        >
                                            <Download className="h-4 w-4" />
                                            Scarica DOCX
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
