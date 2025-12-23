"use client";
import { motion, Variants } from "motion/react";
import { cn } from "@/lib/utils";
import { ReactNode } from "react";

const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: 0.08,
            delayChildren: 0.1,
        },
    },
};

const itemVariants: Variants = {
    hidden: { opacity: 0, y: 8 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.25, ease: "easeOut" }
    },
};

interface StaggerListProps {
    readonly children: ReactNode;
    readonly className?: string;
}

/**
 * StaggerList - Container for staggered list animations.
 * Wrap list items with StaggerItem for each to animate in sequence.
 *
 * @example
 * <StaggerList className="grid gap-2">
 *   {items.map(item => (
 *     <StaggerItem key={item.id}>
 *       <ItemCard {...item} />
 *     </StaggerItem>
 *   ))}
 * </StaggerList>
 */
export function StaggerList({ children, className }: StaggerListProps) {
    return (
        <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className={cn(className)}
        >
            {children}
        </motion.div>
    );
}

/**
 * StaggerItem - Individual item wrapper within a StaggerList.
 * Inherits stagger timing from parent StaggerList.
 */
export function StaggerItem({ children, className }: StaggerListProps) {
    return (
        <motion.div variants={itemVariants} className={cn(className)}>
            {children}
        </motion.div>
    );
}
