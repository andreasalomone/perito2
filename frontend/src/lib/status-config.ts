import { CaseStatusType } from "@/types";
import { LucideIcon, FolderOpen, Loader2, Cog, AlertCircle, CheckCircle, Clock, FileText } from "lucide-react";

/**
 * Centralized status configuration for consistent UI across the app.
 * Change labels, colors, icons in ONE place.
 */

// Badge variants matching shadcn/ui Badge component
export type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "success";

export interface StatusConfig {
    label: string;
    variant: BadgeVariant;
    icon: LucideIcon;
    /** Tailwind color class for text (when not using Badge) */
    colorClass: string;
    /** Whether icon should animate (e.g., spin for loading) */
    animate?: boolean;
}

// ============================================
// CASE STATUS CONFIG
// ============================================
export const CASE_STATUS_CONFIG: Record<CaseStatusType, StatusConfig> = {
    OPEN: {
        label: "Aperto",
        variant: "default",
        icon: FolderOpen,
        colorClass: "text-blue-600 dark:text-blue-400",
    },
    GENERATING: {
        label: "Generazione",
        variant: "secondary",
        icon: Loader2,
        colorClass: "text-amber-600 dark:text-amber-400",
        animate: true,
    },
    PROCESSING: {
        label: "Elaborazione",
        variant: "secondary",
        icon: Cog,
        colorClass: "text-purple-600 dark:text-purple-400",
        animate: true,
    },
    ERROR: {
        label: "Errore",
        variant: "destructive",
        icon: AlertCircle,
        colorClass: "text-red-600 dark:text-red-400",
    },
    CLOSED: {
        label: "Chiuso",
        variant: "success",
        icon: CheckCircle,
        colorClass: "text-green-600 dark:text-green-400",
    },
    ARCHIVED: {
        label: "Archiviato",
        variant: "outline",
        icon: FileText,
        colorClass: "text-muted-foreground",
    },
};

// ============================================
// DOCUMENT AI STATUS CONFIG
// ============================================
export type DocAIStatus = "PENDING" | "PROCESSING" | "SUCCESS" | "ERROR" | "SKIPPED";

export const DOC_STATUS_CONFIG: Record<DocAIStatus, StatusConfig> = {
    PENDING: {
        label: "In Attesa",
        variant: "outline",
        icon: Clock,
        colorClass: "text-muted-foreground",
    },
    PROCESSING: {
        label: "Elaborazione",
        variant: "secondary",
        icon: Loader2,
        colorClass: "text-purple-600 dark:text-purple-400",
        animate: true,
    },
    SUCCESS: {
        label: "Completato",
        variant: "default",
        icon: CheckCircle,
        colorClass: "text-green-600 dark:text-green-400",
    },
    ERROR: {
        label: "Errore",
        variant: "destructive",
        icon: AlertCircle,
        colorClass: "text-red-600 dark:text-red-400",
    },
    SKIPPED: {
        label: "Saltato",
        variant: "outline",
        icon: FileText,
        colorClass: "text-muted-foreground",
    },
};

// ============================================
// HELPER FUNCTIONS
// ============================================

export function getCaseStatusConfig(status: CaseStatusType): StatusConfig {
    return CASE_STATUS_CONFIG[status] ?? CASE_STATUS_CONFIG.OPEN;
}

export function getDocStatusConfig(status: string): StatusConfig {
    return DOC_STATUS_CONFIG[status as DocAIStatus] ?? DOC_STATUS_CONFIG.PENDING;
}
