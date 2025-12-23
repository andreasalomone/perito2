"use client";
import { motion, HTMLMotionProps } from "motion/react";
import { cn } from "@/lib/utils";

interface FadeInProps extends HTMLMotionProps<"div"> {
    /** Delay before animation starts (seconds) */
    delay?: number;
    /** Duration of fade animation (seconds) */
    duration?: number;
    /** Vertical offset to animate from (pixels) */
    y?: number;
}

/**
 * FadeIn - Simple fade-in wrapper with optional vertical slide.
 *
 * @example
 * <FadeIn delay={0.2}>
 *   <Card>Content</Card>
 * </FadeIn>
 */
export function FadeIn({
    children,
    className,
    delay = 0,
    duration = 0.3,
    y = 10,
    ...props
}: FadeInProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration, delay, ease: "easeOut" }}
            className={cn(className)}
            {...props}
        >
            {children}
        </motion.div>
    );
}
