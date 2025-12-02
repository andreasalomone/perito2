"use client";
import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ShieldCheck, Menu, X } from "lucide-react";
import { Sidebar } from "@/components/dashboard/Sidebar";

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
                        <Sidebar
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
                <Sidebar
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

