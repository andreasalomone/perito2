"use client";

import { Search, Loader2, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";

interface SmartSearchProps {
    value?: string;
    onSearch: (value: string) => void;
    className?: string;
    placeholder?: string;
}

export function SmartSearch({
    value = "",
    onSearch,
    className,
    placeholder = "Cerca per riferimento o cliente..."
}: SmartSearchProps) {
    const [localValue, setLocalValue] = useState(value);
    const [isSearching, setIsSearching] = useState(false);

    useEffect(() => {
        setLocalValue(value);
    }, [value]);

    useEffect(() => {
        // Simple debounce
        const handler = setTimeout(() => {
            if (localValue !== value) {
                setIsSearching(true);
                onSearch(localValue);
                // Simulate quick loading effect or wait for parent
                setTimeout(() => setIsSearching(false), 300);
            }
        }, 300);

        return () => clearTimeout(handler);
    }, [localValue, onSearch, value]);

    const handleClear = () => {
        setLocalValue("");
        onSearch("");
    };

    return (
        <div className={`relative w-full max-w-sm ${className}`}>
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
                value={localValue}
                onChange={(e) => setLocalValue(e.target.value)}
                className="pl-9 pr-8 bg-background/50 border-muted focus:bg-background transition-colors"
                placeholder={placeholder}
            />

            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
                {localValue && (
                    <button
                        onClick={handleClear}
                        className="text-muted-foreground hover:text-foreground transition-colors mr-1"
                        type="button"
                    >
                        <X className="h-3 w-3" />
                        <span className="sr-only">Clear</span>
                    </button>
                )}
                {isSearching && <Loader2 className="h-3 w-3 animate-spin text-primary" />}
            </div>
        </div>
    );
}
