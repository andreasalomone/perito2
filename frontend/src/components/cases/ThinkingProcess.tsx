"use client";

import { useState, useEffect, useRef } from "react";
import { ChevronDown, ChevronRight, BrainCircuit, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface ThinkingProcessProps {
    thoughts: string;
    state: "idle" | "thinking" | "done";
    className?: string;
}

/**
 * ThinkingProcess - Collapsible terminal-style display for AI reasoning.
 *
 * Shows streaming "chain of thought" content with:
 * - Auto-scroll as thoughts appear
 * - Character count badge
 * - Animated cursor during streaming
 * - Auto-collapse when complete
 */
export function ThinkingProcess({ thoughts, state, className }: ThinkingProcessProps) {
    const [isExpanded, setIsExpanded] = useState(true);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom as thoughts stream in
    useEffect(() => {
        if (scrollRef.current && isExpanded) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [thoughts, isExpanded]);

    // Auto-collapse when done (optional UX choice)
    useEffect(() => {
        if (state === "done") setIsExpanded(false);
    }, [state]);

    if (!thoughts && state === "idle") return null;

    return (
        <div className={cn(
            "w-full rounded-lg border bg-card text-card-foreground shadow-sm overflow-hidden transition-all duration-300 ease-in-out",
            className
        )}>
            {/* Header */}
            <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex w-full items-center justify-between p-3 bg-muted/30 cursor-pointer hover:bg-muted/50 transition-colors"
            >
                <div className="flex items-center gap-2">
                    {state === "thinking" ? (
                        <div className="relative">
                            <BrainCircuit className="h-4 w-4 text-purple-600 animate-pulse" />
                            <span className="absolute -top-1 -right-1 flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500" />
                            </span>
                        </div>
                    ) : (
                        <Sparkles className="h-4 w-4 text-green-600" />
                    )}

                    <span className="text-sm font-medium text-foreground/80">
                        {state === "thinking" ? "Ragionamento in corso..." : "Analisi Completata"}
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] h-5 font-mono text-muted-foreground">
                        {thoughts.length > 0 ? `${(thoughts.length / 1000).toFixed(1)}k caratteri` : "0 caratteri"}
                    </Badge>
                    {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                </div>
            </button>

            {/* Content Area */}
            {isExpanded && (
                <div className="border-t border-border/50 bg-zinc-950 dark:bg-black">
                    <div
                        ref={scrollRef}
                        className="h-[200px] w-full overflow-y-auto"
                    >
                        <div className="p-4 font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">
                            {thoughts}
                            {state === "thinking" && (
                                <span className="inline-block w-1.5 h-3 ml-1 bg-purple-500 animate-pulse align-middle" />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
