"use client";

import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";

type MarkdownVariant = "default" | "compact" | "report";

interface MarkdownContentProps {
    /** The markdown content to render */
    readonly content: string;
    /** Styling variant: default, compact (less spacing), report (premium styling) */
    readonly variant?: MarkdownVariant;
    /** Additional className */
    readonly className?: string;
}

/**
 * Markdown component configurations for each variant.
 * Centralizes ReactMarkdown styling for consistency.
 */
const MARKDOWN_COMPONENTS: Record<MarkdownVariant, React.ComponentProps<typeof ReactMarkdown>["components"]> = {
    default: {
        p: ({ children }) => <p className="my-3 text-base text-muted-foreground leading-relaxed">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
        ul: ({ children }) => <ul className="list-disc list-inside my-3 space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside my-3 space-y-1">{children}</ol>,
        li: ({ children }) => <li className="text-base">{children}</li>,
        h1: ({ children }) => <h1 className="text-2xl font-bold mt-6 mb-3">{children}</h1>,
        h2: ({ children }) => <h2 className="text-xl font-semibold mt-5 mb-2">{children}</h2>,
        h3: ({ children }) => <h3 className="text-lg font-medium mt-4 mb-2">{children}</h3>,
        blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-muted-foreground/30 pl-4 italic my-4">{children}</blockquote>
        ),
    },
    compact: {
        p: ({ children }) => <p className="my-2 text-sm text-muted-foreground leading-relaxed">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
        ul: ({ children }) => <ul className="list-disc list-inside my-2 space-y-0.5 text-sm">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside my-2 space-y-0.5 text-sm">{children}</ol>,
        li: ({ children }) => <li className="text-sm">{children}</li>,
        h1: ({ children }) => <h1 className="text-lg font-bold mt-4 mb-2">{children}</h1>,
        h2: ({ children }) => <h2 className="text-base font-semibold mt-3 mb-1">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-medium mt-2 mb-1">{children}</h3>,
    },
    report: {
        h1: ({ children }) => <h1 className="text-3xl font-bold mt-8 mb-4 pb-2 border-b">{children}</h1>,
        h2: ({ children }) => <h2 className="text-2xl font-semibold mt-8 mb-4 text-primary">{children}</h2>,
        h3: ({ children }) => <h3 className="text-xl font-medium mt-6 mb-3">{children}</h3>,
        ul: ({ children }) => <ul className="list-disc list-inside my-4 space-y-2">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside my-4 space-y-2">{children}</ol>,
        p: ({ children }) => <p className="my-4 text-gray-700 dark:text-gray-300 leading-relaxed text-justify">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
        blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-primary/50 pl-4 italic my-4 bg-muted/30 p-2 rounded-r">{children}</blockquote>
        ),
    },
};

/**
 * MarkdownContent - Standardized markdown rendering component.
 *
 * @example
 * <MarkdownContent content={report.content} variant="report" />
 * <MarkdownContent content={summary} variant="compact" />
 */
export function MarkdownContent({
    content,
    variant = "default",
    className,
}: MarkdownContentProps) {
    return (
        <div className={cn("prose dark:prose-invert max-w-none", className)}>
            <ReactMarkdown components={MARKDOWN_COMPONENTS[variant]}>
                {content}
            </ReactMarkdown>
        </div>
    );
}
