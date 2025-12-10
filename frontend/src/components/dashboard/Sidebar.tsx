"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { LayoutDashboard, FilePlus, LogOut, User as UserIcon, ChevronLeft, ChevronRight } from "lucide-react";
import { User } from "firebase/auth";
import { DBUser } from "@/types";
import { cn } from "@/lib/utils";

import { motion } from "framer-motion";

interface SidebarProps {
    user: User | null;
    dbUser: DBUser | null;
    logout: () => void;
    pathname: string;
    onItemClick?: () => void;
    collapsed?: boolean;
    onToggle?: () => void;
}

export function Sidebar({
    user,
    dbUser,
    logout,
    pathname,
    onItemClick,
    collapsed = false,
    onToggle
}: SidebarProps) {
    const navItems = [
        { href: "/dashboard", label: "I Miei Report", icon: LayoutDashboard },
        { href: "/dashboard/create", label: "Nuova Perizia", icon: FilePlus },
        { href: "/dashboard/profile", label: "Profilo", icon: UserIcon },
    ];

    return (
        <>
            <div className={cn("p-6 border-b border-white/5 flex items-center justify-between", collapsed && "p-4 justify-center")}>
                <div className="flex items-center gap-2">
                    <div className="bg-primary text-primary-foreground p-1 rounded">
                        <img src="/perito-logo-black.svg" alt="Perito Logo" className="h-5 w-5 invert" />
                    </div>
                    {!collapsed && (
                        <motion.div
                            initial={{ opacity: 0, width: 0 }}
                            animate={{ opacity: 1, width: "auto" }}
                            exit={{ opacity: 0, width: 0 }}
                            className="overflow-hidden"
                        >
                            <img src="/myperito-black.svg" alt="PeritoAI" className="h-5 dark:invert" />
                        </motion.div>
                    )}
                </div>
                {!collapsed && onToggle && (
                    <Button variant="ghost" size="icon" onClick={onToggle} className="h-6 w-6 ml-auto">
                        <ChevronLeft className="h-4 w-4" />
                    </Button>
                )}
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
                                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors relative group",
                                isActive
                                    ? "bg-primary/10 text-primary"
                                    : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
                                collapsed && "justify-center px-2"
                            )}
                            title={collapsed ? item.label : undefined}
                        >
                            <item.icon className="h-4 w-4 shrink-0" />
                            {!collapsed && (
                                <motion.span
                                    initial={{ opacity: 0, width: 0 }}
                                    animate={{ opacity: 1, width: "auto" }}
                                    exit={{ opacity: 0, width: 0 }}
                                    className="whitespace-nowrap overflow-hidden"
                                >
                                    {item.label}
                                </motion.span>
                            )}
                        </Link>
                    );
                })}
            </nav>

            <div className={cn("p-4 border-t border-white/5", collapsed && "items-center flex flex-col")}>
                {collapsed && onToggle && (
                    <Button variant="ghost" size="icon" onClick={onToggle} className="mb-4">
                        <ChevronRight className="h-4 w-4" />
                    </Button>
                )}

                {!collapsed && (
                    <div className="mb-4 px-2">
                        <p className="text-xs text-muted-foreground truncate" title={dbUser?.email || user?.email || ""}>
                            {dbUser?.email || user?.email}
                        </p>
                    </div>
                )}

                <Button
                    variant="ghost"
                    onClick={() => logout()}
                    className={cn(
                        "w-full justify-start gap-3 text-destructive hover:text-destructive hover:bg-destructive/10",
                        collapsed && "justify-center px-0"
                    )}
                    aria-label="Esci"
                >
                    <LogOut className="h-4 w-4 shrink-0" />
                    {!collapsed && (
                        <motion.span
                            initial={{ opacity: 0, width: 0 }}
                            animate={{ opacity: 1, width: "auto" }}
                            exit={{ opacity: 0, width: 0 }}
                            className="whitespace-nowrap overflow-hidden"
                        >
                            Esci
                        </motion.span>
                    )}
                </Button>
            </div>
        </>
    );
}
