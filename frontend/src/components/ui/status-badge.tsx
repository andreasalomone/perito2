"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
    getCaseStatusConfig,
    getDocStatusConfig,
    StatusConfig,
    BadgeVariant,
} from "@/lib/status-config";
import { CaseStatusType } from "@/types";

interface StatusBadgeProps {
    /** The status value (e.g., "OPEN", "PROCESSING", "SUCCESS") */
    status: string;
    /** Type of status: "case" for case status, "document" for document AI status */
    type: "case" | "document";
    /** Whether to show the status icon (default: true) */
    showIcon?: boolean;
    /** Whether to show the label (default: true) */
    showLabel?: boolean;
    /** Additional className for styling */
    className?: string;
}

/**
 * StatusBadge - Unified status indicator component.
 *
 * Uses centralized config from status-config.ts for consistent styling.
 * Supports both case status and document AI status.
 *
 * @example
 * <StatusBadge status="OPEN" type="case" />
 * <StatusBadge status="PROCESSING" type="document" showLabel={false} />
 */
export function StatusBadge({
    status,
    type,
    showIcon = true,
    showLabel = true,
    className,
}: StatusBadgeProps) {
    const config: StatusConfig = type === "case"
        ? getCaseStatusConfig(status as CaseStatusType)
        : getDocStatusConfig(status);

    const Icon = config.icon;

    return (
        <Badge
            variant={config.variant as BadgeVariant}
            className={cn("flex items-center gap-1", className)}
        >
            {showIcon && (
                <Icon
                    className={cn(
                        "h-3 w-3",
                        config.animate && "animate-spin"
                    )}
                />
            )}
            {showLabel && <span>{config.label}</span>}
        </Badge>
    );
}

/**
 * StatusIcon - Just the icon with proper color, no badge wrapper.
 * Useful for inline indicators.
 */
export function StatusIcon({
    status,
    type,
    className,
}: Omit<StatusBadgeProps, "showIcon" | "showLabel">) {
    const config: StatusConfig = type === "case"
        ? getCaseStatusConfig(status as CaseStatusType)
        : getDocStatusConfig(status);

    const Icon = config.icon;

    return (
        <Icon
            className={cn(
                "h-4 w-4",
                config.colorClass,
                config.animate && "animate-spin",
                className
            )}
        />
    );
}
