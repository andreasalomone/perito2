"use client";

import * as React from "react";

const SidebarContext = React.createContext<{
    isOpen: boolean;
    toggle: () => void;
    setIsOpen: (open: boolean) => void;
} | null>(null);

export function SidebarProvider({
    children,
    defaultOpen = true,
}: {
    children: React.ReactNode;
    defaultOpen?: boolean;
}) {
    const [isOpen, setIsOpen] = React.useState(defaultOpen);

    const toggle = React.useCallback(() => {
        setIsOpen((prev) => {
            const next = !prev;
            document.cookie = `sidebar:state=${next}; path=/; max-age=31536000`;
            return next;
        });
    }, []);

    const setOpen = React.useCallback((open: boolean) => {
        setIsOpen(open);
        document.cookie = `sidebar:state=${open}; path=/; max-age=31536000`;
    }, []);

    return (
        <SidebarContext.Provider value={{ isOpen, toggle, setIsOpen: setOpen }}>
            {children}
        </SidebarContext.Provider>
    );
}

export function useSidebar() {
    const context = React.useContext(SidebarContext);
    if (!context) {
        throw new Error("useSidebar must be used within a SidebarProvider");
    }
    return context;
}
