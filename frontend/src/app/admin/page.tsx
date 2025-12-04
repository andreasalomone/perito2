"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, ShieldAlert } from "lucide-react";
import OrganizationManager from "@/components/admin/OrganizationManager";
import UserInviteManager from "@/components/admin/UserInviteManager";
import { useOrganizations } from "@/hooks/useOrganizations";

export default function AdminPage() {
    const { user, loading: authLoading } = useAuth();
    const router = useRouter();
    const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);

    // We use the organizations list fetch as a proxy for "Is Superadmin?" check.
    // If it fails (403), the user is not a superadmin.
    const { isLoading: orgsLoading, isError } = useOrganizations();

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

    if (isError) {
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
                <div>
                    <h1 className="text-3xl font-bold">Super Admin Panel</h1>
                    <p className="text-muted-foreground">Manage organizations and user access</p>
                </div>

                <div className="grid gap-8 lg:grid-cols-2">
                    <OrganizationManager onSelectOrganization={setSelectedOrgId} />
                    <UserInviteManager selectedOrgId={selectedOrgId} />
                </div>
            </div>
        </div>
    );
}
