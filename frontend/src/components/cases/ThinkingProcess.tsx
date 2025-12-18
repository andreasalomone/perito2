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
 * ThinkingProcess - Elegant collapsible display for AI reasoning.
 *
 * Shows streaming "chain of thought" content with:
 * - Auto-scroll as thoughts appear
 * - Character count badge
 * - Animated cursor during streaming
 * - Auto-collapse when complete
 * - Smooth, refined design that matches the app aesthetic
 */
export function ThinkingProcess({ thoughts, state, className }: Readonly<ThinkingProcessProps>) {
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
            "w-full rounded-xl border overflow-hidden transition-all duration-300 ease-in-out",
            "bg-gradient-to-br from-purple-50/50 to-violet-50/30 dark:from-purple-950/20 dark:to-violet-950/10",
            "border-purple-200/50 dark:border-purple-800/30",
            "shadow-sm",
            className
        )}>
            {/* Header */}
            <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className={cn(
                    "flex w-full items-center justify-between p-3",
                    "bg-gradient-to-r from-purple-100/50 to-violet-100/30",
                    "dark:from-purple-900/20 dark:to-violet-900/10",
                    "cursor-pointer hover:from-purple-100/70 hover:to-violet-100/50",
                    "dark:hover:from-purple-900/30 dark:hover:to-violet-900/20",
                    "transition-all duration-200"
                )}
            >
                <div className="flex items-center gap-2">
                    {state === "thinking" ? (
                        <div className="relative">
                            <BrainCircuit className="h-4 w-4 text-purple-600 dark:text-purple-400 animate-pulse" />
                            <span className="absolute -top-1 -right-1 flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500" />
                            </span>
                        </div>
                    ) : (
                        <Sparkles className="h-4 w-4 text-green-600 dark:text-green-400" />
                    )}

                    <span className="text-sm font-medium text-purple-800 dark:text-purple-200">
                        {state === "thinking" ? "Ragionamento in corso..." : "Analisi Completata"}
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    <Badge
                        variant="secondary"
                        className="text-[10px] h-5 font-mono bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 border-0"
                    >
                        {thoughts.length > 0 ? `${(thoughts.length / 1000).toFixed(1)}k caratteri` : "0 caratteri"}
                    </Badge>
                    {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-purple-500 dark:text-purple-400" />
                    ) : (
                        <ChevronRight className="h-4 w-4 text-purple-500 dark:text-purple-400" />
                    )}
                </div>
            </button>

            {/* Content Area */}
            {isExpanded && (
                <div className="border-t border-purple-200/50 dark:border-purple-800/30">
                    <div
                        ref={scrollRef}
                        className="h-[200px] w-full overflow-y-auto bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm"
                    >
                        <div className="p-4 text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
                            {thoughts}
                            {state === "thinking" && (
                                <span className="inline-block w-0.5 h-4 ml-1 bg-purple-500 animate-pulse align-middle rounded-full" />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

