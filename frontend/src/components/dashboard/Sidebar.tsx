"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ShieldCheck, LayoutDashboard, FilePlus, LogOut } from "lucide-react";
import { User } from "firebase/auth";
import { DBUser } from "@/types";
import { cn } from "@/lib/utils";

interface SidebarProps {
    user: User | null;
    dbUser: DBUser | null;
    logout: () => void;
    pathname: string;
    onItemClick?: () => void;
}

export function Sidebar({
    user,
    dbUser,
    logout,
    pathname,
    onItemClick
}: SidebarProps) {
    const navItems = [
        { href: "/dashboard", label: "I Miei Report", icon: LayoutDashboard },
        { href: "/dashboard/create", label: "Nuova Perizia", icon: FilePlus },
    ];

    return (
        <>
            <div className="p-6 border-b border-border/50">
                <div className="flex items-center gap-2 mb-1">
                    <div className="bg-primary text-primary-foreground p-1 rounded">
                        <ShieldCheck className="h-5 w-5" />
                    </div>
                    <h1 className="text-xl font-bold tracking-tight">PeritoAI</h1>
                </div>
                <p className="text-xs text-muted-foreground truncate" title={dbUser?.email || user?.email || ""}>
                    {dbUser?.email || user?.email}
                </p>
            </div>

            <nav className="flex-1 p-4 space-y-1">
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            onClick={onItemClick}
                            className={cn(
                                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                                isActive
                                    ? "bg-primary/10 text-primary"
                                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                            )}
                        >
                            <item.icon className="h-4 w-4" />
                            {item.label}
                        </Link>
                    );
                })}
            </nav>

            <div className="p-4 border-t border-border/50">
                <Button
                    variant="ghost"
                    onClick={() => logout()}
                    className="w-full justify-start gap-3 text-destructive hover:text-destructive hover:bg-destructive/10"
                >
                    <LogOut className="h-4 w-4" />
                    Esci
                </Button>
            </div>
        </>
    );
}
