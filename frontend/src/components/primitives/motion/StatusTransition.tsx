"use client";
import { motion } from "motion/react";
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface StatusTransitionProps {
    /** Current status value - triggers animation on change */
    readonly status: string;
    readonly children: ReactNode;
    readonly className?: string;
}

/**
 * StatusTransition - Micro-interaction wrapper for status changes.
 * Uses motion's key-based remounting to animate on status change.
 *
 * @example
 * <StatusTransition status={doc.ai_status}>
 *   <StatusBadge status={doc.ai_status} />
 * </StatusTransition>
 */
export function StatusTransition({ status, children, className }: StatusTransitionProps) {
    return (
        <motion.div
            key={status}
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
            className={cn(className)}
        >
            {children}
        </motion.div>
    );
}
