"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, useParams } from "next/navigation";
import { useState, useEffect } from "react";
import useSWR from "swr";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, ShieldAlert, ArrowLeft, Users, FileText, FolderOpen, User } from "lucide-react";
import { api } from "@/lib/api";
import { useOrganizations } from "@/hooks/useOrganizations";
import { OrgStats } from "@/types/stats";

export default function OrgStatsPage() {
    const { orgId } = useParams<{ orgId: string }>();
    const { user, loading: authLoading, getToken } = useAuth();
    const router = useRouter();
    const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

    // Check superadmin access
    const { isLoading: orgsLoading, isError: orgsError } = useOrganizations();

    // Fetch org stats
    const { data: stats, isLoading: statsLoading, error: statsError } = useSWR<OrgStats>(
        user && orgId ? ["admin-org-stats", orgId] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.admin.getOrgStats(token, orgId);
        },
        { revalidateOnFocus: true }
    );

    // Redirect if not logged in
    useEffect(() => {
        if (!authLoading && !user) {
            router.push("/");
        }
    }, [user, authLoading, router]);

    // Handle user selection
    const handleUserSelect = (userId: string) => {
        setSelectedUserId(userId);
        router.push(`/admin/stats/${orgId}/${userId}`);
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
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => router.push("/admin/stats")}>
                        <ArrowLeft className="h-5 w-5" />
                    </Button>
                    <div>
                        <h1 className="text-3xl font-bold">
                            {statsLoading ? "Loading..." : stats?.org_name || "Organization Stats"}
                        </h1>
                        <p className="text-muted-foreground">Organization-level metrics</p>
                    </div>
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
                            <span>Failed to load organization statistics</span>
                        </CardContent>
                    </Card>
                )}

                {/* Stats Grid */}
                {stats && (
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {/* Users */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Users in Org</CardTitle>
                                <Users className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">{stats.user_count}</div>
                            </CardContent>
                        </Card>

                        {/* Documents */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Documents</CardTitle>
                                <FileText className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">{stats.document_count}</div>
                            </CardContent>
                        </Card>

                        {/* Total Cases */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Total Cases</CardTitle>
                                <FolderOpen className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">
                                    {stats.case_counts.OPEN + stats.case_counts.CLOSED + stats.case_counts.ERROR +
                                        stats.case_counts.GENERATING + stats.case_counts.PROCESSING + stats.case_counts.ARCHIVED}
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                )}

                {/* Cases by Status */}
                {stats && (
                    <Card>
                        <CardHeader>
                            <CardTitle>Cases by Status</CardTitle>
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

                {/* User Drill-down */}
                {stats && stats.users.length > 0 && (
                    <Card>
                        <CardHeader>
                            <CardTitle>View User Stats</CardTitle>
                            <CardDescription>Select a user to see detailed statistics</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Select value={selectedUserId || ""} onValueChange={handleUserSelect}>
                                <SelectTrigger className="w-full md:w-[400px]">
                                    <SelectValue placeholder="Select a user..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {stats.users.map((u) => (
                                        <SelectItem key={u.id} value={u.id}>
                                            <div className="flex items-center gap-2">
                                                <User className="h-4 w-4" />
                                                <span>{u.email}</span>
                                                {u.first_name && u.last_name && (
                                                    <span className="text-muted-foreground">
                                                        ({u.first_name} {u.last_name})
                                                    </span>
                                                )}
                                            </div>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    );
}
