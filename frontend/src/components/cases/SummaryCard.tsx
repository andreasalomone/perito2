"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText } from "lucide-react";
import { MarkdownContent } from "@/components/ui/markdown-content";

interface SummaryCardProps {
    readonly summary: string | null | undefined;
}

export function SummaryCard({ summary }: SummaryCardProps) {
    if (!summary) return null;

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <FileText className="h-5 w-5 text-blue-600" />
                    Riassunto
                </CardTitle>
            </CardHeader>
            <CardContent>
                <MarkdownContent content={summary} variant="compact" />
            </CardContent>
        </Card>
    );
}

