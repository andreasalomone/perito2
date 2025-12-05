"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/context/AuthContext";
import { useConfig } from "@/context/ConfigContext";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, UserPlus, Trash2, Users } from "lucide-react";
import { useInvites } from "@/hooks/useInvites";

interface Props {
    selectedOrgId: string | null;
}

export default function UserInviteManager({ selectedOrgId }: Props) {
    const { getToken } = useAuth();
    const { apiUrl } = useConfig();
    const { invites, isLoading: loading, mutate } = useInvites(selectedOrgId);
    const [inviting, setInviting] = useState(false);
    const [newEmail, setNewEmail] = useState("");
    const [newRole, setNewRole] = useState("MEMBER");

    const handleInviteUser = async () => {
        if (!selectedOrgId) {
            toast.error("Please select an organization first");
            return;
        }

        if (!newEmail.trim()) {
            toast.error("Email is required");
            return;
        }

        setInviting(true);
        try {
            const token = await getToken();
            await axios.post(
                `${apiUrl}/api/v1/admin/organizations/${selectedOrgId}/users/invite`,
                { email: newEmail, role: newRole },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            toast.success(`${newEmail} invited successfully`);
            setNewEmail("");
            setNewRole("MEMBER");
            mutate(); // Refresh list
        } catch (error: any) {
            console.error("Error inviting user:", error);
            toast.error(error.response?.data?.detail || "Failed to invite user");
        } finally {
            setInviting(false);
        }
    };

    const handleDeleteInvite = async (inviteId: string, email: string) => {
        try {
            const token = await getToken();
            await axios.delete(
                `${apiUrl}/api/v1/admin/invites/${inviteId}`,
                { headers: { Authorization: `Bearer ${token}` } }
            );
            toast.success(`Removed ${email}`);
            mutate(); // Refresh list
        } catch (error: any) {
            console.error("Error deleting invite:", error);
            toast.error(error.response?.data?.detail || "Failed to remove invite");
        }
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center space-x-2">
                    <Users className="h-5 w-5" />
                    <CardTitle>User Invitations</CardTitle>
                </div>
                <CardDescription>
                    {selectedOrgId ? "Whitelist users for the selected organization" : "Select an organization to manage users"}
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {!selectedOrgId ? (
                    <div className="flex items-center justify-center py-12 text-muted-foreground">
                        <p>← Select an organization first</p>
                    </div>
                ) : (
                    <>
                        {/* Invite New User */}
                        <div className="space-y-3">
                            <Label>Invite New User</Label>
                            <div className="space-y-2">
                                <Input
                                    type="email"
                                    placeholder="user@example.com"
                                    value={newEmail}
                                    onChange={(e) => setNewEmail(e.target.value)}
                                    onKeyDown={(e) => e.key === "Enter" && handleInviteUser()}
                                />
                                <div className="flex space-x-2">
                                    <Select value={newRole} onValueChange={setNewRole}>
                                        <SelectTrigger className="w-[180px]">
                                            <SelectValue placeholder="Select role" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="MEMBER">Member</SelectItem>
                                            <SelectItem value="ADMIN">Admin</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Button onClick={handleInviteUser} disabled={inviting} className="flex-1">
                                        {inviting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <UserPlus className="mr-2 h-4 w-4" />}
                                        Invite
                                    </Button>
                                </div>
                            </div>
                        </div>

                        {/* Invites List */}
                        <div className="space-y-2">
                            <Label>Whitelisted Users</Label>
                            {loading ? (
                                <div className="flex items-center justify-center py-8">
                                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : invites.length === 0 ? (
                                <p className="text-sm text-muted-foreground">No users whitelisted yet</p>
                            ) : (
                                <ul className="space-y-2 max-h-[400px] overflow-y-auto list-none" role="list">
                                    {invites.map((invite) => (
                                        <li
                                            key={invite.id}
                                            className="flex items-center justify-between p-3 rounded-md border bg-card"
                                        >
                                            <div className="flex-1">
                                                <div className="font-medium">{invite.email}</div>
                                                <div className="text-xs text-muted-foreground capitalize">
                                                    Role: {invite.role}
                                                </div>
                                            </div>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleDeleteInvite(invite.id, invite.email)}
                                            >
                                                <Trash2 className="h-4 w-4 text-destructive" />
                                            </Button>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
}

