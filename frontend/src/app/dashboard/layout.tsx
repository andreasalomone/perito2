"use client";
import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ShieldCheck, LayoutDashboard, FilePlus, LogOut, Menu, X } from "lucide-react";
import { User } from "firebase/auth";
import { DBUser } from "@/types";
import { cn } from "@/lib/utils";

// Extracted Sidebar Component
const SidebarContent = ({
    user,
    dbUser,
    logout,
    pathname,
    onItemClick
}: {
    user: User | null,
    dbUser: DBUser | null,
    logout: () => void,
    pathname: string,
    onItemClick?: () => void
}) => {
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
};

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const { user, dbUser, loading, logout } = useAuth();
    const router = useRouter();
    const pathname = usePathname();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    // Close mobile menu on route change
    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setIsMobileMenuOpen(false);
    }, [pathname]);

    if (loading) {
        return <div className="min-h-screen flex items-center justify-center bg-background text-muted-foreground">Caricamento...</div>;
    }

    if (!user) {
        return null;
    }

    return (
        <div className="min-h-screen bg-muted/30 flex flex-col md:flex-row">
            {/* Mobile Header */}
            <div className="md:hidden flex items-center justify-between p-4 bg-card border-b border-border sticky top-0 z-20">
                <div className="flex items-center gap-2">
                    <div className="bg-primary text-primary-foreground p-1 rounded">
                        <ShieldCheck className="h-5 w-5" />
                    </div>
                    <h1 className="text-lg font-bold">PeritoAI</h1>
                </div>
                <Button variant="ghost" size="icon" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}>
                    {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                </Button>
            </div>

            {/* Mobile Sidebar Overlay */}
            {isMobileMenuOpen && (
                <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm md:hidden" onClick={() => setIsMobileMenuOpen(false)}>
                    <div className="fixed inset-y-0 left-0 w-64 bg-card border-r border-border shadow-lg flex flex-col animate-in slide-in-from-left duration-200" onClick={e => e.stopPropagation()}>
                        <SidebarContent
                            user={user}
                            dbUser={dbUser}
                            logout={logout}
                            pathname={pathname}
                            onItemClick={() => setIsMobileMenuOpen(false)}
                        />
                    </div>
                </div>
            )}

            {/* Desktop Sidebar */}
            <aside className="w-64 bg-card border-r border-border hidden md:flex flex-col h-screen sticky top-0">
                <SidebarContent
                    user={user}
                    dbUser={dbUser}
                    logout={logout}
                    pathname={pathname}
                />
            </aside>

            {/* Main Content */}
            <main className="flex-1 p-4 md:p-8 overflow-y-auto">
                <div className="max-w-5xl mx-auto">
                    {children}
                </div>
            </main>
        </div>
    );
}
