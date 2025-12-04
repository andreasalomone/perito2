"use client";

import { memo } from "react";
import { Document } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle, AlertCircle, Clock, File as FileIcon } from "lucide-react";

export const DocumentItem = memo(({ doc }: { doc: Document }) => {
    const getStatusColor = (status: string) => {
        switch (status) {
            case "SUCCESS": return "default"; // Black/Primary
            case "PROCESSING": return "secondary"; // Gray
            case "ERROR": return "destructive"; // Red
            default: return "outline";
        }
    };

    const getStatusIcon = (status: string) => {
        if (status === "PROCESSING") return <Loader2 className="h-3 w-3 animate-spin mr-1" />;
        if (status === "SUCCESS") return <CheckCircle className="h-3 w-3 mr-1" />;
        if (status === "ERROR") return <AlertCircle className="h-3 w-3 mr-1" />;
        return <Clock className="h-3 w-3 mr-1" />;
    };

    return (
        <div className="flex items-center justify-between p-3 border rounded-md bg-background hover:bg-muted/10 transition-colors">
            <div className="flex items-center gap-3 overflow-hidden">
                <FileIcon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <span className="truncate text-sm font-medium" title={doc.filename}>{doc.filename}</span>
            </div>
            <Badge variant={getStatusColor(doc.ai_status) as any} className="text-xs flex items-center">
                {getStatusIcon(doc.ai_status)}
                {doc.ai_status}
            </Badge>
        </div>
    );
});
DocumentItem.displayName = "DocumentItem";
