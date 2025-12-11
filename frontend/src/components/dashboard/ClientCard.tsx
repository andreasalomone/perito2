import Link from "next/link";
import { Building2, ChevronRight, MapPin } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { ClientListItem } from "@/types";
import { cn } from "@/lib/utils";

interface ClientCardProps {
    client: ClientListItem;
    className?: string;
}

export function ClientCard({ client, className }: ClientCardProps) {
    return (
        <Link href={`/dashboard/client/${client.id}`}>
            <Card className={cn("hover:bg-muted/50 transition-all cursor-pointer group", className)}>
                <CardContent className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        {client.logo_url ? (
                            <div className="relative h-12 w-12 shrink-0">
                                <img
                                    src={client.logo_url}
                                    alt={client.name}
                                    className="h-full w-full rounded-full object-contain p-1 bg-background border border-border/50"
                                    onError={(e) => {
                                        // Fallback on error
                                        e.currentTarget.style.display = "none";
                                        e.currentTarget.parentElement?.classList.add("hidden");
                                        e.currentTarget.parentElement?.nextElementSibling?.classList.remove("hidden");
                                    }}
                                />
                                {/* Hidden fallback container that shows if img fails */}
                                <div className="absolute inset-0 hidden items-center justify-center rounded-full bg-muted border border-border/50">
                                    <Building2 className="h-5 w-5 text-muted-foreground" />
                                </div>
                            </div>
                        ) : (
                            <div className="h-12 w-12 shrink-0 rounded-full bg-muted border border-border/50 flex items-center justify-center">
                                <Building2 className="h-5 w-5 text-muted-foreground" />
                            </div>
                        )}

                        <div>
                            <h3 className="font-semibold text-lg text-foreground group-hover:text-primary transition-colors">
                                {client.name}
                            </h3>
                            {client.city && (
                                <div className="flex items-center gap-1 text-sm text-muted-foreground mt-0.5">
                                    <MapPin className="h-3 w-3" />
                                    <span>{client.city}</span>
                                </div>
                            )}
                            <div className="text-xs text-muted-foreground mt-1">
                                {client.case_count} {client.case_count === 1 ? "sinistro" : "sinistri"}
                            </div>
                        </div>
                    </div>

                    <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors translate-x-0 group-hover:translate-x-1 duration-200" />
                </CardContent>
            </Card>
        </Link>
    );
}
