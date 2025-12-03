"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ShieldCheck, Menu, X } from "lucide-react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

export function DashboardLayoutClient({
    children,
}: {
    children: React.ReactNode;
}) {
    const { user, dbUser, loading, logout } = useAuth();
    const router = useRouter();
    const pathname = usePathname();
    const { isOpen, setIsOpen, toggle } = useSidebar();

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    // Close mobile menu on route change
    useEffect(() => {
        setIsOpen(false);
    }, [pathname, setIsOpen]);

    if (loading) {
        return <div className="min-h-screen flex items-center justify-center bg-background text-muted-foreground">Caricamento...</div>;
    }

    if (!user) {
        return null;
    }

    // User authenticated in Firebase but not synced to DB (not whitelisted)
    if (!dbUser) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4 text-center space-y-4">
                <div className="bg-destructive/10 p-3 rounded-full">
                    <ShieldCheck className="h-12 w-12 text-destructive" />
                </div>
                <h1 className="text-2xl font-bold">Accesso Negato</h1>
                <p className="text-muted-foreground max-w-md">
                    Il tuo account non è autorizzato ad accedere a questa applicazione.
                    Contatta l'amministratore per richiedere l'accesso.
                </p>
                <Button variant="outline" onClick={() => logout()}>
                    Torna alla Login
                </Button>
            </div>
        );
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
                <Button variant="ghost" size="icon" onClick={toggle} aria-label={isOpen ? "Chiudi menu" : "Apri menu"}>
                    {isOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                </Button>
            </div>

            {/* Mobile Sidebar Overlay */}
            {isOpen && (
                <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm md:hidden" onClick={() => setIsOpen(false)}>
                    <div className="fixed inset-y-0 left-0 w-64 bg-card border-r border-border shadow-lg flex flex-col animate-in slide-in-from-left duration-200" onClick={e => e.stopPropagation()}>
                        <Sidebar
                            user={user}
                            dbUser={dbUser}
                            logout={logout}
                            pathname={pathname}
                            onItemClick={() => setIsOpen(false)}
                        />
                    </div>
                </div>
            )}

            {/* Desktop Sidebar */}
            <aside className={cn(
                "bg-card/50 backdrop-blur-xl border-r border-white/5 hidden md:flex flex-col h-screen sticky top-0 transition-all duration-300",
                isOpen ? "w-64" : "w-20"
            )}>
                <Sidebar
                    user={user}
                    dbUser={dbUser}
                    logout={logout}
                    pathname={pathname}
                    collapsed={!isOpen}
                    onToggle={toggle}
                />
            </aside>

            {/* Main Content */}
            <motion.main layout className="flex-1 p-4 md:p-8 overflow-y-auto">
                <div className="max-w-5xl mx-auto">
                    {children}
                </div>
            </motion.main>
        </div>
    );
}
