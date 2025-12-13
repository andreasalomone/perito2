"use client";
import { motion } from "framer-motion";
import { ReactNode, useEffect, useState, useRef } from "react";
import { cn } from "@/lib/utils";

interface StatusTransitionProps {
    /** Current status value - triggers animation on change */
    readonly status: string;
    readonly children: ReactNode;
    readonly className?: string;
}

/**
 * StatusTransition - Micro-interaction wrapper for status changes.
 * Adds a subtle "pop" animation when status prop changes.
 *
 * @example
 * <StatusTransition status={doc.ai_status}>
 *   <StatusBadge status={doc.ai_status} />
 * </StatusTransition>
 */
export function StatusTransition({ status, children, className }: StatusTransitionProps) {
    const [shouldAnimate, setShouldAnimate] = useState(false);
    const prevStatus = useRef(status);

    useEffect(() => {
        if (prevStatus.current !== status) {
            setShouldAnimate(true);
            prevStatus.current = status;
            const timer = setTimeout(() => setShouldAnimate(false), 500);
            return () => clearTimeout(timer);
        }
    }, [status]);

    return (
        <motion.div
            key={status}
            initial={shouldAnimate ? { scale: 0.9, opacity: 0 } : false}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
            className={cn(className)}
        >
            {children}
        </motion.div>
    );
}
