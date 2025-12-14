"use client";

import { Skeleton } from "@/components/primitives";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReportGeneratingSkeletonProps {
    /** Skeleton structure variant */
    variant?: "report" | "analysis";
    /** Estimated completion time (e.g., "~15 sec") */
    estimatedTime?: string;
    /** Additional class names */
    className?: string;
}

/**
 * ReportGeneratingSkeleton - Rich skeleton for AI generation states
 *
 * Shows a "ghost report" that matches expected output structure,
 * reducing perceived wait time by signaling competence and progress.
 */
export function ReportGeneratingSkeleton({
    variant = "report",
    estimatedTime = "~15 sec",
    className,
}: ReportGeneratingSkeletonProps) {
    return (
        <div className={cn("rounded-lg border bg-card overflow-hidden", className)}>
            {/* Header with spinner and estimated time */}
            <div className="bg-muted/30 p-3 flex items-center justify-between border-b">
                <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <span className="text-sm font-medium text-primary">
                        {variant === "report" ? "Generazione in corso..." : "Analisi in corso..."}
                    </span>
                </div>
                <span className="text-xs text-muted-foreground">{estimatedTime}</span>
            </div>

            {/* Skeleton Content */}
            <div className="space-y-6 p-6 animate-pulse">
                {variant === "report" ? (
                    <ReportSkeleton />
                ) : (
                    <AnalysisSkeleton />
                )}
            </div>
        </div>
    );
}

/** Report skeleton: title, meta, paragraphs, sections with bullets */
function ReportSkeleton() {
    return (
        <>
            {/* Title & Meta */}
            <div className="space-y-2">
                <Skeleton className="h-8 w-2/3 bg-primary/10" />
                <Skeleton className="h-4 w-1/2" />
            </div>

            {/* Summary Paragraph */}
            <div className="space-y-2 pt-4 border-t">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-4/5" />
            </div>

            {/* Section 1 */}
            <div className="space-y-3 pt-4">
                <Skeleton className="h-6 w-1/3 bg-primary/5" />
                <div className="pl-4 space-y-2">
                    <Skeleton className="h-4 w-11/12" />
                    <Skeleton className="h-4 w-10/12" />
                </div>
            </div>

            {/* Section 2 with bullets */}
            <div className="space-y-3 pt-4">
                <Skeleton className="h-6 w-2/5 bg-primary/5" />
                <div className="pl-4 space-y-2">
                    <BulletSkeleton width="w-4/5" />
                    <BulletSkeleton width="w-3/4" />
                    <BulletSkeleton width="w-2/3" />
                </div>
            </div>
        </>
    );
}

/** Analysis skeleton: simpler structure for document analysis */
function AnalysisSkeleton() {
    return (
        <>
            {/* Summary */}
            <div className="space-y-2">
                <Skeleton className="h-5 w-1/2 bg-primary/10" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
            </div>

            {/* Two-column grid skeleton */}
            <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                {/* Received docs */}
                <div className="space-y-2">
                    <Skeleton className="h-4 w-24 bg-green-500/10" />
                    <div className="space-y-1.5">
                        <Skeleton className="h-3 w-full" />
                        <Skeleton className="h-3 w-4/5" />
                        <Skeleton className="h-3 w-3/5" />
                    </div>
                </div>
                {/* Missing docs */}
                <div className="space-y-2">
                    <Skeleton className="h-4 w-24 bg-red-500/10" />
                    <div className="space-y-1.5">
                        <Skeleton className="h-3 w-4/5" />
                        <Skeleton className="h-3 w-3/4" />
                    </div>
                </div>
            </div>
        </>
    );
}

/** Bullet point skeleton row */
function BulletSkeleton({ width }: { width: string }) {
    return (
        <div className="flex items-start gap-2">
            <Skeleton className="h-3 w-3 rounded-full shrink-0 mt-1" />
            <Skeleton className={cn("h-4", width)} />
        </div>
    );
}
