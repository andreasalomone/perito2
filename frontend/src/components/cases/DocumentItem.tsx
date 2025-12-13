"use client";

import { memo } from "react";
import { Document } from "@/types";
import { StatusBadge, StatusTransition } from "@/components/primitives";
import { File as FileIcon, X } from "lucide-react";

interface DocumentItemProps {
    readonly doc: Document;
    readonly onDelete?: (docId: string) => void;
}

/**
 * DocumentItem - Displays a single document with status badge.
 * Uses centralized StatusBadge for consistent status display.
 * Includes StatusTransition for micro-interactions on status changes.
 */
export const DocumentItem = memo(({ doc, onDelete }: DocumentItemProps) => {
    return (
        <div className="flex flex-col gap-0.5">
            <div className="flex items-center justify-between p-3 border rounded-md bg-background hover:bg-muted/10 transition-colors group">
                <div className="flex items-center gap-3 overflow-hidden">
                    <FileIcon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="truncate text-sm font-medium" title={doc.filename}>{doc.filename}</span>
                </div>
                <div className="flex items-center gap-2">
                    <StatusTransition status={doc.ai_status}>
                        <StatusBadge
                            status={doc.ai_status}
                            type="document"
                            className="text-xs"
                        />
                    </StatusTransition>
                    {onDelete && (
                        <button
                            onClick={() => onDelete(doc.id)}
                            className="p-1 rounded-full text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors opacity-0 group-hover:opacity-100"
                            title="Elimina documento"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    )}
                </div>
            </div>
            {doc.ai_status === "ERROR" && doc.error_message && (
                <p className="text-xs text-destructive pl-10">{doc.error_message}</p>
            )}
        </div>
    );
});
DocumentItem.displayName = "DocumentItem";
