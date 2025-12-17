"use client";

import { useRouter } from "next/navigation";
import { CaseSummary } from "@/types";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Building2, Pen, User } from "lucide-react";

interface CaseTableViewProps {
    cases: CaseSummary[];
}

export function CaseTableView({ cases }: CaseTableViewProps) {
    const router = useRouter();

    return (
        <div className="rounded-md border bg-card">
            <div className="relative w-full overflow-auto max-h-[calc(100vh-250px)]">
                <Table>
                    <TableHeader className="bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-10 shadow-sm">
                        <TableRow>
                            <TableHead className="w-[150px] sticky top-0 bg-background/95 backdrop-blur z-20">Rif. Pratica</TableHead>
                            <TableHead className="min-w-[200px] sticky top-0 bg-background/95 backdrop-blur z-20">Cliente</TableHead>
                            <TableHead className="min-w-[200px] sticky top-0 bg-background/95 backdrop-blur z-20">Assicurato</TableHead>
                            <TableHead className="w-[120px] sticky top-0 bg-background/95 backdrop-blur z-20">Stato</TableHead>
                            <TableHead className="w-[150px] sticky top-0 bg-background/95 backdrop-blur z-20">Data Creazione</TableHead>
                            <TableHead className="min-w-[180px] sticky top-0 bg-background/95 backdrop-blur z-20">Creato da</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {cases.map((c) => (
                            <TableRow
                                key={c.id}
                                className="cursor-pointer hover:bg-muted/50 transition-colors"
                                onClick={() => router.push(`/dashboard/cases/${c.id}`)}
                                role="button"
                                tabIndex={0}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                        e.preventDefault();
                                        router.push(`/dashboard/cases/${c.id}`);
                                    }
                                }}
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
                                        <span className="font-medium">
                                            {c.client_name || "N/D"}
                                        </span>
                                    </div>
                                </TableCell>
                                <TableCell>
                                    <div className="flex items-center gap-2">
                                        <Pen className="h-4 w-4 text-muted-foreground" />
                                        <span>
                                            {c.assicurato_display || c.assicurato || "N/D"}
                                        </span>
                                    </div>
                                </TableCell>
                                <TableCell>
                                    <Badge
                                        variant={c.status === "OPEN" ? "default" : "outline"}
                                        className={cn(
                                            "text-xs px-2 py-0.5",
                                            c.status === "CLOSED" && "border-green-500 text-green-600 bg-green-50 dark:bg-green-950 dark:text-green-400"
                                        )}
                                    >
                                        {c.status}
                                    </Badge>
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
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
