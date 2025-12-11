"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, useParams } from "next/navigation";
import { useEffect } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, ShieldAlert, ArrowLeft, Calendar, Clock, FolderOpen } from "lucide-react";
import { api } from "@/lib/api";
import { useOrganizations } from "@/hooks/useOrganizations";
import { UserStats } from "@/types/stats";

export default function UserStatsPage() {
    const { orgId, userId } = useParams<{ orgId: string; userId: string }>();
    const { user, loading: authLoading, getToken } = useAuth();
    const router = useRouter();

    // Check superadmin access
    const { isLoading: orgsLoading, isError: orgsError } = useOrganizations();

    // Fetch user stats
    const { data: stats, isLoading: statsLoading, error: statsError } = useSWR<UserStats>(
        user && orgId && userId ? ["admin-user-stats", orgId, userId] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.admin.getUserStats(token, orgId, userId);
        },
        { revalidateOnFocus: false }
    );

    // Redirect if not logged in
    useEffect(() => {
        if (!authLoading && !user) {
            router.push("/");
        }
    }, [user, authLoading, router]);

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
                    <Button variant="ghost" size="icon" onClick={() => router.push(`/admin/stats/${orgId}`)}>
                        <ArrowLeft className="h-5 w-5" />
                    </Button>
                    <div>
                        <h1 className="text-3xl font-bold">
                            {statsLoading ? "Loading..." : stats?.user_email || "User Stats"}
                        </h1>
                        <p className="text-muted-foreground">Individual user metrics</p>
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
                            <span>Failed to load user statistics</span>
                        </CardContent>
                    </Card>
                )}

                {/* Stats Grid */}
                {stats && (
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {/* Total Cases */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Total Cases</CardTitle>
                                <FolderOpen className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">{stats.total_cases}</div>
                            </CardContent>
                        </Card>

                        {/* Cases Today */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Cases Today</CardTitle>
                                <Clock className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">{stats.cases_today}</div>
                            </CardContent>
                        </Card>

                        {/* Cases Last 7 Days */}
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Last 7 Days</CardTitle>
                                <Calendar className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">{stats.cases_last_7_days}</div>
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
                                    <div className="text-2xl font-bold text-green-600">{stats.cases_by_status.OPEN}</div>
                                    <div className="text-sm text-muted-foreground">Open</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-blue-50 dark:bg-blue-950">
                                    <div className="text-2xl font-bold text-blue-600">{stats.cases_by_status.CLOSED}</div>
                                    <div className="text-sm text-muted-foreground">Closed</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-yellow-50 dark:bg-yellow-950">
                                    <div className="text-2xl font-bold text-yellow-600">{stats.cases_by_status.GENERATING}</div>
                                    <div className="text-sm text-muted-foreground">Generating</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-purple-50 dark:bg-purple-950">
                                    <div className="text-2xl font-bold text-purple-600">{stats.cases_by_status.PROCESSING}</div>
                                    <div className="text-sm text-muted-foreground">Processing</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-red-50 dark:bg-red-950">
                                    <div className="text-2xl font-bold text-red-600">{stats.cases_by_status.ERROR}</div>
                                    <div className="text-sm text-muted-foreground">Error</div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-gray-50 dark:bg-gray-900">
                                    <div className="text-2xl font-bold text-gray-600">{stats.cases_by_status.ARCHIVED}</div>
                                    <div className="text-sm text-muted-foreground">Archived</div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    );
}
