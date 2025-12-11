"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Plus, Users, Building2 } from "lucide-react";
import { useClients } from "@/hooks/useClients";
import { ClientCard } from "@/components/dashboard/ClientCard";
import { ClientDialog } from "@/components/dashboard/ClientDialog";
import { SmartSearch } from "@/components/dashboard/SmartSearch";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "sonner";
import { ClientDetail } from "@/types";
import { ChevronLeft, ChevronRight } from "lucide-react";

export default function ClientsPage() {
    const [page, setPage] = useState(0);
    const [searchQuery, setSearchQuery] = useState("");
    const LIMIT = 50;
    const { clients, isLoading, isError, mutate } = useClients({ q: searchQuery, skip: page * LIMIT, limit: LIMIT });

    const handleCreateSuccess = (newClient: ClientDetail) => {
        toast.success("Cliente creato", {
            description: `${newClient.name} è stato aggiunto con successo.`,
        });
        mutate(); // Refresh list
    };

    Clienti
                            </h1 >
        <p className="text-muted-foreground mt-1">
            Gestisci le anagrafiche delle compagnie e i relativi contatti.
        </p>
                        </div >
        <ClientDialog
            onSuccess={handleCreateSuccess}
            trigger={
                <Button className="gap-2 w-full sm:w-auto">
                    <Plus className="h-4 w-4" />
                    Nuovo Cliente
                </Button>
            }
        />
                    </div >

        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
            <SmartSearch
                value={searchQuery}
                onSearch={setSearchQuery}
                placeholder="Cerca cliente..."
                className="w-full sm:max-w-md"
            />
            <div className="flex items-center gap-2 text-sm text-muted-foreground ml-auto">
                <span className="font-medium text-foreground">{clients ? clients.length : 0}</span> clienti trovati
            </div>
        </div>
                </div >

        {/* Content */ }
    {
        isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                    <div key={i} className="h-24 bg-muted/50 rounded-lg animate-pulse" />
                ))}
            </div>
        ) : isError ? (
            <div className="text-center py-12 text-destructive">
                Errore durante il caricamento dei clienti.
            </div>
        ) : clients.length === 0 ? (
            <Card className="border-dashed border-2 bg-muted/10">
                <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="p-4 bg-muted rounded-full mb-4">
                        <Building2 className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <h3 className="text-lg font-semibold">Nessun cliente trovato</h3>
                    <p className="text-muted-foreground mb-6 max-w-sm">
                        {searchQuery
                            ? `Nessun risultato per "${searchQuery}"`
                            : "Non hai ancora clienti. Creane uno creando un nuovo sinistro."}
                    </p>
                </CardContent>
            </Card>
        ) : (
            <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {clients.map((client) => (
                        <ClientCard key={client.id} client={client} />
                    ))}
                </div>

                {/* Pagination Controls */}
                <div className="flex items-center justify-end gap-2 text-sm">
                    <span className="text-muted-foreground mr-4">
                        Pagina {page + 1}
                    </span>
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={page === 0}
                        onClick={() => setPage((p) => Math.max(0, p - 1))}
                    >
                        <ChevronLeft className="h-4 w-4 mr-1" />
                        Prec
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={clients.length < LIMIT}
                        onClick={() => setPage((p) => p + 1)}
                    >
                        Succ
                        <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                </div>
            </div>
        )
    }
            </div >
            );
}
