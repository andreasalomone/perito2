"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Building2, Plus } from "lucide-react";

interface Organization {
    id: string;
    name: string;
    created_at: string;
}

interface Props {
    onSelectOrganization: (orgId: string) => void;
}

export default function OrganizationManager({ onSelectOrganization }: Props) {
    const { getToken } = useAuth();
    const [organizations, setOrganizations] = useState<Organization[]>([]);
    const [loading, setLoading] = useState(true);
    const [creating, setCreating] = useState(false);
    const [newOrgName, setNewOrgName] = useState("");
    const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);

    useEffect(() => {
        fetchOrganizations();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // Only run on mount

    const fetchOrganizations = async () => {
        try {
            const token = await getToken();
            const response = await axios.get(
                `${process.env.NEXT_PUBLIC_API_URL}/api/admin/organizations`,
                { headers: { Authorization: `Bearer ${token}` } }
            );
            setOrganizations(response.data);
        } catch (error) {
            console.error("Error fetching organizations:", error);
            toast.error("Failed to load organizations");
        } finally {
            setLoading(false);
        }
    };

    const handleCreateOrg = async () => {
        if (!newOrgName.trim()) {
            toast.error("Organization name is required");
            return;
        }

        setCreating(true);
        try {
            const token = await getToken();
            await axios.post(
                `${process.env.NEXT_PUBLIC_API_URL}/api/admin/organizations`,
                { name: newOrgName },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            toast.success("Organization created successfully");
            setNewOrgName("");
            fetchOrganizations();
        } catch (error: any) {
            console.error("Error creating organization:", error);
            toast.error(error.response?.data?.detail || "Failed to create organization");
        } finally {
            setCreating(false);
        }
    };

    const handleSelectOrg = (orgId: string) => {
        setSelectedOrgId(orgId);
        onSelectOrganization(orgId);
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center space-x-2">
                    <Building2 className="h-5 w-5" />
                    <CardTitle>Organizations</CardTitle>
                </div>
                <CardDescription>Create and manage organizations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Create New Organization */}
                <div className="space-y-2">
                    <Label htmlFor="org-name">Create New Organization</Label>
                    <div className="flex space-x-2">
                        <Input
                            id="org-name"
                            placeholder="Organization name"
                            value={newOrgName}
                            onChange={(e) => setNewOrgName(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && handleCreateOrg()}
                        />
                        <Button onClick={handleCreateOrg} disabled={creating}>
                            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                        </Button>
                    </div>
                </div>

                {/* Organizations List */}
                <div className="space-y-2">
                    <Label>Existing Organizations</Label>
                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : organizations.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No organizations yet</p>
                    ) : (
                        <div className="space-y-2 max-h-[400px] overflow-y-auto">
                            {organizations.map((org) => (
                                <button
                                    key={org.id}
                                    onClick={() => handleSelectOrg(org.id)}
                                    className={`w-full text-left p-3 rounded-md border transition-colors ${selectedOrgId === org.id
                                        ? "bg-primary/10 border-primary"
                                        : "bg-card border-border hover:bg-accent"
                                        }`}
                                >
                                    <div className="font-medium">{org.name}</div>
                                    <div className="text-xs text-muted-foreground">
                                        ID: {org.id.slice(0, 8)}...
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
