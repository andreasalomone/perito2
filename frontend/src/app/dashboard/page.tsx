"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";

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
                    setReports(data);
                }
            } catch (error) {
                console.error("Failed to fetch reports", error);
            } finally {
                setLoading(false);
            }
        };

        fetchReports();
    }, [getToken]);

    if (loading) return <div>Loading reports...</div>;

    return (
        <div>
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
                <Link href="/dashboard/create" className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                    Create New Report
                </Link>
            </div>

            <div className="bg-white shadow overflow-hidden sm:rounded-md">
                <ul className="divide-y divide-gray-200">
                    {reports.length === 0 ? (
                        <li className="px-6 py-4 text-center text-gray-500">
                            No reports found. Create your first one!
                        </li>
                    ) : (
                        reports.map((report) => (
                            <li key={report.id}>
                                <div className="px-4 py-4 sm:px-6">
                                    <div className="flex items-center justify-between">
                                        <p className="text-sm font-medium text-blue-600 truncate">
                                            Report {report.id.slice(0, 8)}...
                                        </p>
                                        <div className="ml-2 flex-shrink-0 flex">
                                            <p className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${report.status === 'success' ? 'bg-green-100 text-green-800' :
                                                    report.status === 'error' ? 'bg-red-100 text-red-800' :
                                                        'bg-yellow-100 text-yellow-800'
                                                }`}>
                                                {report.status}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="mt-2 sm:flex sm:justify-between">
                                        <div className="sm:flex">
                                            <p className="flex items-center text-sm text-gray-500">
                                                Created on {new Date(report.created_at).toLocaleDateString()}
                                            </p>
                                        </div>
                                        <div className="mt-2 flex items-center text-sm text-gray-500 sm:mt-0">
                                            {report.status === 'success' && (
                                                <button
                                                    onClick={async () => {
                                                        const token = await getToken();
                                                        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/reports/${report.id}/download`, {
                                                            headers: { Authorization: `Bearer ${token}` }
                                                        });
                                                        const data = await res.json();
                                                        if (data.download_url) window.open(data.download_url, '_blank');
                                                    }}
                                                    className="text-blue-600 hover:text-blue-900"
                                                >
                                                    Download
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </li>
                        ))
                    )}
                </ul>
            </div>
        </div>
    );
}
