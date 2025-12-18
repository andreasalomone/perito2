"use client";

import React, {
    useState,
    useContext,
    createContext,
    useCallback,
    useEffect,
    useId,
} from "react";
import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";
import { createPortal } from "react-dom";

interface ExpandableScreenContextType {
    isExpanded: boolean;
    expand: () => void;
    collapse: () => void;
    layoutId: string;
    triggerRadius: string;
    contentRadius: string;
    animationDuration: number;
}

const ExpandableScreenContext = createContext<
    ExpandableScreenContextType | undefined
>(undefined);

export interface ExpandableScreenProps {
    children: React.ReactNode;
    layoutId?: string;
    triggerRadius?: string;
    contentRadius?: string;
    animationDuration?: number;
    defaultExpanded?: boolean;
    onExpandChange?: (expanded: boolean) => void;
    lockScroll?: boolean;
}

export function ExpandableScreen({
    children,
    layoutId,
    triggerRadius = "12px",
    contentRadius = "16px",
    animationDuration = 0.3,
    defaultExpanded = false,
    onExpandChange,
    lockScroll = true,
}: Readonly<ExpandableScreenProps>) {
    const uniqueId = useId();
    const finalLayoutId = layoutId || `expandable-screen-${uniqueId}`;
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    const handleExpandChange = useCallback(
        (expanded: boolean) => {
            setIsExpanded(expanded);
            onExpandChange?.(expanded);
        },
        [onExpandChange]
    );

    const expand = useCallback(() => handleExpandChange(true), [handleExpandChange]);
    const collapse = useCallback(
        () => handleExpandChange(false),
        [handleExpandChange]
    );

    useEffect(() => {
        if (lockScroll && isExpanded) {
            document.body.style.overflow = "hidden";
        } else {
            document.body.style.overflow = "";
        }
        return () => {
            document.body.style.overflow = "";
        };
    }, [isExpanded, lockScroll]);

    const value = React.useMemo(
        () => ({
            isExpanded,
            expand,
            collapse,
            layoutId: finalLayoutId,
            triggerRadius,
            contentRadius,
            animationDuration,
        }),
        [
            isExpanded,
            expand,
            collapse,
            finalLayoutId,
            triggerRadius,
            contentRadius,
            animationDuration,
        ]
    );

    return (
        <ExpandableScreenContext.Provider value={value}>
            <MotionConfig transition={{ duration: animationDuration, ease: "easeInOut" }}>
                {children}
            </MotionConfig>
        </ExpandableScreenContext.Provider>
    );
}

export function ExpandableScreenTrigger({
    children,
    className,
}: Readonly<{
    children: React.ReactNode;
    className?: string;
}>) {
    const context = useContext(ExpandableScreenContext);
    if (!context) throw new Error("ExpandableScreenTrigger must be used within ExpandableScreen");

    const { isExpanded, expand, layoutId, triggerRadius } = context;

    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            expand();
        }
    }, [expand]);

    return (
        <div className={cn("relative", className)}>
            <motion.div
                layoutId={layoutId}
                className="w-full h-full cursor-pointer"
                style={{ borderRadius: triggerRadius }}
                onClick={expand}
                onKeyDown={handleKeyDown}
                role="button"
                tabIndex={isExpanded ? -1 : 0}
                aria-expanded={isExpanded}
                initial={{ opacity: 1 }}
                animate={{ opacity: isExpanded ? 0 : 1 }}
                transition={{ duration: 0.2 }}
            >
                {children}
            </motion.div>
        </div>
    );
}

export function ExpandableScreenContent({
    children,
    className,
    showCloseButton = true,
    closeButtonClassName,
}: Readonly<{
    children: React.ReactNode;
    className?: string;
    showCloseButton?: boolean;
    closeButtonClassName?: string;
}>) {
    const context = useContext(ExpandableScreenContext);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!context) throw new Error("ExpandableScreenContent must be used within ExpandableScreen");
    if (!mounted) return null;

    const { isExpanded, collapse, layoutId, contentRadius } = context;

    return createPortal(
        <AnimatePresence>
            {isExpanded && (
                <React.Fragment>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm"
                        onClick={collapse}
                    />

                    {/* Expanded Content */}
                    <motion.div
                        layoutId={layoutId}
                        className={cn(
                            "fixed inset-[10%] z-50 flex flex-col bg-background text-foreground shadow-2xl overflow-hidden",
                            className
                        )}
                        style={{ borderRadius: contentRadius }}
                    >
                        {showCloseButton && (
                            <button
                                onClick={collapse}
                                className={cn(
                                    "absolute left-4 top-4 z-10 rounded-full p-2 bg-background/50 hover:bg-background/80 transition-colors",
                                    closeButtonClassName
                                )}
                                aria-label="Close"
                            >
                                <X className="h-6 w-6" />
                            </button>
                        )}
                        <motion.div
                            className="h-full w-full overflow-auto"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.1 }}
                        >
                            {children}
                        </motion.div>
                    </motion.div>
                </React.Fragment>
            )}
        </AnimatePresence>,
        document.body
    );
}

export function useExpandableScreen() {
    const context = useContext(ExpandableScreenContext);
    if (!context) {
        throw new Error("useExpandableScreen must be used within an ExpandableScreen");
    }
    return context;
}
