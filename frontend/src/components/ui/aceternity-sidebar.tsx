"use client";
import { cn } from "@/lib/utils";
import Link from "next/link";
import React, { useState, createContext, useContext } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Menu, X } from "lucide-react";

interface Links {
    label: string;
    href: string;
    icon: React.JSX.Element | React.ReactNode;
    onClick?: () => void;
}

interface SidebarContextProps {
    open: boolean;
    setOpen: React.Dispatch<React.SetStateAction<boolean>>;
    animate: boolean;
}

const SidebarContext = createContext<SidebarContextProps | undefined>(
    undefined
);

export const useSidebar = () => {
    const context = useContext(SidebarContext);
    if (!context) {
        throw new Error("useSidebar must be used within a SidebarProvider");
    }
    return context;
};

export const SidebarProvider = ({
    children,
    open: openProp,
    setOpen: setOpenProp,
    animate = true,
}: {
    children: React.ReactNode;
    open?: boolean;
    setOpen?: React.Dispatch<React.SetStateAction<boolean>>;
    animate?: boolean;
}) => {
    const [openState, setOpenState] = useState(false);

    const open = openProp !== undefined ? openProp : openState;
    const setOpen = setOpenProp !== undefined ? setOpenProp : setOpenState;

    return (
        <SidebarContext.Provider value={{ open, setOpen, animate: animate }}>
            {children}
        </SidebarContext.Provider>
    );
};

export const Sidebar = ({
    children,
    open,
    setOpen,
    animate,
}: {
    children: React.ReactNode;
    open?: boolean;
    setOpen?: React.Dispatch<React.SetStateAction<boolean>>;
    animate?: boolean;
}) => {
    return (
        <SidebarProvider open={open} setOpen={setOpen} animate={animate}>
            {children}
        </SidebarProvider>
    );
};

export const SidebarBody = (props: React.ComponentProps<typeof motion.div>) => {
    return (
        <>
            <DesktopSidebar {...props} />
            <MobileSidebar {...(props as React.ComponentProps<"div">)} />
        </>
    );
};

export const DesktopSidebar = ({
    className,
    children,
    ...props
}: React.ComponentProps<typeof motion.div>) => {
    const { open, setOpen, animate } = useSidebar();
    return (
        <motion.div
            className={cn(
                "h-full px-4 py-4 hidden md:flex md:flex-col bg-card/50 backdrop-blur-xl border-r border-white/5 w-64 shrink-0 noise-surface",
                className
            )}
            animate={{
                width: animate ? (open ? "256px" : "80px") : "256px",
            }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => setOpen(false)}
            {...props}
        >
            {children}
        </motion.div>
    );
};

export const MobileSidebar = ({
    className,
    children,
    ...props
}: React.ComponentProps<"div">) => {
    const { open, setOpen } = useSidebar();
    return (
        <>
            <div
                className={cn(
                    "h-14 px-4 py-4 flex flex-row md:hidden items-center justify-between bg-card border-b border-border w-full"
                )}
                {...props}
            >
                <div className="flex items-center gap-2">
                    <div className="bg-primary text-primary-foreground p-1 rounded">
                        <img src="/perito-logo-black.svg" alt="Perito Logo" className="h-5 w-5 invert" />
                    </div>
                    <img src="/myperito-black.svg" alt="MyPerito" className="h-5 dark:invert" />
                </div>
                <div className="flex justify-end z-20">
                    <Menu
                        className="h-5 w-5 text-foreground cursor-pointer"
                        onClick={() => setOpen(!open)}
                    />
                </div>
            </div>
            <AnimatePresence>
                {open && (
                    <motion.div
                        initial={{ x: "-100%", opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: "-100%", opacity: 0 }}
                        transition={{
                            duration: 0.3,
                            ease: "easeInOut",
                        }}
                        className={cn(
                            "fixed h-full w-full inset-0 bg-card p-6 z-[100] flex flex-col justify-between md:hidden",
                            className
                        )}
                    >
                        <div
                            className="absolute right-6 top-6 z-50 text-foreground cursor-pointer"
                            onClick={() => setOpen(!open)}
                        >
                            <X className="h-5 w-5" />
                        </div>
                        {children}
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};

export const SidebarLink = ({
    link,
    className,
    active,
    ...props
}: {
    link: Links;
    className?: string;
    active?: boolean;
}) => {
    const { open, animate } = useSidebar();

    const content = (
        <>
            {link.icon}
            <motion.span
                animate={{
                    display: animate ? (open ? "inline-block" : "none") : "inline-block",
                    opacity: animate ? (open ? 1 : 0) : 1,
                }}
                className="text-sm group-hover/sidebar:translate-x-1 transition duration-150 whitespace-pre inline-block !p-0 !m-0"
            >
                {link.label}
            </motion.span>
        </>
    );

    const baseClassName = cn(
        "flex items-center justify-start gap-3 group/sidebar py-2 px-3 rounded-md transition-colors",
        active
            ? "bg-primary/10 text-primary"
            : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
        className
    );

    // If there's an onClick handler (like for logout), render a button
    if (link.onClick) {
        return (
            <button
                onClick={link.onClick}
                className={cn(baseClassName, "w-full text-left")}
                {...(props as React.ButtonHTMLAttributes<HTMLButtonElement>)}
            >
                {content}
            </button>
        );
    }

    return (
        <Link
            href={link.href}
            className={baseClassName}
            {...(props as React.AnchorHTMLAttributes<HTMLAnchorElement>)}
        >
            {content}
        </Link>
    );
};
