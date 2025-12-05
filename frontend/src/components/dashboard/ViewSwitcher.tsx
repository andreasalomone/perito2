"use client";

import { LayoutGrid, Kanban, Users } from "lucide-react";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"; // I might need to create ToggleGroup too if missing
import { Button } from "@/components/ui/button";

export type ViewMode = "grid" | "kanban" | "client";

interface ViewSwitcherProps {
    mode: ViewMode;
    onModeChange: (mode: ViewMode) => void;
}

export function ViewSwitcher({ mode, onModeChange }: ViewSwitcherProps) {
    // Simple Button-group implementation if ToggleGroup is missing to be safe
    return (
        <div className="flex items-center p-1 bg-muted rounded-lg border border-border/50">
            <Button
                variant={mode === "grid" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => onModeChange("grid")}
                className="h-8 px-2 lg:px-3 gap-2"
                title="Vista Griglia"
            >
                <LayoutGrid className="h-4 w-4" />
                <span className="hidden lg:inline text-xs">Recenti</span>
            </Button>
            <Button
                variant={mode === "kanban" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => onModeChange("kanban")}
                className="h-8 px-2 lg:px-3 gap-2"
                title="Vista Kanban"
            >
                <Kanban className="h-4 w-4" />
                <span className="hidden lg:inline text-xs">Stato</span>
            </Button>
            <Button
                variant={mode === "client" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => onModeChange("client")}
                className="h-8 px-2 lg:px-3 gap-2"
                title="Raggruppa per Cliente"
            >
                <Users className="h-4 w-4" />
                <span className="hidden lg:inline text-xs">Clienti</span>
            </Button>
        </div>
    );
}
