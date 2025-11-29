"use client";
import ReportGenerator from "@/components/ReportGenerator";

export default function CreateReportPage() {
    return (
        <div className="max-w-4xl mx-auto space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight">Nuova Perizia</h1>
                <p className="text-muted-foreground">
                    Carica i documenti e lascia che l&apos;IA generi un report professionale per te.
                </p>
            </div>

            <ReportGenerator />
        </div>
    );
}
