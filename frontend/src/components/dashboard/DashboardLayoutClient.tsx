/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { ShieldCheck, LayoutDashboard, FilePlus, LogOut, User as UserIcon, Users } from "lucide-react";
import { Sidebar, SidebarBody, SidebarLink, useSidebar } from "@/components/ui/aceternity-sidebar";
import { ModeToggle } from "@/components/primitives";
import { motion } from "motion/react";

export function DashboardLayoutClient({
    children,
}: {
    children: React.ReactNode;
}) {
    const { user, dbUser, loading, logout } = useAuth();
    const router = useRouter();
    const pathname = usePathname();
    const prevPathnameRef = useRef(pathname);
    // Initialize as closed - will only open when user explicitly opens it
    const [open, setOpen] = useState(false);

    useEffect(() => {
        if (!loading && !user) {
            router.push("/");
        }
    }, [user, loading, router]);

    // Close mobile menu on route change
    // This is a valid use case for setState in effect - syncing UI state with external navigation
    // eslint-disable-next-line react-hooks/set-state-in-effect
    useEffect(() => {
        if (prevPathnameRef.current !== pathname && open) {
            setOpen(false);
        }
        prevPathnameRef.current = pathname;
    }, [pathname, open]);

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
                    Contatta l&apos;amministratore per richiedere l&apos;accesso.
                </p>
                <Button variant="outline" onClick={() => logout()}>
                    Torna al Login
                </Button>
            </div>
        );
    }

    const navLinks = [
        { href: "/dashboard", label: "I Miei Report", icon: <LayoutDashboard className="h-5 w-5 shrink-0" /> },
        { href: "/dashboard/clienti", label: "Clienti", icon: <Users className="h-5 w-5 shrink-0" /> },
        { href: "/dashboard/create", label: "Nuova Perizia", icon: <FilePlus className="h-5 w-5 shrink-0" /> },
        { href: "/dashboard/profile", label: "Profilo", icon: <UserIcon className="h-5 w-5 shrink-0" /> },
    ];

    return (
        <div className="min-h-screen md:h-screen bg-canvas flex flex-col md:flex-row md:overflow-hidden">
            <Sidebar open={open} setOpen={setOpen}>
                <SidebarBody className="justify-between gap-10">
                    <div className="flex flex-1 flex-col overflow-x-hidden overflow-y-auto">
                        {/* Logo */}
                        {open ? <Logo /> : <LogoIcon />}

                        {/* Navigation */}
                        <div className="mt-8 flex flex-col gap-1">
                            {navLinks.map((link) => (
                                <SidebarLink
                                    key={link.href}
                                    link={link}
                                    active={pathname === link.href}
                                />
                            ))}
                        </div>
                    </div>

                    {/* Footer */}
                    <div className="flex flex-col gap-2">
                        <div className="px-3">
                            <ModeToggle />
                        </div>

                        {/* Email */}
                        <motion.div
                            animate={{
                                display: open ? "block" : "none",
                                opacity: open ? 1 : 0,
                            }}
                            className="px-3 py-2"
                        >
                            <p className="text-xs text-muted-foreground truncate" title={dbUser?.email || user?.email || ""}>
                                {dbUser?.email || user?.email}
                            </p>
                        </motion.div>

                        {/* Logout */}
                        <SidebarLink
                            link={{
                                label: "Esci",
                                href: "#",
                                icon: <LogOut className="h-5 w-5 shrink-0 text-destructive" />,
                                onClick: () => logout(),
                            }}
                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        />
                    </div>
                </SidebarBody>
            </Sidebar>

            {/* Main Content */}
            <main className="flex-1 p-4 md:p-8 overflow-y-auto">
                <div className="w-full mx-auto">
                    {children}
                </div>
            </main>
        </div>
    );
}

const Logo = () => {
    return (
        <div className="flex items-center gap-2 py-1">
            <div className="bg-primary text-primary-foreground p-1 rounded shrink-0">
                <img src="/perito-logo-black.svg" alt="Perito Logo" className="h-5 w-5 invert" />
            </div>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="overflow-hidden"
            >
                <img src="/myperito-black.svg" alt="MyPerito" className="h-5 dark:invert" />
            </motion.div>
        </div>
    );
};

const LogoIcon = () => {
    return (
        <div className="flex items-center py-1">
            <div className="bg-primary text-primary-foreground p-1 rounded">
                <img src="/perito-logo-black.svg" alt="Perito Logo" className="h-5 w-5 invert" />
            </div>
        </div>
    );
};
