"use client";
import ReportGenerator from "@/components/ReportGenerator";

export default function CreateReportPage() {
    return (
        <div className="max-w-4xl mx-auto">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-gray-900">Create New Report</h1>
                <p className="mt-2 text-gray-600">
                    Upload your documents and let AI generate a professional report for you.
                </p>
            </div>

            <ReportGenerator />
        </div>
    );
}
