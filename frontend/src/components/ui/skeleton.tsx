"use client";

import { cn } from "@/lib/utils";

type SkeletonProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Skeleton - Loading placeholder component
 * Standard shadcn-style skeleton for loading states
 */
export function Skeleton({ className, ...props }: SkeletonProps) {
    return (
        <div
            className={cn(
                "animate-pulse rounded-md bg-muted",
                className
            )}
            {...props}
        />
    );
}
