"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        // Log the error to an error reporting service
        console.error(error);
    }, [error]);

    return (
        <div className="flex min-h-screen items-center justify-center bg-secondary/30 p-4">
            <Card className="w-full max-w-md border-destructive/20 shadow-lg">
                <CardHeader className="items-center text-center">
                    <div className="p-3 bg-destructive/10 rounded-full mb-2">
                        <AlertTriangle className="h-8 w-8 text-destructive" />
                    </div>
                    <CardTitle className="text-xl">Qualcosa è andato storto!</CardTitle>
                    <CardDescription>
                        Si è verificato un errore imprevisto.
                    </CardDescription>
                </CardHeader>
                <CardContent className="text-center space-y-2">
                    <p className="text-sm text-muted-foreground">
                        Non preoccuparti, non sei tu - siamo noi. Puoi provare ad aggiornare la pagina.
                    </p>
                    {process.env.NODE_ENV === "development" && (
                        <div className="text-xs text-left text-destructive bg-destructive/5 p-2 rounded border border-destructive/10 font-mono overflow-auto max-h-32">
                            {error.message || "Errore sconosciuto"}
                        </div>
                    )}
                </CardContent>
                <CardFooter className="justify-center">
                    <Button onClick={() => reset()} className="gap-2">
                        <RefreshCcw className="h-4 w-4" />
                        Riprova
                    </Button>
                </CardFooter>
            </Card>
        </div>
    );
}
