"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import useSWR from "swr";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, ShieldAlert, ArrowLeft, BarChart3, Users, Building2, FileText, HardDrive, ExternalLink, FolderOpen } from "lucide-react";
import { api } from "@/lib/api";
import { useOrganizations } from "@/hooks/useOrganizations";
import { GlobalStats } from "@/types/stats";

export default function AdminStatsPage() {
    const { user, loading: authLoading, getToken } = useAuth();
    const router = useRouter();
    const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);

    // Check superadmin access via organizations list (same pattern as admin page)
    const { organizations, isLoading: orgsLoading, isError: orgsError } = useOrganizations();

    // Fetch global stats
    const { data: stats, isLoading: statsLoading, error: statsError } = useSWR<GlobalStats>(
        user ? ["admin-stats"] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.admin.getGlobalStats(token);
        },
        { revalidateOnFocus: false }
    );

    // Redirect if not logged in
    useEffect(() => {
        if (!authLoading && !user) {
            router.push("/");
        }
    }, [user, authLoading, router]);

    // Handle org selection
    const handleOrgSelect = (orgId: string) => {
        setSelectedOrgId(orgId);
        router.push(`/admin/stats/${orgId}`);
    };

    if (authLoading || (user && orgsLoading)) {
        return (
            <div className="flex h-screen w-full items-center justify-center bg-background">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    if (orgsError) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-background p-4">
                <Card className="w-full max-w-md">
                    <CardHeader>
                        <div className="flex items-center space-x-2">
                            <ShieldAlert className="h-6 w-6 text-destructive" />
                            <CardTitle>Access Denied</CardTitle>
                        </div>
                        <CardDescription>
                            You do not have superadmin permissions to access this page.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button onClick={() => router.push("/dashboard")} className="w-full">
                            Go to Dashboard
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background p-8">
            <div className="mx-auto max-w-7xl space-y-8">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" onClick={() => router.push("/admin")}>
                            <ArrowLeft className="h-5 w-5" />
                        </Button>
                        <div>
                            <h1 className="text-3xl font-bold flex items-center gap-2">
                                <BarChart3 className="h-8 w-8" />
                                Platform Statistics
                            </h1>
                            <p className="text-muted-foreground">Global platform metrics and analytics</p>
                        </div>
                    </div>
                    <Button
                        variant="outline"
                        onClick={() => window.open("https://aistudio.google.com/usage?project=perito-479708&timeRange=last-7-days", "_blank", "noopener,noreferrer")}
                    >
                        <ExternalLink className="h-4 w-4 mr-2" />
                        Gemini Usage
                    </Button>
                </div>

                {/* Stats Loading State */}
                {statsLoading && (
                    <div className="flex items-center justify-center py-16">
                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    </div>
                )}

                {/* Stats Error State */}
                {statsError && (
                    <Card className="border-destructive">
                        <CardContent className="flex items-center gap-2 py-4 text-destructive">
                            <ShieldAlert className="h-5 w-5" />
                            <span>Failed to load statistics</span>
                        </CardContent>
                    </Card>
                )}

                {/* Stats Grid */}
                {stats && (
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {/* Organizations */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Organizations</CardTitle>
                                <Building2 className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">{stats.org_count}</div>
                            </CardContent>
                        </Card>

                        {/* Users */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Total Users</CardTitle>
                                <Users className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">{stats.user_count}</div>
                            </CardContent>
                        </Card>

                        {/* GCS Bucket Size */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
                                <HardDrive className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">
                                    {stats.gcs_bucket_size_gb !== null
                                        ? `${stats.gcs_bucket_size_gb} GB`
                                        : "N/A"}
                                </div>
                            </CardContent>
                        </Card>

                        {/* Documents */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Total Documents</CardTitle>
                                <FileText className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">{stats.document_count}</div>
                            </CardContent>
                        </Card>

                        {/* Reports */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Reports Generated</CardTitle>
                                <FolderOpen className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">{stats.report_count}</div>
                            </CardContent>
                        </Card>
                    </div>
                )}

                {/* Cases by Status */}
                {stats && (
                    <Card>
                        <CardHeader>
                            <CardTitle>Cases by Status</CardTitle>
                            <CardDescription>Distribution of cases across all organizations</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
                                <div className="text-center p-4 rounded-lg bg-green-50 dark:bg-green-950">
                                    <div className="text-2xl font-bold text-green-600">{stats.case_counts.OPEN}</div>
                                    <div className="text-sm text-muted-foreground">Open</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-blue-50 dark:bg-blue-950">
                                    <div className="text-2xl font-bold text-blue-600">{stats.case_counts.CLOSED}</div>
                                    <div className="text-sm text-muted-foreground">Closed</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-yellow-50 dark:bg-yellow-950">
                                    <div className="text-2xl font-bold text-yellow-600">{stats.case_counts.GENERATING}</div>
                                    <div className="text-sm text-muted-foreground">Generating</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-purple-50 dark:bg-purple-950">
                                    <div className="text-2xl font-bold text-purple-600">{stats.case_counts.PROCESSING}</div>
                                    <div className="text-sm text-muted-foreground">Processing</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-red-50 dark:bg-red-950">
                                    <div className="text-2xl font-bold text-red-600">{stats.case_counts.ERROR}</div>
                                    <div className="text-sm text-muted-foreground">Error</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
                                    <div className="text-2xl font-bold text-gray-600">{stats.case_counts.ARCHIVED}</div>
                                    <div className="text-sm text-muted-foreground">Archived</div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Org Drill-down */}
                <Card>
                    <CardHeader>
                        <CardTitle>View Organization Stats</CardTitle>
                        <CardDescription>Select an organization to see detailed statistics</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Select value={selectedOrgId || ""} onValueChange={handleOrgSelect}>
                            <SelectTrigger className="w-full md:w-[300px]">
                                <SelectValue placeholder="Select an organization..." />
                            </SelectTrigger>
                            <SelectContent>
                                {organizations.map((org) => (
                                    <SelectItem key={org.id} value={org.id}>
                                        {org.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
