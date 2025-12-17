"use client";

import { LayoutGrid, Kanban, Users, User } from "lucide-react";
import { Button } from "@/components/ui/button";

export type ViewMode = "grid" | "kanban" | "client" | "assicurato" | "table";

interface ViewSwitcherProps {
    mode: ViewMode;
    onModeChange: (mode: ViewMode) => void;
}

export function ViewSwitcher({ mode, onModeChange }: Readonly<ViewSwitcherProps>) {
    // Simple Button-group implementation if ToggleGroup is missing to be safe
    return (
        <div className="flex items-center p-1 bg-muted rounded-lg border border-border/50 overflow-x-auto">
            <Button
                variant={mode === "table" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => onModeChange("table")}
                className="h-8 px-2 lg:px-3 gap-2"
                title="Vista Elenco"
            >
                <div className="h-4 w-4 flex items-center justify-center">
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="lucide lucide-list"
                    >
                        <line x1="8" x2="21" y1="6" y2="6" />
                        <line x1="8" x2="21" y1="12" y2="12" />
                        <line x1="8" x2="21" y1="18" y2="18" />
                        <line x1="3" x2="3.01" y1="6" y2="6" />
                        <line x1="3" x2="3.01" y1="12" y2="12" />
                        <line x1="3" x2="3.01" y1="18" y2="18" />
                    </svg>
                </div>
                <span className="hidden lg:inline text-xs">Elenco</span>
            </Button>
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
            <Button
                variant={mode === "assicurato" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => onModeChange("assicurato")}
                className="h-8 px-2 lg:px-3 gap-2"
                title="Raggruppa per Assicurato"
            >
                <User className="h-4 w-4" />
                <span className="hidden lg:inline text-xs">Assicurati</span>
            </Button>
        </div>
    );
}
