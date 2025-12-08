"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface SummaryCardProps {
    summary: string | null | undefined;
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
            <CardContent className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown
                    components={{
                        // Style headings
                        h1: ({ children }) => <h1 className="text-xl font-bold mt-4 mb-2">{children}</h1>,
                        h2: ({ children }) => <h2 className="text-lg font-semibold mt-3 mb-2">{children}</h2>,
                        h3: ({ children }) => <h3 className="text-base font-medium mt-2 mb-1">{children}</h3>,
                        // Style lists
                        ul: ({ children }) => <ul className="list-disc list-inside my-2 space-y-1">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal list-inside my-2 space-y-1">{children}</ol>,
                        // Style paragraphs
                        p: ({ children }) => <p className="my-2 text-muted-foreground leading-relaxed">{children}</p>,
                        // Style bold/strong
                        strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                    }}
                >
                    {summary}
                </ReactMarkdown>
            </CardContent>
        </Card>
    );
}
