"use client";

import { useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useVirtualizer } from "@tanstack/react-virtual";
import { CaseSummary } from "@/types";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

import { Building2, User } from "lucide-react";

interface CaseTableViewProps {
    cases: CaseSummary[];
}

// Fixed row height for virtualization calculations
const ROW_HEIGHT = 53;

export function CaseTableView({ cases }: Readonly<CaseTableViewProps>) {
    const router = useRouter();
    const parentRef = useRef<HTMLDivElement>(null);

    const virtualizer = useVirtualizer({
        count: cases.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => ROW_HEIGHT,
        overscan: 5, // Render 5 extra rows above/below viewport for smooth scrolling
    });

    const handleRowClick = useCallback((id: string) => {
        router.push(`/dashboard/cases/${id}`);
    }, [router]);

    const handleRowKeyDown = useCallback((e: React.KeyboardEvent, id: string) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            router.push(`/dashboard/cases/${id}`);
        }
    }, [router]);

    return (
        <div className="rounded-md border bg-card">
            {/* Scrollable container with ref for virtualizer */}
            <div
                ref={parentRef}
                className="relative w-full overflow-auto max-h-[calc(100vh-250px)]"
            >
                <Table>
                    {/* Sticky header - remains fixed during scroll */}
                    <TableHeader className="bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-10 shadow-sm">
                        <TableRow>
                            <TableHead className="w-[150px] sticky top-0 bg-background/95 backdrop-blur z-20">Rif. Pratica</TableHead>
                            <TableHead className="min-w-[200px] sticky top-0 bg-background/95 backdrop-blur z-20">Cliente</TableHead>
                            <TableHead className="min-w-[200px] sticky top-0 bg-background/95 backdrop-blur z-20">Assicurato</TableHead>
                            <TableHead className="w-[150px] sticky top-0 bg-background/95 backdrop-blur z-20">Data Creazione</TableHead>
                            <TableHead className="min-w-[180px] sticky top-0 bg-background/95 backdrop-blur z-20">Creato da</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody className="relative">
                        {virtualizer.getVirtualItems().map((virtualRow) => {
                            const c = cases[virtualRow.index];
                            return (
                                <TableRow
                                    key={c.id}
                                    data-index={virtualRow.index}
                                    className="cursor-pointer hover:bg-muted/50 transition-colors"
                                    style={{
                                        height: `${virtualRow.size}px`,
                                    }}
                                    onClick={() => handleRowClick(c.id)}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => handleRowKeyDown(e, c.id)}
                                >
                                    <TableCell className="font-medium font-mono">
                                        {c.reference_code}
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-2">
                                            {c.client_logo_url ? (
                                                <img
                                                    src={c.client_logo_url}
                                                    alt={c.client_name || "Client"}
                                                    className="h-5 w-5 rounded-full object-contain"
                                                />
                                            ) : (
                                                <Building2 className="h-4 w-4 text-muted-foreground" />
                                            )}
                                            {c.client_id ? (
                                                <button
                                                    type="button"
                                                    className="font-medium hover:underline text-left"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        router.push(`/dashboard/client/${c.client_id}`);
                                                    }}
                                                >
                                                    {c.client_name || "N/D"}
                                                </button>
                                            ) : (
                                                <span className="font-medium">
                                                    {c.client_name || "N/D"}
                                                </span>
                                            )}
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <span>
                                            {c.assicurato_display || c.assicurato || "N/D"}
                                        </span>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">
                                        {new Date(c.created_at).toLocaleDateString("it-IT", {
                                            day: '2-digit',
                                            month: '2-digit',
                                            year: 'numeric'
                                        })}
                                    </TableCell>
                                    <TableCell>
                                        {(c.creator_name || c.creator_email) ? (
                                            <div className="flex items-center gap-2">
                                                <User className="h-4 w-4 text-muted-foreground" />
                                                <span className="text-sm">
                                                    {c.creator_name || c.creator_email}
                                                </span>
                                            </div>
                                        ) : (
                                            <span className="text-muted-foreground text-sm">-</span>
                                        )}
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
