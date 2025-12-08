"use client";

import { memo, useState } from "react";
import { ReportVersion } from "@/types";
import { Button } from "@/components/ui/button";
import { FileText, Download } from "lucide-react";
import { motion } from "framer-motion";

export type TemplateType = "bn" | "salomone";

interface VersionItemProps {
    version: ReportVersion;
    onDownload: (v: ReportVersion, template: TemplateType) => void;
}

export const VersionItem = memo(({
    version,
    onDownload
}: VersionItemProps) => {
    const [template, setTemplate] = useState<TemplateType>("bn");

    return (
        <motion.div
            layout
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center justify-between p-3 bg-secondary/20 rounded border"
        >
            <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-primary" />
                <div>
                    <p className="font-medium text-sm">Versione {version.version_number}</p>
                    <p className="text-xs text-muted-foreground">
                        {version.is_final ? "Finale Approvata" : "Bozza IA"}
                    </p>
                </div>
            </div>
            <div className="flex items-center gap-4">
                {/* Template Selection - Local State */}
                {!version.is_final && (
                    <div className="flex items-center gap-1 text-xs border rounded p-1 bg-background" role="group" aria-label="Seleziona modello report">
                        <button
                            onClick={() => setTemplate("bn")}
                            className={`px-2 py-1 rounded transition-colors ${template === "bn" ? "bg-primary text-primary-foreground" : "hover:bg-muted text-muted-foreground"}`}
                            aria-pressed={template === "bn"}
                        >
                            BN
                        </button>
                        <button
                            onClick={() => setTemplate("salomone")}
                            className={`px-2 py-1 rounded transition-colors ${template === "salomone" ? "bg-primary text-primary-foreground" : "hover:bg-muted text-muted-foreground"}`}
                            aria-pressed={template === "salomone"}
                        >
                            Salomone
                        </button>
                    </div>
                )}

                <Button
                    size="icon"
                    variant="brand"
                    onClick={() => onDownload(version, template)}
                    aria-label={`Scarica versione ${version.version_number}`}
                >
                    <Download className="h-4 w-4" />
                </Button>
            </div>
        </motion.div>
    );
});
VersionItem.displayName = "VersionItem";
